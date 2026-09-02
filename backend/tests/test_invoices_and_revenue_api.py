"""
POST /invoices/generate|{id}/approve|{id}/send|{id}/mark-paid, GET
import logging
/invoices|{id} -- proves HRMS-0907 (S-226 Invoicing) end-to-end.

POST /revenue/leakage/scan|{id}/log-reason, GET /revenue/leakage,
POST /revenue/reconciliation/scan|alerts/{id}/resolve, GET
/revenue/reconciliation/alerts, GET /revenue/dashboard/clients/{id} --
proves HRMS-0906 (S-225 Revenue Leakage), HRMS-0903 (Reconciliation),
and HRMS-0909 (S-228 Client Revenue Dashboard) end-to-end.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys. Timesheets are built directly against the DB rather
than through the /timesheets API, since these tests are about the
invoice/revenue layer, not timesheet submission itself.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.timesheet_dispute import TimesheetDispute
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


# Far enough in the past that scan_project_revenue_leakage's default
# 7-day grace period has definitely elapsed relative to real "now".
PERIOD_START = date.today() - timedelta(days=60)
PERIOD_END = date.today() - timedelta(days=30)
TS_WEEK = _monday_of(date.today() - timedelta(days=45))


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture()
def client(throwaway_jwt_keys):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.invoices import router as invoices_router
    from app.api.v1.endpoints.revenue import router as revenue_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(invoices_router)
    app.include_router(revenue_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    acme = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db.add(acme)
    db.commit()

    # allow_weekend_billing/status/billing_type/currency all default --
    # billing_type defaults TIME_AND_MATERIALS, exactly what the burn-rate
    # "FIXED_BID only" test needs to prove None, not a guessed number.
    project = Project(tenant_id=tenant.id, client_id=acme.id, name="WROS Rollout")
    db.add(project)
    db.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    db.add(demand)
    db.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED",
    )
    db.add(employee)
    db.commit()

    allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id, client_id=acme.id,
        project_id=project.id, status="ACTIVE", start_date=date(2025, 1, 1),
        billing_rate_usd_cents=15000,
    )
    db.add(allocation)
    db.commit()

    ids = {
        "tenant_id": tenant.id, "client_id": acme.id, "project_id": project.id,
        "employee_id": employee.id, "allocation_id": allocation.id,
    }
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.SessionLocal = TestSessionLocal
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _make_timesheet(client, *, status="APPROVED", week_starting_date=TS_WEEK, billable_hours=40.0, approved_at=None):
    ids = client.wros_ids
    db = client.SessionLocal()
    ts = Timesheet(
        tenant_id=ids["tenant_id"], employee_id=ids["employee_id"], allocation_id=ids["allocation_id"],
        week_starting_date=week_starting_date, total_hours=billable_hours, billable_hours=billable_hours,
        non_billable_hours=0, status=status,
        approved_by="U-ADMIN" if status == "APPROVED" else None,
        approved_at=(approved_at or datetime.utcnow()) if status == "APPROVED" else None,
    )
    db.add(ts)
    db.commit()
    ts_id = ts.id
    db.close()
    return ts_id


def _generate_invoice(client, *, period_start=PERIOD_START, period_end=PERIOD_END):
    ids = client.wros_ids
    return client.post(
        "/invoices/generate",
        json={"project_id": ids["project_id"], "period_start": period_start.isoformat(), "period_end": period_end.isoformat()},
        headers=_auth(),
    )


# ---------------------------------------------------------------------------
# HRMS-0907 -- Invoicing
# ---------------------------------------------------------------------------

def test_generate_invoice_success(client):
    _make_timesheet(client)
    resp = _generate_invoice(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "DRAFT"
    assert body["total_usd_cents"] == 15000 * 40
    assert len(body["line_items"]) == 1


def test_generate_invoice_blocks_unapproved_timesheet(client):
    _make_timesheet(client, status="SUBMITTED")
    resp = _generate_invoice(client)
    assert resp.status_code == 409


def test_generate_invoice_blocks_open_dispute(client):
    ts_id = _make_timesheet(client)
    db = client.SessionLocal()
    db.add(TimesheetDispute(
        tenant_id=client.wros_ids["tenant_id"], timesheet_id=ts_id, raised_by="EMPLOYEE",
        reason="Hours logged for Thursday were duplicated across two allocations.",
        original_hours=40,
    ))
    db.commit()
    db.close()

    resp = _generate_invoice(client)
    assert resp.status_code == 409


def test_generate_invoice_404_for_unknown_project(client):
    resp = client.post(
        "/invoices/generate",
        json={"project_id": "does-not-exist", "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_approve_send_mark_paid_flow(client):
    _make_timesheet(client)
    invoice_id = _generate_invoice(client).json()["id"]

    approve_resp = client.post(f"/invoices/{invoice_id}/approve", headers=_auth())
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"
    assert approve_resp.json()["approved_by"] == "U-ADMIN"

    reapprove_resp = client.post(f"/invoices/{invoice_id}/approve", headers=_auth())
    assert reapprove_resp.status_code == 409

    send_resp = client.post(f"/invoices/{invoice_id}/send", headers=_auth())
    assert send_resp.status_code == 200
    assert send_resp.json()["status"] == "SENT"

    paid_resp = client.post(f"/invoices/{invoice_id}/mark-paid", headers=_auth())
    assert paid_resp.status_code == 200
    assert paid_resp.json()["status"] == "PAID"


def test_send_blocked_before_approval(client):
    _make_timesheet(client)
    invoice_id = _generate_invoice(client).json()["id"]
    resp = client.post(f"/invoices/{invoice_id}/send", headers=_auth())
    assert resp.status_code == 409


def test_list_invoices_filtered_by_status(client):
    _make_timesheet(client)
    _generate_invoice(client)
    resp = client.get("/invoices?status=DRAFT", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["invoices"]) == 1


def test_get_invoice_404_for_unknown_id(client):
    resp = client.get("/invoices/does-not-exist", headers=_auth())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HRMS-0906 -- Revenue Leakage Detection
# ---------------------------------------------------------------------------

def test_scan_leakage_returns_null_before_grace_period(client):
    ids = client.wros_ids
    this_week_monday = _monday_of(date.today())
    _make_timesheet(client, week_starting_date=this_week_monday)

    resp = client.post(
        "/revenue/leakage/scan",
        json={"project_id": ids["project_id"], "period_start": this_week_monday.isoformat(), "period_end": date.today().isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_scan_leakage_flags_unbilled_hours_after_grace_period(client):
    _make_timesheet(client)
    resp = client.post(
        "/revenue/leakage/scan",
        json={"project_id": client.wros_ids["project_id"], "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    assert body["unbilled_hours"] == 40.0


def test_scan_leakage_returns_null_once_fully_invoiced(client):
    _make_timesheet(client)
    _generate_invoice(client)

    resp = client.post(
        "/revenue/leakage/scan",
        json={"project_id": client.wros_ids["project_id"], "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_scan_leakage_404_for_unknown_project(client):
    resp = client.post(
        "/revenue/leakage/scan",
        json={"project_id": "does-not-exist", "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_log_leakage_reason_suppresses_from_active_list(client):
    _make_timesheet(client)
    scan_resp = client.post(
        "/revenue/leakage/scan",
        json={"project_id": client.wros_ids["project_id"], "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()},
        headers=_auth(),
    )
    flag_id = scan_resp.json()["id"]

    list_before = client.get("/revenue/leakage", headers=_auth())
    assert len(list_before.json()["flags"]) == 1

    log_resp = client.post(
        f"/revenue/leakage/{flag_id}/log-reason",
        json={"reason": "Client-negotiated cap for this period, confirmed by account manager."},
        headers=_auth(),
    )
    assert log_resp.status_code == 200
    assert log_resp.json()["partial_billing_reason"] is not None

    list_after = client.get("/revenue/leakage", headers=_auth())
    assert list_after.json()["flags"] == []


def test_log_leakage_reason_404_for_unknown_flag(client):
    resp = client.post(
        "/revenue/leakage/does-not-exist/log-reason",
        json={"reason": "N/A"},
        headers=_auth(),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HRMS-0903 -- Timesheet-to-Revenue Reconciliation
# ---------------------------------------------------------------------------

def test_reconciliation_scan_creates_alert_for_uninvoiced_approved_timesheet(client):
    _make_timesheet(client, approved_at=datetime.utcnow() - timedelta(days=5))

    resp = client.post("/revenue/reconciliation/scan", headers=_auth())
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["status"] == "UNRESOLVED"


def test_reconciliation_scan_is_idempotent(client):
    _make_timesheet(client, approved_at=datetime.utcnow() - timedelta(days=5))
    first = client.post("/revenue/reconciliation/scan", headers=_auth())
    second = client.post("/revenue/reconciliation/scan", headers=_auth())
    assert len(first.json()["alerts"]) == len(second.json()["alerts"]) == 1
    assert first.json()["alerts"][0]["id"] == second.json()["alerts"][0]["id"]


def test_reconciliation_scan_skips_recently_approved_timesheet(client):
    _make_timesheet(client, approved_at=datetime.utcnow())
    resp = client.post("/revenue/reconciliation/scan", headers=_auth())
    assert resp.json()["alerts"] == []


def test_reconciliation_scan_skips_already_invoiced_timesheet(client):
    _make_timesheet(client, approved_at=datetime.utcnow() - timedelta(days=5), week_starting_date=TS_WEEK)
    _generate_invoice(client)
    resp = client.post("/revenue/reconciliation/scan", headers=_auth())
    assert resp.json()["alerts"] == []


def test_reconciliation_alerts_list_and_resolve(client):
    _make_timesheet(client, approved_at=datetime.utcnow() - timedelta(days=5))
    client.post("/revenue/reconciliation/scan", headers=_auth())

    list_resp = client.get("/revenue/reconciliation/alerts", headers=_auth())
    assert len(list_resp.json()["alerts"]) == 1
    alert_id = list_resp.json()["alerts"][0]["id"]

    resolve_resp = client.post(f"/revenue/reconciliation/alerts/{alert_id}/resolve", headers=_auth())
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED"

    unresolved = client.get("/revenue/reconciliation/alerts?status=UNRESOLVED", headers=_auth())
    assert unresolved.json()["alerts"] == []
    resolved = client.get("/revenue/reconciliation/alerts?status=RESOLVED", headers=_auth())
    assert len(resolved.json()["alerts"]) == 1


def test_resolve_reconciliation_alert_404_for_unknown_id(client):
    resp = client.post("/revenue/reconciliation/alerts/does-not-exist/resolve", headers=_auth())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HRMS-0909 -- Client Revenue Realization Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_returns_insufficient_data_for_client_with_no_projects(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    empty_client = Client(tenant_id=ids["tenant_id"], company_name="No Projects Yet Inc")
    db.add(empty_client)
    db.commit()
    empty_client_id = empty_client.id
    db.close()

    resp = client.get(f"/revenue/dashboard/clients/{empty_client_id}", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["earned_usd_cents"] is None
    assert "INSUFFICIENT_DATA" in body["note"]


def test_dashboard_computes_earned_and_billable_ratio(client):
    _make_timesheet(client)
    invoice_id = _generate_invoice(client).json()["id"]
    client.post(f"/invoices/{invoice_id}/approve", headers=_auth())

    resp = client.get(f"/revenue/dashboard/clients/{client.wros_ids['client_id']}", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["earned_usd_cents"] == 15000 * 40
    assert body["billable_ratio_pct"] == 100.0
    # project defaults to TIME_AND_MATERIALS -- burn rate is FIXED_BID-only.
    assert body["burn_rate_pct"] is None


def test_dashboard_404_for_unknown_client(client):
    resp = client.get("/revenue/dashboard/clients/does-not-exist", headers=_auth())
    assert resp.status_code == 404

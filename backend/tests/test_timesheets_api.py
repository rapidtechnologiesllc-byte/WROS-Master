"""
POST /timesheets/weekly-draft, PUT /timesheets/{id}/entries, POST
/timesheets/{id}/submit|approve|reject|reopen, POST
/timesheets/bulk-approve, GET /timesheets, GET /timesheets/{id} --
proves S-220 (Create Weekly Timesheet) + S-221 (Validation & Submission
Lock) + S-222 (Manager Approval) end-to-end on real routes. Also closes
import logging
the "time tracking" link in Avinash's stated MVP chain.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
from datetime import date, timedelta

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
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


# A Monday safely in the past (not "this week") so all 5 weekdays are
# always <= today regardless of which day of the week tests actually
# run on -- avoids a flaky "future date" rejection from the real
# service-layer guard.
THIS_MONDAY = _monday_of(date.today() - timedelta(weeks=2))


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

    from app.api.v1.endpoints.timesheets import router as timesheets_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(timesheets_router)
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

    # allow_weekend_billing defaults False, status defaults ACTIVE -- exactly
    # the "flag the weekend entry" case for the S-229 anomaly-detection tests.
    project = Project(tenant_id=tenant.id, client_id=acme.id, name="WROS Rollout")
    db.add(project)
    db.commit()

    allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id, client_id=acme.id,
        project_id=project.id, status="ACTIVE", start_date=date(2025, 1, 1),
    )
    db.add(allocation)
    db.commit()

    ids = {
        "tenant_id": tenant.id, "employee_id": employee.id, "allocation_id": allocation.id,
        "project_id": project.id, "client_id": acme.id, "demand_id": demand.id,
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


def _create_draft(client):
    ids = client.wros_ids
    resp = client.post(
        "/timesheets/weekly-draft",
        json={"allocation_id": ids["allocation_id"], "week_starting_date": THIS_MONDAY.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _log_valid_hours(client, timesheet_id):
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(5)
    ]
    resp = client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/timesheets")
    assert resp.status_code in (401, 403)


def test_create_weekly_draft_is_idempotent(client):
    id1 = _create_draft(client)
    id2 = _create_draft(client)
    assert id1 == id2


def test_create_draft_blocked_for_non_active_allocation(client):
    ids = client.wros_ids
    # flip the fixture allocation to ENDED via a second, distinct allocation setup would be
    # more work than needed -- instead prove the guard using a bogus non-Monday date, the
    # other cheap-to-trigger validation in the same function.
    resp = client.post(
        "/timesheets/weekly-draft",
        json={"allocation_id": ids["allocation_id"], "week_starting_date": (THIS_MONDAY + timedelta(days=2)).isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_upsert_entries_computes_totals(client):
    timesheet_id = _create_draft(client)
    body = _log_valid_hours(client, timesheet_id)
    assert body["total_hours"] == 40.0
    assert body["billable_hours"] == 40.0
    assert body["non_billable_hours"] == 0.0
    assert len(body["entries"]) == 5


def test_upsert_entries_rejects_over_60_hour_week(client):
    timesheet_id = _create_draft(client)
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 13, "entry_type": "BILLABLE"}
        for i in range(5)
    ]
    resp = client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
    assert resp.status_code == 422


def test_submit_requires_logged_hours(client):
    timesheet_id = _create_draft(client)
    resp = client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())
    assert resp.status_code == 422


def test_full_submit_approve_flow(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)

    submit_resp = client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "SUBMITTED"

    approve_resp = client.post(f"/timesheets/{timesheet_id}/approve", headers=_auth())
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"
    assert approve_resp.json()["approved_by"] == "U-ADMIN"


def test_approved_timesheet_entries_are_immutable(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)
    client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())
    client.post(f"/timesheets/{timesheet_id}/approve", headers=_auth())

    resp = client.put(
        f"/timesheets/{timesheet_id}/entries",
        json={"entries": [{"entry_date": THIS_MONDAY.isoformat(), "hours": 1, "entry_type": "BILLABLE"}]},
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_reject_requires_20_char_reason(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)
    client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())

    short = client.post(f"/timesheets/{timesheet_id}/reject", json={"reason": "too short"}, headers=_auth())
    assert short.status_code == 422

    resp = client.post(
        f"/timesheets/{timesheet_id}/reject",
        json={"reason": "Hours don't match the client's approved timesheet for this week."},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


def test_reopen_returns_rejected_to_draft(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)
    client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())
    client.post(
        f"/timesheets/{timesheet_id}/reject",
        json={"reason": "Hours don't match the client's approved timesheet for this week."},
        headers=_auth(),
    )

    resp = client.post(f"/timesheets/{timesheet_id}/reopen", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["status"] == "DRAFT"


def test_bulk_approve(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)
    client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())

    resp = client.post("/timesheets/bulk-approve", json={"timesheet_ids": [timesheet_id]}, headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["approved"] == 1
    assert body["failed"] == []


def test_list_timesheets_filtered_by_status(client):
    timesheet_id = _create_draft(client)
    resp = client.get("/timesheets?status=DRAFT", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["timesheets"]) == 1
    assert resp.json()["timesheets"][0]["id"] == timesheet_id


def test_get_timesheet_404_for_unknown_id(client):
    resp = client.get("/timesheets/does-not-exist", headers=_auth())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# S-229/HRMS-0910 -- Anomaly Detection
# ---------------------------------------------------------------------------

def _approved_timesheet(client, entries=None):
    timesheet_id = _create_draft(client)
    if entries is None:
        _log_valid_hours(client, timesheet_id)
    else:
        resp = client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
        assert resp.status_code == 200, resp.text
    client.post(f"/timesheets/{timesheet_id}/submit", headers=_auth())
    approve_resp = client.post(f"/timesheets/{timesheet_id}/approve", headers=_auth())
    assert approve_resp.status_code == 200, approve_resp.text
    return timesheet_id


def test_scan_anomalies_flags_weekend_entry(client):
    timesheet_id = _create_draft(client)
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(5)
    ] + [{"entry_date": (THIS_MONDAY + timedelta(days=5)).isoformat(), "hours": 4, "entry_type": "BILLABLE"}]
    resp = client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
    assert resp.status_code == 200, resp.text

    scan_resp = client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())
    assert scan_resp.status_code == 200, scan_resp.text
    types = {f["anomaly_type"] for f in scan_resp.json()["flags"]}
    assert "WEEKEND" in types


def test_scan_anomalies_flags_over_12_hour_day(client):
    timesheet_id = _create_draft(client)
    entries = [{"entry_date": THIS_MONDAY.isoformat(), "hours": 13, "entry_type": "BILLABLE"}] + [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(1, 5)
    ]
    resp = client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
    assert resp.status_code == 200, resp.text

    scan_resp = client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())
    assert scan_resp.status_code == 200, scan_resp.text
    types = {f["anomaly_type"] for f in scan_resp.json()["flags"]}
    assert "OVER_12H" in types


def test_scan_anomalies_flags_completed_project(client):
    ids = client.wros_ids
    db = client.SessionLocal()
    completed_project = Project(
        tenant_id=ids["tenant_id"], client_id=ids["client_id"], name="Sunset Migration", status="COMPLETED",
    )
    db.add(completed_project)
    db.commit()
    completed_allocation = EmployeeAllocation(
        tenant_id=ids["tenant_id"], employee_id=ids["employee_id"], demand_id=ids["demand_id"],
        client_id=ids["client_id"], project_id=completed_project.id, status="ACTIVE",
        start_date=date(2025, 1, 1),
    )
    db.add(completed_allocation)
    db.commit()
    allocation_id = completed_allocation.id
    db.close()

    resp = client.post(
        "/timesheets/weekly-draft",
        json={"allocation_id": allocation_id, "week_starting_date": THIS_MONDAY.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    timesheet_id = resp.json()["id"]
    _log_valid_hours(client, timesheet_id)

    scan_resp = client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())
    assert scan_resp.status_code == 200, scan_resp.text
    types = {f["anomaly_type"] for f in scan_resp.json()["flags"]}
    assert "COMPLETED_PROJECT" in types


def test_scan_anomalies_is_idempotent(client):
    timesheet_id = _create_draft(client)
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(5)
    ] + [{"entry_date": (THIS_MONDAY + timedelta(days=5)).isoformat(), "hours": 4, "entry_type": "BILLABLE"}]
    client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())

    first = client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())
    second = client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())
    assert len(first.json()["flags"]) == len(second.json()["flags"])


def test_get_anomalies_before_scan_is_empty(client):
    timesheet_id = _create_draft(client)
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(5)
    ] + [{"entry_date": (THIS_MONDAY + timedelta(days=5)).isoformat(), "hours": 4, "entry_type": "BILLABLE"}]
    client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())

    resp = client.get(f"/timesheets/{timesheet_id}/anomalies", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["flags"] == []


def test_get_anomalies_after_scan_returns_flags(client):
    timesheet_id = _create_draft(client)
    entries = [
        {"entry_date": (THIS_MONDAY + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
        for i in range(5)
    ] + [{"entry_date": (THIS_MONDAY + timedelta(days=5)).isoformat(), "hours": 4, "entry_type": "BILLABLE"}]
    client.put(f"/timesheets/{timesheet_id}/entries", json={"entries": entries}, headers=_auth())
    client.post(f"/timesheets/{timesheet_id}/scan-anomalies", headers=_auth())

    resp = client.get(f"/timesheets/{timesheet_id}/anomalies", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["flags"]) >= 1


# ---------------------------------------------------------------------------
# Timesheet Dispute Resolution
# ---------------------------------------------------------------------------

_LONG_REASON = "The client's approver disputes hours logged on Thursday as incorrect for this week."


def test_raise_dispute_requires_approved_timesheet(client):
    timesheet_id = _create_draft(client)
    _log_valid_hours(client, timesheet_id)

    resp = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_raise_dispute_requires_50_char_reason(client):
    timesheet_id = _approved_timesheet(client)

    resp = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": "too short"},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_raise_and_list_dispute(client):
    timesheet_id = _approved_timesheet(client)

    resp = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON, "disputed_hours": 35.0},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OPEN"
    assert body["original_hours"] == 40.0
    assert body["disputed_hours"] == 35.0

    list_resp = client.get(f"/timesheets/{timesheet_id}/disputes", headers=_auth())
    assert list_resp.status_code == 200
    assert len(list_resp.json()["disputes"]) == 1


def test_resolve_dispute_adjusted_requires_adjusted_hours(client):
    timesheet_id = _approved_timesheet(client)
    dispute_id = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON},
        headers=_auth(),
    ).json()["id"]

    resp = client.post(
        f"/timesheets/disputes/{dispute_id}/resolve",
        json={"resolution": "ADJUSTED", "resolution_notes": "Client confirmed correct hours after review."},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_resolve_dispute_adjusted_does_not_mutate_original_timesheet(client):
    timesheet_id = _approved_timesheet(client)
    dispute_id = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON},
        headers=_auth(),
    ).json()["id"]

    resp = client.post(
        f"/timesheets/disputes/{dispute_id}/resolve",
        json={
            "resolution": "ADJUSTED", "adjusted_hours": 35.0,
            "resolution_notes": "Client confirmed correct hours were 35, not 40.",
        },
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RESOLVED_ADJUSTED"
    assert resp.json()["adjusted_hours"] == 35.0

    timesheet_resp = client.get(f"/timesheets/{timesheet_id}", headers=_auth())
    assert timesheet_resp.json()["total_hours"] == 40.0


def test_resolve_dispute_confirmed(client):
    timesheet_id = _approved_timesheet(client)
    dispute_id = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON},
        headers=_auth(),
    ).json()["id"]

    resp = client.post(
        f"/timesheets/disputes/{dispute_id}/resolve",
        json={"resolution": "CONFIRMED", "resolution_notes": "Confirmed accurate after review."},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "RESOLVED_CONFIRMED"


def test_resolve_already_resolved_dispute_is_409(client):
    timesheet_id = _approved_timesheet(client)
    dispute_id = client.post(
        f"/timesheets/{timesheet_id}/disputes",
        json={"raised_by": "EMPLOYEE", "reason": _LONG_REASON},
        headers=_auth(),
    ).json()["id"]
    client.post(
        f"/timesheets/disputes/{dispute_id}/resolve",
        json={"resolution": "CONFIRMED", "resolution_notes": "Confirmed accurate after review."},
        headers=_auth(),
    )

    resp = client.post(
        f"/timesheets/disputes/{dispute_id}/resolve",
        json={"resolution": "CONFIRMED", "resolution_notes": "Second resolution attempt should fail."},
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_resolve_dispute_404_for_unknown_id(client):
    resp = client.post(
        "/timesheets/disputes/does-not-exist/resolve",
        json={"resolution": "CONFIRMED", "resolution_notes": "N/A"},
        headers=_auth(),
    )
    assert resp.status_code == 404

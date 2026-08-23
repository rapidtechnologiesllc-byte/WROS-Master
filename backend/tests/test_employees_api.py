"""
POST /employees, GET /employees, GET /employees/bench-pool, GET
/employees/bench-aging-alerts, GET /employees/{id}, POST
/employees/{id}/mark-bench|remove-from-bench, GET
/employees/{id}/bench-history -- proves S-245 (Create Employee Profile)
+ S-246 (Mark Employee as Bench, extended with bench_periods history) +
S-247 (View Bench Pool) + S-248 (Bench Duration & Aging Report)
end-to-end on real routes.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import io
import os
import tempfile
from datetime import date, timedelta

import openpyxl
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.resource_management import BenchPoolEntry
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


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

    from app.api.v1.endpoints.employees import router as employees_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(employees_router)
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

    ids = {"tenant_id": tenant.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _create_employee(client, **overrides):
    body = {
        "first_name": "Sam", "last_name": "Lee", "email": "sam@blitzenx.com",
        "joining_date": "2025-01-01", "current_title": "Guidewire Developer",
        "current_skills": ["Guidewire PolicyCenter", "Java"],
        "base_salary_usd_cents": 900000,
    }
    body.update(overrides)
    resp = client.post("/employees", json=body, headers=_auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/employees")
    assert resp.status_code in (401, 403)


def test_create_employee_profile(client):
    body = _create_employee(client)
    assert body["first_name"] == "Sam"
    assert body["status"] == "PRE_JOINING"
    assert body["delivery_engine"] == "SPECIALITY"
    assert body["current_skills"] == ["Guidewire PolicyCenter", "Java"]
    assert body["employee_number"]  # auto-generated, non-empty
    assert body["is_on_bench"] is False


def test_create_employee_rejects_duplicate_email(client):
    _create_employee(client)
    resp = client.post(
        "/employees",
        json={
            "first_name": "Other", "last_name": "Person", "email": "sam@blitzenx.com",
            "joining_date": "2025-02-01",
        },
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_list_employees(client):
    _create_employee(client)
    _create_employee(client, email="jane@blitzenx.com", first_name="Jane")

    resp = client.get("/employees", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["employees"]) == 2


def test_mark_bench_then_visible_in_bench_pool(client):
    employee = _create_employee(client)
    mark_resp = client.post(
        f"/employees/{employee['id']}/mark-bench",
        json={"reason": "NEWLY_JOINED"}, headers=_auth(),
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["is_on_bench"] is True
    assert mark_resp.json()["bench_days"] == 0

    pool_resp = client.get("/employees/bench-pool", headers=_auth())
    assert pool_resp.status_code == 200
    pool = pool_resp.json()["employees"]
    assert len(pool) == 1
    assert pool[0]["id"] == employee["id"]


def test_mark_bench_rejects_invalid_reason(client):
    employee = _create_employee(client)
    resp = client.post(
        f"/employees/{employee['id']}/mark-bench",
        json={"reason": "MADE_UP_REASON"}, headers=_auth(),
    )
    assert resp.status_code == 422


def test_remove_from_bench_closes_history_and_leaves_pool(client):
    employee = _create_employee(client)
    client.post(f"/employees/{employee['id']}/mark-bench", json={"reason": "NEWLY_JOINED"}, headers=_auth())

    remove_resp = client.post(f"/employees/{employee['id']}/remove-from-bench", headers=_auth())
    assert remove_resp.status_code == 200
    assert remove_resp.json()["is_on_bench"] is False

    pool_resp = client.get("/employees/bench-pool", headers=_auth())
    assert pool_resp.json()["employees"] == []

    history_resp = client.get(f"/employees/{employee['id']}/bench-history", headers=_auth())
    assert history_resp.status_code == 200
    periods = history_resp.json()["periods"]
    assert len(periods) == 1
    assert periods[0]["bench_end_date"] is not None
    assert periods[0]["reason_for_bench"] == "NEWLY_JOINED"


def test_bench_aging_alerts_reflect_current_bench_pool(client):
    employee = _create_employee(client)
    client.post(f"/employees/{employee['id']}/mark-bench", json={"reason": "NEWLY_JOINED"}, headers=_auth())

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    entry = session.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee["id"]).first()
    entry.available_from = date.today() - timedelta(days=60)
    session.commit()
    session.close()
    engine.dispose()

    resp = client.get("/employees/bench-aging-alerts", headers=_auth())
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["days_on_bench"] == 60
    assert alerts[0]["employee_name"] == "Sam Lee"


def test_get_employee_404_for_unknown_id(client):
    resp = client.get("/employees/does-not-exist", headers=_auth())
    assert resp.status_code == 404


def test_utilization_history_and_summary(client):
    employee = _create_employee(client)

    from app.models.resource_management import EmployeeUtilizationMetric

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    session.add(EmployeeUtilizationMetric(
        tenant_id=client.wros_ids["tenant_id"], employee_id=employee["id"],
        period_start=date.today() - timedelta(days=7),
        utilization_pct=30, billable_hours=12, bench_hours=28,
    ))
    session.add(EmployeeUtilizationMetric(
        tenant_id=client.wros_ids["tenant_id"], employee_id=employee["id"],
        period_start=date.today(),
        utilization_pct=80, billable_hours=32, bench_hours=8,
    ))
    session.commit()
    session.close()
    engine.dispose()

    history_resp = client.get(f"/employees/{employee['id']}/utilization-history", headers=_auth())
    assert history_resp.status_code == 200
    history = history_resp.json()["history"]
    assert len(history) == 2
    assert history[0]["utilization_pct"] == 80.0  # most recent first

    summary_resp = client.get("/employees/utilization-summary", headers=_auth())
    assert summary_resp.status_code == 200
    body = summary_resp.json()
    assert len(body["employees"]) == 1
    assert body["employees"][0]["latest_utilization_pct"] == 80.0  # latest period wins
    assert body["employees"][0]["is_low_utilization"] is False
    assert body["low_utilization_count"] == 0


def test_record_utilization_computes_from_approved_timesheet(client):
    """S-223/HRMS-0904: utilization = approved billable hours / available
    (standard weekly) hours -- the compute step that populates
    EmployeeUtilizationMetric was real, tested backend with zero caller
    anywhere (record_weekly_utilization_metric() was dead code); this
    proves the endpoint that actually triggers it."""
    employee = _create_employee(client)

    from app.models.client import Client
    from app.models.demand import Demand
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.timesheet import Timesheet

    week = date.today() - timedelta(days=date.today().weekday())

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    acme = Client(tenant_id=client.wros_ids["tenant_id"], company_name="Acme Insurance")
    session.add(acme)
    session.commit()
    demand = Demand(
        tenant_id=client.wros_ids["tenant_id"], client_id=acme.id, job_title="Guidewire Dev",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    session.add(demand)
    session.commit()
    allocation = EmployeeAllocation(
        tenant_id=client.wros_ids["tenant_id"], employee_id=employee["id"], demand_id=demand.id,
        client_id=acme.id, status="ACTIVE", start_date=date(2025, 1, 1),
    )
    session.add(allocation)
    session.commit()
    session.add(Timesheet(
        tenant_id=client.wros_ids["tenant_id"], employee_id=employee["id"], allocation_id=allocation.id,
        week_starting_date=week, total_hours=32, billable_hours=32, non_billable_hours=0,
        status="APPROVED", approved_by="U-ADMIN",
    ))
    session.commit()
    session.close()
    engine.dispose()

    resp = client.post(
        f"/employees/{employee['id']}/record-utilization",
        json={"week_starting_date": week.isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["billable_hours"] == 32.0
    assert body["bench_hours"] == 8.0
    assert body["utilization_pct"] == 80.0

    history_resp = client.get(f"/employees/{employee['id']}/utilization-history", headers=_auth())
    assert len(history_resp.json()["history"]) == 1


def test_record_utilization_404_for_unknown_employee(client):
    resp = client.post(
        "/employees/does-not-exist/record-utilization",
        json={"week_starting_date": date.today().isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_engine_history_shows_initial_speciality_assignment(client):
    """S-351/HRMS-0512: every new hire's engine_history starts at
    creation with from_engine=None -> SPECIALITY -- proves
    convert_candidate_to_employee()/create_employee_profile()'s audit
    trail write is actually reachable through the API, not just
    exercised by a service-layer test."""
    employee = _create_employee(client)

    resp = client.get(f"/employees/{employee['id']}/engine-history", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["history"]) == 1
    assert body["history"][0]["from_engine"] is None
    assert body["history"][0]["to_engine"] == "SPECIALITY"
    assert body["history"][0]["reason"]


def test_engine_history_404_for_unknown_employee(client):
    resp = client.get("/employees/does-not-exist/engine-history", headers=_auth())
    assert resp.status_code == 404


def test_employee_item_exposes_engine_and_certification_fields(client):
    employee = _create_employee(client)
    assert employee["delivery_engine"] == "SPECIALITY"
    assert employee["core_certified"] is False
    assert employee["core_certified_date"] is None
    assert employee["engine_entry_date"]


def test_employee_performance_returns_events_and_score_averages(client):
    """S-354/HRMS-0515: proves the read side reads from the SAME
    employee_performance_events store buddy_program_service.py and
    htd_phase_gate_service.py already write real events into -- events
    with a numeric "score" key in their JSON blob (BUDDY_KPI-shaped)
    average correctly; events without one (CERTIFICATION_GATE-shaped)
    are excluded, not zero-filled."""
    employee = _create_employee(client)

    from app.services.performance_store_service import write_performance_event

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    write_performance_event(
        session, employee_id=employee["id"], event_type="BUDDY_KPI",
        event_data={"kpi_name": "Requirements Gathering", "score": 80},
    )
    write_performance_event(
        session, employee_id=employee["id"], event_type="BUDDY_KPI",
        event_data={"kpi_name": "Communication", "score": 90},
    )
    write_performance_event(
        session, employee_id=employee["id"], event_type="CERTIFICATION_GATE",
        event_data={"phase": "INDUCTION", "decision": "PASS"},
    )
    session.commit()
    session.close()
    engine.dispose()

    resp = client.get(f"/employees/{employee['id']}/performance", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["events"]) == 3
    assert body["score_averages_by_event_type"]["BUDDY_KPI"] == 85.0
    assert "CERTIFICATION_GATE" not in body["score_averages_by_event_type"]


def test_employee_performance_404_for_unknown_employee(client):
    resp = client.get("/employees/does-not-exist/performance", headers=_auth())
    assert resp.status_code == 404


def test_utilization_summary_flags_low_utilization(client):
    employee = _create_employee(client)

    from app.models.resource_management import EmployeeUtilizationMetric

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    session.add(EmployeeUtilizationMetric(
        tenant_id=client.wros_ids["tenant_id"], employee_id=employee["id"],
        period_start=date.today(), utilization_pct=20, billable_hours=8, bench_hours=32,
    ))
    session.commit()
    session.close()
    engine.dispose()

    resp = client.get("/employees/utilization-summary", headers=_auth())
    body = resp.json()
    assert body["employees"][0]["is_low_utilization"] is True
    assert body["low_utilization_count"] == 1


def test_bench_cost_summary(client):
    employee = _create_employee(client, base_salary_usd_cents=900000)
    client.post(f"/employees/{employee['id']}/mark-bench", json={"reason": "NEWLY_JOINED"}, headers=_auth())

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    entry = session.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == employee["id"]).first()
    entry.available_from = date.today() - timedelta(days=10)
    session.commit()
    session.close()
    engine.dispose()

    resp = client.get("/employees/bench-cost-summary", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["employees"]) == 1
    item = body["employees"][0]
    assert item["days_on_bench"] == 10
    assert item["daily_cost_usd_cents"] == round(900000 / 30)
    assert item["running_total_usd_cents"] == round(900000 / 30) * 10
    assert body["total_running_cost_usd_cents"] == item["running_total_usd_cents"]


def _create_candidate(client, candidate_id="CAND-1"):
    from app.models.candidate import Candidate

    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    session.add(Candidate(
        candidateID=candidate_id, candidateFirstName="Jamie", candidateLastName="Fox",
        candidateEmail=f"{candidate_id.lower()}@candidate.com", candidatePassword="x",
        tenant_id=client.wros_ids["tenant_id"],
    ))
    session.commit()
    session.close()
    engine.dispose()
    return candidate_id


def test_convert_candidate_to_employee(client):
    candidate_id = _create_candidate(client)
    resp = client.post(
        f"/employees/convert-candidate/{candidate_id}",
        json={"joining_date": "2026-08-01", "current_title": "Guidewire Developer"},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["first_name"] == "Jamie"
    assert body["last_name"] == "Fox"
    assert body["delivery_engine"] == "SPECIALITY"
    assert body["status"] == "PRE_JOINING"
    assert body["employee_number"]


def test_convert_candidate_twice_is_rejected(client):
    candidate_id = _create_candidate(client)
    client.post(
        f"/employees/convert-candidate/{candidate_id}",
        json={"joining_date": "2026-08-01"}, headers=_auth(),
    )
    resp = client.post(
        f"/employees/convert-candidate/{candidate_id}",
        json={"joining_date": "2026-08-01"}, headers=_auth(),
    )
    assert resp.status_code == 409


def test_convert_unknown_candidate_is_404(client):
    resp = client.post(
        "/employees/convert-candidate/does-not-exist",
        json={"joining_date": "2026-08-01"}, headers=_auth(),
    )
    assert resp.status_code == 404


def _make_xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_bulk_import_creates_all_valid_rows(client):
    xlsx = _make_xlsx([
        ["first_name", "last_name", "email", "joining_date", "current_title", "current_skills"],
        ["Amy", "Chen", "amy@blitzenx.com", "2026-01-05", "Guidewire Dev", "Guidewire, Java"],
        ["Ravi", "Kumar", "ravi@blitzenx.com", "2026-01-06", "PolicyCenter Dev", "PolicyCenter"],
    ])
    resp = client.post(
        "/employees/bulk-import",
        files={"file": ("employees.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []

    list_resp = client.get("/employees", headers=_auth())
    assert len(list_resp.json()["employees"]) == 2


def test_bulk_import_skips_duplicate_email_and_reports_it(client):
    _create_employee(client, email="dup@blitzenx.com")
    xlsx = _make_xlsx([
        ["first_name", "last_name", "email", "joining_date"],
        ["Someone", "Else", "dup@blitzenx.com", "2026-01-05"],
        ["Fresh", "Hire", "fresh@blitzenx.com", "2026-01-06"],
    ])
    resp = client.post(
        "/employees/bulk-import",
        files={"file": ("employees.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["email"] == "dup@blitzenx.com"


def test_bulk_import_rejects_missing_required_columns(client):
    xlsx = _make_xlsx([["first_name", "last_name"], ["No", "Email"]])
    resp = client.post(
        "/employees/bulk-import",
        files={"file": ("employees.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(),
    )
    assert resp.status_code == 422


def test_staffing_eligibility_true_for_speciality_by_default(client):
    employee = _create_employee(client)
    resp = client.get(
        f"/employees/{employee['id']}/staffing-eligibility?delivery_engine=SPECIALITY", headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["eligible"] is True


def test_staffing_eligibility_false_for_core_without_certification(client):
    employee = _create_employee(client)
    resp = client.get(
        f"/employees/{employee['id']}/staffing-eligibility?delivery_engine=CORE", headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["eligible"] is False
    assert "Core-certified" in body["reason"]

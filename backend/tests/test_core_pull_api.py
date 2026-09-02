"""
GET /core-pull/specialty-pool-status, GET /core-pull/events, POST
.../execute|override, POST /core-pull/replacement-plans -- proves S-353
(HRMS-0514) Core-Pull Engine + S-373 (HRMS-0529) Specialty Pool Guard
end-to-end on real routes, not just the service layer (see the
import logging
Definition of Done correction in CLAUDE.md).

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys. No LLM involved in this story.
"""
import os
import tempfile
from datetime import date

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
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.core_pull_service import SPECIALTY_POOL_MINIMUM
from app.services.orchestration_router_service import seed_default_conflict_rules
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


def _make_employee(db, tenant, *, core_certified=True, delivery_engine="SPECIALITY", suffix="1"):
    employee = Employee(
        tenant_id=tenant.id, first_name=f"Sam{suffix}", last_name="Lee",
        email=f"sam{suffix}@blitzenx.com", joining_date=date(2025, 1, 1),
        status="ALLOCATED", core_certified=core_certified, delivery_engine=delivery_engine,
    )
    db.add(employee)
    db.commit()
    return employee


def _make_demand(db, tenant, client, *, delivery_engine="SPECIALITY", suffix="1"):
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title=f"Role {suffix}",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000, delivery_engine=delivery_engine,
    )
    db.add(demand)
    db.commit()
    return demand


def _fill_specialty_pool(db, tenant, count):
    for i in range(count):
        _make_employee(db, tenant, core_certified=True, delivery_engine="SPECIALITY", suffix=f"pool{i}")


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

    from app.api.v1.endpoints.core_pull import router as core_pull_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(core_pull_router)
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
    db.add(Users(
        UserID="U-BUHEAD", UserRole="BU Head", UserEmail="buhead@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    seed_default_conflict_rules(db, tenant_id=tenant.id)
    db.commit()

    acme = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db.add(acme)
    db.commit()

    speciality_demand = _make_demand(db, tenant, acme, delivery_engine="SPECIALITY", suffix="spec")
    core_demand = _make_demand(db, tenant, acme, delivery_engine="CORE", suffix="core")
    db.add_all([speciality_demand, core_demand])
    db.commit()

    employee = _make_employee(db, tenant, core_certified=True, delivery_engine="SPECIALITY")

    speciality_allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=speciality_demand.id,
        client_id=acme.id, status="ACTIVE", start_date=date(2026, 1, 1), utilization_pct=100,
    )
    db.add(speciality_allocation)
    db.commit()

    ids = {
        "tenant_id": tenant.id, "employee_id": employee.id,
        "core_demand_id": core_demand.id, "speciality_allocation_id": speciality_allocation.id,
    }
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


def _admin_auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _buhead_auth():
    return {"Authorization": f"Bearer {_token_for('buhead@blitzenx.com', role='BU Head')}"}


def _make_session_for(client):
    """Short-lived engine+session against the same SQLite file the API
    uses -- always disposed by the caller (via _run_against_db) so the
    file isn't still locked when the client fixture tries to remove it."""
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    return session, engine


def _run_against_db(client, fn):
    session, engine = _make_session_for(client)
    try:
        return fn(session)
    finally:
        session.close()
        engine.dispose()


def _detect_event(client):
    """Helper: creates a PENDING CorePullEvent directly via the service
    layer against the same SQLite file the API uses, so tests can set up
    a conflict without a separate detection endpoint (detection is
    triggered by the caller proposing a Core move -- HRMS-1105's scan or
    S-372's workflow -- not a standalone route in this story)."""
    from app.services.core_pull_service import detect_core_pull_conflict

    ids = client.wros_ids

    def _do(db):
        employee = db.query(Employee).filter(Employee.id == ids["employee_id"]).first()
        core_demand = db.query(Demand).filter(Demand.id == ids["core_demand_id"]).first()
        event = detect_core_pull_conflict(db, employee, core_demand)
        db.commit()
        return event.id

    return _run_against_db(client, _do)


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/core-pull/specialty-pool-status")
    assert resp.status_code in (401, 403)


def test_pool_status_below_minimum_by_default(client):
    resp = client.get("/core-pull/specialty-pool-status", headers=_admin_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["pool_size"] == 1  # just the one fixture employee
    assert body["below_minimum"] is True
    assert body["gap"] == SPECIALTY_POOL_MINIMUM - 1


def test_pool_status_at_edge_when_exactly_at_minimum_plus_one(client):
    def _do(db):
        tenant = db.query(Tenant).first()
        _fill_specialty_pool(db, tenant, SPECIALTY_POOL_MINIMUM)  # +40, fixture employee makes 41
        db.commit()

    _run_against_db(client, _do)

    resp = client.get("/core-pull/specialty-pool-status", headers=_admin_auth())
    body = resp.json()
    assert body["pool_size"] == SPECIALTY_POOL_MINIMUM + 1
    assert body["at_edge"] is True
    assert body["below_minimum"] is False


def test_get_pending_events_enriched(client):
    event_id = _detect_event(client)

    resp = client.get("/core-pull/events", headers=_admin_auth())
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert len(events) == 1
    assert events[0]["id"] == event_id
    assert events[0]["employee_name"] == "Sam1 Lee"
    assert events[0]["core_demand_job_title"] == "Role core"
    assert events[0]["status"] == "PENDING"


def test_execute_blocked_below_minimum_without_replacement_plan(client):
    event_id = _detect_event(client)

    resp = client.post(f"/core-pull/events/{event_id}/execute", headers=_admin_auth())
    assert resp.status_code == 409
    assert "minimum" in resp.json()["detail"].lower()


def test_execute_succeeds_once_replacement_plan_logged(client):
    event_id = _detect_event(client)
    ids = client.wros_ids

    plan_resp = client.post(
        "/core-pull/replacement-plans",
        json={
            "employee_id": ids["employee_id"],
            "replacement_strategy": "x" * 100,
            "expected_replacement_date": "2026-09-01",
        },
        headers=_admin_auth(),
    )
    assert plan_resp.status_code == 200

    exec_resp = client.post(f"/core-pull/events/{event_id}/execute", headers=_admin_auth())
    assert exec_resp.status_code == 200
    body = exec_resp.json()
    assert body["event"]["status"] == "EXECUTED"


def test_execute_with_full_pool_succeeds_without_plan(client):
    def _do(db):
        tenant = db.query(Tenant).first()
        _fill_specialty_pool(db, tenant, SPECIALTY_POOL_MINIMUM)  # avoid the guard entirely
        db.commit()

    _run_against_db(client, _do)

    event_id = _detect_event(client)
    resp = client.post(f"/core-pull/events/{event_id}/execute", headers=_admin_auth())
    assert resp.status_code == 200
    assert resp.json()["event"]["status"] == "EXECUTED"


def test_replacement_plan_rejects_short_strategy(client):
    ids = client.wros_ids
    resp = client.post(
        "/core-pull/replacement-plans",
        json={
            "employee_id": ids["employee_id"],
            "replacement_strategy": "too short",
            "expected_replacement_date": "2026-09-01",
        },
        headers=_admin_auth(),
    )
    assert resp.status_code == 422


def test_override_forbidden_for_non_bu_head(client):
    event_id = _detect_event(client)
    resp = client.post(
        f"/core-pull/events/{event_id}/override",
        json={"justification": "x" * 100},
        headers=_admin_auth(),
    )
    assert resp.status_code == 403


def test_override_succeeds_for_bu_head(client):
    event_id = _detect_event(client)
    resp = client.post(
        f"/core-pull/events/{event_id}/override",
        json={"justification": "x" * 100},
        headers=_buhead_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["event"]["status"] == "OVERRIDDEN"


def test_override_rejects_short_justification(client):
    event_id = _detect_event(client)
    resp = client.post(
        f"/core-pull/events/{event_id}/override",
        json={"justification": "too short"},
        headers=_buhead_auth(),
    )
    assert resp.status_code == 422


def test_execute_nonexistent_event_is_404(client):
    resp = client.post("/core-pull/events/does-not-exist/execute", headers=_admin_auth())
    assert resp.status_code == 404

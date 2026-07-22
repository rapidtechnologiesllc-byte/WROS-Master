"""
POST /demand-confirmation/demands/{id}/confirm-sow, .../schedule-call,
GET .../calls, POST /calls/{id}/confirm-fit|trigger-release -- proves
S-372 (HRMS-0528) Confirmed vs Potential Demand Workflow end-to-end on
real routes, not just the service layer (see the Definition of Done
correction in CLAUDE.md).

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
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

    from app.api.v1.endpoints.demand_confirmation import router as demand_confirmation_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(demand_confirmation_router)
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
        tenant_id=tenant.id, client_id=acme.id, job_title="Sr. Guidewire Developer",
        required_skills="[]", min_experience_years=5.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    db.add(demand)
    db.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED", core_certified=True,
    )
    db.add(employee)
    db.commit()

    ids = {"tenant_id": tenant.id, "demand_id": demand.id, "employee_id": employee.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}


def _schedule_call(client):
    ids = client.wros_ids
    resp = client.post(
        f"/demand-confirmation/demands/{ids['demand_id']}/employees/{ids['employee_id']}/schedule-call",
        json={}, headers=_auth(),
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_unauthenticated_request_is_rejected(client):
    ids = client.wros_ids
    resp = client.post(f"/demand-confirmation/demands/{ids['demand_id']}/confirm-sow", json={"sow_reference": "SOW-1"})
    assert resp.status_code in (401, 403)


def test_confirm_sow_sets_confirmed_status(client):
    ids = client.wros_ids
    resp = client.post(
        f"/demand-confirmation/demands/{ids['demand_id']}/confirm-sow",
        json={"sow_reference": "SOW-2026-001"}, headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confirmation_status"] == "CONFIRMED"
    assert body["sow_reference"] == "SOW-2026-001"


def test_confirm_sow_rejects_empty_reference(client):
    ids = client.wros_ids
    resp = client.post(
        f"/demand-confirmation/demands/{ids['demand_id']}/confirm-sow",
        json={"sow_reference": ""}, headers=_auth(),
    )
    assert resp.status_code in (422,)


def test_schedule_call_is_idempotent(client):
    call_id_1 = _schedule_call(client)
    call_id_2 = _schedule_call(client)
    assert call_id_1 == call_id_2


def test_get_calls_for_demand_enriched(client):
    call_id = _schedule_call(client)
    ids = client.wros_ids

    resp = client.get(f"/demand-confirmation/demands/{ids['demand_id']}/calls", headers=_auth())
    assert resp.status_code == 200
    calls = resp.json()["calls"]
    assert len(calls) == 1
    assert calls[0]["id"] == call_id
    assert calls[0]["employee_name"] == "Sam Lee"
    assert calls[0]["demand_job_title"] == "Sr. Guidewire Developer"


def test_confirm_fit_records_employee_confirmation(client):
    call_id = _schedule_call(client)
    resp = client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "EMPLOYEE", "confirmed": True, "notes": "Looks like a great fit"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["call"]["employee_fit_confirmed"] is True
    assert body["call"]["bu_head_fit_confirmed"] is None


def test_confirm_fit_cannot_be_recorded_twice(client):
    call_id = _schedule_call(client)
    client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "EMPLOYEE", "confirmed": True}, headers=_auth(),
    )
    second = client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "EMPLOYEE", "confirmed": False}, headers=_auth(),
    )
    assert second.status_code == 409


def test_confirm_fit_rejects_invalid_participant(client):
    call_id = _schedule_call(client)
    resp = client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "MANAGER", "confirmed": True}, headers=_auth(),
    )
    assert resp.status_code == 422


def test_trigger_release_blocked_until_both_fits_and_confirmed(client):
    ids = client.wros_ids
    call_id = _schedule_call(client)

    blocked = client.post(f"/demand-confirmation/calls/{call_id}/trigger-release", headers=_auth())
    assert blocked.status_code == 409

    client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "EMPLOYEE", "confirmed": True}, headers=_auth(),
    )
    client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "BU_HEAD", "confirmed": True}, headers=_auth(),
    )

    still_blocked = client.post(f"/demand-confirmation/calls/{call_id}/trigger-release", headers=_auth())
    assert still_blocked.status_code == 409  # confirmation_status still not CONFIRMED

    client.post(
        f"/demand-confirmation/demands/{ids['demand_id']}/confirm-sow",
        json={"sow_reference": "SOW-2026-002"}, headers=_auth(),
    )

    released = client.post(f"/demand-confirmation/calls/{call_id}/trigger-release", headers=_auth())
    assert released.status_code == 200
    assert released.json()["call"]["specialty_client_release_triggered_at"] is not None


def test_trigger_release_blocked_when_one_fit_is_false(client):
    ids = client.wros_ids
    call_id = _schedule_call(client)

    client.post(
        f"/demand-confirmation/demands/{ids['demand_id']}/confirm-sow",
        json={"sow_reference": "SOW-2026-003"}, headers=_auth(),
    )
    client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "EMPLOYEE", "confirmed": False}, headers=_auth(),
    )
    client.post(
        f"/demand-confirmation/calls/{call_id}/confirm-fit",
        json={"participant": "BU_HEAD", "confirmed": True}, headers=_auth(),
    )

    resp = client.post(f"/demand-confirmation/calls/{call_id}/trigger-release", headers=_auth())
    assert resp.status_code == 409


def test_schedule_call_404_for_unknown_demand(client):
    ids = client.wros_ids
    resp = client.post(
        f"/demand-confirmation/demands/does-not-exist/employees/{ids['employee_id']}/schedule-call",
        json={}, headers=_auth(),
    )
    assert resp.status_code == 404

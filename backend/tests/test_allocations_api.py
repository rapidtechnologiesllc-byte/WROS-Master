"""
POST /allocations, GET /allocations, POST /allocations/{id}/end --
proves S-251 (Allocate Employee to Project) + S-252 (Allocation
Conflict Detection) end-to-end on real routes. Conflict detection
(AllocationOverCapacity) is not reimplemented here -- it's the existing
import logging
allocate_employee_to_project() gate, surfaced as a 409.

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
from app.models.project import Project
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

    from app.api.v1.endpoints.allocations import router as allocations_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(allocations_router)
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

    demand_a = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev A",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=15000,
    )
    demand_b = Demand(
        tenant_id=tenant.id, client_id=acme.id, job_title="Guidewire Dev B",
        required_skills="[]", min_experience_years=3.0, work_location="REMOTE",
        status="OPEN", billing_rate_usd_cents=16000,
    )
    db.add_all([demand_a, demand_b])
    db.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    db.add(employee)
    db.commit()

    project = Project(
        tenant_id=tenant.id, client_id=acme.id, name="PolicyCenter Rollout",
        delivery_engine="SPECIALITY", si_partner="PWC",
    )
    db.add(project)
    db.commit()

    ids = {
        "tenant_id": tenant.id, "employee_id": employee.id,
        "demand_a_id": demand_a.id, "demand_b_id": demand_b.id, "project_id": project.id,
    }
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


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/allocations")
    assert resp.status_code in (401, 403)


def test_allocate_employee_to_project(client):
    ids = client.wros_ids
    resp = client.post(
        "/allocations",
        json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"], "utilization_pct": 100},
        headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["employee_name"] == "Sam Lee"
    assert body["demand_job_title"] == "Guidewire Dev A"


def test_allocate_already_allocated_employee_is_blocked(client):
    ids = client.wros_ids
    client.post(
        "/allocations", json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"]}, headers=_auth(),
    )
    resp = client.post(
        "/allocations", json={"employee_id": ids["employee_id"], "demand_id": ids["demand_b_id"]}, headers=_auth(),
    )
    assert resp.status_code == 409


def test_allow_concurrent_over_capacity_is_blocked(client):
    """S-252: over-100% concurrent allocation is rejected."""
    ids = client.wros_ids
    client.post(
        "/allocations",
        json={
            "employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"],
            "utilization_pct": 70, "allow_concurrent": True,
        },
        headers=_auth(),
    )
    resp = client.post(
        "/allocations",
        json={
            "employee_id": ids["employee_id"], "demand_id": ids["demand_b_id"],
            "utilization_pct": 40, "allow_concurrent": True,
        },
        headers=_auth(),
    )
    assert resp.status_code == 409


def test_list_allocations_filtered_by_employee(client):
    ids = client.wros_ids
    client.post(
        "/allocations", json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"]}, headers=_auth(),
    )
    resp = client.get(f"/allocations?employee_id={ids['employee_id']}", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["allocations"]) == 1


def test_end_allocation_moves_employee_back_to_bench(client):
    ids = client.wros_ids
    create_resp = client.post(
        "/allocations", json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"]}, headers=_auth(),
    )
    allocation_id = create_resp.json()["id"]

    end_resp = client.post(f"/allocations/{allocation_id}/end", json={}, headers=_auth())
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "ENDED"


def test_allocate_nonexistent_employee_is_404(client):
    ids = client.wros_ids
    resp = client.post(
        "/allocations", json={"employee_id": "does-not-exist", "demand_id": ids["demand_a_id"]}, headers=_auth(),
    )
    assert resp.status_code == 404


def test_allocate_with_project_denormalizes_si_partner(client):
    """S-358/HRMS-0519: si_partner is copied from the project onto the
    allocation at creation time -- 'who is at PwC right now' without a
    join back to projects."""
    ids = client.wros_ids
    resp = client.post(
        "/allocations",
        json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"], "project_id": ids["project_id"]},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == ids["project_id"]
    assert body["si_partner"] == "PWC"


def test_allocate_with_unknown_project_is_404(client):
    ids = client.wros_ids
    resp = client.post(
        "/allocations",
        json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"], "project_id": "does-not-exist"},
        headers=_auth(),
    )
    assert resp.status_code == 404


def test_allocate_without_project_leaves_si_partner_null(client):
    ids = client.wros_ids
    resp = client.post(
        "/allocations", json={"employee_id": ids["employee_id"], "demand_id": ids["demand_a_id"]}, headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["project_id"] is None
    assert resp.json()["si_partner"] is None

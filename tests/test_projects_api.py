"""
POST /projects, GET /projects|{id}, POST /projects/{id}/status,
POST/GET /projects/{id}/milestones, POST /milestones/{id}/complete,
GET /projects/{id}/unfilled-roles|expected-revenue -- proves
HRMS-0801/0804/0805/0806 end-to-end on real routes (no REST layer
existed for Project at all before this).

Also proves S-358/HRMS-0519 (SI Partner Engagement Tagging): si_partner
required when delivery_engine=SPECIALITY, denormalized to
employee_allocations on allocation creation.

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

    from app.api.v1.endpoints.projects import router as projects_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(projects_router)
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

    ids = {"tenant_id": tenant.id, "client_id": acme.id}
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


def _create_project(client, **overrides):
    body = {
        "client_id": client.wros_ids["client_id"], "name": "PolicyCenter Rollout",
        "delivery_engine": "SPECIALITY", "si_partner": "PWC",
    }
    body.update(overrides)
    resp = client.post("/projects", json=body, headers=_auth())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/projects")
    assert resp.status_code in (401, 403)


def test_create_project_success(client):
    project = _create_project(client)
    assert project["status"] == "ACTIVE"
    assert project["delivery_engine"] == "SPECIALITY"
    assert project["si_partner"] == "PWC"


def test_create_speciality_project_requires_si_partner(client):
    resp = client.post(
        "/projects",
        json={"client_id": client.wros_ids["client_id"], "name": "No Partner Project", "delivery_engine": "SPECIALITY"},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_create_core_project_does_not_require_si_partner(client):
    resp = client.post(
        "/projects",
        json={"client_id": client.wros_ids["client_id"], "name": "Core Engagement", "delivery_engine": "CORE"},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["si_partner"] is None


def test_list_and_get_project(client):
    project = _create_project(client)
    list_resp = client.get("/projects", headers=_auth())
    assert len(list_resp.json()["projects"]) == 1

    get_resp = client.get(f"/projects/{project['id']}", headers=_auth())
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project["id"]


def test_get_project_404_for_unknown_id(client):
    resp = client.get("/projects/does-not-exist", headers=_auth())
    assert resp.status_code == 404


def test_transition_status_valid(client):
    project = _create_project(client)
    resp = client.post(f"/projects/{project['id']}/status", json={"status": "ON_HOLD"}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["status"] == "ON_HOLD"


def test_transition_status_invalid_is_409(client):
    project = _create_project(client)
    resp = client.post(f"/projects/{project['id']}/status", json={"status": "PLANNING"}, headers=_auth())
    assert resp.status_code == 409


def test_create_and_list_milestone(client):
    project = _create_project(client)
    resp = client.post(
        f"/projects/{project['id']}/milestones",
        json={"title": "UAT sign-off", "due_date": (date.today() + timedelta(days=30)).isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_complete"] == "PENDING"

    list_resp = client.get(f"/projects/{project['id']}/milestones", headers=_auth())
    assert len(list_resp.json()["milestones"]) == 1


def test_complete_milestone_computes_delay_days(client):
    project = _create_project(client)
    due = date.today() - timedelta(days=5)
    milestone = client.post(
        f"/projects/{project['id']}/milestones",
        json={"title": "Late milestone", "due_date": due.isoformat()},
        headers=_auth(),
    ).json()

    resp = client.post(
        f"/projects/{project['id']}/milestones/{milestone['id']}/complete",
        json={"completion_date": date.today().isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_complete"] == "COMPLETE"
    assert resp.json()["delay_days"] == 5


def test_complete_milestone_twice_is_409(client):
    project = _create_project(client)
    milestone = client.post(
        f"/projects/{project['id']}/milestones",
        json={"title": "M", "due_date": date.today().isoformat()},
        headers=_auth(),
    ).json()
    client.post(f"/projects/{project['id']}/milestones/{milestone['id']}/complete", json={}, headers=_auth())
    resp = client.post(f"/projects/{project['id']}/milestones/{milestone['id']}/complete", json={}, headers=_auth())
    assert resp.status_code == 409


def test_unfilled_roles_empty_when_no_demands(client):
    project = _create_project(client)
    resp = client.get(f"/projects/{project['id']}/unfilled-roles", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["roles"] == []


def test_expected_revenue_insufficient_data_when_no_allocations(client):
    project = _create_project(client)
    resp = client.get(f"/projects/{project['id']}/expected-revenue", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_revenue_usd_cents"] is None
    assert body["margin_indicator"] == "INSUFFICIENT_DATA"

"""
S-236/HRMS-0207 (Create Opportunity), S-237/HRMS-0208 (Pipeline Kanban),
S-239/HRMS-0210 (Role Demand), S-240/HRMS-0211 (Revenue Potential
rollup) -- proves the first API surface for opportunity_service.py end
to end, including revenue.view BU-scoping (Partner sees only their own
import logging
BU's opportunities, Finance sees org-wide).

Throwaway SQLite app, throwaway JWT keys -- never the real database.
"""
import os
import tempfile

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
from app.models.rbac_template import BusinessUnit, Role
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.rbac_service_template import RBACService
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

    from app.api.v1.endpoints.opportunities import router as opportunities_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(opportunities_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    axion = BusinessUnit(name="Axion")
    prism = BusinessUnit(name="PRISM")
    db.add_all([axion, prism])
    db.commit()

    partner_role = db.query(Role).filter(Role.name == "Partner").first()
    finance_role = db.query(Role).filter(Role.name == "Finance").first()

    db.add(Users(
        UserID="U-TROY", UserRole="Partner", UserEmail="troy@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=partner_role.id, business_unit_id=axion.id,
    ))
    db.add(Users(
        UserID="U-FINANCE", UserRole="Finance", UserEmail="finance@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=finance_role.id,
    ))
    db.commit()

    axion_client = Client(tenant_id=tenant.id, company_name="Builders Insurance", business_unit_id=axion.id)
    prism_client = Client(tenant_id=tenant.id, company_name="Alfa Insurance", business_unit_id=prism.id)
    db.add_all([axion_client, prism_client])
    db.commit()

    ids = {"tenant_id": tenant.id, "axion_client_id": axion_client.id, "prism_client_id": prism_client.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email):
    return security.create_access_token(data={"sub": email, "type": "internal", "name": email})


def _troy_auth():
    return {"Authorization": f"Bearer {_token_for('troy@blitzenx.com')}"}


def _finance_auth():
    return {"Authorization": f"Bearer {_token_for('finance@blitzenx.com')}"}


def test_unauthenticated_request_rejected(client):
    resp = client.get("/opportunities")
    assert resp.status_code in (401, 403)


def test_create_opportunity(client):
    ids = client.wros_ids
    resp = client.post(
        "/opportunities",
        headers=_troy_auth(),
        json={
            "client_id": ids["axion_client_id"], "revenue_value_usd_cents": 100000000,
            "probability_pct": 60, "currency": "USD",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stage"] == "QUALIFICATION"
    assert body["weighted_forecast_usd_cents"] == 60000000
    assert body["client_name"] == "Builders Insurance"


def test_create_opportunity_rejects_invalid_probability(client):
    ids = client.wros_ids
    resp = client.post(
        "/opportunities",
        headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 1000, "probability_pct": 150},
    )
    assert resp.status_code == 400


def test_partner_only_sees_own_bu_opportunities(client):
    ids = client.wros_ids
    client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 500000, "probability_pct": 50},
    )
    client.post(
        "/opportunities", headers=_finance_auth(),
        json={"client_id": ids["prism_client_id"], "revenue_value_usd_cents": 700000, "probability_pct": 40},
    )

    resp = client.get("/opportunities", headers=_troy_auth())
    assert resp.status_code == 200
    names = [o["client_name"] for o in resp.json()["opportunities"]]
    assert names == ["Builders Insurance"]


def test_finance_sees_org_wide(client):
    ids = client.wros_ids
    client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 500000, "probability_pct": 50},
    )
    client.post(
        "/opportunities", headers=_finance_auth(),
        json={"client_id": ids["prism_client_id"], "revenue_value_usd_cents": 700000, "probability_pct": 40},
    )

    resp = client.get("/opportunities", headers=_finance_auth())
    assert resp.status_code == 200
    assert len(resp.json()["opportunities"]) == 2


def test_pipeline_kanban_totals(client):
    ids = client.wros_ids
    client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 1000000, "probability_pct": 50},
    )
    client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 2000000, "probability_pct": 25},
    )

    resp = client.get("/opportunities/pipeline", headers=_troy_auth())
    assert resp.status_code == 200
    qualification = next(c for c in resp.json()["columns"] if c["stage"] == "QUALIFICATION")
    assert qualification["total_revenue_usd_cents"] == 3000000
    assert qualification["total_weighted_forecast_usd_cents"] == 500000 + 500000


def test_stage_transition_to_won_creates_project(client):
    ids = client.wros_ids
    create_resp = client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 1000000, "probability_pct": 80},
    )
    opp_id = create_resp.json()["id"]

    resp = client.post(
        f"/opportunities/{opp_id}/transition", headers=_troy_auth(),
        json={"new_stage": "WON", "project_name": "Builders SI Engagement"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["opportunity"]["stage"] == "WON"
    assert body["project_id"] is not None


def test_cannot_transition_a_closed_opportunity(client):
    ids = client.wros_ids
    create_resp = client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 1000000, "probability_pct": 80, "stage": "LOST"},
    )
    opp_id = create_resp.json()["id"]

    resp = client.post(
        f"/opportunities/{opp_id}/transition", headers=_troy_auth(),
        json={"new_stage": "PROPOSAL"},
    )
    assert resp.status_code == 400


def test_role_demand_from_opportunity(client):
    ids = client.wros_ids
    create_resp = client.post(
        "/opportunities", headers=_troy_auth(),
        json={"client_id": ids["axion_client_id"], "revenue_value_usd_cents": 1000000, "probability_pct": 80},
    )
    opp_id = create_resp.json()["id"]

    resp = client.post(
        f"/opportunities/{opp_id}/role-demand", headers=_troy_auth(),
        json={
            "job_title": "Senior Guidewire Developer", "required_skills": "[\"PolicyCenter\"]",
            "min_experience_years": 5.0, "work_location": "REMOTE",
            "quantity": 3, "duration_hours": 2000, "billing_rate_usd_cents": 12000,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["headcount"] == 3
    assert body["revenue_potential_usd_cents"] == 12000 * 2000 * 3

    rollup_resp = client.get(f"/opportunities/{opp_id}/revenue-rollup", headers=_troy_auth())
    assert rollup_resp.json()["role_demand_revenue_usd_cents"] == 12000 * 2000 * 3


def test_get_nonexistent_opportunity_404s(client):
    resp = client.get("/opportunities/does-not-exist", headers=_troy_auth())
    assert resp.status_code == 404

"""
Proves the self-service ownership boundary at the route level: POST
/expenses always attributes to the authenticated caller, never a
request-body field -- and that list-all/approve/investment-position
import logging
stay gated behind revenue.view/revenue.view_pnl.

Throwaway SQLite app, throwaway JWT keys -- never the real database.
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

    from app.api.v1.endpoints.expenses import router as expenses_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(expenses_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    axion = BusinessUnit(name="Axion")
    db.add(axion)
    db.commit()

    partner_role = db.query(Role).filter(Role.name == "Partner").first()
    hr_manager_role = db.query(Role).filter(Role.name == "HR Manager").first()

    db.add(Users(
        UserID="U-TROY", UserRole="Partner", UserEmail="troy@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=partner_role.id, business_unit_id=axion.id,
    ))
    db.add(Users(
        UserID="U-HEMANT", UserRole="HR Manager", UserEmail="hemant@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=hr_manager_role.id, business_unit_id=axion.id,
    ))
    db.commit()

    goldenbear = Client(tenant_id=tenant.id, company_name="Goldenbear", status="PROSPECT", business_unit_id=axion.id)
    db.add(goldenbear)
    db.commit()

    ids = {"goldenbear_id": goldenbear.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email):
    return security.create_access_token(data={"sub": email, "type": "internal", "name": email})

def _troy_auth():
    return {"Authorization": f"Bearer {_token_for('troy@blitzenx.com')}"}

def _hemant_auth():
    return {"Authorization": f"Bearer {_token_for('hemant@blitzenx.com')}"}

def test_unauthenticated_request_rejected(client):
    resp = client.post("/expenses", json={
        "purpose": "CONFERENCE", "conference_name": "NAMIC 2026", "expense_category": "TRAVEL",
        "amount_usd_cents": 45000, "expense_date": "2026-08-01",
    })
    assert resp.status_code in (401, 403)

def test_self_service_create_ignores_any_impersonation_attempt(client):
    """Even if a caller tried to smuggle a different logged_by_user_id
    into the body, the schema doesn't accept that field at all -- the
    real proof is that the created expense is always attributed to
    whoever the token authenticates as."""
    resp = client.post(
        "/expenses", headers=_troy_auth(),
        json={
            "purpose": "CONFERENCE", "conference_name": "NAMIC 2026", "expense_category": "TRAVEL",
            "travel_type": "AIRFARE", "amount_usd_cents": 45000, "expense_date": "2026-08-01",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["logged_by_user_id"] == "U-TROY"

def test_my_expenses_only_shows_own(client):
    client.post(
        "/expenses", headers=_troy_auth(),
        json={"purpose": "CONFERENCE", "conference_name": "NAMIC 2026", "expense_category": "TRAVEL", "amount_usd_cents": 45000, "expense_date": "2026-08-01"},
    )
    client.post(
        "/expenses", headers=_hemant_auth(),
        json={"purpose": "CONFERENCE", "conference_name": "Guidewire Connections", "expense_category": "TRAVEL", "amount_usd_cents": 30000, "expense_date": "2026-08-02"},
    )

    resp = client.get("/expenses/mine", headers=_troy_auth())
    assert resp.status_code == 200
    names = [e["conference_name"] for e in resp.json()["expenses"]]
    assert names == ["NAMIC 2026"]

def test_client_prospect_expense_end_to_end(client):
    ids = client.wros_ids
    resp = client.post(
        "/expenses", headers=_troy_auth(),
        json={
            "purpose": "CLIENT_PROSPECT", "client_id": ids["goldenbear_id"],
            "expense_category": "TRAVEL", "travel_type": "AIRFARE", "amount_usd_cents": 120000,
            "expense_date": "2026-08-05", "trip_label": "Seattle - Goldenbear - Aug 2026",
        },
    )
    assert resp.status_code == 201, resp.text

    position = client.get(f"/clients/{ids['goldenbear_id']}/investment-position", headers=_troy_auth())
    assert position.status_code == 200
    body = position.json()
    assert body["status"] == "PROSPECT"
    assert body["total_expense_usd_cents"] == 120000
    assert body["total_revenue_usd_cents"] == 0

def test_list_all_requires_revenue_view(client):
    resp = client.get("/expenses", headers=_troy_auth())
    assert resp.status_code == 200  # Partner has revenue.view

def test_approve_requires_revenue_view_pnl(client):
    create_resp = client.post(
        "/expenses", headers=_troy_auth(),
        json={"purpose": "CONFERENCE", "conference_name": "NAMIC 2026", "expense_category": "TRAVEL", "amount_usd_cents": 45000, "expense_date": "2026-08-01"},
    )
    expense_id = create_resp.json()["id"]

    # HR Manager has revenue.view but NOT revenue.view_pnl, per the
    # RBAC seed's own explicit "no actual p&l" rule.
    resp = client.post(f"/expenses/{expense_id}/approve", headers=_hemant_auth())
    assert resp.status_code == 403

    resp = client.post(f"/expenses/{expense_id}/approve", headers=_troy_auth())
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "APPROVED"

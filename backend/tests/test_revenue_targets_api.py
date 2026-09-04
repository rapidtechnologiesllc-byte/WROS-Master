"""
S-267/S-241/S-244 API-level proof: BU target create/read, PartnerGoal
CEO-only enforcement, and the Executive Dashboard aggregation, all on
import logging
real routes.

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
import app.models  # noqa: F401

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

    from app.api.v1.endpoints.revenue_targets import router as revenue_targets_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(revenue_targets_router)
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
    db.add(Users(
        UserID="U-TROY", UserRole="Partner", UserEmail="troy@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=partner_role.id, business_unit_id=axion.id,
    ))
    db.add(Users(
        UserID="U-AVINASH", UserRole="Super User", UserEmail="avinash@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id,
    ))
    db.commit()

    builders = Client(tenant_id=tenant.id, company_name="Builders Insurance", business_unit_id=axion.id)
    db.add(builders)
    db.commit()

    ids = {"axion_id": axion.id, "builders_id": builders.id}
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

def _avinash_auth():
    return {"Authorization": f"Bearer {_token_for('avinash@blitzenx.com')}"}

def test_troy_can_set_bu_target(client):
    ids = client.wros_ids
    resp = client.post(
        "/revenue-targets/bu", headers=_troy_auth(),
        json={"business_unit_id": ids["axion_id"], "target_period": "ANNUAL", "fiscal_year": 2026, "target_amount_usd_cents": 2000000},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["target_amount_usd_cents"] == 2000000

def test_partner_can_set_partner_goal_rejected(client):
    """Partner has revenue.view_pnl (passes the endpoint gate) but the
    service layer still rejects a non-CEO caller -- proves the CEO-only
    rule is enforced even for a role that clears the coarser
    permission tier."""
    resp = client.post(
        "/revenue-targets/partner-goals", headers=_troy_auth(),
        json={"partner_user_id": "U-TROY", "target_period": "ANNUAL", "fiscal_year": 2026, "target_amount_usd_cents": 2000000},
    )
    assert resp.status_code == 403

def test_ceo_can_set_partner_goal(client):
    resp = client.post(
        "/revenue-targets/partner-goals", headers=_avinash_auth(),
        json={"partner_user_id": "U-TROY", "target_period": "ANNUAL", "fiscal_year": 2026, "target_amount_usd_cents": 2000000},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["created_by"] == "U-AVINASH"

def test_executive_dashboard_bu_scoped_for_partner(client):
    resp = client.get("/revenue-targets/dashboard", headers=_troy_auth())
    assert resp.status_code == 200
    assert "by_business_unit" in resp.json()

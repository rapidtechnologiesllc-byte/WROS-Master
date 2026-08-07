"""
GET/PATCH /admin/ai-config (app.api.v1.endpoints.tenant_ai_config) --
the real, frontend-wired Tenant AI Configuration endpoint.

2026-08-06: written to give this endpoint real test coverage. It had
none before -- the only tests that ever exercised this URL path were
against a since-deleted duplicate endpoint
(app.api.v1.endpoints.ai_recruiter_assignment's old /admin/tenant/ai-
config, confirmed dead code with zero frontend usage) that happened to
share the same tenant.ai_config permission gate but a genuinely
different request/response contract (no ba_approved BR-01 gate, no
unified Users+TenantAIConfig merge). Proves: Super-User-only gating,
the real unified read (Users-backed fields + TenantAIConfig row merged
into one view), and BR-01 (persona changes rejected without
ba_approved=true).

Throwaway SQLite app, throwaway JWT keys, real RBAC seed -- never the
real database.
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
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.rbac import Role
from app.models.user import Users
import app.models  # noqa: F401


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo,
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

    from app.api.v1.endpoints.tenant_ai_config import router as tenant_ai_config_router
    from app.core.database import get_db
    from app.services.rbac_service import RBACService

    app = FastAPI()
    app.include_router(tenant_ai_config_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    super_user_role = db.query(Role).filter_by(name="Super User").first()
    recruiter_role = db.query(Role).filter_by(name="Recruiter").first()

    super_user = Users(
        UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com",
        UserPassword=get_password_hash("x"), role_id=super_user_role.id if super_user_role else None,
        ai_agent_name="Thunder", ai_agent_persona="I am Thunder, BlitzenX's recruiting assistant.",
    )
    recruiter = Users(
        UserID="U-REC", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com",
        UserPassword=get_password_hash("x"), role_id=recruiter_role.id if recruiter_role else None,
    )
    db.add_all([super_user, recruiter])
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _token_for(email, role):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})


def test_get_config_allowed_for_super_user(client):
    resp = client.get(
        "/admin/ai-config",
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_agent_name"] == "Thunder"
    assert body["thunder_enabled"] is True
    # Real unified merge -- TenantAIConfig row fields present alongside
    # the Users-backed ones, auto-created with real defaults on first read.
    assert "greeting_channel" in body
    assert "max_followup_count" in body


def test_get_config_forbidden_for_recruiter(client):
    resp = client.get(
        "/admin/ai-config",
        headers={"Authorization": f"Bearer {_token_for('recruiter@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 403


def test_patch_non_persona_field_succeeds_without_ba_approved(client):
    resp = client.patch(
        "/admin/ai-config",
        json={"max_followup_count": 5},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["max_followup_count"] == 5


def test_patch_persona_without_ba_approved_is_rejected(client):
    """BR-01 -- the real business rule this endpoint enforces that the
    deleted duplicate never did."""
    resp = client.patch(
        "/admin/ai-config",
        json={"ai_agent_persona": "I am Nova now."},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 422


def test_patch_persona_with_ba_approved_succeeds(client):
    resp = client.patch(
        "/admin/ai-config",
        json={"ai_agent_name": "Nova", "ai_agent_persona": "I am Nova, a custom bot.", "ba_approved": True},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ai_agent_name"] == "Nova"


def test_patch_forbidden_for_recruiter(client):
    resp = client.patch(
        "/admin/ai-config",
        json={"max_followup_count": 3},
        headers={"Authorization": f"Bearer {_token_for('recruiter@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 403


def test_patch_invalid_greeting_channel_returns_422(client):
    resp = client.patch(
        "/admin/ai-config",
        json={"greeting_channel": "carrier_pigeon"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 422

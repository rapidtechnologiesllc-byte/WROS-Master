"""
POST/GET /templates -- proves the HTTP-level auth gating: activation is
template.manage-only (Super User by default), create/list/preview are
any internal user. Business rules covered at the service layer.

Throwaway SQLite app, throwaway JWT keys, real RBAC seed.
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
from app.models.user import Users
import app.models  # noqa: F401


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
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

    from app.api.v1.endpoints.message_templates import router as templates_router
    from app.core.database import get_db
    from app.services.rbac_service import RBACService
    from app.models.rbac import Role

    app = FastAPI()
    app.include_router(templates_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)
    super_role = db.query(Role).filter_by(name="Super User").first()
    rec_role = db.query(Role).filter_by(name="Recruiter").first()

    db.add_all([
        Users(UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"), role_id=super_role.id if super_role else None),
        Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword=get_password_hash("x"), role_id=rec_role.id if rec_role else None),
    ])
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


def test_recruiter_can_create_template(client):
    resp = client.post(
        "/templates",
        json={"template_key": "GREETING_WHATSAPP", "template_name": "V1", "channel": "WHATSAPP", "body": "Hi {{candidate_name}}"},
        headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is False


def test_recruiter_cannot_activate(client):
    create_resp = client.post(
        "/templates",
        json={"template_key": "GREETING_WHATSAPP", "template_name": "V1", "channel": "WHATSAPP", "body": "Hi {{candidate_name}}"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    template_id = create_resp.json()["id"]

    resp = client.post(
        f"/templates/{template_id}/activate",
        headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 403


def test_super_user_can_activate(client):
    create_resp = client.post(
        "/templates",
        json={"template_key": "GREETING_WHATSAPP", "template_name": "V1", "channel": "WHATSAPP", "body": "Hi {{candidate_name}}"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    template_id = create_resp.json()["id"]

    resp = client.post(
        f"/templates/{template_id}/activate",
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_list_templates_returns_created(client):
    client.post(
        "/templates",
        json={"template_key": "GREETING_WHATSAPP", "template_name": "V1", "channel": "WHATSAPP", "body": "Hi {{candidate_name}}"},
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    resp = client.get("/templates", headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"})
    assert resp.status_code == 200
    assert len(resp.json()["templates"]) == 1

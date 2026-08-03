"""
GET /candidates/{id}/jobs/{job_id}/offer-readiness -- TC-005/AC-7:
proves the real HTTP-level RBAC gate. offer.readiness_check is a new,
narrower permission than offer.manage/offer.view (see rbac_service.py's
own note) added specifically so Recruiter gets a real 403 here, without
touching the two broader offer permissions other already-shipped routes
depend on (which currently, inconsistently, still include Recruiter).

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
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata


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

    from app.api.v1.endpoints.offer_readiness import router as offer_readiness_router
    from app.core.database import get_db
    from app.services.rbac_service import RBACService
    from app.models.rbac import Role

    app = FastAPI()
    app.include_router(offer_readiness_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)
    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    super_role = db.query(Role).filter_by(name="Super User").first()
    hr_role = db.query(Role).filter_by(name="HR Manager").first()
    rec_role = db.query(Role).filter_by(name="Recruiter").first()

    db.add_all([
        Users(UserID="U-CEO", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=super_role.id if super_role else None),
        Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=hr_role.id if hr_role else None),
        Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=rec_role.id if rec_role else None),
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


def test_recruiter_gets_403(client):
    resp = client.get(
        "/candidates/C-1/jobs/JOB-1/offer-readiness",
        headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 403


def test_hr_manager_gets_200(client):
    resp = client.get(
        "/candidates/C-1/jobs/JOB-1/offer-readiness",
        headers={"Authorization": f"Bearer {_token_for('hr@blitzenx.com', 'HR Manager')}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "is_ready" in body and "blockers" in body and "warnings" in body and "checked_at" in body


def test_super_user_gets_200(client):
    resp = client.get(
        "/candidates/C-1/jobs/JOB-1/offer-readiness",
        headers={"Authorization": f"Bearer {_token_for('ceo@blitzenx.com', 'Super User')}"},
    )
    assert resp.status_code == 200


def test_no_auth_gets_401_or_403(client):
    resp = client.get("/candidates/C-1/jobs/JOB-1/offer-readiness")
    assert resp.status_code in (401, 403)

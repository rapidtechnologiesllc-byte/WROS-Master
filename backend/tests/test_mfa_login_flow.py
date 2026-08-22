"""
End-to-end MFA flow test: login -> mfa_pending token -> setup -> confirm
-> full token, and login -> mfa_pending token -> verify -> full token
for an already-enrolled account. Also proves the negative case that
matters most: an mfa_pending token is rejected everywhere except the
two MFA endpoints, and a normal full token is rejected BY the MFA
endpoints.

Builds a small standalone FastAPI app (auth + mfa routers only) against
JWT keys (a fresh throwaway RSA key pair is generated and monkeypatched
in, same pattern as test_session_token_expiry.py).
"""
import os

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
import app.core.database as database_module
from app.core.mfa import generate_totp_secret
import pyotp

from app.models.base import Base
from app.models.user import Users
from app.models.tenant import Tenant

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
def client(throwaway_jwt_keys, monkeypatch):
    engine = create_engine(f"sqlite:///{db_path}")

    # Point get_db (used by every route via Depends) at the throwaway
    # SQLite session instead of the real configured database.
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setenv("MFA_ENFORCEMENT_ENABLED", "true")

    from app.api.v1.endpoints.auth import router as auth_router
    from app.api.v1.endpoints.mfa import router as mfa_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mfa_router)
    app.dependency_overrides[get_db] = override_get_db

    # Seed a Super User (MFA-required role) and a Recruiter (not required)
    db = TestSessionLocal()
    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-PRIYA", UserRole="Super User", UserEmail="priya@blitzenx.com",
        UserPassword=get_password_hash("correct-horse"),
    ))
    db.add(Users(
        UserID="U-RAVI", UserRole="Recruiter", UserEmail="ravi@blitzenx.com",
        UserPassword=get_password_hash("correct-horse"),
    ))
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def test_non_mfa_role_logs_in_unaffected(client):
    """Recruiter isn't in MFA_REQUIRED_ROLES -- login must behave exactly
    as before, full token immediately, no MFA fields set."""
    resp = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is False
    assert body["mfa_setup_required"] is False
    assert body["access_token"]

def test_mfa_required_role_gets_pending_token_not_full_access(client):
    resp = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_setup_required"] is True  # never enrolled yet
    assert body["mfa_required"] is False
    assert body["access_token"]  # this is a pending token, not a full one

def test_pending_token_cannot_reach_a_normal_protected_endpoint(client):
    login = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]

    from app.api.v1.endpoints.mfa import router as mfa_router  # noqa
    from fastapi import Depends
    from app.core.dependencies import get_current_hr_or_admin

    # Build a tiny protected route on the same app to prove the point
    # generically, without depending on any specific business route.
    @client.app.get("/some-protected-thing")
    def protected(user=Depends(get_current_hr_or_admin)):
        return {"ok": True}

    resp = client.get("/some-protected-thing", headers={"Authorization": f"Bearer {pending_token}"})
    assert resp.status_code == 403

def test_full_enrollment_flow_setup_then_confirm_then_full_token(client):
    login = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    setup_resp = client.post("/auth/mfa/setup", headers=headers)
    assert setup_resp.status_code == 200
    setup_body = setup_resp.json()
    assert setup_body["secret"]
    assert len(setup_body["backup_codes"]) == 10

    code = pyotp.TOTP(setup_body["secret"]).now()
    confirm_resp = client.post("/auth/mfa/setup/confirm", json={"code": code}, headers=headers)
    assert confirm_resp.status_code == 200
    full_token_body = confirm_resp.json()
    assert full_token_body["access_token"]

    # The confirmed full token now works on a normal protected route.
    from fastapi import Depends
    from app.core.dependencies import get_current_hr_or_admin

    @client.app.get("/some-other-protected-thing")
    def protected(user=Depends(get_current_hr_or_admin)):
        return {"ok": True, "email": user.UserEmail}

    real_resp = client.get(
        "/some-other-protected-thing",
        headers={"Authorization": f"Bearer {full_token_body['access_token']}"},
    )
    assert real_resp.status_code == 200
    assert real_resp.json()["email"] == "priya@blitzenx.com"

def test_wrong_code_at_confirm_is_rejected(client):
    login = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    client.post("/auth/mfa/setup", headers=headers)
    resp = client.post("/auth/mfa/setup/confirm", json={"code": "000000"}, headers=headers)
    assert resp.status_code == 401

def test_already_enrolled_account_uses_verify_not_setup(client):
    # First, fully enroll.
    login = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}
    setup_body = client.post("/auth/mfa/setup", headers=headers).json()
    code = pyotp.TOTP(setup_body["secret"]).now()
    client.post("/auth/mfa/setup/confirm", json={"code": code}, headers=headers)

    # Second login: should now say mfa_required (already enrolled), not mfa_setup_required.
    login2 = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    body2 = login2.json()
    assert body2["mfa_required"] is True
    assert body2["mfa_setup_required"] is False

    pending_token2 = body2["access_token"]
    code2 = pyotp.TOTP(setup_body["secret"]).now()
    verify_resp = client.post(
        "/auth/mfa/verify", json={"code": code2},
        headers={"Authorization": f"Bearer {pending_token2}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["access_token"]

def test_backup_code_works_once_then_is_rejected(client):
    login = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}
    setup_body = client.post("/auth/mfa/setup", headers=headers).json()
    code = pyotp.TOTP(setup_body["secret"]).now()
    client.post("/auth/mfa/setup/confirm", json={"code": code}, headers=headers)

    login2 = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token2 = login2.json()["access_token"]
    backup_code = setup_body["backup_codes"][0]

    resp = client.post(
        "/auth/mfa/verify", json={"backup_code": backup_code},
        headers={"Authorization": f"Bearer {pending_token2}"},
    )
    assert resp.status_code == 200

    # Reusing the same backup code must fail.
    login3 = client.post("/auth/login", json={"email": "priya@blitzenx.com", "password": "correct-horse"})
    pending_token3 = login3.json()["access_token"]
    resp2 = client.post(
        "/auth/mfa/verify", json={"backup_code": backup_code},
        headers={"Authorization": f"Bearer {pending_token3}"},
    )
    assert resp2.status_code == 401

def test_a_full_normal_token_is_rejected_by_mfa_endpoints(client):
    """A real, already-authenticated user must not be able to call the
    MFA endpoints without having gone through login's pending-token gate."""
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    full_token = login.json()["access_token"]

    resp = client.post("/auth/mfa/setup", headers={"Authorization": f"Bearer {full_token}"})
    assert resp.status_code == 403

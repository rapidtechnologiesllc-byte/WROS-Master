"""
Email OTP backlog item, 2026-08-05 (wros_email_2fa_backlog): "Missing
two step validation via email for employees and internal users."
Supplements the existing TOTP flow (see test_mfa_login_flow.py) rather
than replacing it -- a SEPARATE, independently-off-by-default gate
(EMAIL_OTP_ENFORCEMENT_ENABLED), covering a broader role set
(EMAIL_OTP_REQUIRED_ROLES) than MFA_REQUIRED_ROLES.

Builds a small standalone FastAPI app (auth + mfa routers only) against
a throwaway SQLite database -- never the real one, never real .env JWT
keys or real SMTP, same pattern as test_mfa_login_flow.py.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users


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
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Users.__table__])
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setenv("EMAIL_OTP_ENFORCEMENT_ENABLED", "true")
    # MFA_ENFORCEMENT_ENABLED deliberately left unset/false -- proves
    # email OTP works as its own independent gate, not riding on TOTP's.
    monkeypatch.setattr("app.services.email_service.EmailService.send_email", lambda *a, **k: None)

    import app.api.v1.endpoints.auth as auth_module
    import app.api.v1.endpoints.mfa as mfa_module
    from app.core.database import get_db

    # Deterministic code for test assertions -- the real code is only
    # ever knowable via the email that was sent, which we've mocked away.
    monkeypatch.setattr(auth_module, "generate_email_otp_code", lambda: "123456")
    monkeypatch.setattr(mfa_module, "generate_email_otp_code", lambda: "654321")

    app = FastAPI()
    app.include_router(auth_module.router)
    app.include_router(mfa_module.router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash
    db.add(Users(
        UserID="U-RAVI", UserRole="Recruiter", UserEmail="ravi@blitzenx.com",
        UserPassword=get_password_hash("correct-horse"),
    ))
    db.add(Users(
        UserID="U-CANDIDATE-LIKE", UserRole="Candidate", UserEmail="not-really-a-user@blitzenx.com",
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


def test_recruiter_login_triggers_email_otp_not_totp(client):
    """Recruiter is in EMAIL_OTP_REQUIRED_ROLES but NOT in
    MFA_REQUIRED_ROLES -- proves this is a real, separate gate."""
    resp = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_otp_required"] is True
    assert body["mfa_required"] is False
    assert body["mfa_setup_required"] is False
    assert body["access_token"]  # pending token


def test_candidate_like_role_is_unaffected(client):
    """Candidate is deliberately excluded from EMAIL_OTP_REQUIRED_ROLES
    -- the candidate side of this ask (opt-in popup) is separate,
    not-yet-built scope."""
    resp = client.post("/auth/login", json={"email": "not-really-a-user@blitzenx.com", "password": "correct-horse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_otp_required"] is False


def test_correct_code_completes_login(client):
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    resp = client.post("/auth/mfa/email/verify", json={"code": "123456"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    # The full token now works on a normal protected route.
    from fastapi import Depends
    from app.core.dependencies import get_current_hr_or_admin

    @client.app.get("/some-protected-thing")
    def protected(user=Depends(get_current_hr_or_admin)):
        return {"ok": True, "email": user.UserEmail}

    real_resp = client.get(
        "/some-protected-thing",
        headers={"Authorization": f"Bearer {resp.json()['access_token']}"},
    )
    assert real_resp.status_code == 200
    assert real_resp.json()["email"] == "ravi@blitzenx.com"


def test_wrong_code_is_rejected(client):
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]

    resp = client.post(
        "/auth/mfa/email/verify", json={"code": "000000"},
        headers={"Authorization": f"Bearer {pending_token}"},
    )
    assert resp.status_code == 401


def test_code_is_single_use(client):
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    first = client.post("/auth/mfa/email/verify", json={"code": "123456"}, headers=headers)
    assert first.status_code == 200

    second = client.post("/auth/mfa/email/verify", json={"code": "123456"}, headers=headers)
    assert second.status_code == 400  # code already cleared -- "no code issued"


def test_expired_code_is_rejected(client):
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    # Force expiry directly against the DB the app is using.
    from app.core.database import get_db
    override = client.app.dependency_overrides[get_db]
    db = next(override())
    user = db.query(Users).filter(Users.UserEmail == "ravi@blitzenx.com").first()
    user.email_otp_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.add(user)
    db.commit()
    db.close()

    resp = client.post("/auth/mfa/email/verify", json={"code": "123456"}, headers=headers)
    assert resp.status_code == 401


def test_resend_issues_a_new_code_that_works(client):
    login = client.post("/auth/login", json={"email": "ravi@blitzenx.com", "password": "correct-horse"})
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    resend_resp = client.post("/auth/mfa/email/resend", headers=headers)
    assert resend_resp.status_code == 200
    assert resend_resp.json()["sent"] is True

    # The original login-time code ("123456") must no longer work --
    # resend overwrote it with mfa module's mocked code ("654321").
    stale = client.post("/auth/mfa/email/verify", json={"code": "123456"}, headers=headers)
    assert stale.status_code == 401

    fresh = client.post("/auth/mfa/email/verify", json={"code": "654321"}, headers=headers)
    assert fresh.status_code == 200


def test_pending_token_cannot_reach_email_otp_endpoints_of_another_flow_without_auth(client):
    """A normal full token (non-pending) must be rejected by the email
    OTP endpoints, same posture as the existing TOTP endpoints."""
    login = client.post("/auth/login", json={"email": "not-really-a-user@blitzenx.com", "password": "correct-horse"})
    full_token = login.json()["access_token"]  # Candidate role -> not gated -> full token

    resp = client.post(
        "/auth/mfa/email/verify", json={"code": "123456"},
        headers={"Authorization": f"Bearer {full_token}"},
    )
    assert resp.status_code == 403

"""
Email OTP backlog item, 2026-08-05 (wros_email_2fa_backlog), candidate
half: "for external we need to give a pop up to check if they want to
register for 2 step." Opt-in, not enforced -- a candidate who has never
been asked gets a normal login plus show_2fa_opt_in_popup=true; once
they opt in, every future login challenges them for an emailed code.

Builds a small standalone FastAPI app (auth + mfa routers only) against
keys or real SMTP, same pattern as test_email_otp_login_flow.py.
"""
import os
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
from app.models.candidate import Candidate
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
    engine = create_engine(f"sqlite:///{db_path}")

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.services.email_service.EmailService.send_email", lambda *a, **k: None)

    import app.api.v1.endpoints.auth as auth_module
    import app.api.v1.endpoints.mfa as mfa_module
    from app.core.database import get_db

    monkeypatch.setattr(auth_module, "generate_email_otp_code", lambda: "111222")
    monkeypatch.setattr(mfa_module, "generate_email_otp_code", lambda: "333444")

    app = FastAPI()
    app.include_router(auth_module.router)
    app.include_router(mfa_module.router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    def _add_candidate(candidate_id, email, opted_in=None):
        db.add(Candidate(
            candidateID=candidate_id, candidateEmail=email, candidatePassword=get_password_hash("correct-horse"),
            candidateFirstName="Priya", candidateLastName="Rao", email_2fa_opted_in=opted_in,
        ))

    _add_candidate("C-NEVER-ASKED", "never-asked@example.com", opted_in=None)
    _add_candidate("C-OPTED-IN", "opted-in@example.com", opted_in=True)
    _add_candidate("C-DECLINED", "declined@example.com", opted_in=False)
    db.commit()
    db.close()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _login(client, email):
    return client.post("/auth/login", json={"email": email, "password": "correct-horse"})

# ---- login-time behavior ----

def test_never_asked_candidate_logs_in_normally_and_gets_the_popup_flag(client):
    resp = _login(client, "never-asked@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_otp_required"] is False
    assert body["show_2fa_opt_in_popup"] is True
    assert body["access_token"]  # a real, full candidate token -- login is not blocked

def test_declined_candidate_logs_in_normally_with_no_popup(client):
    resp = _login(client, "declined@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_otp_required"] is False
    assert body["show_2fa_opt_in_popup"] is False

def test_opted_in_candidate_gets_a_pending_token_not_a_full_one(client):
    resp = _login(client, "opted-in@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_otp_required"] is True
    assert body["show_2fa_opt_in_popup"] is False
    assert body["access_token"]  # pending token

# ---- opt-in endpoint ----

def test_never_asked_candidate_can_opt_in(client):
    login = _login(client, "never-asked@example.com")
    token = login.json()["access_token"]

    resp = client.post("/auth/mfa/candidate/opt-in", json={"opted_in": True}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"email_2fa_opted_in": True}

    # Next login now challenges for a code.
    second_login = _login(client, "never-asked@example.com")
    assert second_login.json()["candidate_otp_required"] is True

def test_opt_in_endpoint_requires_a_full_candidate_token_not_a_pending_one(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]

    resp = client.post("/auth/mfa/candidate/opt-in", json={"opted_in": False}, headers={"Authorization": f"Bearer {pending_token}"})
    assert resp.status_code == 403

# ---- email verify / resend ----

def test_correct_code_completes_login(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]

    resp = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers={"Authorization": f"Bearer {pending_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["candidate_id"] == "C-OPTED-IN"

    # The full token now works on a normal candidate-only route.
    from fastapi import Depends
    from app.core.dependencies import get_current_candidate

    @client.app.get("/some-candidate-route")
    def protected(candidate=Depends(get_current_candidate)):
        return {"ok": True, "id": candidate.candidateID}

    real_resp = client.get("/some-candidate-route", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert real_resp.status_code == 200
    assert real_resp.json()["id"] == "C-OPTED-IN"

def test_wrong_code_is_rejected(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]

    resp = client.post("/auth/mfa/candidate/email/verify", json={"code": "000000"}, headers={"Authorization": f"Bearer {pending_token}"})
    assert resp.status_code == 401

def test_pending_token_cannot_reach_a_normal_candidate_route(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]

    from fastapi import Depends
    from app.core.dependencies import get_current_candidate

    @client.app.get("/some-other-candidate-route")
    def protected(candidate=Depends(get_current_candidate)):
        return {"ok": True}

    resp = client.get("/some-other-candidate-route", headers={"Authorization": f"Bearer {pending_token}"})
    assert resp.status_code == 403

def test_a_full_candidate_token_cannot_be_used_as_a_pending_token(client):
    """The inverse of the check above -- a normal, already-verified
    candidate session must not be accepted by the OTP-pending-only
    endpoints either."""
    login = _login(client, "declined@example.com")
    full_token = login.json()["access_token"]

    resp = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers={"Authorization": f"Bearer {full_token}"})
    assert resp.status_code == 403

def test_resend_issues_a_new_code_that_works(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    resend_resp = client.post("/auth/mfa/candidate/email/resend", headers=headers)
    assert resend_resp.status_code == 200
    assert resend_resp.json()["sent"] is True

    stale = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers=headers)
    assert stale.status_code == 401

    fresh = client.post("/auth/mfa/candidate/email/verify", json={"code": "333444"}, headers=headers)
    assert fresh.status_code == 200

def test_code_is_single_use(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    first = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers=headers)
    assert first.status_code == 200

    second = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers=headers)
    assert second.status_code == 400

def test_expired_code_is_rejected(client):
    login = _login(client, "opted-in@example.com")
    pending_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {pending_token}"}

    from app.core.database import get_db
    override = client.app.dependency_overrides[get_db]
    db = next(override())
    candidate = db.query(Candidate).filter(Candidate.candidateID == "C-OPTED-IN").first()
    candidate.email_otp_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.add(candidate)
    db.commit()
    db.close()

    resp = client.post("/auth/mfa/candidate/email/verify", json={"code": "111222"}, headers=headers)
    assert resp.status_code == 401

def test_internal_user_mfa_pending_token_cannot_be_used_on_candidate_endpoints(client):
    """Cross-token-type isolation: an internal-user mfa_pending token
    must not satisfy the candidate_otp_pending-only dependency."""
    internal_pending_token = security.create_access_token(
        data={"sub": "someone@blitzenx.com", "type": "Recruiter", "mfa_pending": True}
    )
    resp = client.post(
        "/auth/mfa/candidate/email/verify", json={"code": "111222"},
        headers={"Authorization": f"Bearer {internal_pending_token}"},
    )
    assert resp.status_code == 403

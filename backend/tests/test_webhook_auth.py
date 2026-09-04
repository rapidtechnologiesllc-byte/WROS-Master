"""
Proves app.core.webhook_auth: fail-closed when unconfigured, rejects a
missing/wrong secret, accepts a correct one, and (for the combined
check) accepts a valid internal-user bearer token as an alternative to
the secret -- since POST /ai-agent/webhook/email-reply must work for
both external callers (secret) and manual HR-portal use (their own
login), and a plain require_permission() would have broken the
import logging
external-caller path entirely.

The combined check takes `db` via Depends(get_db) (not its own
SessionLocal()), so these tests can pass a throwaway SQLite session
directly as a keyword argument -- never touching the real database.
"""
import asyncio
import os
import tempfile

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.webhook_auth import require_webhook_secret, require_webhook_secret_or_internal_user
from app.models.base import Base
from app.models.user import Users
import app.core.security as security

@pytest.fixture()
def configured_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "test-secret-abc123")
    yield "test-secret-abc123"

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Users.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

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

def _fake_request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)

def _run(coro):
    return asyncio.run(coro)

# ---------------------------------------------------------------------------
# require_webhook_secret (secret-only, for pure-webhook endpoints)
# ---------------------------------------------------------------------------

def test_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SHARED_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_webhook_secret(x_webhook_secret="anything")
    assert exc_info.value.status_code == 503

def test_rejects_missing_secret(configured_secret):
    with pytest.raises(HTTPException) as exc_info:
        require_webhook_secret(x_webhook_secret="")
    assert exc_info.value.status_code == 401

def test_rejects_wrong_secret(configured_secret):
    with pytest.raises(HTTPException) as exc_info:
        require_webhook_secret(x_webhook_secret="wrong-value")
    assert exc_info.value.status_code == 401

def test_accepts_correct_secret(configured_secret):
    require_webhook_secret(x_webhook_secret=configured_secret)  # must not raise

# ---------------------------------------------------------------------------
# require_webhook_secret_or_internal_user (dual-mode, for this endpoint)
# ---------------------------------------------------------------------------

def test_combined_accepts_correct_secret_without_any_token(configured_secret, db_session):
    request = _fake_request({})
    _run(require_webhook_secret_or_internal_user(request, x_webhook_secret=configured_secret, db=db_session))  # must not raise

def test_combined_rejects_no_secret_and_no_token(configured_secret, db_session):
    request = _fake_request({})
    with pytest.raises(HTTPException) as exc_info:
        _run(require_webhook_secret_or_internal_user(request, x_webhook_secret="", db=db_session))
    assert exc_info.value.status_code == 401

def test_combined_rejects_wrong_secret_and_no_token(configured_secret, db_session):
    request = _fake_request({})
    with pytest.raises(HTTPException) as exc_info:
        _run(require_webhook_secret_or_internal_user(request, x_webhook_secret="nope", db=db_session))
    assert exc_info.value.status_code == 401

def test_combined_accepts_a_valid_internal_user_token_with_no_secret(configured_secret, throwaway_jwt_keys, db_session):
    priya = Users(
        UserID="U-PRIYA", UserRole="Recruiter", UserEmail="priya@blitzenx.com", UserPassword="hashed",
    )
    db_session.add(priya)
    db_session.commit()

    token = security.create_access_token({"sub": "priya@blitzenx.com", "type": "user"})
    request = _fake_request({"Authorization": f"Bearer {token}"})

    _run(require_webhook_secret_or_internal_user(request, x_webhook_secret="", db=db_session))  # must not raise

def test_combined_rejects_a_token_for_a_user_that_does_not_exist(configured_secret, throwaway_jwt_keys, db_session):
    token = security.create_access_token({"sub": "ghost@blitzenx.com", "type": "user"})
    request = _fake_request({"Authorization": f"Bearer {token}"})

    with pytest.raises(HTTPException) as exc_info:
        _run(require_webhook_secret_or_internal_user(request, x_webhook_secret="", db=db_session))
    assert exc_info.value.status_code == 401

def test_combined_rejects_a_candidate_token(configured_secret, throwaway_jwt_keys, db_session):
    token = security.create_access_token({"sub": "C-AISHA", "type": "candidate"})
    request = _fake_request({"Authorization": f"Bearer {token}"})

    with pytest.raises(HTTPException) as exc_info:
        _run(require_webhook_secret_or_internal_user(request, x_webhook_secret="", db=db_session))
    assert exc_info.value.status_code == 403

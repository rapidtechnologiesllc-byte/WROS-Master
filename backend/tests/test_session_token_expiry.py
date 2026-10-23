"""
Phase 1 B3 acceptance test (session-expiry half): a token past its expiry window, or signed
with any other secret, is rejected.

Verifies the REAL app.core.security.create_access_token / decode_access_token -- not a
reimplementation. Tokens are HS256 signed with JWT_SECRET; the test swaps in a throwaway
secret so it never touches the real one.
"""
from datetime import timedelta

import pytest
from fastapi import HTTPException

import app.core.security as security

CLAIMS = {"sub": "USR_TEST", "type": "user", "tenant_id": 1, "role_template_id": 1}


@pytest.fixture()
def throwaway_secret(monkeypatch):
    monkeypatch.setattr(security, "SECRET_KEY", "throwaway-test-secret-" + "a" * 40)


def test_positive_case_fresh_token_decodes(throwaway_secret):
    payload = security.decode_access_token(security.create_access_token(dict(CLAIMS)))
    assert payload["sub"] == "USR_TEST"
    assert payload["tenant_id"] == 1


def test_negative_case_expired_token_is_rejected(throwaway_secret):
    token = security.create_access_token(dict(CLAIMS), expires_delta=timedelta(minutes=-1))
    with pytest.raises(HTTPException) as exc_info:
        security.decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_negative_case_token_signed_by_a_different_key_is_rejected(monkeypatch):
    """A token signed with any other secret (an attacker's, or a rotated-out one) must not
    verify -- the property that makes rotating a leaked secret meaningful."""
    monkeypatch.setattr(security, "SECRET_KEY", "attacker-secret-" + "b" * 40)
    forged_token = security.create_access_token(dict(CLAIMS))

    monkeypatch.setattr(security, "SECRET_KEY", "real-secret-" + "c" * 40)
    with pytest.raises(HTTPException) as exc_info:
        security.decode_access_token(forged_token)
    assert exc_info.value.status_code == 401

"""
Phase 1 B3 acceptance test (session-expiry half): "attempt to use a
import logging
token past its expiry window; must be rejected."

Verifies the REAL app.core.security.create_access_token /
decode_access_token functions -- not a reimplementation -- actually
enforce the JWT `exp` claim. Uses a throwaway RSA key pair generated
inside the test and monkeypatched in, so this never touches the real
signing keys from .env.

(MFA-for-Admin/Director, the other half of B3's acceptance test, is not
implemented yet -- see the developer handoff for why that's scoped as
a separate, larger piece of work rather than rushed here.)
"""
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

import app.core.security as security

@pytest.fixture()
def throwaway_keys(monkeypatch):
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

def test_positive_case_fresh_token_decodes(throwaway_keys):
    token = security.create_access_token({"sub": "aisha@blitzenx.com", "type": "user"})
    payload = security.decode_access_token(token)
    assert payload["sub"] == "aisha@blitzenx.com"

def test_negative_case_expired_token_is_rejected(throwaway_keys):
    token = security.create_access_token(
        {"sub": "aisha@blitzenx.com", "type": "user"},
        expires_delta=timedelta(minutes=-1),  # already expired the moment it's issued
    )
    with pytest.raises(HTTPException) as exc_info:
        security.decode_access_token(token)
    assert exc_info.value.status_code == 401

def test_negative_case_token_signed_by_a_different_key_is_rejected(monkeypatch):
    """
    Defense-in-depth check adjacent to B3: a token signed by a key other
    than the current PUBLIC_KEY (e.g. an old, rotated-out private key)
    must not verify -- this is exactly the property that made rotating
    the leaked JWT keys meaningful.
    """
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_private_pem = attacker_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    real_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    real_public_pem = real_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    monkeypatch.setattr(security, "PRIVATE_KEY", attacker_private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", real_public_pem)  # server actually trusts a different key

    forged_token = security.create_access_token({"sub": "aisha@blitzenx.com", "type": "user"})
    with pytest.raises(HTTPException) as exc_info:
        security.decode_access_token(forged_token)
    assert exc_info.value.status_code == 401

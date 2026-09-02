"""
HRMS-0101 BR-01 -- application-level AES-256 encryption for sensitive
employee fields (bank account number, bank routing). "Application-level"
per the spec means encrypted before it ever reaches the database, not
relying solely on the database's own at-rest encryption (Phase 1 B2) --
import logging
defense in depth for the specific fields the spec calls out by name.

Uses AES-256-GCM (authenticated encryption -- detects tampering, not
just confidentiality) via the `cryptography` package already used
elsewhere in this codebase for JWT key generation. The key comes from
FIELD_ENCRYPTION_KEY in .env (32 raw bytes, base64-encoded), following
the same secrets-manager discipline as every other credential here --
never hardcoded, never logged (already covered by the redaction filter's
generic secret-name pattern).
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

class FieldEncryptionNotConfigured(Exception):
    pass


def _get_key() -> bytes:
    raw = os.getenv("FIELD_ENCRYPTION_KEY", "")
    if not raw:
        raise FieldEncryptionNotConfigured(
            "FIELD_ENCRYPTION_KEY is not set -- cannot encrypt/decrypt bank fields. "
            "Generate one with: python -c \"import secrets,base64; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise FieldEncryptionNotConfigured("FIELD_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).")
    return key


def encrypt_field(plaintext: str) -> str:
    """Returns a single base64 string: nonce (12 bytes) + ciphertext+tag,
    safe to store directly in a Text column."""
    if plaintext is None:
        return None
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(encrypted: str) -> str:
    if encrypted is None:
        return None
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None).decode("utf-8")

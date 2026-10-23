"""Signature verification for delivery-outcome webhooks (SendGrid, Mailgun, Twilio).

Providers call these endpoints with no WROS session, so the provider's own signature is
the only authentication. Every check fails closed:
- secret not configured on this server -> WebhookNotConfigured (endpoint answers 503)
- signature missing, stale or wrong    -> WebhookSignatureInvalid (endpoint answers 401)

Secrets are server configuration (env / secret store), one per provider:
- SENDGRID_WEBHOOK_PUBLIC_KEY  SendGrid "Signed Event Webhook" verification key (base64 DER,
                               ECDSA P-256 / SHA-256 over timestamp + raw body)
- MAILGUN_WEBHOOK_SIGNING_KEY  Mailgun "HTTP webhook signing key" (HMAC-SHA256 over
                               timestamp + token) -- not the API key
- TWILIO_AUTH_TOKEN            Twilio account auth token (HMAC-SHA1 over the public URL +
                               each POST parameter name and value, sorted by name)
- WEBHOOK_PUBLIC_BASE_URL      The URL prefix providers call (e.g. https://hrms.blitzenx.com/api).
                               Twilio signs the public URL, which nginx rewrites before it
                               reaches this app.
"""
import base64
import hashlib
import hmac
import time
from typing import Mapping, Optional

from app.core.config import get_secret

# Reject signed requests older than this (replay window), per provider guidance.
MAX_SIGNATURE_AGE_SECONDS = 300


class WebhookNotConfigured(Exception):
    pass


class WebhookSignatureInvalid(Exception):
    pass


def _required_secret(name: str) -> str:
    value = get_secret(name.lower().replace("_", "-"), default="") or ""
    if not value.strip():
        raise WebhookNotConfigured(f"{name} is not configured on this server")
    return value.strip()


def _check_fresh(timestamp: str) -> None:
    try:
        age = abs(time.time() - int(float(timestamp)))
    except (TypeError, ValueError):
        raise WebhookSignatureInvalid("signature timestamp is missing or not a number")
    if age > MAX_SIGNATURE_AGE_SECONDS:
        raise WebhookSignatureInvalid(f"signature timestamp is {int(age)}s old")


def verify_sendgrid(raw_body: bytes, signature_b64: Optional[str], timestamp: Optional[str]) -> None:
    """SendGrid Signed Event Webhook: ECDSA over (timestamp + payload) with SendGrid's key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key_b64 = _required_secret("SENDGRID_WEBHOOK_PUBLIC_KEY")
    if not signature_b64 or not timestamp:
        raise WebhookSignatureInvalid("missing SendGrid signature headers")
    _check_fresh(timestamp)
    try:
        public_key = serialization.load_der_public_key(base64.b64decode(key_b64))
        public_key.verify(base64.b64decode(signature_b64), timestamp.encode() + raw_body,
                          ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise WebhookSignatureInvalid("SendGrid signature does not match") from exc


def verify_mailgun(signature: Optional[Mapping]) -> None:
    """Mailgun: HMAC-SHA256(signing key, timestamp + token) == signature (in the JSON body)."""
    signing_key = _required_secret("MAILGUN_WEBHOOK_SIGNING_KEY")
    if not isinstance(signature, Mapping):
        raise WebhookSignatureInvalid("missing Mailgun signature block")
    timestamp, token, given = (str(signature.get(k, "")) for k in ("timestamp", "token", "signature"))
    if not (timestamp and token and given):
        raise WebhookSignatureInvalid("incomplete Mailgun signature block")
    _check_fresh(timestamp)
    expected = hmac.new(signing_key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, given):
        raise WebhookSignatureInvalid("Mailgun signature does not match")


def twilio_public_url(path: str, query: str = "") -> str:
    base = _required_secret("WEBHOOK_PUBLIC_BASE_URL").rstrip("/")
    return f"{base}{path}" + (f"?{query}" if query else "")


def verify_twilio(public_url: str, form: Mapping[str, str], signature_b64: Optional[str]) -> None:
    """Twilio: base64(HMAC-SHA1(auth token, url + name1 + value1 + name2 + value2 ...))."""
    auth_token = _required_secret("TWILIO_AUTH_TOKEN")
    if not signature_b64:
        raise WebhookSignatureInvalid("missing X-Twilio-Signature")
    data = public_url + "".join(f"{k}{form[k]}" for k in sorted(form))
    expected = base64.b64encode(hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    if not hmac.compare_digest(expected, signature_b64):
        raise WebhookSignatureInvalid("Twilio signature does not match")

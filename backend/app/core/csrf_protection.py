"""CSRF protection utilities for state-changing operations."""
import secrets
import hashlib
from datetime import datetime, timedelta

# In-memory CSRF token store: {token: (timestamp, used)}
_csrf_tokens = {}

def generate_csrf_token() -> str:
    """Generate a new CSRF token."""
    token = secrets.token_urlsafe(32)
    _csrf_tokens[token] = (datetime.utcnow(), False)
    return token

def validate_csrf_token(token: str) -> bool:
    """Validate CSRF token. Returns True if valid, False if invalid or expired."""
    if token not in _csrf_tokens:
        return False

    timestamp, used = _csrf_tokens[token]

    # Check expiration (tokens valid for 1 hour)
    if datetime.utcnow() - timestamp > timedelta(hours=1):
        del _csrf_tokens[token]
        return False

    # Check if already used (prevent replay)
    if used:
        del _csrf_tokens[token]
        return False

    # Mark as used
    _csrf_tokens[token] = (timestamp, True)
    return True

def cleanup_expired_tokens():
    """Remove expired CSRF tokens."""
    now = datetime.utcnow()
    expired = [
        token for token, (timestamp, _) in _csrf_tokens.items()
        if now - timestamp > timedelta(hours=2)
    ]
    for token in expired:
        del _csrf_tokens[token]

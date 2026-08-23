"""
Shared-secret authentication for webhook-style endpoints that must
accept calls from non-interactive external callers (a scheduler, an
email service) alongside manual internal use -- a user-identity check
like require_permission() would break the external-caller path, since
those callers have no JWT to present.

Pattern: the caller sends the shared secret in a request header
(X-Webhook-Secret). Constant-time comparison to avoid a timing side
channel. The secret itself lives in .env (WEBHOOK_SHARED_SECRET),
following the same secrets-manager discipline as every other credential
in this codebase -- never hardcoded, never logged (app.core.logging's
redaction filter also catches "webhook_shared_secret=..." style values
via its generic secret-name pattern).
"""
import hmac
import os

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db


def _secret_is_valid(provided: str) -> bool:
    expected = os.getenv("WEBHOOK_SHARED_SECRET", "")
    return bool(expected) and bool(provided) and hmac.compare_digest(provided, expected)


def require_webhook_secret(x_webhook_secret: str = Header(default="")) -> None:
    """For endpoints that are ONLY ever called by external services --
    no legitimate interactive-user caller exists."""
    if not os.getenv("WEBHOOK_SHARED_SECRET", ""):
        # Fail closed: an unconfigured secret must reject every call,
        # not silently accept everything because there's nothing to
        # compare against.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook authentication is not configured",
        )
    if not _secret_is_valid(x_webhook_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


async def require_webhook_secret_or_internal_user(
    request: Request,
    x_webhook_secret: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    """
    For endpoints that are BOTH a genuine webhook (external caller, no
    JWT available) AND manually triggerable from the HR portal (an
    internal user's JWT). Accepts either. Checks the webhook secret
    first since it's cheaper (no DB query); falls back to resolving an
    internal user from the Authorization header if present.

    Takes `db` via the standard Depends(get_db) pattern (same as every
    other route in this codebase) rather than opening its own session,
    so it's overridable in tests via app.dependency_overrides and never
    silently reaches for the real configured database in a unit test.

    Deliberately does NOT use Depends(get_current_hr_or_admin) directly
    for the JWT path -- that dependency's own HTTPBearer sub-dependency
    has auto_error=True and would reject the request before this
    function got a chance to try the webhook-secret path first.
    """
    if _secret_is_valid(x_webhook_secret):
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide either X-Webhook-Secret or a valid internal-user Bearer token",
        )

    from app.core.security import decode_access_token
    from app.models.user import Users

    token = auth_header.split(" ", 1)[1]
    payload = decode_access_token(token)  # raises 401 on invalid/expired token
    user_id = payload.get("sub")
    user_type = (payload.get("type") or "").lower()
    if not user_id or user_type == "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")


# HRMS-0114 -- marks these as real (if coarse) identity checks so
# route_security_audit.py doesn't flag routes using them as having zero
# protection.
require_webhook_secret.__wros_authn__ = "webhook_shared_secret"
require_webhook_secret_or_internal_user.__wros_authn__ = "webhook_shared_secret_or_internal_user"

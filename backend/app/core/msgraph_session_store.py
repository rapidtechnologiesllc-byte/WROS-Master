"""
M365 account-link state, persisted in msgraph_sessions (one row per
WROS user who connected Outlook).

Shared between:
- app.api.v1.endpoints.msgraph (OAuth callback stores tokens; mail send /
  calendar calls read them)
- app.services.msgraph_mail_sync_service (reads tokens for mail sync)

get_access_token() returns a usable token, refreshing it with the stored
refresh token when it is within REFRESH_MARGIN of expiry -- delegated
Graph access tokens only live about an hour, so without this every
mailbox would stop syncing an hour after it was connected.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.msgraph_session import MsgraphSession

logger = logging.getLogger(__name__)

REFRESH_MARGIN = timedelta(minutes=5)


def _real(value: Optional[str]) -> Optional[str]:
    """Env value, or None when unset or still a template placeholder."""
    if not value or "your_" in value.lower() or "{" in value:
        return None
    return value


def graph_oauth_settings() -> dict:
    """OAuth app settings (env). TENANT_ID/CLIENT_ID/CLIENT_SECRET with the
    AZURE_* names as fallback; placeholder values count as unset."""
    tenant = _real(os.getenv("TENANT_ID")) or _real(os.getenv("AZURE_TENANT_ID"))
    client_id = _real(os.getenv("CLIENT_ID")) or _real(os.getenv("AZURE_CLIENT_ID"))
    secret = _real(os.getenv("CLIENT_SECRET")) or _real(os.getenv("AZURE_CLIENT_SECRET"))
    authority = _real(os.getenv("AUTHORITY")) or (f"https://login.microsoftonline.com/{tenant}" if tenant else None)
    return {
        "client_id": client_id,
        "client_secret": secret,
        "authority": authority,
        "scopes": (os.getenv("SCOPES") or "https://graph.microsoft.com/.default").split(),
        "configured": bool(tenant and client_id and secret),
    }


def _msal_client():
    import msal

    settings = graph_oauth_settings()
    return msal.ConfidentialClientApplication(
        settings["client_id"], authority=settings["authority"], client_credential=settings["client_secret"],
    )


def _expiry(token_result: dict) -> Optional[datetime]:
    seconds = token_result.get("expires_in")
    return datetime.utcnow() + timedelta(seconds=int(seconds)) if seconds else None


def store_session(user_id: str, account_id: str, token_result: dict, account_email: Optional[str] = None) -> None:
    """Create or replace this user's linked session from an MSAL token result."""
    db = SessionLocal()
    try:
        row = db.query(MsgraphSession).filter(MsgraphSession.user_id == user_id).first()
        if row is None:
            row = MsgraphSession(user_id=user_id)
            db.add(row)
        row.account_id = account_id
        row.account_email = account_email
        row.access_token = token_result["access_token"]
        row.refresh_token = token_result.get("refresh_token") or row.refresh_token
        row.expires_at = _expiry(token_result)
        row.is_active = True
        row.mail_access = None
        row.last_error = None
        db.commit()
        logger.info(f"[MsgraphSessionStore] Stored session for user {user_id}")
    finally:
        db.close()


def clear_session(user_id: str) -> None:
    """Disconnect: deactivate and drop the tokens."""
    db = SessionLocal()
    try:
        row = db.query(MsgraphSession).filter(MsgraphSession.user_id == user_id).first()
        if row:
            row.is_active = False
            row.access_token = ""
            row.refresh_token = None
            row.last_error = None
            db.commit()
            logger.info(f"[MsgraphSessionStore] Cleared session for user {user_id}")
    finally:
        db.close()


def get_session_row(db: Session, user_id: str) -> Optional[MsgraphSession]:
    return db.query(MsgraphSession).filter(
        MsgraphSession.user_id == user_id, MsgraphSession.is_active.is_(True)
    ).first()


def active_user_ids(db: Session) -> List[str]:
    return [r[0] for r in db.query(MsgraphSession.user_id).filter(MsgraphSession.is_active.is_(True)).all()]


def record_mail_access(db: Session, user_id: str, ok: bool, error: Optional[str] = None) -> None:
    row = get_session_row(db, user_id)
    if row:
        row.mail_access = ok
        row.last_error = error
        db.commit()


def get_access_token(user_id: str, db: Optional[Session] = None) -> Optional[str]:
    """A usable access token for this user, refreshed if needed; None when
    the user has no active link or the refresh failed (the session is then
    deactivated and last_error says why, so they can reconnect)."""
    own_session = db is None
    db = db or SessionLocal()
    try:
        row = get_session_row(db, user_id)
        if row is None:
            return None
        if row.expires_at is None or row.expires_at - REFRESH_MARGIN > datetime.utcnow():
            return row.access_token
        if not row.refresh_token:
            row.is_active = False
            row.last_error = "Session expired and no refresh token was issued; reconnect Outlook."
            db.commit()
            return None
        result = _msal_client().acquire_token_by_refresh_token(row.refresh_token, scopes=graph_oauth_settings()["scopes"])
        if "access_token" not in result:
            row.is_active = False
            row.last_error = f"Token refresh failed: {result.get('error_description') or result.get('error')}"
            db.commit()
            logger.warning(f"[MsgraphSessionStore] Refresh failed for user {user_id}: {row.last_error}")
            return None
        row.access_token = result["access_token"]
        row.refresh_token = result.get("refresh_token") or row.refresh_token
        row.expires_at = _expiry(result)
        db.commit()
        return row.access_token
    finally:
        if own_session:
            db.close()

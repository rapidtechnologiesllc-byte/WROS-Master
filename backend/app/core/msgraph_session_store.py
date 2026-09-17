"""
M365 account-link state (DATABASE-BACKED for persistence across server restarts).

Shared between:
- app.api.v1.endpoints.msgraph (OAuth callback stores tokens)
- app.services.msgraph_mail_sync_service (reads tokens for mail sync)

CRITICAL FIX (2026-09-17): Changed from in-memory to DB-backed storage.
In-memory was cleared on server restart, breaking M365 email sync pipeline.
Now persists to msgraph_session table in database.
"""

import logging
from app.core.database import SessionLocal
from app.models.msgraph_session import MsgraphSession

logger = logging.getLogger(__name__)

# Lazy-loaded cache (refreshed on each access)
_user_tokens_cache = {}
_account_id_cache = {}


def _refresh_cache():
    """Load tokens from database into memory cache."""
    global _user_tokens_cache, _account_id_cache
    try:
        db = SessionLocal()
        sessions = db.query(MsgraphSession).filter(MsgraphSession.is_active == True).all()
        _user_tokens_cache = {
            s.account_id: {
                "access_token": s.access_token,
                "refresh_token": s.refresh_token,
                "expires_at": s.expires_at,
            }
            for s in sessions
        }
        _account_id_cache = {s.user_id: s.account_id for s in sessions}
        logger.info(f"[MsgraphSessionStore] Loaded {len(sessions)} active M365 sessions from database")
        db.close()
    except Exception as e:
        logger.warning(f"[MsgraphSessionStore] Failed to load from database: {e}")
        db.close()


# Property-like access that auto-refreshes
class UserTokensDict(dict):
    """Dict wrapper that refreshes from DB on each access."""
    def __getitem__(self, key):
        _refresh_cache()
        return _user_tokens_cache.get(key)

    def get(self, key, default=None):
        _refresh_cache()
        return _user_tokens_cache.get(key, default)

    def items(self):
        _refresh_cache()
        return _user_tokens_cache.items()


class AccountIdDict(dict):
    """Dict wrapper that refreshes from DB on each access."""
    def __getitem__(self, key):
        _refresh_cache()
        return _account_id_cache.get(key)

    def get(self, key, default=None):
        _refresh_cache()
        return _account_id_cache.get(key, default)

    def items(self):
        _refresh_cache()
        return _account_id_cache.items()


# Public interface (auto-refreshing from DB)
user_tokens = UserTokensDict()
account_id_by_user_id = AccountIdDict()


def store_session(user_id: str, account_id: str, access_token: str, refresh_token: str, expires_at: str):
    """Store M365 session to database (persists across server restarts)."""
    try:
        db = SessionLocal()
        # Deactivate any existing session for this user
        db.query(MsgraphSession).filter(MsgraphSession.user_id == user_id).update(
            {"is_active": False}
        )
        # Create new session
        session = MsgraphSession(
            user_id=user_id,
            account_id=account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(session)
        db.commit()
        logger.info(f"[MsgraphSessionStore] Stored session for user {user_id}")
        _refresh_cache()
        db.close()
    except Exception as e:
        logger.error(f"[MsgraphSessionStore] Failed to store session: {e}", exc_info=True)
        db.close()


def get_session(account_id: str) -> dict:
    """Get token data for account (auto-loads from DB)."""
    _refresh_cache()
    return _user_tokens_cache.get(account_id, {})


def clear_session(user_id: str):
    """Deactivate session (logout)."""
    try:
        db = SessionLocal()
        db.query(MsgraphSession).filter(MsgraphSession.user_id == user_id).update(
            {"is_active": False}
        )
        db.commit()
        logger.info(f"[MsgraphSessionStore] Cleared session for user {user_id}")
        _refresh_cache()
        db.close()
    except Exception as e:
        logger.error(f"[MsgraphSessionStore] Failed to clear session: {e}", exc_info=True)
        db.close()

"""Every employee account must be usable: when it is created (candidate converted,
user created by an admin) the person is emailed a single-use link to set their own
password. The plaintext password is never generated, stored or emailed.

prepare_new_account(db, user) -> password unusable until the person sets one
queue_account_email(user, p)  -> enqueue send_account_email; the handler creates the token, so the
                                 plaintext link exists only inside the email (never in the queue/DB)
activate(db, token, pw)       -> sets the password, clears password_reset_required, burns the token
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.account_activation import AccountActivationToken
from app.models.user import Users

logger = logging.getLogger(__name__)

ACCOUNT_EMAIL_TASK = "send_account_email"
TTL = {"ACTIVATE": timedelta(days=7), "RESET": timedelta(hours=2)}
MIN_PASSWORD_LENGTH = 10
RESET_EMAIL_WINDOW_MINUTES = 10


class ActivationError(Exception):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db: Session, user: Users, purpose: str = "ACTIVATE", now: Optional[datetime] = None) -> Tuple[AccountActivationToken, str]:
    """Supersede any open token of the same purpose and create a new one. Returns (row, plaintext)."""
    now = now or datetime.utcnow()
    for old in db.query(AccountActivationToken).filter(
            AccountActivationToken.user_id == user.UserID, AccountActivationToken.purpose == purpose,
            AccountActivationToken.used_at.is_(None)).all():
        old.used_at = now  # superseded
    plaintext = secrets.token_urlsafe(32)
    row = AccountActivationToken(user_id=user.UserID, token_hash=_hash(plaintext), purpose=purpose,
                                 expires_at=now + TTL[purpose])
    db.add(row)
    db.flush()
    return row, plaintext


def link_for(plaintext: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/activate?token={plaintext}"


def queue_account_email(user: Users, purpose: str = "ACTIVATE", *, once_key: Optional[str] = None) -> bool:
    """Call after commit. One queued email per request (uuid task id); with once_key, one ever for
    this user, purpose and key (a re-applied import never emails the same person twice)."""
    import uuid

    from app.services.thunder_mail.cadence_service import enqueue_once

    suffix = once_key or uuid.uuid4().hex[:12]
    return enqueue_once(ACCOUNT_EMAIL_TASK, f"account-email-{user.UserID}-{purpose}-{suffix}",
                        {"user_id": user.UserID, "purpose": purpose}, user.tenant_id)


def prepare_new_account(db: Session, user: Users) -> None:
    """New accounts get no usable password: the person sets their own from the emailed link."""
    user.password_reset_required = True
    user.UserPassword = get_password_hash(secrets.token_urlsafe(48))
    db.add(user)


def activate(db: Session, plaintext: str, new_password: str, now: Optional[datetime] = None) -> Users:
    now = now or datetime.utcnow()
    if not isinstance(new_password, str) or len(new_password) < MIN_PASSWORD_LENGTH:
        raise ActivationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    row = db.query(AccountActivationToken).filter(
        AccountActivationToken.token_hash == _hash(plaintext or "")).with_for_update().first()
    if row is None or row.used_at is not None or row.expires_at < now:
        raise ActivationError("This link is invalid, already used or expired. Ask for a new one.")
    user = db.query(Users).filter(Users.UserID == row.user_id).one()
    user.UserPassword = get_password_hash(new_password)
    user.password_reset_required = False
    row.used_at = now
    db.add_all([user, row])
    db.commit()
    logger.info(f"[Account] {row.purpose.lower()} completed for {user.UserID}")
    return user


def request_reset(db: Session, email: str) -> None:
    """Forgot password. Silent when the email is unknown (no account enumeration)."""
    user = db.query(Users).filter(Users.UserEmail.ilike((email or "").strip())).first()
    if user is None:
        logger.info("[Account] reset requested for an unknown email")
        return
    # One reset email per 10 minutes per account. The token is created when the worker sends
    # the email, so a reset already queued (not yet sent) counts too -- otherwise rapid
    # requests before the worker runs each queue another email.
    from app.models.channel_queue import ChannelQueueItem
    window_start = datetime.utcnow() - timedelta(minutes=RESET_EMAIL_WINDOW_MINUTES)
    recent_token = db.query(AccountActivationToken.id).filter(
        AccountActivationToken.user_id == user.UserID, AccountActivationToken.purpose == "RESET",
        AccountActivationToken.created_at > window_start).first()
    recent_queued = db.query(ChannelQueueItem.id).filter(
        ChannelQueueItem.type == ACCOUNT_EMAIL_TASK,
        ChannelQueueItem.id.like(f"account-email-{user.UserID}-RESET-%"),
        ChannelQueueItem.created_at > window_start).first()
    if recent_token is not None or recent_queued is not None:
        return
    queue_account_email(user, "RESET")


def users_never_activated(db: Session):
    """Employee accounts nobody can log into: still on a generated password and with no
    open activation link. Used to repair accounts created before activation existed."""
    from app.models.employee import Employee

    open_tokens = {r[0] for r in db.query(AccountActivationToken.user_id).filter(
        AccountActivationToken.used_at.is_(None), AccountActivationToken.expires_at > datetime.utcnow()).all()}
    rows = db.query(Users).join(Employee, Employee.wros_user_id == Users.UserID).filter(
        Users.password_reset_required.is_(True), Employee.status != "EXITED").all()
    return [u for u in rows if u.UserID not in open_tokens]

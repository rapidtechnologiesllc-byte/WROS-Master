"""Who an email is sent as (CEO 2026-11-03: "all emails should be sent by the user logged in and not
helpdesk_hrms. Helpdesk is the kind of thought where we keep it as a repository").

Rules (every outbound path):
- The person responsible for the email -- whoever did the action, the candidate's recruiter, the
  invoice's approver, the client's account manager, the creator of a task -- sends it from their own
  Outlook when they have connected it (Connect Outlook: delegated Mail.Send + Mail.ReadWrite).
- The helpdesk mailbox is copied on every email sent from a person's mailbox, so it stays the
  repository (client emails are logged from that copy, client_email_log_service).
- Nobody connected, or no one responsible (a system reminder): the helpdesk mailbox sends it, as before.
- The choice is made once per email (OutboundEmailSender) so retries re-send the same draft from the
  mailbox that holds it. A conversation stays in the mailbox it started in (Thunder threads).
"""
import logging
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.outbound_email import OutboundEmailSender
from app.models.user import Users
from app.services.delivery_errors import DeliveryDeferred
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)


def helpdesk_address() -> str:
    return settings.THUNDER_MAILBOX


def _service_addresses() -> set:
    """Shared mailboxes HRMS reaches with its own (application) permission."""
    return {a.lower() for a in (settings.THUNDER_MAILBOX, settings.FINANCE_MAILBOX,
                                getattr(settings, "CLIENT_TIMESHEET_APPROVAL_MAILBOX", None)) if a}


def _token_provider(user_id: str):
    def provide() -> str:
        from app.core.msgraph_session_store import get_access_token

        token = get_access_token(user_id)
        if not token:
            raise DeliveryDeferred(f"Outlook is no longer connected for user {user_id}: they must reconnect it")
        return token
    return provide


def connected_mailbox(db: Session, user_id: Optional[str]) -> Optional[GraphMailbox]:
    """The user's own mailbox when they have connected Outlook and it still answers, else None.
    Emails drafted there copy the helpdesk mailbox."""
    if not user_id:
        return None
    from app.core.msgraph_session_store import get_access_token, get_session_row

    user = db.query(Users).filter(Users.UserID == user_id).first()
    if user is None or not user.UserEmail or user.terminated_at is not None:
        return None
    if get_session_row(db, user_id) is None or not get_access_token(user_id, db):
        return None
    return GraphMailbox(user.UserEmail, token_provider=_token_provider(user_id), cc=[helpdesk_address()],
                        delegated=True)


def mailbox_for_address(db: Session, address: str) -> GraphMailbox:
    """The mailbox an email already lives in: a shared HRMS mailbox, or a person's connected Outlook
    (DeliveryDeferred if they have disconnected it since -- the draft is in their mailbox)."""
    if not address or address.lower() in _service_addresses():
        return GraphMailbox(address or helpdesk_address())
    user = db.query(Users).filter(func.lower(Users.UserEmail) == address.lower()).first()
    mailbox = connected_mailbox(db, user.UserID) if user else None
    if mailbox is None:
        raise DeliveryDeferred(f"The draft is in {address}'s mailbox and Outlook is not connected for them; "
                               "they must reconnect it")
    return mailbox


def sender_for(db: Session, key: str, responsible: Iterable[Optional[str]], *, fallback: Optional[str] = None,
               tenant_id: Optional[int] = None) -> GraphMailbox:
    """The mailbox to draft and send this email from: the one already chosen for it (a retry), else
    the first responsible person with Outlook connected, else the fallback shared mailbox. The
    choice is added to the session; the caller's commit (with the draft id) keeps it."""
    row = db.get(OutboundEmailSender, key)
    if row is not None:
        return mailbox_for_address(db, row.mailbox)
    chosen, sender_id = None, None
    for user_id in responsible:
        chosen = connected_mailbox(db, user_id)
        if chosen is not None:
            sender_id = user_id
            break
    if chosen is None:
        chosen = GraphMailbox(fallback or helpdesk_address())
    db.add(OutboundEmailSender(key=key, tenant_id=tenant_id, mailbox=chosen.mailbox, sender_user_id=sender_id))
    db.flush()
    logger.info(f"[MailSender] {key}: from {chosen.mailbox}" + (" (own Outlook, helpdesk copied)" if sender_id else ""))
    return chosen


def record_sent(db: Session, key: str, internet_message_id: Optional[str]) -> None:
    """Remember the email's Message-ID, so the helpdesk copy of it is recognised as ours."""
    row = db.get(OutboundEmailSender, key)
    if row is not None and internet_message_id:
        row.internet_message_id = internet_message_id


def is_our_email(db: Session, internet_message_id: Optional[str]) -> bool:
    """An email HRMS sent (from any mailbox): the helpdesk's copy of it is never a forward or a reply."""
    if not internet_message_id:
        return False
    from app.models.thunder_email import ThunderEmailMessage

    if db.query(OutboundEmailSender.key).filter(OutboundEmailSender.internet_message_id == internet_message_id).first():
        return True
    return db.query(ThunderEmailMessage.id).filter(ThunderEmailMessage.direction == "OUT",
                                                   ThunderEmailMessage.internet_message_id == internet_message_id).first() is not None

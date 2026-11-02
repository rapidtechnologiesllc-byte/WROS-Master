"""Log emails on the client they are about (CEO 2026-11-02: "when an email is sent from my email to
this client you need to log it on this client ... we can always CC helpdesk").

Staff put the helpdesk mailbox (settings.THUNDER_MAILBOX) on CC or BCC of an email to a client; the
mailbox poll (thunder_mail.mail_poll_service) hands every email it does not match to a candidate
thread to log_mailbox_email(). The email belongs to a client when any address on it, other than our
own staff and the mailbox, is
1. one of the client's contacts (ClientContact.email), or
2. at the client's own domain (Client.website, e.g. moter.ai).
Staff sender -> OUT (sent by that user); anyone else -> IN (the client wrote to us). An email that
names several clients is logged on each. The system's own emails to a client's internal team are
logged as TEAM by log_team_email().
"""
import logging
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client, ClientContact, ClientEmail
from app.models.user import Users

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 2000


def _domain(website: Optional[str]) -> Optional[str]:
    """www.moter.ai / https://moter.ai/about -> moter.ai"""
    if not website:
        return None
    host = re.sub(r"^[a-z]+://", "", website.strip().lower()).split("/")[0].split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return host or None


def _addresses(recipients: Optional[List[Dict]]) -> List[str]:
    return [((r.get("emailAddress") or {}).get("address") or "").lower()
            for r in recipients or [] if (r.get("emailAddress") or {}).get("address")]


def match_clients(db: Session, addresses: Iterable[str]) -> List[Client]:
    """The clients these external addresses belong to, by contact email, then by website domain."""
    addresses = {a.lower() for a in addresses if a and "@" in a}
    if not addresses:
        return []
    found: Dict[str, Client] = {}
    for client in (db.query(Client).join(ClientContact, ClientContact.client_id == Client.id)
                   .filter(func.lower(ClientContact.email).in_(addresses)).all()):
        found[client.id] = client
    domains = {a.split("@", 1)[1] for a in addresses}
    for client in db.query(Client).filter(Client.website.isnot(None)).all():
        if _domain(client.website) in domains:
            found[client.id] = client
    return list(found.values())


def _staff_addresses(db: Session, addresses: Set[str]) -> Set[str]:
    if not addresses:
        return set()
    return {e.lower() for (e,) in db.query(Users.UserEmail).filter(func.lower(Users.UserEmail).in_(addresses))}


def log_mailbox_email(db: Session, message: Dict, sender: str, received: datetime, mailbox_address: str) -> int:
    """Log one mailbox email on every client it is about; returns how many clients it was logged on
    (0 = not a client email). Does not commit -- the poll commits once per run."""
    to = _addresses(message.get("toRecipients"))
    cc = _addresses(message.get("ccRecipients"))
    everyone = {sender, *to, *cc} - {mailbox_address}
    staff = _staff_addresses(db, everyone)
    clients = match_clients(db, everyone - staff)
    if not clients:
        return 0
    sender_user = (db.query(Users).filter(func.lower(Users.UserEmail) == sender).first()
                   if sender in staff else None)
    body = (message.get("uniqueBody") or {}).get("content") or ""
    logged = 0
    for client in clients:
        savepoint = db.begin_nested()
        try:
            db.add(ClientEmail(
                tenant_id=client.tenant_id, client_id=client.id, direction="OUT" if sender_user else "IN",
                message_key=message["id"], from_address=sender, to_addresses=", ".join(to),
                cc_addresses=", ".join(cc), subject=(message.get("subject") or "")[:998],
                snippet=body.strip()[:SNIPPET_CHARS], sent_by_user_id=sender_user.UserID if sender_user else None,
                sent_at=received,
            ))
            savepoint.commit()
            logged += 1
        except IntegrityError:
            savepoint.rollback()  # logged by an earlier, overlapping poll
    logger.info(f"[ClientEmailLog] {message.get('id')} from {sender}: logged on {logged} client(s)")
    return logged


def log_team_email(db: Session, client: Client, recipient: Users, *, key: str, subject: str,
                   summary: str, actor_id: Optional[str]) -> None:
    """Record the system's email to one of the client's internal team. Does not commit."""
    savepoint = db.begin_nested()
    try:
        db.add(ClientEmail(
            tenant_id=client.tenant_id, client_id=client.id, direction="TEAM", message_key=key,
            to_addresses=recipient.UserEmail, subject=subject[:998], snippet=summary[:SNIPPET_CHARS],
            sent_by_user_id=actor_id, sent_at=datetime.utcnow(),
        ))
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()  # the same key was logged before (a retried request)


def log_forwarded_email(db: Session, client: Client, intake, forwarder: Users,
                        original_sender: Optional[str], summary: Optional[str]) -> None:
    """A forwarded email about a client (the mailbox intake matched it by address). Does not commit."""
    savepoint = db.begin_nested()
    try:
        db.add(ClientEmail(
            tenant_id=client.tenant_id, client_id=client.id,
            direction="IN" if original_sender and original_sender != (forwarder.UserEmail or "").lower() else "OUT",
            message_key=intake.graph_message_id, from_address=original_sender or forwarder.UserEmail,
            to_addresses=None, subject=(intake.subject or "")[:998], snippet=(summary or "")[:SNIPPET_CHARS],
            sent_by_user_id=forwarder.UserID, sent_at=intake.received_at or datetime.utcnow(),
        ))
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()  # the same message is already on this client

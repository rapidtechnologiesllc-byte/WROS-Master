"""Read the Thunder mailbox and hand candidate emails to the reply engine.

Runs from the cron'd mail_sync_worker (every 15 min in prod). Matches, in order:
1. conversationId of one of our outbound emails (a reply in our thread);
2. one of our Message-IDs in In-Reply-To / References;
3. a NEW email whose sender is a candidate already in a Thunder cadence.
Anything else sent by an active staff member (a forward, usually) goes to the
mailbox intake (forward_intake_service): it becomes a candidate, a note or a
task, never dropped. Other mail (ordinary HR mail from outside) is neither
stored nor processed here.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage, ThunderMailboxCursor
from app.services.delivery_errors import DeliveryDeferred
from app.services.thunder_mail.cadence_service import INBOUND_TASK, enqueue_once
from app.services.thunder_mail.forward_intake_service import forwarding_user, queue_forward, store_forward
from app.services.thunder_mail.graph_mailbox import GraphMailbox
from app.services.thunder_mail.reply_classifier import is_auto_message

logger = logging.getLogger(__name__)

OVERLAP = timedelta(minutes=10)
FIRST_RUN_LOOKBACK = timedelta(days=1)
MAX_BODY_CHARS = 20000
CLASSIFIER_HEADERS = ("auto-submitted", "x-autoreply", "precedence")


def _parse_time(raw: str) -> datetime:
    return datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")


def _headers(message: Dict) -> Dict[str, str]:
    return {(h.get("name") or "").lower(): h.get("value") or "" for h in message.get("internetMessageHeaders") or []}


def _match(db: Session, message: Dict, headers: Dict[str, str], sender: str) -> Optional[ThunderCadenceState]:
    out = None
    if message.get("conversationId"):
        out = db.query(ThunderEmailMessage).filter_by(
            direction="OUT", conversation_id=message["conversationId"]).first()
    if out is None:
        referenced = f"{headers.get('in-reply-to', '')} {headers.get('references', '')}".split()
        if referenced:
            out = db.query(ThunderEmailMessage).filter(
                ThunderEmailMessage.direction == "OUT",
                ThunderEmailMessage.internet_message_id.in_(referenced)).first()
    if out is not None:
        return db.query(ThunderCadenceState).filter_by(candidate_id=out.candidate_id).first()
    candidate = db.query(Candidate).filter(func.lower(Candidate.candidateEmail) == sender).first()
    if candidate is None:
        return None
    return db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).first()


def poll_thunder_mailbox(db: Session, mailbox: Optional[GraphMailbox] = None,
                         now: Optional[datetime] = None) -> Dict:
    now = now or datetime.utcnow()
    mailbox_address = settings.THUNDER_MAILBOX.lower()
    mailbox = mailbox or GraphMailbox(settings.THUNDER_MAILBOX)
    cursor = db.query(ThunderMailboxCursor).filter_by(mailbox=mailbox_address).first()
    if cursor is None:
        cursor = ThunderMailboxCursor(mailbox=mailbox_address, last_received_at=now - FIRST_RUN_LOOKBACK)
        db.add(cursor)
        db.commit()

    cursor.last_run_at = now
    try:
        messages = mailbox.list_inbox(cursor.last_received_at - OVERLAP)
    except (DeliveryDeferred, RuntimeError) as exc:
        cursor.last_error = str(exc)[:2000]
        db.commit()
        logger.error(f"[ThunderPoll] Could not read {mailbox_address}: {exc}")
        return {"read": 0, "matched": 0, "error": str(exc)}

    matched, newest, queued, forwards = 0, cursor.last_received_at, [], []
    for message in messages:
        received = _parse_time(message["receivedDateTime"])
        newest = max(newest, received)
        sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
        if not sender or sender == mailbox_address:
            continue
        if db.query(ThunderEmailMessage.id).filter_by(
                mailbox=mailbox_address, graph_message_id=message.get("id")).first():
            continue  # seen in an earlier, overlapping run
        headers = _headers(message)
        state = _match(db, message, headers, sender)
        if state is None:
            staff = forwarding_user(db, sender) if settings.MAILBOX_INTAKE_ENABLED else None
            if staff is not None and not is_auto_message(message.get("subject") or "", headers):
                intake_id = store_forward(db, message, staff, mailbox_address, received)
                if intake_id:
                    forwards.append((intake_id, staff.tenant_id))
            continue
        row = ThunderEmailMessage(
            id=str(uuid.uuid4()), tenant_id=state.tenant_id, candidate_id=state.candidate_id,
            direction="IN", status="RECEIVED", cadence_seq=state.cadence_seq, mailbox=mailbox_address,
            graph_message_id=message.get("id"), conversation_id=message.get("conversationId"),
            internet_message_id=message.get("internetMessageId"), in_reply_to=headers.get("in-reply-to"),
            from_address=sender, subject=(message.get("subject") or "")[:998],
            body_text=((message.get("uniqueBody") or {}).get("content") or "")[:MAX_BODY_CHARS],
            received_at=received,
        )
        savepoint = db.begin_nested()
        try:
            db.add(row)
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()  # already stored by an earlier, overlapping run
            continue
        matched += 1
        queued.append((row.id, state.tenant_id, {k: headers[k] for k in CLASSIFIER_HEADERS if k in headers},
                       bool(message.get("hasAttachments"))))

    cursor.last_received_at, cursor.last_error = newest, None
    db.commit()
    for row_id, tenant_id, classifier_headers, has_attachments in queued:
        enqueue_once(INBOUND_TASK, f"thunder_inbound:{row_id}",
                     {"thunder_message_id": row_id, "headers": classifier_headers,
                      "has_attachments": has_attachments}, tenant_id)
    for intake_id, tenant_id in forwards:
        queue_forward(intake_id, tenant_id)
    logger.info(f"[ThunderPoll] {mailbox_address}: read {len(messages)}, matched {matched}, forwarded {len(forwards)}")
    return {"read": len(messages), "matched": matched, "forwarded": len(forwards)}


def run_cadence_sweep(db: Session, now: Optional[datetime] = None) -> Dict:
    """Queue every due touch (silence follow-ups and monthly nurture). The
    deterministic task id makes repeated sweeps harmless."""
    from app.services.thunder_mail.cadence_service import enqueue_send

    now = now or datetime.utcnow()
    due = db.query(ThunderCadenceState).filter(
        ThunderCadenceState.stage.in_(("ACTIVE", "NURTURE", "HANDOFF")),
        ThunderCadenceState.next_step.isnot(None),
        ThunderCadenceState.next_action_at <= now,
    ).all()
    queued = sum(1 for state in due if enqueue_send(state))
    logger.info(f"[ThunderSweep] due={len(due)} newly_queued={queued}")
    return {"due": len(due), "queued": queued}

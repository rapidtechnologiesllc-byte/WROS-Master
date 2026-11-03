"""Read the Thunder mailbox and hand candidate emails to the reply engine.

Runs from the cron'd mail_sync_worker (every 15 min in prod). Matches, in order:
1. conversationId of one of our outbound emails (a reply in our thread);
2. one of our Message-IDs in In-Reply-To / References;
3. a NEW email whose sender is a candidate already in a Thunder cadence.
An email to or from a client's people (staff put the mailbox on CC/BCC) is logged on that client
(client_email_log_service). An email in a candidate's thread from one of our own people is ours,
never the candidate's reply (staff_email_service). Anything else sent by an active staff member (a forward, usually) goes to the
mailbox intake (forward_intake_service): it becomes a candidate, a note or a
task, never dropped. Other mail (ordinary HR mail from outside) is neither
stored nor processed here.

Since emails go from people's own Outlook (mail_sender, helpdesk copied): the helpdesk copy of an
email we sent is ours -- logged on the client when it is a client's email, never a forward or a
reply. poll_connected_mailboxes() reads every email in each connected person's inbox and sent items (CEO
2026-11-03: "we need to read and process every email to find new jobs, new candidate, client updates
and escalations"): replies in our threads go to Thunder, the rest to mailbox_signals.
A reply that reached two mailboxes (reply-all with the helpdesk on copy) is stored once.
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
from app.services.client_email_log_service import log_mailbox_email
from app.services.delivery_errors import DeliveryDeferred
from app.services.mail_sender import is_our_email
from app.services.thunder_mail.cadence_service import INBOUND_TASK, enqueue_once
from app.models.user import Users
from app.services.thunder_mail.forward_intake_service import forwarding_user, queue_forward, store_direct, store_forward
from app.services.thunder_mail.graph_mailbox import GraphMailbox
from app.services.thunder_mail.reply_classifier import is_auto_message
from app.services.thunder_mail.staff_email_service import handle_staff_email, staff_sender

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


def _already_received(db: Session, message: Dict) -> bool:
    internet_id = message.get("internetMessageId")
    return bool(internet_id) and db.query(ThunderEmailMessage.id).filter(
        ThunderEmailMessage.internet_message_id == internet_id,
        ThunderEmailMessage.direction == "IN").first() is not None


def _reply_row(state: ThunderCadenceState, message: Dict, headers: Dict[str, str], sender: str,
               received: datetime, mailbox_address: str) -> ThunderEmailMessage:
    return ThunderEmailMessage(
        id=str(uuid.uuid4()), tenant_id=state.tenant_id, candidate_id=state.candidate_id,
        direction="IN", status="RECEIVED", cadence_seq=state.cadence_seq, mailbox=mailbox_address,
        graph_message_id=message.get("id"), conversation_id=message.get("conversationId"),
        internet_message_id=message.get("internetMessageId"), in_reply_to=headers.get("in-reply-to"),
        from_address=sender, subject=(message.get("subject") or "")[:998],
        body_text=((message.get("uniqueBody") or {}).get("content") or "")[:MAX_BODY_CHARS],
        received_at=received,
    )


def _our_thread(db: Session, message: Dict, headers: Dict[str, str], mailbox_address: str):
    """The cadence of OUR email this message answers, among emails sent from this mailbox only."""
    ours = db.query(ThunderEmailMessage).filter(ThunderEmailMessage.direction == "OUT",
                                                func.lower(ThunderEmailMessage.mailbox) == mailbox_address)
    out = ours.filter(ThunderEmailMessage.conversation_id == message["conversationId"]).first() \
        if message.get("conversationId") else None
    if out is None:
        referenced = f"{headers.get('in-reply-to', '')} {headers.get('references', '')}".split()
        out = ours.filter(ThunderEmailMessage.internet_message_id.in_(referenced)).first() if referenced else None
    return db.query(ThunderCadenceState).filter_by(candidate_id=out.candidate_id).first() if out else None


def poll_connected_mailboxes(db: Session, mailboxes: Optional[Dict[str, GraphMailbox]] = None,
                             now: Optional[datetime] = None) -> Dict:
    """Every email in each connected person's Outlook, once: replies in our threads go to Thunder;
    the rest to mailbox_signals (client History + escalations + role requests, employee escalations,
    the mailbox intake for candidates and notes); sent items to clients go on the client's History.
    mailboxes: {address: mailbox} (tests); default every connected user (mail_sender.connected_mailbox)."""
    from app.core.msgraph_session_store import active_user_ids
    from app.services.mail_sender import connected_mailbox

    now = now or datetime.utcnow()
    if mailboxes is None:
        mailboxes = {}
        for user_id in active_user_ids(db):
            mailbox = connected_mailbox(db, user_id)
            if mailbox is not None:
                mailboxes[mailbox.mailbox.lower()] = mailbox
    result = {"mailboxes": len(mailboxes), "matched": 0, "client_emails": 0, "intake": 0, "signals": 0,
              "sent_logged": 0, "errors": 0}
    for address, mailbox in mailboxes.items():
        address = address.lower()
        cursor = db.query(ThunderMailboxCursor).filter_by(mailbox=address).first()
        if cursor is None:
            cursor = ThunderMailboxCursor(mailbox=address, last_received_at=now - FIRST_RUN_LOOKBACK)
            db.add(cursor)
            db.commit()
        cursor.last_run_at = now
        try:
            messages = mailbox.list_inbox(cursor.last_received_at - OVERLAP)
        except (DeliveryDeferred, RuntimeError) as exc:
            cursor.last_error = str(exc)[:2000]
            db.commit()
            result["errors"] += 1
            logger.error(f"[ThunderPoll] Could not read {address}: {exc}")
            continue
        newest, queued, staff_rows, intakes = cursor.last_received_at, [], [], []
        owner = db.query(Users).filter(func.lower(Users.UserEmail) == address).first()
        for message in messages:
            received = _parse_time(message["receivedDateTime"])
            newest = max(newest, received)
            sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
            if not sender or sender == address or _already_received(db, message):
                continue
            if db.query(ThunderEmailMessage.id).filter_by(mailbox=address, graph_message_id=message.get("id")).first():
                continue
            headers = _headers(message)
            state = _our_thread(db, message, headers, address)
            if state is None:
                _route_own_email(db, message, headers, sender, received, address, owner, result, intakes, mailbox)
                continue
            row = _reply_row(state, message, headers, sender, received, address)
            staff = staff_sender(db, sender)
            if staff is not None:
                row.direction, row.status, row.sent_at, row.received_at = "OUT", "SENT", received, None
            savepoint = db.begin_nested()
            try:
                db.add(row)
                savepoint.commit()
            except IntegrityError:
                savepoint.rollback()
                continue
            if staff is not None:
                staff_rows.append((row.id, staff))
                continue
            result["matched"] += 1
            queued.append((row.id, state.tenant_id, {k: headers[k] for k in CLASSIFIER_HEADERS if k in headers},
                           bool(message.get("hasAttachments"))))
        cursor.last_received_at, cursor.last_error = newest, None
        db.commit()
        for row_id, tenant_id, classifier_headers, has_attachments in queued:
            enqueue_once(INBOUND_TASK, f"thunder_inbound:{row_id}",
                         {"thunder_message_id": row_id, "headers": classifier_headers,
                          "has_attachments": has_attachments}, tenant_id)
        for intake_id, tenant_id in intakes:
            queue_forward(intake_id, tenant_id)
        for row_id, staff in staff_rows:
            handle_staff_email(db, db.query(ThunderEmailMessage).filter_by(id=row_id).one(), staff)
        _log_sent_items(db, mailbox, address, now, result)
    logger.info(f"[ThunderPoll] connected mailboxes: {result}")
    return result


def _vendor_invoice(db: Session, mailbox, message: Dict, sender: str, received: datetime) -> bool:
    """An email from a sub-vendor with attachments: their invoice is recorded and validated. True when the
    sender is a sub-vendor and the email carried an invoice (handled here, never filed elsewhere)."""
    from app.services import vendor_invoice_intake as intake
    from app.services.thunder_mail.forward_classifier import read_attachments

    vendor = intake.vendor_for_sender(db, sender)
    if vendor is None or not message.get("hasAttachments"):
        return False
    try:
        attachments, _ = read_attachments(mailbox.list_attachments(message["id"]))
    except Exception as exc:
        logger.error(f"[ThunderPoll] could not read the attachments of {vendor.company_name}'s email: {exc}", exc_info=True)
        return False
    if not any((a.text or "").strip() for a in attachments):
        return False
    intake.receive(db, vendor, message, attachments, received)
    return True


def _route_own_email(db: Session, message: Dict, headers: Dict[str, str], sender: str, received: datetime,
                     address: str, owner, result: Dict, intakes: list, mailbox=None) -> None:
    """An email in a person's own inbox that is not a reply in our threads (mailbox_signals)."""
    from app.services.client_email_log_service import match_clients
    from app.services.thunder_mail import mailbox_signals as signals

    if owner is None or is_auto_message(message.get("subject") or "", headers) or signals.is_bulk(headers) \
            or is_our_email(db, message.get("internetMessageId")):
        return
    if _vendor_invoice(db, mailbox, message, sender, received):
        return
    if log_mailbox_email(db, message, sender, received, address):
        result["client_emails"] += 1
        result["signals"] += len(signals.client_signals(db, message, sender, match_clients(db, [sender]), owner))
        return
    if signals.employee_escalation(db, message, sender, owner):
        result["signals"] += 1
    intake_id = store_direct(db, message, owner, address, sender, received)
    if intake_id:
        intakes.append((intake_id, owner.tenant_id))
        result["intake"] += 1


def _log_sent_items(db: Session, mailbox: GraphMailbox, address: str, now: datetime, result: Dict) -> None:
    """What the person sent to clients from Outlook goes on the client's History (HRMS's own emails
    are logged from the helpdesk copy)."""
    key = f"{address}#sent"
    cursor = db.query(ThunderMailboxCursor).filter_by(mailbox=key).first()
    if cursor is None:
        cursor = ThunderMailboxCursor(mailbox=key, last_received_at=now - FIRST_RUN_LOOKBACK)
        db.add(cursor)
        db.commit()
    try:
        messages = mailbox.list_folder("sentitems", cursor.last_received_at - OVERLAP)
    except (DeliveryDeferred, RuntimeError) as exc:
        cursor.last_error = str(exc)[:2000]
        db.commit()
        result["errors"] += 1
        logger.error(f"[ThunderPoll] Could not read the sent items of {address}: {exc}")
        return
    newest = cursor.last_received_at
    for message in messages:
        sent = _parse_time(message["receivedDateTime"])
        newest = max(newest, sent)
        if is_our_email(db, message.get("internetMessageId")):
            continue
        if log_mailbox_email(db, message, address, sent, ""):  # "": the person is the sender, kept
            result["sent_logged"] += 1
    cursor.last_received_at, cursor.last_error, cursor.last_run_at = newest, None, now
    db.commit()


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

    matched, clients_logged, newest, queued, forwards, staff_rows = 0, 0, cursor.last_received_at, [], [], []
    for message in messages:
        received = _parse_time(message["receivedDateTime"])
        newest = max(newest, received)
        sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address", "").lower()
        if not sender or sender == mailbox_address:
            continue
        if db.query(ThunderEmailMessage.id).filter_by(
                mailbox=mailbox_address, graph_message_id=message.get("id")).first():
            continue  # seen in an earlier, overlapping run
        if _already_received(db, message):
            continue  # the same reply, already read from a person's own mailbox
        if _vendor_invoice(db, mailbox, message, sender, received):
            continue  # a sub-vendor's invoice: recorded and validated (vendor_invoice_intake)
        if is_our_email(db, message.get("internetMessageId")):
            # our own email, sent from a person's Outlook with the helpdesk copied: the repository copy
            if log_mailbox_email(db, message, sender, received, mailbox_address):
                clients_logged += 1
            continue
        headers = _headers(message)
        state = _match(db, message, headers, sender)
        if state is None and log_mailbox_email(db, message, sender, received, mailbox_address):
            clients_logged += 1
            continue
        if state is None:
            staff = forwarding_user(db, sender) if settings.MAILBOX_INTAKE_ENABLED else None
            if staff is not None and not is_auto_message(message.get("subject") or "", headers):
                intake_id = store_forward(db, message, staff, mailbox_address, received)
                if intake_id:
                    forwards.append((intake_id, staff.tenant_id))
            continue
        row = _reply_row(state, message, headers, sender, received, mailbox_address)
        staff = staff_sender(db, sender)
        if staff is not None:
            # one of our people wrote in the candidate's thread: ours, never the candidate's reply
            row.direction, row.status, row.sent_at, row.received_at = "OUT", "SENT", received, None
        savepoint = db.begin_nested()
        try:
            db.add(row)
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()  # already stored by an earlier, overlapping run
            continue
        if staff is not None:
            staff_rows.append((row.id, staff))
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
    for row_id, staff in staff_rows:
        handle_staff_email(db, db.query(ThunderEmailMessage).filter_by(id=row_id).one(), staff)
    logger.info(f"[ThunderPoll] {mailbox_address}: read {len(messages)}, matched {matched}, "
                f"client emails {clients_logged}, forwarded {len(forwards)}")
    return {"read": len(messages), "matched": matched, "client_emails": clients_logged, "forwarded": len(forwards)}


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

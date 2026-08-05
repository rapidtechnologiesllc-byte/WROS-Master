"""
S-002/HRMS-0402 -- Store WhatsApp Messages (inbound webhook).

Adapted from the literal spec to this codebase's real architecture: the
spec's brand-new `conversation_messages` table was never built here --
this project's own architecture decision (02-DATA-MODEL.md, see the
wros_epic04_scoping memory note) is that CandidateConversation /
ConversationEvent is the single real message log every channel already
writes to (WhatsApp outbound via whatsapp_routing_service, email via
ai_conversation_service, web chat via public_chat_service). This module
makes WhatsApp's INBOUND side of that real, not a second table.

No live WhatsApp Business API app is registered with Meta in this
environment yet (WHATSAPP_VERIFY_TOKEN / WHATSAPP_APP_SECRET are both
empty by default -- see app.core.config) -- same posture as
whatsapp_routing_service's outbound send stub (ChannelNotConfigured by
default, no real credentials exist here). Every function below is
real, tested against Meta's documented Cloud API webhook payload
shape; what's missing to receive live traffic is Avinash registering a
real Meta app + webhook subscription pointed at this endpoint, not
more code.

Known gap, honestly flagged rather than silently left broken: outbound
sends (send_whatsapp_message) don't currently capture the message ID a
real WhatsApp API call would return, so an inbound delivery-status
update (keyed by that ID) can't yet be matched back to the original
sent event. Fixing this means extending the injectable whatsapp_client
interface once a real client exists to call -- not useful to guess at
before then.
"""
import hashlib
import hmac
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent

# Meta's message.type -> this codebase's message_type vocabulary.
MESSAGE_TYPE_MAP = {
    "text": "TEXT", "image": "IMAGE", "document": "DOCUMENT",
    "audio": "AUDIO", "video": "VIDEO",
}
# Meta's status.status -> this codebase's delivery_status vocabulary.
DELIVERY_STATUS_MAP = {"sent": "SENT", "delivered": "DELIVERED", "read": "READ", "failed": "FAILED"}


def verify_webhook_challenge(mode: Optional[str], verify_token: Optional[str], challenge: Optional[str]) -> Optional[str]:
    """GET /webhooks/whatsapp -- Meta's one-time verification handshake.
    Returns the challenge string to echo back (HTTP 200), or None if
    verification fails (caller returns 403)."""
    if not settings.WHATSAPP_VERIFY_TOKEN:
        logger.warning("[WhatsAppWebhook] WHATSAPP_VERIFY_TOKEN not configured -- rejecting all verification attempts.")
        return None
    if mode == "subscribe" and verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return challenge
    return None


def validate_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Meta's real X-Hub-Signature-256 scheme: 'sha256=<hex hmac>' over
    the raw request body, keyed by the app secret. Fails closed (rejects)
    if WHATSAPP_APP_SECRET isn't configured -- there's nothing to
    validate against, so an unsigned/unverifiable request is never
    silently accepted."""
    if not settings.WHATSAPP_APP_SECRET:
        logger.warning("[WhatsAppWebhook] WHATSAPP_APP_SECRET not configured -- rejecting inbound webhook (fail closed).")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def normalize_e164(phone: str) -> str:
    """BR-04: Meta sends phone numbers with or without a leading '+'.
    Digits only, then re-prefixed -- matches how candidates are stored
    in this codebase since the country-code fix earlier this project."""
    digits = re.sub(r"\D", "", phone or "")
    return f"+{digits}" if digits else ""


def _find_candidate_by_phone(db: Session, phone_e164: str) -> Optional[Candidate]:
    return db.query(Candidate).filter(Candidate.candidateMobile == phone_e164).first()


def _find_active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id, CandidateConversation.status != "closed")
        .order_by(CandidateConversation.id.desc())
        .first()
    )


def _is_duplicate_inbound(db: Session, conversation_id: int, whatsapp_message_id: str) -> bool:
    """BR-02: Meta uses at-least-once delivery -- the same webhook can
    arrive twice. Filtered in Python (event_data is JSON), scoped to
    this one conversation's events -- same convention and same
    Python-side-JSON-filtering tradeoff as thunder_service's
    _is_duplicate_send, just keyed by wamid instead of a time window
    (a wamid must never be reprocessed, not just within 60s)."""
    events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply")
        .all()
    )
    return any((event.event_data or {}).get("whatsapp_message_id") == whatsapp_message_id for event in events)


def store_inbound_whatsapp_message(db: Session, message: Dict) -> Dict:
    """
    One inbound WhatsApp message from Meta's `messages[]` array.

    Never raises for a normal "no candidate found" / "duplicate" /
    "no active conversation" case -- BR-03/AC-11 both require the
    caller to return HTTP 200 regardless; this function reports what
    it did (or didn't do) for logging, the caller doesn't fail the
    webhook response over it.
    """
    wamid = message.get("id")
    from_phone_raw = message.get("from", "")
    msg_type = message.get("type", "text")
    timestamp = message.get("timestamp")

    phone = normalize_e164(from_phone_raw)
    candidate = _find_candidate_by_phone(db, phone)
    if not candidate:
        logger.info(f"[WhatsAppWebhook] UNKNOWN_SENDER: no candidate matches phone {phone!r}")
        return {"status": "unknown_sender", "phone": phone}

    conversation = _find_active_conversation(db, candidate.candidateID)
    if not conversation:
        logger.info(f"[WhatsAppWebhook] No active conversation for candidate {candidate.candidateID} -- message not stored.")
        return {"status": "no_active_conversation", "candidate_id": candidate.candidateID}

    if wamid and _is_duplicate_inbound(db, conversation.id, wamid):
        logger.info(f"[WhatsAppWebhook] Duplicate wamid {wamid} -- skipped.")
        return {"status": "duplicate", "candidate_id": candidate.candidateID, "whatsapp_message_id": wamid}

    body = (message.get("text") or {}).get("body") if msg_type == "text" else None
    media_id = None
    if msg_type in ("image", "document", "audio", "video"):
        media_id = (message.get(msg_type) or {}).get("id")

    try:
        sent_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None) if timestamp else datetime.utcnow()
    except (TypeError, ValueError):
        sent_at = datetime.utcnow()

    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="candidate_reply",
        event_data={
            "channel": "whatsapp",
            "body": body,
            "whatsapp_message_id": wamid,
            "message_type": MESSAGE_TYPE_MAP.get(msg_type, "TEXT"),
            "from_phone": phone,
            "sent_at": sent_at.isoformat(),
            # Media download/S3 upload (spec Step 5) needs a real S3
            # bucket + WHATSAPP_ACCESS_TOKEN, neither configured in this
            # environment -- media_id is stored so a future pass can
            # backfill media_url once that infra exists, same "keep the
            # message record, never lose it over a media failure" rule
            # the spec itself requires (BR-01/Step 5's own fallback).
            "media_id": media_id,
            "media_url": None,
        },
        triggered_by="candidate",
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()

    # S-041/HRMS-0441 BR-02: cancel ALL pending follow-ups the moment any
    # inbound message arrives. Never raises -- see
    # follow_up_scheduler_service.cancel_pending_follow_ups().
    from app.services.follow_up_scheduler_service import cancel_pending_follow_ups
    cancel_pending_follow_ups(db, candidate.candidateID, conversation.tenant_id)

    # S-043/HRMS-0443 Step 4/BR-03: any inbound message immediately
    # reactivates a ghosted candidate. Cheap no-op for the common
    # non-ghosted case.
    from app.services.ghosting_detection_service import reactivate_candidate
    reactivate_candidate(db, candidate.candidateID, conversation.tenant_id, conversation.id)

    # S-044/HRMS-0444 BR-01: cancel the outreach campaign the moment any
    # inbound message arrives. Never raises -- cheap no-op if no
    # ACTIVE campaign exists.
    from app.services.outreach_campaign_service import cancel_campaign_on_reply
    cancel_campaign_on_reply(db, candidate.candidateID, conversation.tenant_id)

    # S-347/HRMS-P117 -- every channel is an equal desire-signal source
    # (BR-02). Fire-and-forget, never raises.
    from app.services.desire_signal_service import (
        minutes_since_last_outbound, record_message_signal, record_response_speed_signal,
    )
    if body:
        record_message_signal(db, conversation.tenant_id, candidate.candidateID, "WHATSAPP_MESSAGE", body)
    _prior_gap = minutes_since_last_outbound(db, conversation.id, before=event.created_at)
    if _prior_gap is not None:
        record_response_speed_signal(db, conversation.tenant_id, candidate.candidateID, _prior_gap)

    logger.info(f"[WhatsAppWebhook] Stored inbound message for candidate {candidate.candidateID} (wamid={wamid})")
    return {
        "status": "stored",
        "candidate_id": candidate.candidateID,
        "conversation_id": conversation.id,
        "event_id": event.id,
    }


def _find_ai_sent_event_by_wamid(db: Session, wamid: str) -> Optional[ConversationEvent]:
    """O(n) over every ai_message_sent event -- event_data is JSON, no
    index possible on a sub-field portably (Text-backed on SQL Server
    per this codebase's architecture notes). Acceptable at this
    system's current real WhatsApp volume; flagged as a known scaling
    gap rather than silently ignored, same posture as
    RateLimitMiddleware's own documented in-memory-store limitation."""
    events = db.query(ConversationEvent).filter(ConversationEvent.event_type == "ai_message_sent").all()
    for event in events:
        if (event.event_data or {}).get("whatsapp_message_id") == wamid:
            return event
    return None


def process_delivery_status(db: Session, status: Dict) -> Dict:
    """
    One entry from Meta's `statuses[]` array. See this module's
    docstring for the known gap: outbound sends don't yet capture a
    wamid to match against, so this currently only has something to
    update once that's wired up -- the matching/mapping logic itself
    is real and tested now regardless.
    """
    wamid = status.get("id")
    raw_status = status.get("status")
    mapped = DELIVERY_STATUS_MAP.get(raw_status)
    if not wamid or not mapped:
        return {"status": "ignored", "reason": "unrecognized status payload"}

    event = _find_ai_sent_event_by_wamid(db, wamid)
    if not event:
        logger.info(f"[WhatsAppWebhook] STATUS_FOR_UNKNOWN_MESSAGE: wamid={wamid}")
        return {"status": "unknown_message", "whatsapp_message_id": wamid}

    data = dict(event.event_data or {})
    data["delivery_status"] = mapped
    data["delivery_status_updated_at"] = datetime.utcnow().isoformat()
    event.event_data = data
    db.add(event)
    db.commit()
    return {"status": "updated", "whatsapp_message_id": wamid, "delivery_status": mapped}

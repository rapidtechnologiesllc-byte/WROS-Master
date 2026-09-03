"""
S-004/HRMS-0404 -- Store Web Portal Chat Messages.
import logging
S-346/HRMS-P116 -- Portal Real-Time Chat Widget (2026-08-05 addition).

Adapted to this codebase's real architecture: stores into the existing
ConversationEvent log (channel="portal"), not a new conversation_messages
table -- same pattern as S-002 (WhatsApp) and S-003 (email). Real
candidate identity here is JWT via app.core.dependencies.
get_current_candidate (this codebase's actual candidate auth mechanism),
not the spec's HRMS-P111 magic link, which was never built -- per the
standing "requirement is a direction, not the literal spec" rule.

S-346 real gap this closes: send_portal_message() used to only STORE
the candidate's inbound message -- nothing ever generated a reply, so
the portal Messages tab was receive-only (confirmed by grep: nothing
in this codebase called store_outbound_portal_message() from a live
inbound path before this). Now mirrors
public_chat_service.send_public_chat_message()'s real pipeline
(escalation check -> objection routing -> generate_thunder_reply_with_
fallback()) for the one channel difference that matters: portal sends
go through store_outbound_portal_message() (no external transport,
"the reply IS the HTTP response", same posture S-346's own spec states
for the widget) rather than send_thunder_message() (portal was never
added to CHANNEL_CONSENT_TYPES -- this is an already-authenticated,
already-onboarded candidate with an existing relationship, not a new
anonymous visitor like public_chat, so a second portal-specific
consent gate would be bureaucracy without a real decision behind it).
R-08 ownership is enforced by hand here instead
(conversation.owner_type/is_thunder_paused) since
store_outbound_portal_message() doesn't check it itself.

No WebSocket infrastructure exists anywhere in this codebase (grepped
clean) and S-346's own "BEFORE YOU START" gate names that as a
precondition -- built as the documented fallback (long-polling, see
get_portal_message_history's `after_id` support below) instead of
introducing a first-ever async WS layer into an otherwise-synchronous
FastAPI/SQLAlchemy app for one screen.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent

MAX_MESSAGE_LENGTH = 4000
RATE_LIMIT_PER_HOUR = 20
PAGE_SIZE = 50

logger = logging.getLogger(__name__)

class PortalMessageEmpty(Exception):
    pass


class PortalMessageTooLong(Exception):
    pass


class PortalConversationNotFound(Exception):
    """BR-01: doesn't exist, or doesn't belong to this candidate -- same
    403 either way, no information leak about other candidates'
    conversation IDs."""


class PortalRateLimitExceeded(Exception):
    pass


def _get_owned_conversation(db: Session, candidate: Candidate, conversation_id: int) -> CandidateConversation:
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.id == conversation_id, CandidateConversation.candidate_id == candidate.candidateID)
        .first()
    )
    if not conversation:
        raise PortalConversationNotFound(f"Conversation {conversation_id} not found for this candidate.")
    return conversation


def _portal_messages_sent_since(db: Session, candidate_id: str, since: datetime) -> int:
    """BR-02: DB-based rolling-hour rate limit -- no Redis in this stack.
    Scoped by candidate (across all their conversations), not a single
    conversation, so switching conversations can't reset the limit."""
    conversation_ids = [
        row[0] for row in
        db.query(CandidateConversation.id).filter(CandidateConversation.candidate_id == candidate_id).all()
    ]
    if not conversation_ids:
        return 0
    events = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id.in_(conversation_ids),
            ConversationEvent.event_type == "candidate_reply",
            ConversationEvent.created_at >= since,
        )
        .all()
    )
    return sum(1 for e in events if (e.event_data or {}).get("channel") == "portal")


def send_portal_message(db: Session, candidate: Candidate, conversation_id: int, message_body: str) -> Dict:
    conversation = _get_owned_conversation(db, candidate, conversation_id)

    body = (message_body or "").strip()
    if not body:
        raise PortalMessageEmpty("Message cannot be empty.")
    if len(body) > MAX_MESSAGE_LENGTH:
        raise PortalMessageTooLong(f"Message too long -- maximum {MAX_MESSAGE_LENGTH} characters.")

    window_start = datetime.utcnow() - timedelta(hours=1)
    if _portal_messages_sent_since(db, candidate.candidateID, window_start) >= RATE_LIMIT_PER_HOUR:
        raise PortalRateLimitExceeded("You are sending messages too quickly. Please wait before sending another message.")

    # BR-03: no status gate here -- a PAUSED (or any-status) conversation
    # still accepts and stores the message.
    # BR-04: server-side timestamp only (created_at's DB default / this
    # function's own datetime.utcnow() calls) -- a client timestamp is
    # never read from the request.
    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="candidate_reply",
        event_data={"channel": "portal", "body": body, "delivery_status": "RECEIVED"},
        triggered_by="candidate",
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(event)

    logger.info(f"[PortalMessages] Stored inbound portal message for candidate {candidate.candidateID}, conversation {conversation.id}")

    # S-347/HRMS-P117 -- every channel is an equal desire-signal source
    # (BR-02). Fire-and-forget, never raises (see desire_signal_service
    # module docstring) -- measured against the PRIOR outbound, before
    # this turn's own reply (generated below) exists.
    from app.services.desire_signal_service import (
        minutes_since_last_outbound, record_message_signal, record_response_speed_signal,
    )
    record_message_signal(db, conversation.tenant_id, candidate.candidateID, "CHAT_MESSAGE", body)
    _prior_gap = minutes_since_last_outbound(db, conversation.id, before=event.created_at)
    if _prior_gap is not None:
        record_response_speed_signal(db, conversation.tenant_id, candidate.candidateID, _prior_gap)

    reply_text, reply_sent_at, escalated, suppressed = _maybe_reply_to_portal_message(db, conversation, candidate, body)

    return {
        "message_id": event.id,
        "sent_at": event.created_at,
        "reply": reply_text,
        "reply_sent_at": reply_sent_at,
        "escalated": escalated,
        "suppressed": suppressed,
    }


def _maybe_reply_to_portal_message(db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str):
    """S-346 Step 4: same real generation pipeline every other live
    channel uses (public_chat_service.send_public_chat_message() is
    this codebase's one other genuinely live real-time inbound loop --
    same escalation-first, objection-routed, fallback-safe shape).
    Never raises -- a reply failure must never break message storage,
    which has already committed by the time this runs. Returns
    (reply_text_or_None, sent_at_or_None, escalated, suppressed)."""
    if conversation.owner_type != "ai_agent" or conversation.is_thunder_paused:
        # R-08 / pause: a human owns this conversation, or Thunder is
        # paused on it -- the message is stored, no auto-reply. Same
        # posture as every other channel's ownership gate, just
        # enforced by hand since store_outbound_portal_message() has
        # no transport-layer gate to do it for us.
        return None, None, False, False

    try:
        from app.services.escalation_detection_service import check_escalation, execute_escalation
        escalation = check_escalation(db, conversation.tenant_id, candidate.candidateID, message_body)
        if escalation["needs_escalation"]:
            execute_escalation(db, conversation, candidate, reason=escalation["reason"], trigger_type=escalation["trigger_type"])
            db.commit()
            return None, None, True, False

        from app.services.detect_intent_service import detect_intent
        intent_result = detect_intent(db, conversation.tenant_id, candidate.candidateID, message_body, conversation_id=conversation.id, message_event_id=None)

        if intent_result["intent"] == "objecting":
            from app.services.objection_handling_service import ObjectionEscalatedError, handle_objection
            try:
                objection_result = handle_objection(db, conversation, candidate, message_body)
                reply_text = objection_result["response"]
            except ObjectionEscalatedError as exc:
                execute_escalation(db, conversation, candidate, reason=str(exc), trigger_type="OBJECTION_REPEATED")
                db.commit()
                raise ValueError("Operation failed")
        else:
            from app.services.thunder_service import generate_thunder_reply_with_fallback
            reply_text, _used_fallback = generate_thunder_reply_with_fallback(
                db, candidate, message_body, channel="portal", conversation=conversation,
            )

        reply_event = store_outbound_portal_message(db, conversation, sender_type="ai_agent", message_body=reply_text)
        db.commit()
        db.refresh(reply_event)
        return reply_text, reply_event.created_at, False, False
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        # Fail-soft, not fail-closed, here specifically: the candidate's
        # own message is already safely stored (BR-03/S-004's own
        # guarantee) -- a broken reply must not turn into a 500 on a
        # send the candidate already successfully made.
        logger.warning(f"[PortalMessages] Reply generation failed for candidate {candidate.candidateID}, conversation {conversation.id}: {exc}")
        db.rollback()
        return None, None, False, True


def store_outbound_portal_message(db: Session, conversation: CandidateConversation, *, sender_type: str, sender_id: str = None, message_body: str) -> ConversationEvent:
    """storeOutboundPortalMessage() -- portal sends are immediately
    'delivered' on insert, no external transport to wait for (unlike
    WhatsApp/email)."""
    event = ConversationEvent(
        conversation_id=conversation.id,
        event_type="ai_message_sent" if sender_type == "ai_agent" else "hr_message_sent",
        event_data={"channel": "portal", "body": message_body, "delivery_status": "DELIVERED"},
        triggered_by=sender_type,
    )
    db.add(event)
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    return event


def get_portal_message_history(db: Session, candidate: Candidate, conversation_id: int, *, page: int = 0, per_page: int = PAGE_SIZE, after_id: Optional[int] = None) -> Dict:
    """S-346 Step 2 (long-polling fallback): passing after_id switches
    this into "what's new since I last checked" mode -- the widget's
    poll loop, distinct from page's "scroll back through history" mode.
    The two are mutually exclusive by convention (after_id wins)."""
    conversation = _get_owned_conversation(db, candidate, conversation_id)

    events = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type.in_(("candidate_reply", "ai_message_sent", "hr_message_sent")),
        )
        .order_by(ConversationEvent.created_at.asc(), ConversationEvent.id.asc())
        .all()
    )
    # Only portal-channel events belong in this transcript -- same
    # "don't leak a different channel's traffic" fix as
    # public_chat_service.get_public_chat_history().
    portal_events = [e for e in events if (e.event_data or {}).get("channel") == "portal"]

    if after_id is not None:
        new_events = [e for e in portal_events if e.id > after_id]
        messages = [
            {
                "id": e.id,
                "direction": "INBOUND" if e.event_type == "candidate_reply" else "OUTBOUND",
                "sender_type": "CANDIDATE" if e.event_type == "candidate_reply" else ("AI" if e.event_type == "ai_message_sent" else "RECRUITER"),
                "channel": "PORTAL",
                "message_body": (e.event_data or {}).get("body", ""),
                "sent_at": e.created_at,
                "delivery_status": (e.event_data or {}).get("delivery_status", "SENT"),
            }
            for e in new_events
        ]
        return {"messages": messages, "total_count": len(portal_events), "page": 0, "per_page": len(messages), "has_more": False}

    total_count = len(portal_events)
    start = page * per_page
    page_events = portal_events[start:start + per_page]

    messages = [
        {
            "id": e.id,
            "direction": "INBOUND" if e.event_type == "candidate_reply" else "OUTBOUND",
            "sender_type": "CANDIDATE" if e.event_type == "candidate_reply" else ("AI" if e.event_type == "ai_message_sent" else "RECRUITER"),
            "channel": "PORTAL",
            "message_body": (e.event_data or {}).get("body", ""),
            "sent_at": e.created_at,
            "delivery_status": (e.event_data or {}).get("delivery_status", "SENT"),
        }
        for e in page_events
    ]
    return {
        "messages": messages,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "has_more": start + per_page < total_count,
    }

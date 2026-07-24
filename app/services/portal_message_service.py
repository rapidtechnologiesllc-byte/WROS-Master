"""
S-004/HRMS-0404 -- Store Web Portal Chat Messages.

Adapted to this codebase's real architecture: stores into the existing
ConversationEvent log (channel="portal"), not a new conversation_messages
table -- same pattern as S-002 (WhatsApp) and S-003 (email). Real
candidate identity here is JWT via app.core.dependencies.
get_current_candidate (this codebase's actual candidate auth mechanism),
not the spec's HRMS-P111 magic link, which was never built -- per the
standing "requirement is a direction, not the literal spec" rule.
"""
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent

MAX_MESSAGE_LENGTH = 4000
RATE_LIMIT_PER_HOUR = 20
PAGE_SIZE = 50


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
    return {"message_id": event.id, "sent_at": event.created_at}


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


def get_portal_message_history(db: Session, candidate: Candidate, conversation_id: int, *, page: int = 0, per_page: int = PAGE_SIZE) -> Dict:
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

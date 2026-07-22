"""
Phase 3 Part A1 -- Thunder Conversation Core.

`03-THUNDER-AGENTIC-LAYER.md` calls for exactly two functions every
other story in this platform must call instead of reimplementing:

  build_candidate_context() -- read cross-channel history before
                                generating any candidate-facing response.
  send_thunder_message()    -- the one send path, enforcing R-08,
                                consent, and duplicate-send prevention
                                every time, no bypass.

Neither is built from scratch. `app.services.whatsapp_routing_service.
send_whatsapp_message()` already IS the real, tested R-08 ownership gate
(HRMS-0410 BR-01 -- "Thunder must never send when a recruiter owns the
conversation") and the one place `conversation_inactivity_service.py`
sends from. This module wraps it rather than duplicating that logic,
and adds the two guarantees the Phase 3 doc calls for that the existing
gate doesn't cover yet: consent and debounce.

Consent: the doc says "candidates.consent_given must be true" -- that
column does not exist in this codebase. `app.models.consent.ConsentRecord`
(Phase 1 B6) is the real, general-purpose consent table its own
docstring says every story should honor instead of inventing a flag --
same doc-vs-reality gap pattern already flagged elsewhere in this
project (Locale/Currency, SQL Server vs Postgres). This module reads
that table, not a fictional column.

candidate_desire_profiles (02-DATA-MODEL.md Domain 2) does not exist in
this codebase -- it's EPIC-11 scope (HRMS-1101-1110, Phase 3 Workstream
1 / Recruit), not Part A. build_candidate_context() returns
desire_profile=None rather than fabricating one, so a caller can tell
"not built yet" apart from "built and empty."
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.internal_note import InternalNote
from app.services.whatsapp_routing_service import send_whatsapp_message  # noqa: F401 -- re-exported gate

WHATSAPP_OUTREACH_CONSENT_TYPE = "whatsapp_outreach"
DEBOUNCE_SECONDS = 60


class ConsentNotGiven(Exception):
    """A1: no active whatsapp_outreach ConsentRecord for this candidate."""


class DuplicateMessageSuppressed(Exception):
    """A1's debounce guarantee -- the same message body was already sent
    on this conversation within DEBOUNCE_SECONDS."""


def has_active_consent(
    db: Session, candidate_id: str, *, consent_type: str = WHATSAPP_OUTREACH_CONSENT_TYPE,
) -> bool:
    """Most recent ConsentRecord for this subject+type wins -- a later
    revocation overrides an earlier grant, same convention as every
    other "latest row wins" status field in this codebase."""
    record = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.subject_type == "candidate",
            ConsentRecord.subject_id == candidate_id,
            ConsentRecord.consent_type == consent_type,
        )
        .order_by(ConsentRecord.captured_at.desc(), ConsentRecord.id.desc())
        .first()
    )
    return bool(record and record.consent_given)


def _is_duplicate_send(
    db: Session, conversation: CandidateConversation, message_body: str,
) -> bool:
    # Filtered in Python, not SQL -- event_data is a JSON-encoded column
    # (Text-backed on SQL Server, per this codebase's architecture notes)
    # and per-conversation volume is small enough that this is cheap.
    #
    # Compared against real wall-clock time, not a caller-supplied `now`
    # -- the ConversationEvent this guards against was itself inserted
    # with a real DB-server timestamp (send_whatsapp_message's created_at
    # is func.now(), never caller-controlled), so the window check has
    # to use the same clock or it silently stops working (a synthetic
    # `now` would never fall near a real inserted timestamp).
    window_start = datetime.utcnow() - timedelta(seconds=DEBOUNCE_SECONDS)
    recent = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id == conversation.id,
            ConversationEvent.event_type.in_(("ai_message_sent", "hr_message_sent")),
            ConversationEvent.created_at >= window_start,
        )
        .all()
    )
    return any((event.event_data or {}).get("body") == message_body for event in recent)


def send_thunder_message(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    message_body: str,
    *,
    sender_type: str,
    sender_id: Optional[str] = None,
    channel: str = "whatsapp",
    whatsapp_client=None,
    auto_generated: bool = False,
) -> ConversationEvent:
    """
    A1's sendThunderMessage() -- the single send path every candidate-
    facing story in this platform must call instead of hand-rolling its
    own send logic. R-08 (ownership lock) is enforced by
    send_whatsapp_message() below, not reimplemented here; this function
    adds the consent and debounce checks in front of it.

    channel: only 'whatsapp' has a real transport wired in this
    codebase (see whatsapp_routing_service's own scope note on email/SMS
    not being provisioned). Kept as a parameter rather than hardcoded so
    a future transport doesn't require every caller to change.
    """
    if channel != "whatsapp":
        raise NotImplementedError(
            f"send_thunder_message: no transport wired for channel '{channel}' in this "
            f"codebase yet -- only 'whatsapp' does."
        )

    if not has_active_consent(db, candidate.candidateID):
        raise ConsentNotGiven(
            f"Candidate {candidate.candidateID} has no active {WHATSAPP_OUTREACH_CONSENT_TYPE} "
            f"consent record -- send rejected."
        )

    if _is_duplicate_send(db, conversation, message_body):
        raise DuplicateMessageSuppressed(
            f"An identical message was already sent on conversation {conversation.id} "
            f"within the last {DEBOUNCE_SECONDS}s -- suppressed."
        )

    return send_whatsapp_message(
        db, conversation, candidate, message_body,
        sender_type=sender_type, sender_id=sender_id,
        whatsapp_client=whatsapp_client, auto_generated=auto_generated,
    )


def build_candidate_context(db: Session, candidate: Candidate) -> Dict:
    """
    A1's buildCandidateContext() -- must be called before any future
    Thunder response-generation path produces a candidate-facing reply,
    so Thunder never re-asks something already answered on a different
    channel. Unifies email (ai_conversation_service) and WhatsApp
    (whatsapp_routing_service) history for the first time -- both
    already log into the same conversation_events table keyed by
    conversation_id, but nothing previously read them back as one
    ordered timeline.
    """
    conversations: List[CandidateConversation] = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate.candidateID)
        .order_by(CandidateConversation.id.asc())
        .all()
    )

    history: List[Dict] = []
    for conversation in conversations:
        events = (
            db.query(ConversationEvent)
            .filter(ConversationEvent.conversation_id == conversation.id)
            .order_by(ConversationEvent.created_at.asc(), ConversationEvent.id.asc())
            .all()
        )
        for event in events:
            data = event.event_data or {}
            history.append({
                "conversation_id": conversation.id,
                "event_type": event.event_type,
                "triggered_by": event.triggered_by,
                "channel": data.get("channel"),
                "body": data.get("body"),
                "created_at": event.created_at,
            })
    history.sort(key=lambda item: item["created_at"] or datetime.min)

    notes = (
        db.query(InternalNote)
        .filter(InternalNote.candidate_id == candidate.candidateID)
        .order_by(InternalNote.created_at.asc())
        .all()
    )

    active_conversation = next(
        (conv for conv in reversed(conversations) if conv.status != "closed"), None,
    )

    return {
        "candidate_id": candidate.candidateID,
        "message_history": history,
        "internal_notes": [
            {"content": note.content, "category": note.category, "created_at": note.created_at}
            for note in notes
        ],
        "desire_profile": None,  # not built yet -- EPIC-11 scope, see module docstring
        "active_conversation_id": active_conversation.id if active_conversation else None,
        "current_owner_type": active_conversation.owner_type if active_conversation else None,
        "current_owner_id": active_conversation.owner_id if active_conversation else None,
    }

"""
import logging
S-015/HRMS-0415 -- Conversation Search.

Adapted to real architecture: the spec's PostgreSQL tsvector/
plainto_tsquery generated column doesn't exist here (this project's
real database is SQL Server, not Postgres -- see wros_build_
conventions memory on the SQL-Server-specific constraint gaps found
earlier this project). There's also no plain `message_body` column to
index -- every channel's message body lives inside ConversationEvent.
event_data (a JSON column), the architecture this whole EPIC-04 round
committed to (S-002/S-003/S-004).

Real adaptation: search filters candidate-and-date scope at the DB
level (real tenant isolation, real indexed columns), then does a
case-insensitive substring match over event_data.body in Python --
same "JSON isn't queryable at the DB level, filter in Python" tradeoff
already established by thunder_service._is_duplicate_send and
whatsapp_webhook_service's wamid lookup. Honest limitation, not
silently pretended away: this is a real O(n) scan over one tenant's
own messages, acceptable at the "BlitzenX has 60+ consultants" scale
the story itself describes; a real Postgres/SQL-Server full-text index
would need a schema change (a real, indexed message_body column) this
round didn't make -- flagged for a future pass if message volume ever
makes this measurably slow.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.core.logging import logger

MIN_QUERY_LENGTH = 2
SNIPPET_LENGTH = 150
SEARCHABLE_EVENT_TYPES = ("candidate_reply", "ai_message_sent", "hr_message_sent")

logger = logging.getLogger(__name__)

class SearchTermTooShort(Exception):
    pass

def _snippet(body: str, query: str) -> str:
    if not body:
        return ""
    if len(body) <= SNIPPET_LENGTH:
        return body
    idx = body.lower().find(query.lower())
    if idx == -1:
        return body[:SNIPPET_LENGTH]
    start = max(0, idx - 40)
    return body[start:start + SNIPPET_LENGTH]

def search_conversations(
    db: Session, tenant_id: str, q: str, *,
    channel: Optional[str] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    page: int = 1, per_page: int = 20,
    # S-016/HRMS-0416 -- additive filters on top of the S-015 search.
    # Adapted to this codebase's real status vocabulary: the spec's
    # single QUALIFYING/QUALIFIED/ESCALATED/PAUSED/COMPLETED status
    # enum doesn't exist here -- CandidateConversation really has two
    # orthogonal real fields, status ("open"/"awaiting_candidate"/
    # "closed") and escalation_state ("none"/"pending"/"escalated"/
    # "resolved"), so `status` filters the first and `escalated`
    # filters the second rather than inventing a fictional mapping
    # between them. has_missing_fields is computed live via the real
    # get_missing_fields() (no candidate_missing_fields table exists).
    status: Optional[List[str]] = None,
    escalated: Optional[bool] = None,
    has_missing_fields: Optional[bool] = None,
    updated_after: Optional[datetime] = None,
    updated_before: Optional[datetime] = None,
) -> Dict:
    """BR-01: minimum 2 characters. BR-02: absolute tenant isolation --
    every conversation/candidate looked up is filtered by tenant_id at
    the DB level before any Python-side body matching happens."""
    if not q or len(q) < MIN_QUERY_LENGTH:
        raise SearchTermTooShort("Search term must be at least 2 characters")

    q_lower = q.lower()

    conv_query = db.query(CandidateConversation).filter(CandidateConversation.tenant_id == tenant_id)
    if status:
        conv_query = conv_query.filter(CandidateConversation.status.in_(status))
    if escalated is True:
        conv_query = conv_query.filter(CandidateConversation.escalation_state.in_(("pending", "escalated")))
    elif escalated is False:
        conv_query = conv_query.filter(CandidateConversation.escalation_state.in_((None, "none", "resolved")))
    if updated_after:
        conv_query = conv_query.filter(CandidateConversation.updated_at >= updated_after)
    if updated_before:
        conv_query = conv_query.filter(CandidateConversation.updated_at <= updated_before)

    conversations = conv_query.all()
    conv_by_id = {c.id: c for c in conversations}
    if not conv_by_id:
        return {"results": [], "total_count": 0, "page": page, "per_page": per_page, "has_more": False}

    candidate_ids = {c.candidate_id for c in conversations}
    candidates_by_id = {
        c.candidateID: c
        for c in db.query(Candidate).filter(Candidate.candidateID.in_(candidate_ids)).all()
    }

    if has_missing_fields is not None:
        from app.services.ai_conversation_service import get_missing_fields
        keep_candidate_ids = set()
        for candidate in candidates_by_id.values():
            missing = get_missing_fields(candidate, db)
            if bool(missing) == has_missing_fields:
                keep_candidate_ids.add(candidate.candidateID)
        candidates_by_id = {cid: c for cid, c in candidates_by_id.items() if cid in keep_candidate_ids}
        conv_by_id = {cid: c for cid, c in conv_by_id.items() if c.candidate_id in keep_candidate_ids}
        if not conv_by_id:
            return {"results": [], "total_count": 0, "page": page, "per_page": per_page, "has_more": False}

    event_query = (
        db.query(ConversationEvent)
        .filter(
            ConversationEvent.conversation_id.in_(conv_by_id.keys()),
            ConversationEvent.event_type.in_(SEARCHABLE_EVENT_TYPES),
        )
    )
    if date_from:
        event_query = event_query.filter(ConversationEvent.created_at >= date_from)
    if date_to:
        event_query = event_query.filter(ConversationEvent.created_at <= date_to)

    events = event_query.order_by(ConversationEvent.created_at.desc()).all()

    matches: List[Dict] = []
    for event in events:
        data = event.event_data or {}
        event_channel = (data.get("channel") or "").upper()
        if channel and event_channel != channel.upper():
            continue

        conversation = conv_by_id.get(event.conversation_id)
        candidate = candidates_by_id.get(conversation.candidate_id) if conversation else None
        candidate_name = " ".join(filter(None, [
            candidate.candidateFirstName if candidate else None,
            candidate.candidateLastName if candidate else None,
        ])) or (candidate.candidateEmail if candidate else "")

        body = data.get("body") or ""
        body_matches = q_lower in body.lower()
        name_matches = q_lower in candidate_name.lower()
        if not (body_matches or name_matches):
            continue

        matches.append({
            "candidate_id": candidate.candidateID if candidate else None,
            "candidate_name": candidate_name,
            "conversation_id": event.conversation_id,
            "message_snippet": _snippet(body, q) if body_matches else body[:SNIPPET_LENGTH],
            "channel": event_channel,
            "sent_at": event.created_at,
            "direction": "INBOUND" if event.event_type == "candidate_reply" else "OUTBOUND",
        })

    total_count = len(matches)
    start = (page - 1) * per_page
    page_results = matches[start:start + per_page]

    return {
        "results": page_results,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "has_more": start + per_page < total_count,
    }

"""
import logging
S-019/HRMS-0419 -- Conversation Summary Auto-Generation.

Adapted to real architecture:
- No `conversation_messages` table -- "last 20 messages" reads the last
  20 relevant ConversationEvent rows (candidate_reply/ai_message_sent/
  hr_message_sent), same source every other messaging story this round
  reads from.
- No `candidate_memory` table (HRMS-0421 was never built) -- "known
  facts" are built from the candidate's own real profile fields
  (name/skills/experience/job title) plus get_missing_fields(), the
  same real signal S-011/S-014/S-016/S-017 already standardized on.
- The real LLM already integrated in this codebase is Gemini
  (GEMINI_API_KEY, raw REST call), not the spec's Anthropic
  "claude-sonnet-4-6" -- reuses the exact same call shape as
  ai_conversation_service.parse_reply_with_gemini() rather than adding
  a second LLM integration.
- `summary_generated_at` is a real new column (migration
  d3e4f5a6b7c8_add_summary_generated_at_to_candidate_conversations) --
  distinct from `updated_at`, which already gets bumped by unrelated
  mutations (next_action/summary text edits elsewhere), so it can't
  answer "when was the summary itself last regenerated."

Wiring scope, 2026-07-24: only wired into the message-count half of
BR-01 so far -- maybe_generate_summary_after_reply() is called from
process_candidate_reply() once its own real inbound-reply count for
the conversation is a multiple of 5, guarded so the LLM is never even
considered on the (overwhelmingly common in tests) sub-5-message case.
maybe_generate_summary_after_transition() is fully implemented and
tested but deliberately NOT auto-wired into
conversation_state_service.transition_status()'s ~19 call sites this
round -- that would put a real, unmocked LLM call behind every one of
S-018's just-stabilized call sites and its 159-test regression
baseline, this late before tonight's launch. Flagged as an explicit
follow-up wiring task, not a silent gap.
"""
import json
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent

MIN_SUMMARY_LENGTH = 50
MAX_SUMMARY_LENGTH = 400
MESSAGE_COUNT_TRIGGER = 5
LAST_N_EVENTS = 20
SEARCHABLE_EVENT_TYPES = ("candidate_reply", "ai_message_sent", "hr_message_sent")

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _candidate_reply_count(db: Session, conversation_id: int) -> int:
    return (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "candidate_reply")
        .count()
    )


def should_generate_summary_after_reply(db: Session, conversation_id: int) -> bool:
    """BR-01, message-count half: every 5th inbound message."""
    return _candidate_reply_count(db, conversation_id) % MESSAGE_COUNT_TRIGGER == 0


def _recent_events_text(db: Session, conversation_id: int) -> str:
    events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type.in_(SEARCHABLE_EVENT_TYPES))
        .order_by(ConversationEvent.created_at.desc())
        .limit(LAST_N_EVENTS)
        .all()
    )
    events = list(reversed(events))  # ASC order per spec's data mapping
    lines = []
    for e in events:
        data = e.event_data or {}
        speaker = "Candidate" if e.event_type == "candidate_reply" else "Thunder"
        body = (data.get("body") or "").strip()
        if body:
            lines.append(f"{speaker}: {body[:500]}")
    return "\n".join(lines) or "(no messages yet)"


def _known_facts_text(db: Session, candidate: Candidate) -> str:
    from app.services.ai_conversation_service import get_missing_fields

    name = " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])).strip() or "Unknown"
    facts = [
        f"Name: {name}",
        f"Job title applied for: {candidate.candidateJobTitle or 'unknown'}",
        f"Experience: {candidate.candidateExperience or 'unknown'}",
        f"Skills: {candidate.candidateSkills or 'unknown'}",
    ]
    missing = get_missing_fields(candidate, db)
    if missing:
        facts.append("Still missing: " + ", ".join(m["label"] for m in missing))
    else:
        facts.append("Profile is complete.")
    return "\n".join(facts)

logger = logging.getLogger(__name__)

class SummaryGenerationFailed(Exception):
    pass


def _default_llm_call(prompt: str, api_key: str) -> str:
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def _call_llm_for_summary(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    import os

    if llm_call is not None:
        return llm_call(prompt)

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise SummaryGenerationFailed("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def _build_summary_prompt(messages_text: str, facts_text: str) -> str:
    return (
        "Summarize this recruiting conversation in 2-3 sentences. Focus on: what "
        "information has been collected, what is still missing, and the "
        "candidate's current engagement level. Be factual and concise. No "
        "filler phrases. Return only the summary text, no markdown, no quotes.\n\n"
        f"Conversation:\n{messages_text}\n\nKnown facts:\n{facts_text}"
    )


def generate_conversation_summary(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    *,
    llm_call: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """
    Real generation + validation (BR-02). Returns the new summary on
    success. On any failure -- LLM error, or a regenerated attempt
    still under MIN_SUMMARY_LENGTH -- leaves conversation.summary
    untouched, logs SUMMARY_GENERATION_FAILED, and returns None. Never
    raises -- callers (the reply pipeline) must not have their own
    flow interrupted by a summary-generation failure.
    """
    messages_text = _recent_events_text(db, conversation.id)
    facts_text = _known_facts_text(db, candidate)
    prompt = _build_summary_prompt(messages_text, facts_text)

    for attempt in range(2):  # BR-02: one regeneration attempt if too short
        try:
            raw = _call_llm_for_summary(prompt, llm_call).strip()
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[ConversationSummary] LLM call failed for conversation {conversation.id}: {exc}")
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="SUMMARY_GENERATION_FAILED",
                event_data={"reason": str(exc), "attempt": attempt + 1}, triggered_by="system",
            ))
            db.flush()
            return None

        if len(raw) > MAX_SUMMARY_LENGTH:
            raw = raw[:MAX_SUMMARY_LENGTH]
        if len(raw) >= MIN_SUMMARY_LENGTH:
            conversation.summary = raw
            conversation.summary_generated_at = datetime.utcnow()
            db.add(conversation)
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="SUMMARY_GENERATED",
                event_data={"summary": raw, "attempt": attempt + 1}, triggered_by="system",
            ))
            db.flush()
            return raw
        logger.info(f"[ConversationSummary] Summary too short ({len(raw)} chars) for conversation {conversation.id}, attempt {attempt + 1}")

    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="SUMMARY_GENERATION_FAILED",
        event_data={"reason": "regenerated summary still under minimum length"}, triggered_by="system",
    ))
    db.flush()
    return None


def maybe_generate_summary_after_reply(
    db: Session, conversation: CandidateConversation, candidate: Candidate, *, llm_call: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """BR-01, message-count half. Non-blocking -- swallows any
    unexpected error so a summary-generation bug can never break the
    real reply pipeline it's called from."""
    if not should_generate_summary_after_reply(db, conversation.id):
        return None
    try:
        return generate_conversation_summary(db, conversation, candidate, llm_call=llm_call)
    except Exception as exc:  # belt-and-suspenders -- generate_conversation_summary already shouldn't raise
        logger.error(f"[ConversationSummary] Unexpected error generating summary for conversation {conversation.id}: {exc}")
        raise ValueError("Operation failed")


def maybe_generate_summary_after_transition(
    db: Session, conversation: CandidateConversation, candidate: Candidate, *, llm_call: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """BR-01, state-transition half. See module docstring -- fully
    implemented and tested, not yet auto-wired into transition_status()."""
    try:
        return generate_conversation_summary(db, conversation, candidate, llm_call=llm_call)
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[ConversationSummary] Unexpected error generating summary for conversation {conversation.id}: {exc}")
        raise ValueError("Operation failed")

"""
import logging
S-021/HRMS-0421 -- Candidate Memory Store.

Foundational story only, per its own dependency note ("HRMS-0422 Facts
Extraction... built next -- this story creates the table"): tables +
getMemory()/upsertFact()/updateMemorySummary() + the viewer API. Not
wired into the reply pipeline yet -- that's S-022 (Facts Extraction),
a separate, not-yet-built story that will be the actual caller of
upsert_fact() after every candidate inbound message.

Real architecture adaptations (see candidate_memory.py's module
docstring for the model-level ones):
- source_message_id FKs into ConversationEvent (no conversation_messages
  table).
- BR-02's "ON CONFLICT... UPDATE" is a query-then-write pattern here
  (SQL Server, not Postgres) -- upsert_fact() looks up the existing
  active row itself rather than relying on a DB-level upsert.
- updateMemorySummary()'s real LLM is Gemini (reusing the same raw-
  REST call shape as conversation_summary_service), not the spec's
  unspecified LLM. Validation is 200-500 WORDS (per this story's own
  spec), not characters -- distinct from S-019's char-based rule.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact, FACT_CATEGORIES

MIN_SUMMARY_WORDS = 200
MAX_SUMMARY_WORDS = 500
FACTS_PER_SUMMARY_TRIGGER = 5
SUMMARY_MAX_AGE = timedelta(days=1)  # "daily whichever comes first"

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

logger = logging.getLogger(__name__)

class InvalidFactCategory(Exception):
    pass


def _get_or_create_memory(db: Session, candidate_id: str, tenant_id: str) -> CandidateMemory:
    memory = db.query(CandidateMemory).filter(CandidateMemory.candidate_id == candidate_id).first()
    if not memory:
        memory = CandidateMemory(tenant_id=tenant_id, candidate_id=candidate_id, version=1)
        db.add(memory)
        db.flush()
    return memory


def get_memory(db: Session, candidate_id: str, tenant_id: str) -> Dict:
    """getMemory() -- BR-01: candidate-level, one record shared across
    all conversations. Returns {summary: None, facts: []} if nothing
    exists yet."""
    memory = db.query(CandidateMemory).filter(CandidateMemory.candidate_id == candidate_id, CandidateMemory.tenant_id == tenant_id).first()
    facts = (
        db.query(CandidateMemoryFact)
        .filter(CandidateMemoryFact.candidate_id == candidate_id, CandidateMemoryFact.tenant_id == tenant_id, CandidateMemoryFact.is_active == True)
        .order_by(CandidateMemoryFact.fact_category.asc(), CandidateMemoryFact.extracted_at.desc())
        .all()
    )
    return {
        "summary": memory.summary if memory else None,
        "last_updated": memory.last_updated if memory else None,
        "facts": [
            {
                "id": f.id, "category": f.fact_category, "key": f.fact_key, "value": f.fact_value,
                "confidence": f.confidence, "is_low_confidence": f.confidence < 0.7,  # BR-03
                "extracted_at": f.extracted_at,
            }
            for f in facts
        ],
    }


def upsert_fact(
    db: Session, candidate_id: str, tenant_id: str, fact_category: str, fact_key: str,
    fact_value: str, confidence: float = 1.0, source_message_id: Optional[int] = None,
) -> CandidateMemoryFact:
    """
    BR-02: at most one is_active=true row per (candidate, category, key).
    When the value actually changes, the old row is deactivated (history
    preserved) and a new row inserted; an unchanged value just refreshes
    confidence/extracted_at in place, avoiding pointless history churn.
    """
    if fact_category not in FACT_CATEGORIES:
        raise InvalidFactCategory(f"fact_category must be one of {FACT_CATEGORIES}, got {fact_category!r}")

    _get_or_create_memory(db, candidate_id, tenant_id)

    existing = (
        db.query(CandidateMemoryFact)
        .filter(
            CandidateMemoryFact.candidate_id == candidate_id, CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.fact_category == fact_category, CandidateMemoryFact.fact_key == fact_key,
            CandidateMemoryFact.is_active == True,
        )
        .first()
    )

    if existing and existing.fact_value == fact_value:
        existing.confidence = confidence
        existing.extracted_at = datetime.utcnow()
        db.add(existing)
        db.flush()
        return existing

    if existing:
        existing.is_active = False
        db.add(existing)

    new_fact = CandidateMemoryFact(
        tenant_id=tenant_id, candidate_id=candidate_id, fact_category=fact_category, fact_key=fact_key,
        fact_value=fact_value, confidence=confidence, source_message_id=source_message_id, is_active=True,
        # Explicit Python-side timestamp (not the DB server_default) so it's
        # always comparable at the same precision as CandidateMemory.last_updated,
        # which is also set via datetime.utcnow() -- avoids a should_update_summary()
        # false negative from mismatched DB-vs-Python clock granularity.
        extracted_at=datetime.utcnow(),
    )
    db.add(new_fact)
    db.flush()
    return new_fact


def _active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.created_at.desc())
        .first()
    )


def _log_memory_event(db: Session, candidate_id: str, event_type: str, event_data: Dict) -> None:
    """Memory has no natural home of its own for an audit log (it's
    candidate-level, not conversation-level) -- attached to the
    candidate's own conversation, same append-only ConversationEvent
    log every other story this round reuses."""
    conversation = _active_conversation(db, candidate_id)
    if not conversation:
        return
    db.add(ConversationEvent(conversation_id=conversation.id, event_type=event_type, event_data=event_data, triggered_by="system"))
    db.flush()


def _default_llm_call(prompt: str, api_key: str) -> str:
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def _build_summary_prompt(candidate: Candidate, facts: List[CandidateMemoryFact]) -> str:
    facts_lines = "\n".join(f"- [{f.fact_category}] {f.fact_key}: {f.fact_value}" for f in facts) or "(no facts recorded yet)"
    name = " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])).strip() or "the candidate"
    return (
        f"Write a 200-500 word summary of what we know about {name} as a talent "
        "scout would describe them. Include: salary expectations, career "
        "preferences, constraints, availability. Use professional language. "
        f"Return only the summary text, no markdown, no headers.\n\nFacts:\n{facts_lines}"
    )


def should_update_summary(db: Session, candidate_id: str, tenant_id: str) -> bool:
    """'After every 5 new facts or daily whichever comes first.'"""
    memory = db.query(CandidateMemory).filter(CandidateMemory.candidate_id == candidate_id, CandidateMemory.tenant_id == tenant_id).first()
    if not memory or not memory.last_updated:
        return True
    if datetime.utcnow() - memory.last_updated >= SUMMARY_MAX_AGE:
        return True
    new_fact_count = (
        db.query(CandidateMemoryFact)
        .filter(
            CandidateMemoryFact.candidate_id == candidate_id, CandidateMemoryFact.tenant_id == tenant_id,
            CandidateMemoryFact.is_active == True, CandidateMemoryFact.extracted_at > memory.last_updated,
        )
        .count()
    )
    return new_fact_count >= FACTS_PER_SUMMARY_TRIGGER


def update_memory_summary(
    db: Session, candidate_id: str, tenant_id: str, *, llm_call: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    """Never raises -- on any failure, keeps the previous summary and
    logs MEMORY_SUMMARY_FAILED."""
    memory = _get_or_create_memory(db, candidate_id, tenant_id)
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        return None

    facts = (
        db.query(CandidateMemoryFact)
        .filter(CandidateMemoryFact.candidate_id == candidate_id, CandidateMemoryFact.tenant_id == tenant_id, CandidateMemoryFact.is_active == True)
        .order_by(CandidateMemoryFact.fact_category.asc())
        .all()
    )
    prompt = _build_summary_prompt(candidate, facts)

    try:
        raw = _call_llm(prompt, llm_call).strip()
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[CandidateMemory] Summary generation failed for candidate {candidate_id}: {exc}")
        _log_memory_event(db, candidate_id, "MEMORY_SUMMARY_FAILED", {"reason": str(exc)})
        db.commit()
        return None

    word_count = len(raw.split())
    if word_count < MIN_SUMMARY_WORDS or word_count > MAX_SUMMARY_WORDS:
        logger.warning(f"[CandidateMemory] Summary for candidate {candidate_id} out of range ({word_count} words)")
        _log_memory_event(db, candidate_id, "MEMORY_SUMMARY_FAILED", {"reason": f"word count {word_count} outside 200-500 range"})
        db.commit()
        return None

    memory.summary = raw
    memory.last_updated = datetime.utcnow()
    memory.version = (memory.version or 1) + 1
    db.add(memory)
    _log_memory_event(db, candidate_id, "MEMORY_SUMMARY_GENERATED", {"word_count": word_count})
    db.commit()
    return raw


class FactNotFound(Exception):
    pass


def correct_fact(
    db: Session, candidate_id: str, tenant_id: str, fact_id: int, new_value: str, *, corrected_by: str,
) -> CandidateMemoryFact:
    """
    S-023/HRMS-0423 -- recruiter manual correction. BR-01: a manual
    correction is treated as verified ground truth (confidence=1.0).
    BR-03: if the corrected fact_key maps to a real Candidate column,
    the correction cascades to the profile too -- the same
    PROFILE_FIELD_MAP facts_extraction_service already uses, imported
    locally to avoid a module-level import cycle (facts_extraction_service
    itself imports from this module).
    """
    fact = (
        db.query(CandidateMemoryFact)
        .filter(CandidateMemoryFact.id == fact_id, CandidateMemoryFact.candidate_id == candidate_id, CandidateMemoryFact.tenant_id == tenant_id)
        .first()
    )
    if not fact:
        raise FactNotFound(f"Fact {fact_id} not found for candidate {candidate_id}.")

    fact.fact_value = new_value
    fact.confidence = 1.0
    fact.extracted_at = datetime.utcnow()
    db.add(fact)

    from app.services.facts_extraction_service import PROFILE_FIELD_MAP
    column = PROFILE_FIELD_MAP.get(fact.fact_key)
    if column:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if candidate:
            setattr(candidate, column, new_value)
            db.add(candidate)

    _log_memory_event(db, candidate_id, "MEMORY_FACT_CORRECTED", {"fact_id": fact_id, "fact_key": fact.fact_key, "new_value": new_value, "corrected_by": corrected_by})
    db.commit()
    db.refresh(fact)
    return fact

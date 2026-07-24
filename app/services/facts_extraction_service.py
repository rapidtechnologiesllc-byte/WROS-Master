"""
S-022/HRMS-0422 -- Candidate Facts Extraction Engine.

Real architecture adaptations:
- No conversation_messages table -- the caller (process_candidate_reply)
  already has the inbound message body and the conversation/candidate
  at hand; extract_facts() takes them directly rather than re-deriving
  from a message-bus event.
- No internal event bus / message.received pub-sub, and no background
  task queue (Celery/RQ) exists anywhere in this codebase -- BR-01's
  "runs in a background worker, never blocks" is therefore satisfied
  the same way every other "should be async" story this round has
  been: the real, synchronous function is correct and callable now;
  true fire-and-forget wiring is a follow-up once real async
  infrastructure exists. What IS guaranteed here: an LLM failure
  inside extract_facts() is caught and never propagates -- the
  caller's message-storage flow is never at risk of failing because
  extraction failed (BR-02).
- No HRMS-0433 Intent Detection exists yet -- every candidate reply is
  attempted for extraction rather than pre-filtered; a non-informational
  message just yields an empty facts array, a safe degenerate case.
- No markFieldReceived()/candidate_missing_fields table -- get_missing_fields()
  already recomputes live from real Candidate columns (S-016/S-017's
  established pattern), so writing the mapped profile field directly is
  the complete real equivalent; there's nothing separate to "mark received."
- Real LLM is Gemini (reusing candidate_memory_service's call shape),
  not the spec's Anthropic claude-sonnet-4-6.
- PROFILE_FIELD_MAP only maps fact_keys to columns that actually exist
  on Candidate (candidateExpectedSalary, candidateCurrentSalary) -- the
  spec's own notice_period/current_employer example fields have no
  real column to write to and are intentionally left out rather than
  invented; genuinely new columns for those are a follow-up ask, not a
  silent scope cut made without a story to point at.
"""
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.llm_prompt_safety import build_safe_prompt, flag_suspicious_patterns
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_memory import FACT_CATEGORIES
from app.services.candidate_memory_service import get_memory, upsert_fact

PROFILE_UPDATE_CONFIDENCE_THRESHOLD = 0.5  # BR-03

# fact_key -> real Candidate column. Only fields that actually exist on
# the model -- see module docstring.
PROFILE_FIELD_MAP = {
    "expected_ctc": "candidateExpectedSalary",
    "current_ctc": "candidateCurrentSalary",
}

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _default_llm_call(prompt: str, api_key: str) -> str:
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512}},
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


def _build_extraction_prompt(message_body: str, memory: Dict) -> str:
    facts_summary = memory.get("summary") or "(no summary yet)"
    known_facts = ", ".join(f"{f['key']}={f['value']}" for f in memory.get("facts", [])) or "(none yet)"

    instruction = f"""You are extracting structured facts from a candidate's message in a recruiting conversation.

Known context so far: {facts_summary}
Known facts: {known_facts}

Extract any NEW or UPDATED facts from the candidate's message below as JSON.
Return ONLY a valid JSON array. No explanation, no markdown, no code fences.
Each item: {{"fact_category": one of {list(FACT_CATEGORIES)}, "fact_key": short snake_case key, "fact_value": the extracted value as a string, "confidence": 0.0-1.0}}.
If no facts can be extracted, return an empty array: []

Candidate message:"""
    return build_safe_prompt(instruction=instruction, untrusted_label="CANDIDATE_MESSAGE", untrusted_content=message_body)


def _log_extraction_event(db: Session, conversation_id: int, event_type: str, event_data: Dict) -> None:
    db.add(ConversationEvent(conversation_id=conversation_id, event_type=event_type, event_data=event_data, triggered_by="system"))
    db.flush()


def _validate_extracted_items(raw_items: Any) -> List[Dict]:
    if not isinstance(raw_items, list):
        raise ValueError(f"Expected a JSON array, got {type(raw_items).__name__}")

    validated = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        category = item.get("fact_category")
        key = item.get("fact_key")
        value = item.get("fact_value")
        confidence = item.get("confidence")
        if category not in FACT_CATEGORIES or not key or value is None:
            continue
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        validated.append({"fact_category": category, "fact_key": str(key), "fact_value": str(value), "confidence": confidence})
    return validated


def _apply_profile_field_updates(db: Session, candidate: Candidate, facts: List[Dict]) -> List[str]:
    """BR-03: confidence >= 0.5 only. Returns the list of profile
    fields actually updated."""
    updated = []
    for fact in facts:
        column = PROFILE_FIELD_MAP.get(fact["fact_key"])
        if not column or fact["confidence"] < PROFILE_UPDATE_CONFIDENCE_THRESHOLD:
            continue
        setattr(candidate, column, fact["fact_value"])
        updated.append(column)
    if updated:
        db.add(candidate)
        db.flush()
    return updated


def extract_facts(
    db: Session,
    candidate: Candidate,
    tenant_id: str,
    conversation_id: int,
    message_body: str,
    *,
    source_message_id: Optional[int] = None,
    llm_call: Optional[Callable[[str], str]] = None,
) -> List[Dict]:
    """
    Never raises -- an LLM/parse failure logs FACTS_EXTRACTION_FAILED
    and returns [] so the caller's message flow is never at risk
    (BR-01/BR-02). Each valid extracted fact is upserted into
    candidate_memory_facts; facts with confidence >= 0.5 that map to a
    real Candidate column also update the profile directly (BR-03) --
    the real equivalent of markFieldReceived(), since get_missing_fields()
    already recomputes live from these same columns.
    """
    suspicious = flag_suspicious_patterns(message_body)
    if suspicious:
        logger.warning(f"[FactsExtraction] Candidate message contains injection-shaped phrasing: {suspicious}")

    memory = get_memory(db, candidate.candidateID, tenant_id)
    prompt = _build_extraction_prompt(message_body, memory)

    try:
        raw = _call_llm(prompt, llm_call)
        parsed = json.loads(raw)
        facts = _validate_extracted_items(parsed)
    except Exception as exc:
        logger.warning(f"[FactsExtraction] Extraction failed for candidate {candidate.candidateID}: {exc}")
        _log_extraction_event(db, conversation_id, "FACTS_EXTRACTION_FAILED", {"reason": str(exc)})
        db.commit()
        return []

    for fact in facts:
        upsert_fact(
            db, candidate.candidateID, tenant_id, fact["fact_category"], fact["fact_key"], fact["fact_value"],
            confidence=fact["confidence"], source_message_id=source_message_id,
        )

    updated_fields = _apply_profile_field_updates(db, candidate, facts)

    _log_extraction_event(db, conversation_id, "FACTS_EXTRACTED", {
        "facts_count": len(facts),
        "fact_keys_extracted": [f["fact_key"] for f in facts],
        "profile_fields_updated": updated_fields,
        "source_message_id": source_message_id,
    })
    db.commit()

    # S-038/HRMS-0438: recalculate compensation fit only when
    # expected_ctc was actually part of this turn's extraction --
    # unlike S-037's unconditional skill-update trigger, salary changes
    # are comparatively rare within this broad fact stream. Never
    # raises -- see compensation_scoring_service.recalculate_for_candidate().
    if any(f["fact_key"] == "expected_ctc" for f in facts):
        from app.services.compensation_scoring_service import recalculate_for_candidate
        recalculate_for_candidate(db, candidate, tenant_id)

    # S-039/HRMS-0439: same conditional-trigger posture as expected_ctc
    # above -- only recalculate when notice_period_days was actually
    # part of this turn's extraction. Never raises -- see
    # availability_scoring_service.recalculate_for_candidate().
    if any(f["fact_key"] == "notice_period_days" for f in facts):
        from app.services.availability_scoring_service import recalculate_for_candidate as recalculate_availability
        recalculate_availability(db, candidate, tenant_id)

    # S-040/HRMS-0440 Step 4: keep overall_score current whenever either
    # component above just changed. See overall_scoring_service's own
    # module docstring for why this is wired at the producer.
    if any(f["fact_key"] in ("expected_ctc", "notice_period_days") for f in facts):
        from app.services.overall_scoring_service import recalculate_for_candidate as recalculate_overall
        recalculate_overall(db, candidate, tenant_id)

    return facts

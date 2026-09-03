"""
import logging
S-026/HRMS-0426 -- Candidate Response Parser.

Real architecture adaptation, the important one: the spec assumes
dedicated normalized-integer columns on the candidates table
(current_ctc/expected_ctc in paise/cents, notice_period_days,
total_experience_years as DECIMAL(4,1)). None of those columns exist
here -- the real Candidate model only has candidateExpectedSalary/
candidateCurrentSalary as plain display STRINGS (e.g. "24 LPA"),
already read and shown as human text everywhere else in this app
(candidate profile screens, offer letters). Writing a raw normalized
integer into those columns would silently corrupt that existing real
display usage, not just add a feature.

So BR-01/AC-3's "update the candidates table" is adapted to "upsert
the NORMALIZED, machine-readable value into candidate_memory_facts"
(S-021/S-022's real fact store) instead of a schema change to the
live, widely-used Candidate table this late before launch. This is
exactly what the spec's own downstream consumers actually need --
HRMS-0438/0439 (Compensation Fit Score, Availability Score) read
structured facts, not display strings -- and it's a real, complete,
immediately useful piece of data, not a silent gap. A future story
that adds real notice_period_days/current_ctc columns can migrate
these facts over; documented as a follow-up, not decided unilaterally
here.

Also NOT wired into run_qualification_turn()/process_candidate_reply()
this round: S-024's real QUALIFICATION_QUESTIONS catalog only covers
this codebase's actual 12 tracked missing fields (mobile, gender, DOB,
location, joining date, experience, job title, marital status,
nationality, address) -- none of which are salary/notice-period, the
exact fields this story's normalization exists for. There is no live
call site asking about salary/notice-period yet, so wiring this into
the reply loop now would have nothing real to attach to. Built and
tested standalone, ready to be called once a future story asks these
questions (or once HRMS-0438/0439 need the data directly).

Step 1's LLM extraction is Gemini (reusing the established call
shape), not the spec's unspecified LLM. Step 2's normalization rules
are deterministic (regex-based), not LLM calls, matching the spec's
own "field-specific normalization rules" framing.
"""
import os
import re
from typing import Callable, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.services.candidate_memory_service import upsert_fact

CONFIDENCE_THRESHOLD = 0.6  # BR-01
MAX_CLARIFICATIONS_PER_FIELD = 1  # BR-03

# Canonical parser field names -> (memory fact_category, fact_key). These
# are logical identifiers this story's normalization targets, not
# necessarily literal columns on any table -- see module docstring.
FIELD_CATEGORY = {
    "current_ctc": "SALARY",
    "expected_ctc": "SALARY",
    "notice_period_days": "AVAILABILITY",
    "total_experience_years": "SKILL",
    "location": "PERSONAL",
    "skills": "SKILL",
}

CLARIFICATION_MESSAGES = {
    "notice_period_days": "Could you share your notice period in days or weeks? For example: 30 days, 2 weeks, or 3 months.",
    "current_ctc": "Could you share your current salary as a number? For example: 18 LPA or $120,000 per year.",
    "expected_ctc": "Could you share your expected salary as a number? For example: 24 LPA or $150,000 per year.",
    "total_experience_years": "Could you share your total years of professional experience as a number, e.g. 5 years, or 3 years 6 months?",
}

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

_NUMBER_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _first_number(text: str) -> Optional[float]:
    match = _NUMBER_RE.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        raise ValueError("Operation failed")


def normalize_notice_period_days(raw_value: str) -> Optional[int]:
    text = (raw_value or "").lower().strip()
    if not text:
        return None
    if "immediate" in text:
        return 0
    number = _first_number(text)
    if number is None:
        return None
    if "week" in text:
        return int(round(number * 7))
    if "month" in text:
        return int(round(number * 30))
    return int(round(number))  # default: already days


def normalize_salary(raw_value: str) -> Optional[int]:
    """Returns the value in the smallest local currency unit (paise
    for LPA/lakh phrasing, cents for $/k phrasing) -- BR-02. No
    cross-currency conversion (out of scope per spec section 9)."""
    text = (raw_value or "").lower().strip()
    if not text:
        return None
    number = _first_number(text)
    if number is None:
        return None

    # Check lakh/LPA phrasing before the generic "k" (shorthand for
    # thousand) check -- "lakhs" itself contains the letter "k" and
    # would otherwise be misread as dollar-shorthand.
    if "lpa" in text or "lakh" in text or "lac" in text:
        return int(round(number * 100000 * 100))  # LPA -> rupees -> paise

    if "$" in text or "usd" in text or re.search(r"\d\s*k\b", text):
        if re.search(r"\d\s*k\b", text) and number < 10000:  # "$120k" -> 120 * 1000
            number *= 1000
        return int(round(number * 100))  # dollars -> cents

    # Bare number with no unit -- assume it's already in the major unit
    # (rupees/dollars) and convert to the smallest unit.
    return int(round(number * 100))


def normalize_experience_years(raw_value: str) -> Optional[float]:
    text = (raw_value or "").lower().strip()
    if not text:
        return None
    years_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*year", text)
    months_match = re.search(r"(\d+(?:\.\d+)?)\s*month", text)
    if years_match:
        years = float(years_match.group(1))
        if months_match:
            years += float(months_match.group(1)) / 12.0
        return round(years, 1)
    number = _first_number(text)
    return round(number, 1) if number is not None else None


NORMALIZERS: Dict[str, Callable[[str], Optional[Union[int, float]]]] = {
    "notice_period_days": normalize_notice_period_days,
    "current_ctc": normalize_salary,
    "expected_ctc": normalize_salary,
    "total_experience_years": normalize_experience_years,
}


def normalize_value(field_name: str, raw_value: str) -> Optional[Union[int, float, str]]:
    normalizer = NORMALIZERS.get(field_name)
    if normalizer is None:
        return raw_value  # location/skills/etc. -- stored as-is per spec section 9
    return normalizer(raw_value)


def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100}},
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


def _extract_raw_value(field_name: str, message_body: str, llm_call: Optional[Callable[[str], str]]) -> Dict:
    field_label = field_name.replace("_", " ")
    prompt = (
        f"Extract the {field_label} from this candidate message. "
        'Return ONLY valid JSON: {"value": string, "confidence": 0.0-1.0}. '
        'If the value cannot be determined: {"value": null, "confidence": 0.0}.\n\n'
        f"Message: {message_body}"
    )
    import json
    raw = _call_llm(prompt, llm_call)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or "value" not in parsed or "confidence" not in parsed:
        raise ValueError(f"LLM response missing required keys: {parsed!r}")
    confidence = float(parsed["confidence"])
    return {"value": parsed["value"], "confidence": max(0.0, min(1.0, confidence))}


def _clarification_count(db: Session, conversation_id: int, field_name: str) -> int:
    events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "CLARIFICATION_REQUESTED")
        .all()
    )
    return sum(1 for e in events if (e.event_data or {}).get("field_name") == field_name)


def parse_field_response(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    tenant_id: str,
    field_name: str,
    message_body: str,
    *,
    llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """
    Never raises. Returns one of:
      {"outcome": "parsed", "normalized_value": ..., "confidence": ...}
      {"outcome": "clarification_requested", "message": ...}
      {"outcome": "accepted_low_confidence", "raw_value": ...}  (BR-03, 2nd low-confidence answer)
      {"outcome": "parse_failed"}  (BR: LLM/parse failure, profile untouched)
    """
    try:
        extracted = _extract_raw_value(field_name, message_body, llm_call)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[ResponseParser] Parse failed for field {field_name}, candidate {candidate.candidateID}: {exc}")
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="PARSE_API_FAILED",
            event_data={"field_name": field_name, "reason": str(exc)}, triggered_by="system",
        ))
        db.commit()
        return {"outcome": "parse_failed"}

    raw_value = extracted["value"]
    confidence = extracted["confidence"]

    if raw_value is not None and confidence >= CONFIDENCE_THRESHOLD:  # BR-01
        normalized = normalize_value(field_name, raw_value)
        category = FIELD_CATEGORY.get(field_name, "PERSONAL")
        upsert_fact(db, candidate.candidateID, tenant_id, category, field_name, str(normalized), confidence=confidence)
        db.commit()
        return {"outcome": "parsed", "normalized_value": normalized, "confidence": confidence}

    # Low confidence (or no value extracted) -- BR-01/BR-03.
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="PARSE_LOW_CONFIDENCE",
        event_data={"field_name": field_name, "raw_value": raw_value, "confidence": confidence}, triggered_by="system",
    ))

    prior_clarifications = _clarification_count(db, conversation.id, field_name)
    if prior_clarifications >= MAX_CLARIFICATIONS_PER_FIELD:
        # BR-03: second low-confidence answer -- accept as-is into memory, move on.
        category = FIELD_CATEGORY.get(field_name, "PERSONAL")
        if raw_value is not None:
            upsert_fact(db, candidate.candidateID, tenant_id, category, field_name, str(raw_value), confidence=confidence)
        db.commit()
        return {"outcome": "accepted_low_confidence", "raw_value": raw_value}

    clarification_message = CLARIFICATION_MESSAGES.get(field_name, f"Could you clarify your {field_name.replace('_', ' ')}?")
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="CLARIFICATION_REQUESTED",
        event_data={"field_name": field_name, "original_message": message_body[:500]}, triggered_by="system",
    ))
    db.commit()
    return {"outcome": "clarification_requested", "message": clarification_message}

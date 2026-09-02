"""
import logging
S-024/HRMS-0424 -- Candidate Qualification Questionnaire Engine.

Real architecture adaptations:
- No standalone getNextMissingField() -- get_next_missing_field() here
  is a thin wrapper over the real, already-established
  ai_conversation_service.get_missing_fields(), which already returns
  fields in priority order (CANDIDATE_CORE_FIELDS then INFO_FORM_FIELDS,
  in the order those constants are declared). This story does NOT
  invent a second, competing missing-fields list.
- The spec's own question-catalog example (resume_url, phone,
  notice_period_days, current_ctc, expected_ctc, location,
  current_employer, total_experience_years, skills, email) doesn't map
  1:1 onto this codebase's real tracked fields -- QUALIFICATION_QUESTIONS
  below is keyed to the REAL field names get_missing_fields() actually
  returns (candidateMobile, candidateGender, ... marital_status,
  nationality, permanent_address), in the same warm/professional voice
  the spec's examples use.
- No candidate_missing_fields table exists (fields are computed live
  from real Candidate/CandidateInfoForm columns), so "SKIPPED" can't be
  a status column update. A new, small CandidateFieldSkip table tracks
  per-candidate skipped field names instead; get_next_missing_field()
  filters the shared get_missing_fields() output against it. This
  deliberately does NOT touch get_missing_fields() itself -- that
  function is relied on by ~10 other already-shipped, heavily-tested
  stories (S-011/S-014/S-016/S-017/S-021/S-022) this round, and
  widening its own contract this late carries real regression risk.
  One real, documented scope cut follows from this: a skipped field
  still counts as "missing" in every OTHER completeness view (recruiter
  dashboard, candidate portal progress bar) that calls
  get_missing_fields() directly -- only this engine's own field
  selection treats it as done. Flagged as a follow-up, not a silent gap.
- BR-01's QUALIFYING state maps onto this codebase's real
  CandidateConversation fields: status != "closed" AND escalation_state
  not in ("pending", "escalated") -- the real equivalent of "actively
  being qualified, not yet closed or handed to a human" (same mapping
  philosophy S-018/S-020 already established for this fictional enum).
- LLM is Gemini (reusing the established call shape), not the spec's
  unspecified LLM; question-variation failure falls back to the base
  catalog question and logs QUESTION_VARIATION_FAILED, never crashes.
"""
import os
import re
from typing import Callable, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.services.ai_conversation_service import (
    DEFAULT_THUNDER_PERSONA_TEXT,
    get_missing_fields,
)

MAX_ASKS_BEFORE_AUTO_SKIP = 2  # BR-02

# Keyed to the REAL fields get_missing_fields() returns -- see module docstring.
QUALIFICATION_QUESTIONS: Dict[str, str] = {
    "candidateMobile": "To stay in touch easily, could you share your phone number (with country code)?",
    "candidateGender": "Could you share your gender for our records?",
    "candidateDateOfBirth": "Could you share your date of birth?",
    "candidateCurrentLocation": "Where are you currently based, and are you open to relocation?",
    "candidateJoiningDate": "What's your expected joining date if things move forward?",
    "candidateExperience": "How many years of professional experience do you have in total?",
    "candidateJobTitle": "What role or job title are you looking for next?",
    "marital_status": "Could you share your marital status for our records?",
    "nationality": "Could you share your nationality?",
    "permanent_address": "Could you share your permanent address (city, state, country)?",
}

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

logger = logging.getLogger(__name__)

class QualificationNotApplicable(Exception):
    """BR-01: conversation is not in a qualifying state."""


def _default_llm_call(prompt: str, api_key: str) -> str:
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 150}},
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


def is_qualifying_state(conversation: CandidateConversation) -> bool:
    """BR-01, real-state mapping -- see module docstring."""
    if conversation.status == "closed":
        return False
    if conversation.escalation_state in ("pending", "escalated"):
        return False
    return True


def skipped_field_names(db: Session, candidate_id: str, tenant_id: str) -> List[str]:
    rows = (
        db.query(CandidateFieldSkip)
        .filter(CandidateFieldSkip.candidate_id == candidate_id, CandidateFieldSkip.tenant_id == tenant_id)
        .all()
    )
    return [r.field_name for r in rows]


def skip_field(db: Session, candidate_id: str, tenant_id: str, field_name: str) -> None:
    existing = (
        db.query(CandidateFieldSkip)
        .filter(CandidateFieldSkip.candidate_id == candidate_id, CandidateFieldSkip.tenant_id == tenant_id, CandidateFieldSkip.field_name == field_name)
        .first()
    )
    if existing:
        return
    db.add(CandidateFieldSkip(candidate_id=candidate_id, tenant_id=tenant_id, field_name=field_name))
    db.flush()


def get_next_missing_field(db: Session, candidate: Candidate, tenant_id: str) -> Optional[Dict[str, str]]:
    """The real getNextMissingField() -- get_missing_fields() output,
    minus anything explicitly skipped, first item = highest priority."""
    missing = get_missing_fields(candidate, db)
    skipped = set(skipped_field_names(db, candidate.candidateID, tenant_id))
    remaining = [m for m in missing if m["field"] not in skipped]
    return remaining[0] if remaining else None


def _ask_count(db: Session, conversation_id: int, field_name: str) -> int:
    events = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "QUESTION_ASKED")
        .all()
    )
    return sum(1 for e in events if (e.event_data or {}).get("field_name") == field_name)


def generate_qualification_question(
    db: Session, conversation: CandidateConversation, field_name: str, *, llm_call: Optional[Callable[[str], str]] = None,
) -> str:
    """BR-03: variations must still sound like Thunder -- the persona
    text is included in the rephrase prompt."""
    base_question = QUALIFICATION_QUESTIONS.get(field_name, f"Could you share your {field_name.replace('_', ' ')}?")
    prior_asks = _ask_count(db, conversation.id, field_name)

    question_text = base_question
    if prior_asks >= 1:
        prompt = (
            f"You are Thunder, a recruiter at BlitzenX. Your persona: {DEFAULT_THUNDER_PERSONA_TEXT}\n"
            f"Rephrase this question in a slightly different way, acknowledging you asked before "
            f"but didn't get a response: \"{base_question}\". Keep it warm and professional. "
            "Maximum 2 sentences. Return only the question text."
        )
        try:
            question_text = _call_llm(prompt, llm_call).strip() or base_question
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[QualificationEngine] Question variation failed for {field_name}: {exc}")
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="QUESTION_VARIATION_FAILED",
                event_data={"field_name": field_name, "reason": str(exc)}, triggered_by="system",
            ))
            question_text = base_question

    ask_count = prior_asks + 1
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="QUESTION_ASKED",
        event_data={"field_name": field_name, "question_text": question_text, "ask_count": ask_count},
        triggered_by="ai_agent",
    ))
    db.flush()
    return question_text


def get_qualification_plan(
    db: Session, conversation: CandidateConversation, candidate: Candidate, tenant_id: str, *, llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """The single function HRMS-0425 (AI Qualification Conversation
    Engine, not yet built) calls to know what Thunder should ask next.
    Raises QualificationNotApplicable when BR-01's state gate fails --
    callers should catch this and simply not run qualification, not
    treat it as an error."""
    if not is_qualifying_state(conversation):
        raise QualificationNotApplicable(f"Conversation {conversation.id} is not in a qualifying state (status={conversation.status!r}, escalation_state={conversation.escalation_state!r}).")

    field = get_next_missing_field(db, candidate, tenant_id)
    while field is not None:
        ask_count_so_far = _ask_count(db, conversation.id, field["field"])
        if ask_count_so_far >= MAX_ASKS_BEFORE_AUTO_SKIP:  # BR-02
            skip_field(db, candidate.candidateID, tenant_id, field["field"])
            field = get_next_missing_field(db, candidate, tenant_id)
            continue
        break

    if field is None:
        return {"is_complete": True, "next_field": None, "question": None, "remaining_fields_count": 0}

    question = generate_qualification_question(db, conversation, field["field"], llm_call=llm_call)
    remaining_count = len(get_missing_fields(candidate, db)) - len(skipped_field_names(db, candidate.candidateID, tenant_id))
    return {
        "is_complete": False,
        "next_field": field["field"],
        "question": question,
        "remaining_fields_count": max(0, remaining_count),
    }

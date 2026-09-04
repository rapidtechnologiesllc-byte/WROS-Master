"""
import logging
S-072/HRMS-0472 -- Objection Handling Engine.

Real architecture reuse: "objecting" was already a defined VALID_INTENT
in detect_intent_service (S-033), routed to this exact story's own
name and marked NOT_BUILT -- this module is the real handler S-033
always pointed to. FACT_CATEGORIES already includes "OBJECTION"
(S-021) -- no schema change needed for either. Uses
prompt_framework_service.build_prompt()/call_llm() directly, calling
call_llm() with hand-built system/user prompts rather than a
registered PROMPT_TEMPLATES entry -- build_prompt()'s placeholder
system is designed around the candidate-context template shape
(missing_fields, next_question, ...), a poor fit for this story's
short, dynamically-composed classification/response prompts;
call_llm() itself only uses prompt_type as a PromptExecutionLog label,
it doesn't require a registered template (confirmed by reading its
own body).

Real wiring: detect_intent() was itself "not wired into any live
inbound path" (S-033's own module docstring). Wired here, for the
first time, into public_chat_service.send_public_chat_message() (the
ONE genuinely live real-time inbound loop in this codebase), right
after the existing S-035 escalation check and before the normal
reply-generation path -- if intent=="objecting", handle_objection()
replaces generate_thunder_reply_with_fallback() for that turn.

BR-01's "3+ times = escalate" count comes from a real, new
OBJECTION_RAISED ConversationEvent logged on every call -- NOT
candidate_memory_facts, whose own upsert_fact() dedupes to at most one
active row per (candidate, category, key) (see that function's own
BR-02 versioning docstring), so it cannot answer "how many times in
THIS conversation" by itself.

BR-02 (never quote specific salary numbers): this codebase has no
job.salary_range "shareable" flag anywhere -- Jobs.salaryRange is a
free-text string with no visibility/shareability column at all
(checked directly). The safe default is therefore always "not
shareable": the SALARY objection type never reaches the LLM at all,
it short-circuits straight to the safe fallback line below -- provably
correct rather than a post-generation filter trying to catch a number
the model might still slip through.

Step 1's taxonomy below is copied verbatim from this story's own spec
-- flagged for explicit Lead BA sign-off before going live to real
candidates, same posture as S-029's synonym library / S-055's
DEFAULT_FAQ_CONTENT / S-067's joining-instructions template.
"""
import logging
import json
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.services import candidate_context_service, prompt_framework_service
from app.services.candidate_memory_service import upsert_fact

OBJECTION_TAXONOMY = {
    "SALARY": "concerns about compensation ('salary too low', 'looking for more', 'not matching expectations')",
    "LOCATION": "concerns about work location ('not relocating', 'prefer remote', 'too far from home')",
    "ROLE_FIT": "concerns about the role ('not my area', 'different domain', 'not what I expected')",
    "TIMING": "not ready to move ('happy where I am', 'just got a raise', 'committed to current project')",
    "COMPANY": "concerns about BlitzenX ('not familiar with company', 'what do you do?')",
    "PROCESS": "concerns about the hiring process ('too many rounds', 'when will I hear back?')",
    "OTHER": "any objection that doesn't fit above",
}
OBJECTION_TYPES = tuple(OBJECTION_TAXONOMY.keys())

MAX_SAME_OBJECTION_BEFORE_ESCALATE = 3  # BR-01

SAFE_FALLBACK_MESSAGE = "I understand your concern. Let me have one of our team members follow up with you on this."
SALARY_NO_NUMBERS_MESSAGE = "Let me connect you with our team to discuss compensation in detail."  # BR-02

logger = logging.getLogger(__name__)

class ObjectionEscalatedError(Exception):
    """BR-01: caller (public_chat_service) should treat this the same
    as any other real escalation -- conversation handed to a recruiter,
    not answered again by Thunder."""

    def __init__(self, objection_type: str, count: int):
        self.objection_type = objection_type
        self.count = count
        super().__init__(f"Objection type {objection_type!r} raised {count} times -- escalating per BR-01.")

def classify_objection(db: Session, tenant_id: str, candidate_id: str, message_body: str, *, llm_call: Optional[Callable] = None) -> Dict:
    """Step 2. Never raises -- LLM failure or invalid JSON collapses to
    {objection_type: 'OTHER', key_concern: '', confidence: 0.0}, same
    defensive posture detect_intent_service's own BR-01 established."""
    try:
        system_prompt = (
            "Classify this objection from a job candidate into one of: "
            f"{', '.join(OBJECTION_TYPES)}. Also identify the key specific concern in max 10 words. "
            'Return ONLY JSON: {"objection_type": "...", "key_concern": "...", "confidence": 0.0}'
        )
        user_prompt = f"Message: {message_body}"
        response = prompt_framework_service.call_llm(
            db, tenant_id, candidate_id, "OBJECTION_CLASSIFICATION", "v1",
            system_prompt, user_prompt, 200, 0.0, llm_call=llm_call,
        )
        parsed = json.loads(response)
        objection_type = parsed.get("objection_type")
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        key_concern = str(parsed.get("key_concern", ""))[:200]
        if objection_type not in OBJECTION_TYPES:
            objection_type = "OTHER"
        return {"objection_type": objection_type, "key_concern": key_concern, "confidence": confidence}
    except Exception:
        return {"objection_type": "OTHER", "key_concern": "", "confidence": 0.0}

def _count_prior_occurrences(db: Session, conversation_id: int, objection_type: str) -> int:
    events = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation_id, ConversationEvent.event_type == "OBJECTION_RAISED").all()
    return sum(1 for e in events if (e.event_data or {}).get("objection_type") == objection_type)

def _generate_objection_response(db: Session, conversation: CandidateConversation, candidate: Candidate, objection_type: str, key_concern: str, *, llm_call: Optional[Callable] = None) -> str:
    if objection_type == "SALARY":  # BR-02: never reaches the LLM at all -- see module docstring
        return SALARY_NO_NUMBERS_MESSAGE

    try:
        context = candidate_context_service.build_candidate_context(db, candidate.candidateID, conversation.tenant_id)
        memory = context.get("memory") or {}
        known_facts = ", ".join(f"{f.get('key')}={f.get('value')}" for f in memory.get("facts") or [])

        system_prompt = (
            f"You are {context.get('thunder', {}).get('name', 'Thunder')}, a recruiter at BlitzenX talking to a "
            f"job candidate over chat. The candidate has raised a {objection_type} objection: {key_concern}. "
            "Acknowledge their concern professionally, use what you already know about them and the role to "
            "respond with something genuinely relevant, and gently keep the conversation open -- never "
            "dismissive, never pushy. Keep it to 2-3 sentences."
        )
        user_prompt = f"Candidate summary: {memory.get('summary') or '(none yet)'}\nKnown facts: {known_facts or '(none yet)'}\nRespond to their {objection_type} objection: {key_concern}"

        response = prompt_framework_service.call_llm(
            db, conversation.tenant_id, candidate.candidateID, "OBJECTION_HANDLING", "v1",
            system_prompt, user_prompt, 300, 0.6, llm_call=llm_call,
        )
        return response.strip() or SAFE_FALLBACK_MESSAGE
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[ObjectionHandling] Response generation failed for candidate {candidate.candidateID!r}: {exc}")
        return SAFE_FALLBACK_MESSAGE

def handle_objection(db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str, *, llm_call: Optional[Callable] = None) -> Dict:
    """Step 3. Raises ObjectionEscalatedError on the 3rd+ occurrence of
    the SAME objection_type in this conversation (BR-01) -- the caller
    should route that the same way it routes any other real
    escalation, not attempt to catch and retry."""
    classification = classify_objection(db, conversation.tenant_id, candidate.candidateID, message_body, llm_call=llm_call)
    objection_type = classification["objection_type"]
    key_concern = classification["key_concern"] or objection_type

    occurrence_number = _count_prior_occurrences(db, conversation.id, objection_type) + 1
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="OBJECTION_RAISED",
        event_data={"objection_type": objection_type, "key_concern": key_concern, "confidence": classification["confidence"], "occurrence_number": occurrence_number},
        triggered_by="candidate",
    ))
    db.commit()

    # S-347/HRMS-P117 BR-03: objection_type -> desire_category,
    # direction=AWAY_FROM always. Fire-and-forget, never raises.
    from app.services.desire_signal_service import record_objection_signal
    record_objection_signal(db, conversation.tenant_id, candidate.candidateID, objection_type, key_concern)

    # Step 5: real memory fact, regardless of escalation outcome below --
    # future context should know this objection was raised either way.
    try:
        upsert_fact(db, candidate.candidateID, conversation.tenant_id, fact_category="OBJECTION", fact_key=objection_type, fact_value=key_concern, confidence=classification["confidence"])
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[ObjectionHandling] Failed to store objection memory fact for candidate {candidate.candidateID!r}: {exc}")

    if occurrence_number >= MAX_SAME_OBJECTION_BEFORE_ESCALATE:
        raise ObjectionEscalatedError(objection_type, occurrence_number)

    response = _generate_objection_response(db, conversation, candidate, objection_type, key_concern, llm_call=llm_call)
    return {"response": response, "objection_type": objection_type, "key_concern": key_concern, "occurrence_number": occurrence_number}

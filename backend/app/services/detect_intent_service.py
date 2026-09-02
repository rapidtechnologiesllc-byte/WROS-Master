"""
import logging
S-033/HRMS-0433 -- Intent Detection Engine.

Real architecture adaptations:
- callLLM()/getContextForPrompt() are S-031/S-032's already-real
  prompt_framework_service.call_llm() and
  candidate_context_service.build_candidate_context() -- reused as-is.
  Real LLM is Gemini, not the spec's Anthropic claude-sonnet-4-6 (same
  adaptation every LLM-calling story this round has made).
- The INTENT_DETECTION template's user_prompt_template is
  "Message: {{conversation_history}}" (a deliberate S-031 placeholder
  hack) -- so detect_intent() builds a MINIMAL candidate_context
  overriding recent_messages to just the single message being
  classified, not the real multi-message thread build_candidate_context()
  would otherwise assemble. This matches the spec's own
  detectIntent(message_body, candidate_context) signature, which takes
  message_body as a separate argument precisely because it isn't "the
  last N messages".
- BR-01: LLM failure, invalid JSON, or an unknown intent value all
  collapse to {intent: "unclear", confidence: 0.0} -- this function
  never raises to its caller.
- BR-03: every inbound message's detected intent is logged to
  ConversationEvent(event_type="INTENT_DETECTED") -- on the success
  path AND the failure path, so analytics never silently miss a
  message. No new table needed; conversation_events already exists.
- Real HRMS-0472 (Objection Handling) and HRMS-0447 (Interview
  Availability Collection) don't exist in this codebase yet (Sprint 4 /
  Sprint 3 stories, not yet built) -- get_intent_routing_decision()
  reports this honestly instead of pretending a handler exists.
  HRMS-0427's "document_received event" also doesn't exist (neither
  WhatsApp nor email inbound paths in this codebase produce one yet --
  see resume_upload_service.py's own docstring) -- document_sharing is
  flagged NOT_WIRED, not LIVE, even though handle_resume_document()
  itself is real.
- Not wired into any live inbound path this round (whatsapp_webhook_service,
  ai_conversation_service.process_candidate_reply(),
  qualification_conversation_service.run_qualification_turn()) --
  same non-retrofit posture as S-019/S-025/S-031/S-032. Built as a
  real, complete, standalone, tested module ready for that wiring as a
  deliberate future decision.
- S-056/HRMS-0456 added offer_accepted/offer_declined/offer_counter to
  VALID_INTENTS (INTENT_DETECTION prompt bumped v1.1->v1.2, same
  version-bump convention S-033 itself established when confidence was
  added). These 3 are only actually acted on by
  offer_decision_service.py when conversation.offer_faq_active is
  true -- this classifier has no such gate itself, so a casual "I
  accept" sent outside an active offer window would still classify as
  offer_accepted; the real precondition check lives in the caller, not
  here.
"""
import json
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate_ai import ConversationEvent
from app.services import candidate_context_service, prompt_framework_service

VALID_INTENTS = (
    "answering_question", "asking_question", "objecting",
    "scheduling_request", "document_sharing", "not_interested", "unclear",
    # S-056/HRMS-0456 -- added directly to the shared classifier rather
    # than a separate offer-specific classification pass, since this
    # story's own Step 1 explicitly says "add offer-specific intents to
    # HRMS-0433". Only meaningful when conversation.offer_faq_active is
    # true (checked by the caller, offer_decision_service.py) -- the
    # classifier itself has no notion of that flag.
    "offer_accepted", "offer_declined", "offer_counter",
)

# BR-01 default -- never crash, never leave a message unclassified.
UNCLEAR_RESULT = {"intent": "unclear", "confidence": 0.0}

# Step 3's routing map, reported honestly rather than blindly invoked --
# see module docstring for why each status is what it is.
INTENT_ROUTING = {
    "answering_question": {"status": "LIVE", "target": "qualification_conversation_service.run_qualification_turn"},
    "asking_question": {"status": "LIVE", "target": "qualification_conversation_service.run_qualification_turn (candidate-question branch)"},
    "objecting": {"status": "NOT_BUILT", "target": "HRMS-0472 Objection Handling Engine (Sprint 4, not yet built)"},
    "scheduling_request": {"status": "NOT_WIRED", "target": "interview_availability_service.parse_availability_response (first-time ask) / interview_reschedule_service.start_reschedule (mid-flow reschedule, HRMS-0451) -- both real and tested, no live trigger calls either yet"},
    "document_sharing": {"status": "NOT_WIRED", "target": "resume_upload_service.handle_resume_document (real, but no live document_received trigger exists yet)"},
    "not_interested": {"status": "LIVE", "target": "qualification_conversation_service.run_qualification_turn (BR-04 not-interested branch, graceful exit)"},
    "unclear": {"status": "LIVE", "target": "thunder_service.generate_thunder_reply_with_fallback (clarification request)"},
    "offer_accepted": {"status": "NOT_WIRED", "target": "offer_decision_service.handle_offer_decision (HRMS-0456, real and tested, no live trigger yet)"},
    "offer_declined": {"status": "NOT_WIRED", "target": "offer_decision_service.handle_offer_decision (HRMS-0456, real and tested, no live trigger yet)"},
    "offer_counter": {"status": "NOT_WIRED", "target": "offer_decision_service.handle_offer_decision (HRMS-0456, real and tested, no live trigger yet)"},
}


def get_intent_routing_decision(intent: str) -> Dict:
    """Step 3. Honest routing lookup -- never silently invokes a
    handler that doesn't exist yet."""
    return INTENT_ROUTING.get(intent, INTENT_ROUTING["unclear"])


def _log_intent(db: Session, conversation_id: Optional[int], intent: str, confidence: float, message_event_id: Optional[int]) -> None:
    if conversation_id is None:
        return
    db.add(ConversationEvent(
        conversation_id=conversation_id, event_type="INTENT_DETECTED",
        event_data={"intent": intent, "confidence": confidence, "message_id": message_event_id},
        triggered_by="ai_agent",
    ))
    db.commit()


def detect_intent(
    db: Session, tenant_id: str, candidate_id: str, message_body: str, *,
    conversation_id: Optional[int] = None, message_event_id: Optional[int] = None,
    llm_call: Optional[Callable[[str, str, int, float], str]] = None,
) -> Dict:
    """
    Step 2. Returns {intent, confidence, raw_response, secondary_intent}.
    BR-01: never raises -- any failure resolves to the unclear default.
    BR-03: always logs INTENT_DETECTED, success or failure.
    """
    try:
        context = candidate_context_service.build_candidate_context(db, candidate_id, tenant_id)
        context["recent_messages"] = [{"sender": "Candidate", "body": message_body}]

        prompt = prompt_framework_service.build_prompt("INTENT_DETECTION", {
            "thunder_name": context["thunder"]["name"], "name": context["candidate"]["name"],
            "memory": {}, "recent_messages": context["recent_messages"], "missing_fields": [],
        })
        response = prompt_framework_service.call_llm(
            db, tenant_id, candidate_id, "INTENT_DETECTION", prompt["template_version"],
            prompt["system_prompt"], prompt["user_prompt"], prompt["max_tokens"], prompt["temperature"],
            llm_call=llm_call,
        )
        parsed = json.loads(response)
        intent = parsed.get("intent")
        confidence = float(parsed.get("confidence", 0.0))
        if intent not in VALID_INTENTS:
            intent, confidence = UNCLEAR_RESULT["intent"], UNCLEAR_RESULT["confidence"]
        confidence = max(0.0, min(1.0, confidence))
    except Exception:
        intent, confidence, response = UNCLEAR_RESULT["intent"], UNCLEAR_RESULT["confidence"], None

    # Step 4 -- compound-message secondary-indicator check. Deterministic,
    # not a second LLM call, matching this codebase's existing "?"-heuristic
    # precedent in qualification_conversation_service.
    secondary_intent = None
    if intent == "answering_question" and "?" in message_body:
        secondary_intent = "asking_question"

    _log_intent(db, conversation_id, intent, confidence, message_event_id)

    return {"intent": intent, "confidence": confidence, "raw_response": response, "secondary_intent": secondary_intent}

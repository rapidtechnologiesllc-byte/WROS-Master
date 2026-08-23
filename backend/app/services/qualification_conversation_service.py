"""
S-025/HRMS-0425 -- AI Qualification Conversation Engine.

Ties together everything this round already built: S-018 (state),
S-020's real R-08 ownership gate (is_ai_owner, already implemented in
whatsapp_routing_service), S-022 (fact extraction, already wired into
process_candidate_reply), S-024 (qualification plan). This is the
decision layer that turns "candidate replied" into "what does Thunder
say next" -- meant to be called from process_candidate_reply() right
after extract_facts(), for the same conversation/candidate.

Real architecture adaptations:
- No message.received event bus -- this is a plain function called
  directly from the real inbound pipeline (same posture as every
  other should-be-event-driven story this round).
- No HRMS-0431 Prompt Framework / HRMS-0434 AI Response Generation as
  separate named things -- their real equivalent already exists and
  is reused as-is: thunder_service.generate_thunder_reply_with_fallback()
  (never fails, falls back to a safe hardcoded message).
- No HRMS-0433 Intent Detection exists -- "not interested" is detected
  with a real, deterministic phrase-match heuristic
  (_looks_not_interested()) rather than an LLM classifier that doesn't
  exist yet; documented as a real, if simple, first version rather
  than a silent no-op. "asking_question" is approximated by the
  presence of a "?" in the message -- when true, Thunder answers via
  the existing generate_thunder_reply_with_fallback() pipeline before
  appending the next qualification question (Step 5), reusing the
  already-built, already-tested Q&A pipeline instead of inventing a
  second one.
- transitionState() targets: this codebase's real state model only has
  three lifecycle values (open/awaiting_candidate/closed -- S-018),
  not the spec's distinct QUALIFIED vs COMPLETED. Both "qualification
  complete" and "not interested" transition to the one real terminal
  state, "closed", differentiated by conversation.next_action /
  ConversationEvent.event_data.reason instead of a fourth status value
  that doesn't exist.
- Channel dispatch: WhatsApp/web_chat go through the existing,
  R-08-enforcing thunder_service.send_thunder_message(); portal goes
  through the existing portal_message_service.store_outbound_portal_message();
  anything else (email, or channel_preference unset) logs a real
  ai_message_sent ConversationEvent directly -- honest about not
  re-implementing email_first_engagement_service's full template
  pipeline for this one new call site, not a fake success.
"""
import time
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.services.conversation_state_service import transition_status
from app.services.qualification_engine_service import (
    QualificationNotApplicable,
    get_qualification_plan,
    is_qualifying_state,
)
from app.services.whatsapp_routing_service import is_ai_owner

RESPONSE_DELAY_SECONDS = 2  # BR-01

NOT_INTERESTED_PHRASES = (
    "not interested", "no longer interested", "not looking", "no thank you", "no thanks",
    "please remove me", "unsubscribe", "stop contacting", "don't contact me", "not a good fit for me",
)

COMPLETION_MESSAGE_TEMPLATE = (
    "Thank you {name}! I now have everything I need to find you the best "
    "opportunities. Our team will be in touch with relevant roles shortly."
)
NOT_INTERESTED_MESSAGE = (
    "Thank you for letting me know, and no worries at all! I'll stop reaching out for now. "
    "If anything changes, feel free to message me anytime -- we'd love to help whenever the timing works better for you."
)


def _candidate_name(candidate: Candidate) -> str:
    return candidate.candidateFirstName or candidate.candidateEmail or "there"


def _looks_not_interested(message_body: str) -> bool:
    lowered = (message_body or "").lower()
    return any(phrase in lowered for phrase in NOT_INTERESTED_PHRASES)


def send_channel_aware_message(
    db: Session, conversation: CandidateConversation, candidate: Candidate, message_body: str,
    *, whatsapp_client=None,
) -> None:
    """Dispatches an outbound Thunder message via whichever channel this
    conversation prefers. Public (no leading underscore) so other
    modules -- e.g. resume_upload_service (S-027) -- can send a
    channel-aware confirmation without duplicating this dispatch logic."""
    # channel_preference lives on the conversation (S-069), not Candidate.
    channel = conversation.channel_preference or "email"

    if channel == "whatsapp":
        from app.services.thunder_service import send_thunder_message
        send_thunder_message(db, conversation, candidate, message_body, sender_type="ai_agent", channel="whatsapp", whatsapp_client=whatsapp_client, auto_generated=True)
        return
    if channel == "web_chat":
        from app.services.thunder_service import send_thunder_message
        send_thunder_message(db, conversation, candidate, message_body, sender_type="ai_agent", channel="web_chat", auto_generated=True)
        return
    if channel == "portal":
        from app.services.portal_message_service import store_outbound_portal_message
        store_outbound_portal_message(db, conversation, sender_type="ai_agent", message_body=message_body)
        return

    # email or unset -- honest fallback, see module docstring.
    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "email", "body": message_body, "auto_generated": True},
        triggered_by="ai_agent",
    ))
    db.flush()


def run_qualification_turn(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    tenant_id: str,
    candidate_message: str,
    *,
    answer_question_fn: Optional[Callable[[Session, Candidate, str], str]] = None,
    llm_call: Optional[Callable[[str], str]] = None,
    whatsapp_client=None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Dict:
    """
    The qualification conversation loop's single entry point. Meant to
    be called once per inbound candidate message, right after
    extract_facts() in process_candidate_reply(). Returns a dict
    describing what happened -- never raises.
    """
    if not is_ai_owner(conversation):  # BR-03
        return {"action": "skipped_recruiter_owns"}

    from app.services.ghosting_detection_service import is_candidate_ghosted  # S-043 BR-01
    if is_candidate_ghosted(db, candidate.candidateID, tenant_id):
        return {"action": "skipped_candidate_ghosted"}

    if not is_qualifying_state(conversation):
        return {"action": "not_qualifying"}

    sleep_fn(RESPONSE_DELAY_SECONDS)  # BR-01

    if _looks_not_interested(candidate_message):  # BR-04
        transition_status(db, conversation, "closed", reason="Candidate not interested", triggered_by="candidate")
        conversation.next_action = "none"
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="CANDIDATE_NOT_INTERESTED",
            event_data={"message": candidate_message[:500]}, triggered_by="candidate",
        ))
        send_channel_aware_message(db, conversation, candidate, NOT_INTERESTED_MESSAGE, whatsapp_client=whatsapp_client)
        db.commit()
        return {"action": "not_interested"}

    try:
        plan = get_qualification_plan(db, conversation, candidate, tenant_id, llm_call=llm_call)
    except QualificationNotApplicable:
        return {"action": "not_qualifying"}

    if plan["is_complete"]:  # BR-02
        transition_status(db, conversation, "closed", reason="Qualification complete", triggered_by="ai_agent")
        conversation.next_action = "ready_for_matching"
        message = COMPLETION_MESSAGE_TEMPLATE.format(name=_candidate_name(candidate))

        # S-073/HRMS-0473 Step 3: the real completion trigger -- appends
        # the first un-asked preference question, if any. The full
        # multi-turn preference loop has no live trigger yet since this
        # conversation is closed immediately after (see
        # preference_capture_service.py's own module docstring).
        from app.services.preference_capture_service import append_preference_question_to_message, ask_preference_question
        preference_item = ask_preference_question(db, candidate.candidateID, tenant_id)
        message = append_preference_question_to_message(message, preference_item)

        send_channel_aware_message(db, conversation, candidate, message, whatsapp_client=whatsapp_client)
        db.commit()
        return {"action": "qualification_complete"}

    # Step 5: candidate asked a question -- answer it first, then continue.
    prefix = ""
    if "?" in candidate_message:
        if answer_question_fn is not None:
            answer = answer_question_fn(db, candidate, candidate_message)
        else:
            from app.services.thunder_service import generate_thunder_reply_with_fallback
            answer, _used_fallback = generate_thunder_reply_with_fallback(db, candidate, candidate_message, channel="whatsapp", conversation=conversation)
        prefix = f"{answer} To continue getting to know your background, "
    else:
        prefix = "Great, thanks for sharing that! "

    message = f"{prefix}{plan['question']}"
    send_channel_aware_message(db, conversation, candidate, message, whatsapp_client=whatsapp_client)
    db.commit()
    return {"action": "qualification_question_sent", "next_field": plan["next_field"], "message": message}

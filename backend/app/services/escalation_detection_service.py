"""
S-035/HRMS-0435 -- Human Escalation Detection.

Real architecture adaptations:
- No fictional 10-state ESCALATED enum -- conversation_state_service's
  existing escalate()/resolve_escalation() (the escalation_state axis)
  plus the new pause_for_recruiter_queue() (the ownership axis,
  unassigned -- "any recruiter can pick up" is explicitly in scope per
  this story's own "what not to build" list, no specific-recruiter
  routing) ARE the real state model. No new conversation_state_history
  table needed -- conversation.status (axis 1, the lifecycle) is never
  touched by escalation, so there is nothing to snapshot-and-restore on
  de-escalation; that axis's own reversibility is by construction (see
  conversation_state_service's module docstring).
- ESCALATION_CHECK prompt template already existed (S-031) but had
  never actually been called anywhere in this codebase until now.
- Real LLM is Gemini via prompt_framework_service.call_llm() (already
  retries once, always logs to prompt_execution_log, raises
  LLMCallFailedError on double failure) -- mapped directly onto BR-03
  (LLM failure -> needs_escalation=False, no false positives).
- check_escalation() builds its own context with use_cache=False
  (never the candidate_context_service's 30s cache) -- escalation
  decisions must see the message that was just logged this turn, not a
  snapshot from up to 30 seconds ago that might predate it.
- Rule #3 (NEGATIVE sentiment for 3+ consecutive messages, "from
  HRMS-0436") reads sentiment_analysis_service.has_negative_sentiment_trend()
  (S-036, built after this file -- a plain query against the real
  candidate_sentiment_log table, not a fabricated
  candidate.negative_sentiment_trend event/listener pair, since no
  event bus exists anywhere in this codebase). Sentiment analysis
  itself runs asynchronously (BackgroundTasks) relative to the message
  that triggered it, so this rule honestly can't fire on the very
  message that made the trend go negative -- it fires on the next
  inbound message once that background analysis has landed. Same class
  of honest lag sla_monitoring_service already accepts elsewhere in
  this codebase, not a defect.
- Rule #2 ("same question asked 3+ times") has no existing fuzzy-
  match/embeddings infrastructure in this codebase -- implemented as a
  cheap normalized-text near-duplicate check over the candidate's last
  3 inbound messages, same "cheap deterministic heuristic over an LLM
  call" posture as qualification_conversation_service's
  NOT_INTERESTED_PHRASES / detect_intent_service's "?" heuristic.
- BR-02's "notify the recruiting manager" has no real target -- no
  Users.UserRole value for "recruiting manager" exists anywhere in
  this codebase (only "Super User", "Partner", "BU Head", etc., are
  real roles in use). Adapted to additionally notify the tenant's
  owning Super User (resolved via CandidateConversation.tenant_id, the
  real String(50) UserID convention) as this codebase's closest real
  analog to "manager" -- a real, already-existing user, not a
  fabricated role -- whenever they differ from the primary recipient.
- Wired into the one genuinely live, real-time inbound-to-reply loop in
  this codebase today: public_chat_service.send_public_chat_message().
  qualification_conversation_service.run_qualification_turn() (the
  other natural call site) is fully built and tested but is not called
  from any live inbound path yet -- a pre-existing gap from earlier
  this EPIC-04 round, not something this story silently fixes; wiring
  it into a live path is flagged as a separate follow-up decision.
"""
import json
import re
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.user import Users
from app.services import candidate_context_service, conversation_state_service, prompt_framework_service
from app.services.ai_conversation_service import resolve_thunder_config
from app.services.notification_service import send_notification
from app.services.qualification_conversation_service import send_channel_aware_message
from app.services.qualification_engine_service import QualificationNotApplicable, get_qualification_plan

# BR-01 rule triggers -- checked before any LLM call, cheap and fast.
HUMAN_REQUEST_KEYWORDS = (
    "speak to a human", "speak to a person", "speak to a recruiter", "talk to a human",
    "talk to a recruiter", "call me", "this is wrong", "i want to complain",
)
# BR-02: immediate escalation, no LLM check, dual notification (recruiter + manager analog).
LEGAL_KEYWORDS = ("lawyer", "legal action", "discrimination", "harassment")

REPEATED_QUESTION_THRESHOLD = 3

# BR-04: exit message goes out to the candidate BEFORE ownership transfers.
ESCALATION_EXIT_MESSAGE = (
    "Thank you for your patience. I am connecting you with a member of our "
    "recruiting team who will be in touch shortly."
)


def _matches_any(message_lower: str, phrases) -> Optional[str]:
    for phrase in phrases:
        if phrase in message_lower:
            return phrase
    return None


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _is_repeated_question(recent_messages: List[Dict], latest_message_body: str) -> bool:
    """Rule #2. Cheap normalized-substring near-duplicate check over the
    candidate's last REPEATED_QUESTION_THRESHOLD inbound messages
    (including the one just received) -- see module docstring."""
    inbound = [m.get("message_body", "") for m in recent_messages if m.get("direction") == "INBOUND" and m.get("message_body")]
    inbound.append(latest_message_body)
    if len(inbound) < REPEATED_QUESTION_THRESHOLD:
        return False
    last_n = [_normalize(m) for m in inbound[-REPEATED_QUESTION_THRESHOLD:]]
    if not all(last_n):
        return False
    return len(set(last_n)) == 1


def check_escalation(
    db: Session, tenant_id: str, candidate_id: str, latest_message_body: str, *,
    llm_call: Optional[Callable[[str, str, int, float], str]] = None,
) -> Dict:
    """
    Step 2. Returns {needs_escalation, reason, trigger_type}.
    BR-01: rules checked first -- LLM only runs if no rule fires.
    BR-02: legal/compliance keywords escalate immediately, no LLM call.
    BR-03: any LLM failure (call or parse) collapses to
    needs_escalation=False -- never raises.
    """
    message_lower = latest_message_body.lower()

    legal_hit = _matches_any(message_lower, LEGAL_KEYWORDS)
    if legal_hit:  # BR-02
        return {"needs_escalation": True, "reason": f"Legal/compliance keyword detected: {legal_hit!r}", "trigger_type": "RULE"}

    human_hit = _matches_any(message_lower, HUMAN_REQUEST_KEYWORDS)
    if human_hit:
        return {"needs_escalation": True, "reason": f"Candidate explicitly asked for a human: {human_hit!r}", "trigger_type": "RULE"}

    try:
        context = candidate_context_service.build_candidate_context(db, candidate_id, tenant_id, use_cache=False)
    except Exception as exc:
        logger.warning(f"[Escalation] Failed to build context for candidate {candidate_id!r}: {exc}")
        return {"needs_escalation": False, "reason": None, "trigger_type": None}

    if _is_repeated_question(context["recent_messages"], latest_message_body):
        return {"needs_escalation": True, "reason": "Candidate asked the same question 3+ times without resolution", "trigger_type": "RULE"}

    # Rule #3 (NEGATIVE sentiment 3+ consecutive, "from HRMS-0436"). A
    # plain DB read against candidate_sentiment_log -- see
    # sentiment_analysis_service.has_negative_sentiment_trend()'s own
    # docstring for why this isn't a fabricated event/listener pair.
    from app.services.sentiment_analysis_service import has_negative_sentiment_trend
    if has_negative_sentiment_trend(db, candidate_id):
        return {"needs_escalation": True, "reason": "Candidate sentiment has been negative for 3+ consecutive messages", "trigger_type": "RULE"}

    try:
        prompt = prompt_framework_service.build_prompt("ESCALATION_CHECK", {
            "thunder_name": context["thunder"]["name"], "name": context["candidate"]["name"],
            "memory": {}, "recent_messages": context["recent_messages"], "missing_fields": [],
        })
        response = prompt_framework_service.call_llm(
            db, tenant_id, candidate_id, "ESCALATION_CHECK", prompt["template_version"],
            prompt["system_prompt"], prompt["user_prompt"], prompt["max_tokens"], prompt["temperature"],
            llm_call=llm_call,
        )
        parsed = json.loads(response)
        needs_escalation = bool(parsed.get("needs_escalation", False))
        reason = str(parsed.get("reason") or "LLM-detected escalation need")
    except Exception as exc:
        logger.warning(f"[Escalation] ESCALATION_LLM_FAILED for candidate {candidate_id!r}: {exc}")
        return {"needs_escalation": False, "reason": None, "trigger_type": None}

    if not needs_escalation:
        return {"needs_escalation": False, "reason": None, "trigger_type": None}
    return {"needs_escalation": True, "reason": reason, "trigger_type": "LLM"}


def _candidate_display_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail


def _assigned_recruiter(db: Session, candidate_id: str) -> Optional[Users]:
    """Mirrors sla_monitoring_service's own tenant-bridging resolver --
    kept local rather than imported since that one is a private
    (underscore-prefixed) helper of its own module."""
    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    if assignment and assignment.assigned_by:
        return db.query(Users).filter(Users.UserID == assignment.assigned_by).first()
    return None


def _notify_escalation(db: Session, conversation: CandidateConversation, candidate: Candidate, *, reason: str, is_legal: bool) -> None:
    name = _candidate_display_name(candidate)
    recipient = _assigned_recruiter(db, candidate.candidateID) or db.query(Users).filter(Users.UserID == conversation.tenant_id).first()

    primary_message = (
        f"LEGAL/COMPLIANCE escalation for {name}: {reason}. Review immediately (conversation {conversation.id})."
        if is_legal else
        f"{name} needs human attention: {reason}. Review in the Messages tab (conversation {conversation.id})."
    )
    if recipient:
        try:
            send_notification(
                db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
                priority_tier="P0", channel_preference="IN_APP", message=primary_message,
            )
        except Exception as exc:
            logger.warning(f"[Escalation] Failed to notify recruiter for conversation {conversation.id}: {exc}")

    if is_legal:  # BR-02 -- see module docstring on the "recruiting manager" adaptation
        manager = db.query(Users).filter(Users.UserID == conversation.tenant_id).first()
        if manager and (not recipient or manager.UserID != recipient.UserID):
            try:
                send_notification(
                    db, calling_context_tenant_id=manager.tenant_id, recipient=manager,
                    priority_tier="P0", channel_preference="IN_APP",
                    message=f"LEGAL/COMPLIANCE escalation for {name}: {reason}. Review immediately (conversation {conversation.id}).",
                )
            except Exception as exc:
                logger.warning(f"[Escalation] Failed to notify manager for conversation {conversation.id}: {exc}")


def execute_escalation(
    db: Session, conversation: CandidateConversation, candidate: Candidate, *,
    reason: str, trigger_type: str, whatsapp_client=None,
) -> None:
    """
    Step 3, in the BR-04-mandated order: the exit message goes out to
    the candidate BEFORE ownership transfers (no response gap), then
    escalation_state flips, ownership clears to the unassigned
    recruiter queue, and the assigned recruiter (or tenant-owner
    fallback) is notified -- plus the tenant owner again, as this
    codebase's "recruiting manager" analog, for legal/compliance
    triggers (BR-02). Commits at the end.
    """
    is_legal = trigger_type == "RULE" and reason.startswith("Legal/compliance keyword")

    send_channel_aware_message(db, conversation, candidate, ESCALATION_EXIT_MESSAGE, whatsapp_client=whatsapp_client)

    conversation_state_service.escalate(db, conversation, reason=reason, triggered_by="ai_agent")
    conversation_state_service.pause_for_recruiter_queue(db, conversation, reason=reason)

    _notify_escalation(db, conversation, candidate, reason=reason, is_legal=is_legal)

    db.commit()


def resolve_and_resume(
    db: Session, conversation: CandidateConversation, candidate: Candidate, tenant_id: str, *,
    triggered_by: str, llm_call: Optional[Callable[[str], str]] = None, whatsapp_client=None,
) -> Dict:
    """
    Step 4: de-escalation. escalation_state -> resolved, ownership back
    to Thunder, then Thunder immediately resumes qualification --
    conversation.status was never touched by escalation, so there is no
    "previous state" to restore (see module docstring). Commits at the
    end.
    """
    thunder_name = resolve_thunder_config(db, tenant_id)["name"]

    conversation_state_service.resolve_escalation(db, conversation, reason="Recruiter resolved and handed back to Thunder", triggered_by=triggered_by)
    conversation_state_service.resume_to_thunder(db, conversation, ai_agent_name=thunder_name, reason="Escalation resolved")

    resumed_question = None
    try:
        plan = get_qualification_plan(db, conversation, candidate, tenant_id, llm_call=llm_call)
        if not plan["is_complete"]:
            send_channel_aware_message(db, conversation, candidate, plan["question"], whatsapp_client=whatsapp_client)
            resumed_question = plan["question"]
    except QualificationNotApplicable:
        pass

    db.commit()
    return {"escalation_state": conversation.escalation_state, "owner_type": conversation.owner_type, "owner_id": conversation.owner_id, "resumed_question": resumed_question}

"""
import logging
S-055/HRMS-0455 -- Offer FAQ Bot.

Real architecture adaptations:
- No `system_configuration` table exists anywhere in this codebase
  (same gap every prior story that assumed one has already flagged,
  e.g. S-020/S-041's env-var-overridable constants). `offer_faq_entries`
  (genuinely new, see its own model docstring) is the real,
  admin-editable-in-the-future substitute; `DEFAULT_FAQ_CONTENT` below
  is the real fallback when no tenant-specific row exists yet -- same
  "module constant fallback with a documented content-approval gap"
  posture S-029's synonym library already took ("no Lead BA available
  to review live"). No admin UI is built for this table (explicitly
  out of scope per this story's own "What NOT to build").
- No literal `offers` table -- reuses the real, pre-existing
  `OfferLetter` model (position/salary/joining_date/offer_expire_date
  -- see S-054's own module docstring for why this table already
  existed before EPIC-04's sequential build reached it).
- BR-03's "offer_faq_active=true AND conversation.status=OFFER_SENT"
  gate is mapped onto the ONE real signal that exists:
  `conversation.offer_faq_active` (S-054). No `OFFER_SENT` conversation
  state value exists (same fictional-state issue every S-041-054 story
  has flagged). A known, honest, forward-flagged gap: nothing in this
  codebase yet clears `offer_faq_active` back to false on acceptance/
  decline, because HRMS-0456 (Offer Acceptance Tracking, this story's
  own literal "Blocks" dependency) is not built yet -- the very next
  story in this sequence.
- Step 4 (routing "I accept"/"I decline" signals mid-FAQ-conversation
  to HRMS-0456) is NOT implemented here -- HRMS-0456 doesn't exist in
  this codebase yet. This module only ever answers intent=
  'asking_question' messages (this story's own Step 3 trigger
  condition); an accept/decline signal is a DIFFERENT intent
  classification that a future story would need to add to
  `detect_intent_service.VALID_INTENTS` -- extending that ahead of its
  own real consumer would be building speculative scope, not done here.
- Escalation (BR-01, negotiation questions) reuses the same
  `conversation_state_service.escalate()`/`pause_for_recruiter_queue()`
  primitives S-035's `execute_escalation()` is itself built from,
  rather than that function directly -- this story's own spec
  prescribes a distinct exit message, same precedent
  `interview_reschedule_service` already established for an identical
  "needs a custom message, reuse the primitives not the wrapper" case.
- BR-02 ("answers must reference actual offer data, not generic
  statements") is enforced by a real, cheap heuristic after the LLM
  call: the generated answer must mention at least one concrete offer
  fact (position/joining date/expiry date) or the specific FAQ topic
  content that was fed into the prompt -- an answer that fails this
  check is treated the same as an LLM failure (safe fallback +
  escalate), not silently returned.
- Uses Gemini (this codebase's only real LLM, via the same minimal,
  injectable REST-call pattern `response_parser_service`/
  `interview_availability_service` already established), not the
  spec's literal `ANTHROPIC_API_KEY` assumption.
- Sent via the candidate's `channel_preference` (whatsapp default) --
  unlike S-049/050/054's "always both channels" rule for high-stakes
  moments, this story's own Step 3 says "via candidate's preferred
  channel," a real, deliberate difference from those siblings, not an
  oversight.
"""
import json
import os
import re
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.offer_faq_entry import FAQ_TOPICS, OfferFAQEntry
from app.models.offer_letter import OfferLetter
from app.models.submission import Submission
from app.models.user import Users
from app.services import conversation_state_service
from app.services.notification_service import send_notification
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message

NEGOTIATION_KEYWORDS = ("negotiate", "counter", "counter-offer", "higher salary", "lower salary", "more money", "increase the offer", "match my current")
SALARY_KEYWORDS = ("salary", "pay", "compensation", "ctc", "bonus")
LOGISTICS_KEYWORDS = ("start date", "when do i start", "role", "location", "position", "expire", "expiry", "deadline")

# keyword -> FAQ topic
POLICY_KEYWORD_TOPICS = {
    "benefit": "BENEFITS", "insurance": "BENEFITS", "health": "BENEFITS",
    "joining process": "JOINING_PROCESS", "onboarding": "JOINING_PROCESS",
    "first day": "FIRST_DAY",
    "background check": "BACKGROUND_CHECK", "background verification": "BACKGROUND_CHECK",
    "probation": "PROBATION_PERIOD",
    "leave": "LEAVE_POLICY", "pto": "LEAVE_POLICY", "vacation": "LEAVE_POLICY",
    "remote": "REMOTE_WORK_POLICY", "wfh": "REMOTE_WORK_POLICY", "work from home": "REMOTE_WORK_POLICY",
    "equipment": "EQUIPMENT_PROVIDED", "laptop": "EQUIPMENT_PROVIDED",
}

# Real, honest content-approval gap: placeholder wording, not yet
# reviewed by a Lead BA (none available live in this session) -- see
# the model's own docstring.
DEFAULT_FAQ_CONTENT = {
    "BENEFITS": "BlitzenX offers health insurance, 18 days of paid leave, a performance bonus, and a $500 annual learning budget.",
    "JOINING_PROCESS": "Our onboarding team will reach out with document collection and system-access steps once your offer is accepted.",
    "FIRST_DAY": "Your first day includes an orientation session, equipment setup, and an introduction to your team.",
    "BACKGROUND_CHECK": "A standard background verification is conducted after offer acceptance and before your start date.",
    "PROBATION_PERIOD": "New hires have a 90-day probation period with a check-in at 30 and 60 days.",
    "LEAVE_POLICY": "Employees accrue 18 days of paid leave per year, in addition to public holidays.",
    "REMOTE_WORK_POLICY": "BlitzenX supports remote and hybrid work arrangements depending on role and team.",
    "EQUIPMENT_PROVIDED": "BlitzenX provides a laptop and any role-specific equipment before your start date.",
}

SAFE_FALLBACK_MESSAGE = "Let me check on that for you. A recruiter will be in touch."
NEGOTIATION_ESCALATION_MESSAGE = "I've flagged this to our recruiting team and someone will be in touch."

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def _classify_question(text: str) -> Dict:
    """Returns {"category": "negotiation"|"salary"|"logistics"|"policy"|"general", "topic": Optional[str]}."""
    lowered = (text or "").lower()
    if any(kw in lowered for kw in NEGOTIATION_KEYWORDS):
        return {"category": "negotiation", "topic": None}
    for keyword, topic in POLICY_KEYWORD_TOPICS.items():
        if keyword in lowered:
            return {"category": "policy", "topic": topic}
    if any(kw in lowered for kw in SALARY_KEYWORDS):
        return {"category": "salary", "topic": None}
    if any(kw in lowered for kw in LOGISTICS_KEYWORDS):
        return {"category": "logistics", "topic": None}
    return {"category": "general", "topic": None}

def _get_faq_content(db: Session, tenant_id: str, topic: str) -> str:
    entry = db.query(OfferFAQEntry).filter(OfferFAQEntry.tenant_id == tenant_id, OfferFAQEntry.topic == topic).first()
    if entry is not None:
        return entry.answer_text
    return DEFAULT_FAQ_CONTENT.get(topic, "")

def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}},
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

def _answer_references_offer_data(answer: str, offer: OfferLetter, faq_content: str) -> bool:
    """BR-02 -- a cheap, real heuristic: the answer must mention a
    concrete offer fact or the specific FAQ content fed into the
    prompt, not a generic non-answer."""
    if not answer or not answer.strip():
        return False
    lowered = answer.lower()
    facts = [offer.position, str(offer.joining_date) if offer.joining_date else None, str(offer.offer_expire_date) if offer.offer_expire_date else None]
    if any(fact and fact.lower() in lowered for fact in facts):
        return True
    if faq_content and any(word in lowered for word in faq_content.lower().split()[:6]):
        return True
    return False

def _notify_recruiter(db: Session, submission: Optional[Submission], message: str) -> None:
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P2", channel_preference="IN_APP", message=message,
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OfferFAQ] Failed to notify recruiter: {exc}")

def _escalate_for_negotiation(db: Session, candidate: Candidate, conversation: CandidateConversation) -> None:
    conversation_state_service.escalate(db, conversation, reason="Salary negotiation question", triggered_by="ai_agent")
    conversation_state_service.pause_for_recruiter_queue(db, conversation, reason="Salary negotiation question")
    db.commit()

    submission = (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate.candidateID)
        .order_by(Submission.submitted_at.desc())
        .first()
    )
    _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} is asking about salary negotiation on their offer.")

def _send_channel_aware(db: Session, conversation: CandidateConversation, candidate: Candidate, message: str) -> bool:
    channel = conversation.channel_preference if conversation.channel_preference in ("whatsapp", "web_chat") else "whatsapp"
    try:
        send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel=channel, auto_generated=True)
        return True
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
        logger.info(f"[OfferFAQ] Message skipped for candidate {candidate.candidateID!r}: {exc}")
        return False

def answer_offer_question(
    db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str, question_text: str, *, llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """Step 2/3. BR-03: only active when offer_faq_active=true. Never
    raises. Returns:
      {"outcome": "not_active"}
      {"outcome": "no_offer_found"}
      {"outcome": "escalated", "answer": ...}
      {"outcome": "answered", "answer": ...}
    """
    if not conversation.offer_faq_active:  # BR-03
        return {"outcome": "not_active"}

    try:
        offer = (
            db.query(OfferLetter)
            .filter(OfferLetter.candidate_id == candidate.candidateID, OfferLetter.offer_status == "Released")
            .order_by(OfferLetter.released_at.desc())
            .first()
        )
        if offer is None:
            return {"outcome": "no_offer_found"}

        classification = _classify_question(question_text)

        if classification["category"] == "negotiation":  # BR-01
            _escalate_for_negotiation(db, candidate, conversation)
            _send_channel_aware(db, conversation, candidate, NEGOTIATION_ESCALATION_MESSAGE)
            db.commit()
            return {"outcome": "escalated", "answer": NEGOTIATION_ESCALATION_MESSAGE}

        faq_content = _get_faq_content(db, tenant_id, classification["topic"]) if classification["topic"] else ""
        prompt = (
            "You are Thunder, BlitzenX's recruiting assistant, answering a candidate's question about their "
            "job offer. Use ONLY the facts below -- never invent details, never make promises beyond them.\n\n"
            f"Candidate's question: {question_text}\n"
            f"Offer details: Position: {offer.position}. Start date: {offer.joining_date}. "
            f"Offer expires: {offer.offer_expire_date}.\n"
            + (f"Relevant policy information: {faq_content}\n" if faq_content else "")
            + "Answer in 1-3 warm, specific sentences."
        )

        try:
            answer = _call_llm(prompt, llm_call)
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[OfferFAQ] LLM call failed for candidate {candidate.candidateID!r}: {exc}")
            answer = None

        if not answer or not _answer_references_offer_data(answer, offer, faq_content):
            _escalate_for_negotiation(db, candidate, conversation)  # BR-02: can't answer specifically -> escalate, same real primitives
            _send_channel_aware(db, conversation, candidate, SAFE_FALLBACK_MESSAGE)
            db.commit()
            return {"outcome": "escalated", "answer": SAFE_FALLBACK_MESSAGE}

        _send_channel_aware(db, conversation, candidate, answer)
        db.commit()
        return {"outcome": "answered", "answer": answer}
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OfferFAQ] Unexpected failure answering question for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "answer_failed"}

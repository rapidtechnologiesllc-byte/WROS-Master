"""
S-056/HRMS-0456 -- Offer Acceptance Tracking.

Real, major pre-existing feature found: `POST /offer-letter/respond`
already exists (built in an earlier, pre-EPIC-04 round of this
session) and already does the core of the ACCEPTED/REJECTED half of
this story for real -- candidate auth check, `offer_status`
Accepted/Rejected (the real values, not the spec's literal ACCEPTED/
DECLINED), `candidate_response`/`responded_at`, a pipeline-status
upsert, an Org Pool transition on decline
(`candidate_pool_service.set_org_pool()`), and an HR email
(`EmailService.notify_hr_candidate_responded()`). That endpoint is a
structured API call from a candidate-portal form, though -- this
story's real, novel job is the CONVERSATIONAL path: detecting
acceptance/decline/counter from a casual WhatsApp/email message (Step
1's intent-detection extension) and driving the exact same real state
changes from there, plus the genuinely new counter-offer branch (which
the existing endpoint has no concept of at all) and Thunder's own
warm, per-outcome messages.

Real architecture adaptations:
- Reuses `candidate_pool_service.set_org_pool()` directly on decline
  (real, public, already the exact mechanism `/respond` uses for the
  same real-world event).
- Does NOT import `offer_letters.py`'s private `_update_pipeline_status()`
  across modules (established convention this whole round) -- its own
  3-line CandidateStatus upsert is duplicated locally rather than
  risking a cross-file refactor of an already-shipped, working
  candidate-facing endpoint this late. A small, deliberate duplication,
  not an oversight.
- Introduces a new real `offer_status` value, `"Countered"` --
  `OfferLetter.offer_status` is a plain `String(30)` column (not a
  DB-enforced enum), so no migration is needed; the existing
  Pending/AwaitingApproval/Approved/Released/Accepted/Rejected/Cancelled
  set (see `OfferLetter`'s own model comment) never included a counter
  outcome because the pre-existing `/respond` endpoint only ever
  handled accept/reject.
- No literal `PREBOARDING`/`COMPLETED`/`ESCALATED` conversation states
  exist (same fictional-state issue every S-041-055 story has
  flagged). BR-01's "PREBOARDING, not COMPLETED" is honored by NOT
  touching `conversation.status` on acceptance at all (the real
  "not done yet, still an active conversation" signal) -- only a real
  `OFFER_ACCEPTED` `ConversationEvent` is logged, and
  `conversation.offer_faq_active` is cleared (closing the real,
  forward-flagged gap S-055's own docstring left open). Decline maps
  to the one real "done" value that exists, `conversation.status =
  "closed"`. Counter maps to the real escalation axes
  (`conversation_state_service.escalate()`/`pause_for_recruiter_queue()`),
  matching "ESCALATED" in spirit.
- BR-02 (decline reason is a one-time ask, optional): no new column or
  scheduled 24h-timeout job -- "ask once" is satisfied structurally by
  this function only ever asking a single time per decline (never
  retried), and a reason volunteered inline in the same decline
  message is captured directly into the real `candidate_response`
  field without a separate follow-up ask.
- No internal event bus -- "publish offer.accepted/offer.declined" has
  nothing to publish through; the real `OFFER_ACCEPTED`/
  `OFFER_DECLINED`/`OFFER_COUNTERED` `ConversationEvent`s ARE the real,
  durable signal (same posture every "downstream story not built yet"
  case this round has taken -- HRMS-0457 Document Collection Agent,
  this story's own literal "Blocks" dependency, doesn't exist yet).
- HR notified via the pre-existing, already-real
  `EmailService.notify_hr_candidate_responded()` (reused as-is, same
  recipient -- `OfferLetter.created_by` -- the existing endpoint
  already uses); the recruiter is separately notified in-app via
  `notification_service.send_notification()` (Submission.
  submitted_by_user_id), since "HR and recruiter" are two real,
  potentially-different people in this codebase.
"""
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.offer_letter import OfferLetter
from app.models.submission import Submission
from app.models.user import Users
from app.services import conversation_state_service
from app.services.candidate_pool_service import set_org_pool
from app.services.email_service import EmailService
from app.services.notification_service import send_notification
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, send_thunder_message

ACCEPTANCE_MESSAGE = (
    "Congratulations and welcome to BlitzenX! We are thrilled to have you join the team. Our HR team will be in "
    "touch with the next steps for your joining process. In the meantime, I will start collecting some documents we need."
)
DECLINE_MESSAGE = (
    "Thank you for letting us know. We completely understand, and we appreciate the time you spent with us. "
    "We wish you all the best in your next role. We will keep your profile for future opportunities that may be a better fit."
)
DECLINE_REASON_ASK_MESSAGE = "If you are comfortable sharing, could you let us know why you decided not to proceed? It helps us improve our process."
COUNTER_MESSAGE = "Thank you for sharing your thoughts. I am passing your feedback to our recruiting team who will be in touch to discuss. Please hold tight!"


def _relevant_offer(db: Session, candidate_id: str) -> Optional[OfferLetter]:
    return (
        db.query(OfferLetter)
        .filter(OfferLetter.candidate_id == candidate_id, OfferLetter.offer_status == "Released")
        .order_by(OfferLetter.released_at.desc())
        .first()
    )


def _relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate_id)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def _upsert_pipeline_status(db: Session, candidate_id: str, new_status: str) -> None:
    """Small, deliberate local duplicate of offer_letters.py's private
    _update_pipeline_status() -- see module docstring."""
    cs = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if cs:
        cs.piplineStatus = new_status
    else:
        cs = CandidateStatus(candidateID=candidate_id, status="Active", piplineStatus=new_status)
        db.add(cs)


def _notify_recruiter(db: Session, submission: Optional[Submission], message: str, *, priority_tier: str = "P2") -> None:
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier=priority_tier, channel_preference="IN_APP", message=message)
    except Exception as exc:
        logger.warning(f"[OfferDecision] Failed to notify recruiter: {exc}")


def _notify_hr_by_email(db: Session, offer: OfferLetter, candidate: Candidate, decision: str, response_message: str = "") -> None:
    try:
        hr_creator = db.query(Users).filter(Users.UserID == offer.created_by).first()
        if hr_creator:
            EmailService.notify_hr_candidate_responded(
                hr_email=hr_creator.UserEmail,
                candidate_name=candidate.candidateFirstName or candidate.candidateEmail,
                position=offer.position or "",
                offer_id=offer.id,
                decision=decision,
                response_message=response_message,
            )
    except Exception as exc:
        logger.warning(f"[OfferDecision] HR email notification failed: {exc}")


def _send_channel_aware(db: Session, conversation: CandidateConversation, candidate: Candidate, message: str) -> bool:
    channel = conversation.channel_preference if conversation.channel_preference in ("whatsapp", "web_chat") else "whatsapp"
    try:
        send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel=channel, auto_generated=True)
        return True
    except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed) as exc:
        logger.info(f"[OfferDecision] Message skipped for candidate {candidate.candidateID!r}: {exc}")
        return False


def _handle_acceptance(db: Session, candidate: Candidate, conversation: CandidateConversation, offer: OfferLetter) -> Dict:
    offer.offer_status = "Accepted"
    offer.responded_at = datetime.now()
    db.add(offer)

    _upsert_pipeline_status(db, candidate.candidateID, "Hired")

    conversation.offer_faq_active = False  # BR-01: not "completed" -- just no longer FAQ mode; closes S-055's own flagged gap
    db.add(conversation)
    db.add(ConversationEvent(conversation_id=conversation.id, event_type="OFFER_ACCEPTED", event_data={"offer_id": offer.id, "candidate_id": candidate.candidateID}, triggered_by="candidate"))
    db.commit()

    _send_channel_aware(db, conversation, candidate, ACCEPTANCE_MESSAGE)

    submission = _relevant_submission(db, candidate.candidateID)
    start_date = str(offer.joining_date) if offer.joining_date else "TBD"
    _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} has accepted the offer for {offer.position}. Starting date: {start_date}.")
    _notify_hr_by_email(db, offer, candidate, "Accepted")

    return {"outcome": "accepted", "message": ACCEPTANCE_MESSAGE}


def _handle_decline(db: Session, candidate: Candidate, conversation: CandidateConversation, offer: OfferLetter, message_body: str) -> Dict:
    already_asked = db.query(ConversationEvent).filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "DECLINE_REASON_REQUESTED").first() is not None

    offer.offer_status = "Rejected"
    offer.responded_at = datetime.now()
    if not already_asked:
        offer.candidate_response = message_body[:1000] if message_body else None
    db.add(offer)

    _upsert_pipeline_status(db, candidate.candidateID, "Rejected")

    conversation.offer_faq_active = False
    conversation.status = "closed"  # the one real "done" value that exists -- see module docstring
    db.add(conversation)
    db.add(ConversationEvent(conversation_id=conversation.id, event_type="OFFER_DECLINED", event_data={"offer_id": offer.id, "candidate_id": candidate.candidateID, "decline_reason": offer.candidate_response}, triggered_by="candidate"))
    db.commit()

    _send_channel_aware(db, conversation, candidate, DECLINE_MESSAGE)

    if not already_asked:  # BR-02: ask once, never again
        _send_channel_aware(db, conversation, candidate, DECLINE_REASON_ASK_MESSAGE)
        db.add(ConversationEvent(conversation_id=conversation.id, event_type="DECLINE_REASON_REQUESTED", event_data={"offer_id": offer.id}, triggered_by="system"))
        db.commit()

    set_org_pool(candidate_id=candidate.candidateID, reason=f"Candidate declined offer #{offer.id} via Thunder", db=db, performed_by_id=candidate.candidateID, performed_by_name=candidate.candidateFirstName or candidate.candidateEmail)
    db.commit()

    submission = _relevant_submission(db, candidate.candidateID)
    reason_clause = f" Reason: {offer.candidate_response}." if offer.candidate_response else " Reason not provided."
    _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate.candidateID} declined the offer.{reason_clause} Consider re-opening the pipeline.")
    _notify_hr_by_email(db, offer, candidate, "Rejected", response_message=offer.candidate_response or "")

    return {"outcome": "declined", "message": DECLINE_MESSAGE}


def _handle_counter(db: Session, candidate: Candidate, conversation: CandidateConversation, offer: OfferLetter, message_body: str) -> Dict:
    offer.offer_status = "Countered"
    offer.responded_at = datetime.now()
    offer.candidate_response = message_body[:1000] if message_body else None
    db.add(offer)

    conversation.offer_faq_active = False  # a human owns this now
    db.add(conversation)
    conversation_state_service.escalate(db, conversation, reason="Candidate countered offer", triggered_by="ai_agent")
    conversation_state_service.pause_for_recruiter_queue(db, conversation, reason="Candidate countered offer")
    db.add(ConversationEvent(conversation_id=conversation.id, event_type="OFFER_COUNTERED", event_data={"offer_id": offer.id, "candidate_id": candidate.candidateID, "message": message_body}, triggered_by="candidate"))
    db.commit()

    _send_channel_aware(db, conversation, candidate, COUNTER_MESSAGE)

    submission = _relevant_submission(db, candidate.candidateID)
    expiry = str(offer.offer_expire_date) if offer.offer_expire_date else "soon"
    _notify_recruiter(
        db, submission,
        f"{candidate.candidateFirstName or candidate.candidateID} has countered the offer. Their message: \"{message_body}\". "
        f"Please respond within 24 hours -- offer expires on {expiry}.",
        priority_tier="P1",  # BR-03: urgency
    )

    return {"outcome": "countered", "message": COUNTER_MESSAGE}


def handle_offer_decision(db: Session, candidate: Candidate, conversation: CandidateConversation, tenant_id: str, intent: str, message_body: str) -> Dict:
    """Steps 2-4. Never raises. Returns one of:
      {"outcome": "not_active"}
      {"outcome": "no_offer_found"}
      {"outcome": "accepted"|"declined"|"countered", "message": ...}
      {"outcome": "unrecognized_intent"}
    """
    if not conversation.offer_faq_active:  # BR-03-style precondition, same gate S-055 established
        return {"outcome": "not_active"}

    try:
        offer = _relevant_offer(db, candidate.candidateID)
        if offer is None:
            return {"outcome": "no_offer_found"}

        if intent == "offer_accepted":
            return _handle_acceptance(db, candidate, conversation, offer)
        if intent == "offer_declined":
            return _handle_decline(db, candidate, conversation, offer, message_body)
        if intent == "offer_counter":
            return _handle_counter(db, candidate, conversation, offer, message_body)
        return {"outcome": "unrecognized_intent"}
    except Exception as exc:
        logger.error(f"[OfferDecision] Unexpected failure handling '{intent}' for candidate {candidate.candidateID!r}: {exc}")
        db.rollback()
        return {"outcome": "decision_failed"}

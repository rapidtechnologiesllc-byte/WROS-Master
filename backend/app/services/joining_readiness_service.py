"""
import logging
S-058/HRMS-0458 -- Joining Readiness Score.

Real architecture adaptations:
- No new `offers` table -- `offer_id` FKs the real, pre-existing
  `OfferLetter.id` (same substitute S-057's `preboarding_documents`
  already established).
- BR-01/Step 3's "PREBOARDING candidates" query has no literal
  `conversation.status='PREBOARDING'` value to filter on (same
  fictional-state issue every S-041-057 story has flagged). The real
  substitute: `OfferLetter.offer_status == "Accepted"` -- the one
  real, durable signal that a candidate has accepted and hasn't been
  otherwise resolved (declined/countered would have a different
  `offer_status`; there is no real "candidate has joined" transition
  built anywhere in this codebase yet -- HRMS-0708 employee conversion
  is a separate, later system this round doesn't touch -- so "Accepted"
  is the honest upper bound of "still in preboarding" available today).
- Component 2 ("offer signed, if e-signature available"): this
  codebase has no e-signature mechanism at all (explicitly out of
  scope per this story's own -- and S-057's -- "What NOT to build").
  Rather than inventing a signature check that can never pass (which
  would silently cap every real candidate at 15/20 forever), the
  "signed" condition is treated as vacuously satisfied: ACCEPTED +
  `joining_date` set = the full 20 points. Documented, not silently
  glossed over.
- Component 4 (responsiveness since acceptance) is computed from the
  real `OFFER_ACCEPTED` `ConversationEvent` (S-056) as the t0 reference
  point, and the candidate's own `candidate_reply` `ConversationEvent`
  history after it -- no fictional `conversation.updated_at`-since-
  acceptance field is used (that column is also bumped by unrelated
  mutations, same caveat this codebase's own `candidate_ai.py`
  docstring already documents). A candidate who hasn't replied yet but
  is still within the 48h window gets the benefit of the doubt (15pts,
  not 0) -- they haven't failed to respond, they just haven't had to
  yet.
- Component 5 (background check): no real background-check
  verification/status tracking exists anywhere in this codebase (this
  story's own "What NOT to build" note -- "HR verifies manually" --
  confirms there's no real system-of-record for CLEARED/FAILED
  outcomes). The best real proxy available is whether the
  `BACKGROUND_CHECK_CONSENT` `PreboardingDocument` (S-057) has been
  submitted: RECEIVED/VERIFIED maps to the "IN_PROGRESS" tier (5pts,
  since submitting consent is what starts the process, not completes
  it); no row or still-PENDING maps to "NOT_STARTED" (2pts). There is
  no real signal anywhere for "CLEARED" or "FAILED" -- this component
  can never award the full 10 or the blocking 0 in this codebase as it
  stands today. A real, honest, flagged limitation, not fabricated.
- BR-01 (score < 50 = immediate alert): `calculate_joining_readiness()`
  itself notifies the recruiter, not just the periodic job -- and only
  on the real transition into sub-50 (previous stored score was >=50,
  or no previous score existed), matching the "notify once on a real
  transition, not every recompute" convention S-046's abandonment
  scoring already established, so a candidate stuck at a low score
  doesn't spam the recruiter every 6 hours forever.
- No internal event bus -- "publish candidate.readiness_score_updated"
  has nothing to publish through; the row itself (upserted,
  `calculated_at` refreshed) is the real, durable, queryable signal
  (HRMS-0459 Journey Dashboard, this story's own literal "Blocks"
  dependency, doesn't exist yet).
- Real wiring: `calculate_joining_readiness()` is called directly from
  S-057's `document_collection_service.mark_document_received()` --
  this story's own integrations table says exactly that
  ("preboarding.document_received event... triggers readiness
  recalculation"), so recalculating right there is in-scope reuse of
  the one real trigger point that exists, not speculative wiring.
"""
from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users
from app.services.notification_service import send_notification

READINESS_ALERT_THRESHOLD = 50  # BR-01


def _document_component(db: Session, tenant_id: str, candidate_id: str, offer_id: int) -> int:
    docs = db.query(PreboardingDocument).filter(PreboardingDocument.tenant_id == tenant_id, PreboardingDocument.candidate_id == candidate_id, PreboardingDocument.offer_id == offer_id, PreboardingDocument.status != "CANCELLED").all()
    if not docs:
        return 0
    received = sum(1 for d in docs if d.status in ("RECEIVED", "VERIFIED"))
    return round((received / len(docs)) * 40)


def _offer_formality_component(offer: OfferLetter) -> int:
    if offer.offer_status != "Accepted":
        return 0
    if offer.joining_date is None:
        return 10  # missing start date confirmation
    return 20  # ACCEPTED + start date confirmed (e-signature vacuously satisfied -- see module docstring)


def _timeline_component(offer: OfferLetter) -> int:
    if offer.joining_date is None:
        return 0
    days = (offer.joining_date - date.today()).days
    if days < 0:
        return 0  # overdue
    if days < 3:
        return 15  # imminent -- committed
    if days < 7:
        return 8
    if days < 15:
        return 10
    if days <= 30:
        return 12
    return 15


def _responsiveness_component(db: Session, conversation: Optional[CandidateConversation]) -> int:
    if conversation is None:
        return 0
    accepted_event = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "OFFER_ACCEPTED")
        .order_by(ConversationEvent.created_at.desc())
        .first()
    )
    if accepted_event is None:
        return 0

    reply = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply", ConversationEvent.created_at > accepted_event.created_at)
        .order_by(ConversationEvent.created_at.asc())
        .first()
    )
    reference_time = reply.created_at if reply is not None else datetime.utcnow()
    elapsed_hours = (reference_time - accepted_event.created_at).total_seconds() / 3600

    if elapsed_hours <= 48:
        return 15
    if elapsed_hours <= 96:
        return 10
    return 0


def _background_check_component(db: Session, tenant_id: str, candidate_id: str, offer_id: int) -> int:
    doc = db.query(PreboardingDocument).filter(PreboardingDocument.tenant_id == tenant_id, PreboardingDocument.candidate_id == candidate_id, PreboardingDocument.offer_id == offer_id, PreboardingDocument.document_type == "BACKGROUND_CHECK_CONSENT").first()
    if doc is not None and doc.status in ("RECEIVED", "VERIFIED"):
        return 5  # real proxy for IN_PROGRESS -- see module docstring
    return 2  # NOT_STARTED


def _relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate_id)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def _notify_recruiter(db: Session, submission: Optional[Submission], message: str) -> None:
    if submission is None or not submission.submitted_by_user_id:
        return
    recipient = db.query(Users).filter(Users.UserID == submission.submitted_by_user_id).first()
    if not recipient:
        return
    try:
        send_notification(db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient, priority_tier="P1", channel_preference="IN_APP", message=message)
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[JoiningReadiness] Failed to notify recruiter: {exc}")


def calculate_joining_readiness(db: Session, candidate_id: str, offer_id: int, tenant_id: str) -> Dict:
    """Step 1. Never raises. Returns
    {"readiness_score": int, "score_breakdown": {...}}, or
    {"outcome": "not_found"} if the candidate/offer can't be resolved."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).first()
        if candidate is None or offer is None:
            return {"outcome": "not_found"}

        conversation = (
            db.query(CandidateConversation)
            .filter(CandidateConversation.candidate_id == candidate_id)
            .order_by(CandidateConversation.id.desc())
            .first()
        )

        documents_pts = _document_component(db, tenant_id, candidate_id, offer_id)
        offer_pts = _offer_formality_component(offer)
        timeline_pts = _timeline_component(offer)
        responsiveness_pts = _responsiveness_component(db, conversation)
        background_check_pts = _background_check_component(db, tenant_id, candidate_id, offer_id)

        score_breakdown = {
            "documents": documents_pts, "offer_formality": offer_pts, "timeline": timeline_pts,
            "responsiveness": responsiveness_pts, "background_check": background_check_pts,
        }
        readiness_score = min(documents_pts + offer_pts + timeline_pts + responsiveness_pts + background_check_pts, 100)

        existing = db.query(CandidateJoiningScore).filter(CandidateJoiningScore.tenant_id == tenant_id, CandidateJoiningScore.candidate_id == candidate_id, CandidateJoiningScore.offer_id == offer_id).first()
        previous_score = existing.readiness_score if existing else None

        if existing:
            existing.readiness_score = readiness_score
            existing.score_breakdown = score_breakdown
            existing.calculated_at = datetime.utcnow()
            db.add(existing)
        else:
            db.add(CandidateJoiningScore(tenant_id=tenant_id, candidate_id=candidate_id, offer_id=offer_id, readiness_score=readiness_score, score_breakdown=score_breakdown))
        db.commit()

        newly_crossed_below_threshold = readiness_score < READINESS_ALERT_THRESHOLD and (previous_score is None or previous_score >= READINESS_ALERT_THRESHOLD)
        if newly_crossed_below_threshold:  # BR-01: immediate, not on next job run
            submission = _relevant_submission(db, candidate_id)
            _notify_recruiter(db, submission, f"{candidate.candidateFirstName or candidate_id} joining readiness score has dropped to {readiness_score}. Review their preboarding status.")

        return {"readiness_score": readiness_score, "score_breakdown": score_breakdown}
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[JoiningReadiness] Failed calculating readiness for candidate {candidate_id!r}: {exc}")
        db.rollback()
        return {"outcome": "calculation_failed"}


def run_joining_readiness_job(db: Session) -> Dict:
    """Step 3. Runs every 6 hours. Never lets one bad row abort the batch."""
    result = {"processed": 0, "calculated": 0, "skipped": 0}

    accepted_offers = db.query(OfferLetter).filter(OfferLetter.offer_status == "Accepted").all()
    for offer in accepted_offers:
        result["processed"] += 1
        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
            if candidate is None:
                result["skipped"] += 1
                continue
            conversation = (
                db.query(CandidateConversation)
                .filter(CandidateConversation.candidate_id == offer.candidate_id)
                .order_by(CandidateConversation.id.desc())
                .first()
            )
            tenant_id = conversation.tenant_id if conversation is not None else None
            if tenant_id is None:
                result["skipped"] += 1
                continue

            calc_result = calculate_joining_readiness(db, offer.candidate_id, offer.id, tenant_id)
            if "readiness_score" in calc_result:
                result["calculated"] += 1
            else:
                result["skipped"] += 1
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.error(f"[JoiningReadiness] Failed processing offer id={offer.id}: {exc}")
            db.rollback()
            result["skipped"] += 1

    return result

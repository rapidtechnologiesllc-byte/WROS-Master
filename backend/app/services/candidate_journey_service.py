"""
import logging
S-059/HRMS-0459 -- Candidate Journey Dashboard.

Real architecture adaptations:
- No `conversation_state_history` table and no fictional 10-value
  state enum (INITIATED/QUALIFYING/QUALIFIED/INTERVIEW_SCHEDULING/
  INTERVIEW_SCHEDULED/OFFER_SENT/PREBOARDING/COMPLETED) anywhere in
  this codebase -- `conversation_state_service.py` (S-018) already
  documented why: CandidateConversation only has 3 real orthogonal
  axes (status/escalation_state/owner_type), none of which is a
  7-stage recruiting-pipeline position. The 7 stages this story wants
  are therefore derived here from the EXISTENCE of real, already-built
  artifacts across the whole EPIC-04/interview/offer chain, not from
  reading a single state column:
    1. ENGAGED     -- CandidateConversation row exists (created_at).
    2. QUALIFYING  -- candidate has replied at least once (first real
                       `candidate_reply` ConversationEvent) but no
                       CandidateJobScore has been computed yet.
    3. SCREENED    -- a CandidateJobScore row exists (S-037/S-040).
                       Scoring is per-candidate-per-job (no single
                       global score) -- the most recently calculated
                       row across all jobs is used as the
                       representative "screened" score, same
                       most-recent-record resolution S-053 already
                       established for the identical no-single-bridge
                       problem.
    4. INTERVIEW   -- a SubmissionInterview row exists for the
                       candidate's most recent Submission (same
                       most-recent-submission resolution S-053 uses).
    5. OFFER       -- an OfferLetter row exists for the candidate.
    6. PREBOARDING -- OfferLetter.offer_status == "Accepted" (the real
                       substitute this whole session has used since
                       S-057/S-058 -- no fictional PREBOARDING state
                       exists).
    7. JOINED      -- Employee.candidate_id is set (BR-04's real
                       one-candidate-to-one-employee link) -- this IS
                       HRMS-0708 Convert Candidate to Employee, already
                       built and shipped pre-EPIC-04. Satisfies BR-02
                       automatically: an accepted offer alone never
                       sets this, only a real Employee row does.
- BR-01 ("shows historical stages even if candidate returns to an
  earlier stage, multiple entries for the same stage") has no real
  equivalent to build honestly: this codebase's conversation model has
  no per-stage backward-transition/history mechanism at all (the
  spec's own QUALIFIED->ESCALATED->QUALIFYING loop assumes the
  fictional enum this codebase doesn't have -- escalation here is a
  separate, orthogonal axis, not a stage regression). This dashboard
  therefore shows each stage's single first-reached timestamp, not a
  multi-visit history. A real, flagged limitation, not silently
  faked as multi-visit support that doesn't exist.
- The "current stage" is the right-most stage with real evidence;
  every earlier stage is 'completed', every later one 'pending' --
  matching this story's own UI spec (green/blue/gray), and consistent
  with BR-02 since JOINED only lights up on real Employee data.
"""
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.employee import Employee
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.interview_pipeline import SubmissionInterview
from app.services.ai_conversation_service import CANDIDATE_CORE_FIELDS, INFO_FORM_FIELDS, get_missing_fields

TOTAL_PROFILE_FIELDS = len(CANDIDATE_CORE_FIELDS) + len(INFO_FORM_FIELDS)

logger = logging.getLogger(__name__)

class CandidateNotFound(Exception):
    pass


def _relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate_id)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def _latest_job_score(db: Session, candidate_id: str) -> Optional[CandidateJobScore]:
    return (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.overall_score.isnot(None))
        .order_by(CandidateJobScore.calculated_at.desc())
        .first()
    )


def _earliest_job_score(db: Session, candidate_id: str) -> Optional[CandidateJobScore]:
    return (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.candidate_id == candidate_id)
        .order_by(CandidateJobScore.calculated_at.asc())
        .first()
    )


def _first_candidate_reply(db: Session, conversation: Optional[CandidateConversation]) -> Optional[ConversationEvent]:
    if conversation is None:
        return None
    return (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "candidate_reply")
        .order_by(ConversationEvent.created_at.asc())
        .first()
    )


def _thunder_message_count(db: Session, conversation: Optional[CandidateConversation]) -> int:
    if conversation is None:
        return 0
    return (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id, ConversationEvent.event_type == "ai_message_sent")
        .count()
    )


def _stage_status(reached: List[bool]) -> List[str]:
    current_index = -1
    for i, is_reached in enumerate(reached):
        if is_reached:
            current_index = i
    statuses = []
    for i in range(len(reached)):
        if i < current_index:
            statuses.append("completed")
        elif i == current_index:
            statuses.append("active")
        else:
            statuses.append("pending")
    return statuses


def get_candidate_journey(db: Session, candidate_id: str, tenant_id: str) -> Dict:
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")

    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    first_reply = _first_candidate_reply(db, conversation)
    earliest_score = _earliest_job_score(db, candidate_id)
    latest_score = _latest_job_score(db, candidate_id)
    submission = _relevant_submission(db, candidate_id)
    interviews = (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.candidate_id == candidate_id, SubmissionInterview.superseded_at.is_(None))
        .order_by(SubmissionInterview.created_at.asc())
        .all()
        if submission is not None else []
    )
    offer = (
        db.query(OfferLetter)
        .filter(OfferLetter.candidate_id == candidate_id)
        .order_by(OfferLetter.created_at.desc())
        .first()
    )
    joining_score = (
        db.query(CandidateJoiningScore)
        .filter(CandidateJoiningScore.candidate_id == candidate_id)
        .order_by(CandidateJoiningScore.calculated_at.desc())
        .first()
        if offer is not None else None
    )
    documents = (
        db.query(PreboardingDocument)
        .filter(PreboardingDocument.candidate_id == candidate_id, PreboardingDocument.offer_id == offer.id, PreboardingDocument.status != "CANCELLED")
        .all()
        if offer is not None else []
    )
    employee = db.query(Employee).filter(Employee.candidate_id == candidate_id).first()

    reached = [
        conversation is not None,
        first_reply is not None,
        earliest_score is not None,
        len(interviews) > 0,
        offer is not None,
        offer is not None and offer.offer_status == "Accepted",
        employee is not None,
    ]
    statuses = _stage_status(reached)

    missing_fields = get_missing_fields(candidate, db)

    stages = []

    try:
        # Stage 1: ENGAGED
        response_time = None
        if conversation and first_reply:
            try:
                response_time = round((first_reply.created_at - conversation.created_at).total_seconds() / 3600, 1)
            except (TypeError, AttributeError) as e:
                from app.core.logging import logger
                logger.warning(f"[Journey] Stage 1 (ENGAGED) response_time calc failed for {candidate_id}: {e}")

        stages.append({
            "stage_name": "ENGAGED", "stage_label": "Engaged", "status": statuses[0],
            "entered_at": conversation.created_at if conversation else None,
            "exited_at": first_reply.created_at if first_reply else None,
            "metrics": {
                "channel": conversation.channel_preference if conversation else None,
                "response_time_hours": response_time,
            },
        })
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        from app.core.logging import logger
        logger.error(f"[Journey] Stage 1 (ENGAGED) failed for {candidate_id}: {e}", exc_info=True)
        raise

    try:
        # Stage 2: QUALIFYING
        profile_completeness_pct = None
        if TOTAL_PROFILE_FIELDS > 0:
            try:
                profile_completeness_pct = round(100 * (TOTAL_PROFILE_FIELDS - len(missing_fields)) / TOTAL_PROFILE_FIELDS)
            except (ZeroDivisionError, TypeError) as e:
                from app.core.logging import logger
                logger.warning(f"[Journey] Stage 2 (QUALIFYING) profile_completeness calc failed for {candidate_id}: TOTAL={TOTAL_PROFILE_FIELDS}, missing={len(missing_fields)}, error={e}")
        else:
            from app.core.logging import logger
            logger.warning(f"[Journey] Stage 2 (QUALIFYING) TOTAL_PROFILE_FIELDS is 0 for {candidate_id}")

        days_in_stage = None
        if first_reply:
            try:
                stage_end_time = earliest_score.calculated_at if earliest_score else datetime.utcnow()
                days_in_stage = (stage_end_time - first_reply.created_at).days
            except (TypeError, AttributeError) as e:
                from app.core.logging import logger
                logger.warning(f"[Journey] Stage 2 (QUALIFYING) days_in_stage calc failed for {candidate_id}: {e}")

        thunder_count = None
        try:
            thunder_count = _thunder_message_count(db, conversation)
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            from app.core.logging import logger
            logger.warning(f"[Journey] Stage 2 (QUALIFYING) thunder_message_count failed for {candidate_id}: {e}")

        stages.append({
            "stage_name": "QUALIFYING", "stage_label": "Qualifying", "status": statuses[1],
            "entered_at": first_reply.created_at if first_reply else None,
            "exited_at": earliest_score.calculated_at if earliest_score else None,
            "metrics": {
                "profile_completeness_pct": profile_completeness_pct,
                "missing_fields_count": len(missing_fields),
                "days_in_stage": days_in_stage,
                "thunder_message_count": thunder_count,
            },
        })
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        from app.core.logging import logger
        logger.error(f"[Journey] Stage 2 (QUALIFYING) failed for {candidate_id}: {e}", exc_info=True)
        raise

    # Stage 3: SCREENED
    stages.append({
        "stage_name": "SCREENED", "stage_label": "Screened", "status": statuses[2],
        "entered_at": earliest_score.calculated_at if earliest_score else None,
        "exited_at": interviews[0].created_at if interviews else None,
        "metrics": {
            "overall_score": latest_score.overall_score if latest_score else None,
            "technical_score": latest_score.technical_score if latest_score else None,
            "compensation_score": latest_score.compensation_score if latest_score else None,
            "availability_score": latest_score.availability_score if latest_score else None,
            "missing_fields_count": len(missing_fields),
        },
    })

    # Stage 4: INTERVIEW
    l1 = next((i for i in interviews if i.level == "L1"), None)
    l2 = next((i for i in interviews if i.level == "L2"), None)
    stages.append({
        "stage_name": "INTERVIEW", "stage_label": "Interview", "status": statuses[3],
        "entered_at": interviews[0].created_at if interviews else None,
        "exited_at": offer.created_at if offer else None,
        "metrics": {
            "l1_outcome": l1.outcome if l1 else None,
            "l1_scheduled_at": l1.scheduled_at if l1 else None,
            "l2_outcome": l2.outcome if l2 else None,
            "l2_scheduled_at": l2.scheduled_at if l2 else None,
        },
    })

    # Stage 5: OFFER
    stages.append({
        "stage_name": "OFFER", "stage_label": "Offer", "status": statuses[4],
        "entered_at": offer.created_at if offer else None,
        "exited_at": offer.responded_at if offer and offer.offer_status == "Accepted" else None,
        "metrics": {
            "released_at": offer.released_at if offer else None,
            "offer_expire_date": offer.offer_expire_date if offer else None,
            "offer_status": offer.offer_status if offer else None,
        },
    })

    try:
        # Stage 6: PREBOARDING
        received_count = sum(1 for d in documents if d.status in ("RECEIVED", "VERIFIED"))

        days_until_start = None
        if offer and offer.joining_date:
            try:
                days_until_start = (offer.joining_date - date.today()).days
            except (TypeError, AttributeError) as e:
                from app.core.logging import logger
                logger.warning(f"[Journey] Stage 6 (PREBOARDING) days_until_start calc failed for {candidate_id}: joining_date={offer.joining_date}, error={e}")

        stages.append({
            "stage_name": "PREBOARDING", "stage_label": "Preboarding", "status": statuses[5],
            "entered_at": offer.responded_at if offer and offer.offer_status == "Accepted" else None,
            "exited_at": employee.created_at if employee else None,
            "metrics": {
                "joining_readiness_score": joining_score.readiness_score if joining_score else None,
                "documents_received": received_count,
                "documents_total": len(documents),
                "days_until_start": days_until_start,
            },
        })
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        from app.core.logging import logger
        logger.error(f"[Journey] Stage 6 (PREBOARDING) failed for {candidate_id}: {e}", exc_info=True)
        raise

    # Stage 7: JOINED
    stages.append({
        "stage_name": "JOINED", "stage_label": "Joined", "status": statuses[6],
        "entered_at": employee.created_at if employee else None,
        "exited_at": None,
        "metrics": {
            "joining_date": employee.joining_date if employee else None,
            "employee_number": employee.employee_number if employee else None,
        },
    })

    current_stage = next((s["stage_name"] for s in stages if s["status"] == "active"), stages[0]["stage_name"])

    return {"candidate_id": candidate_id, "current_stage": current_stage, "stages": stages}

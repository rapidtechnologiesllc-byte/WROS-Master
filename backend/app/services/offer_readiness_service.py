"""
S-053/HRMS-0453 -- Offer Readiness Check.

Blockers:
  - the hiring pipeline has not reached OFFER: the recruiter screen, the L1 (technical)
    and L2 (management) round verdicts must all have passed, and the candidate must not
    have been rejected (hiring_pipeline_service; verdicts come from interviewer feedback)
  - experience below the 5-year rule (BR-02) -- also enforced before every interview, in the
    pipeline and at client submission (CEO 2026-10-10: at every step, so it is never missed)
  - an unresolved COMPLIANCE_BLOCK flag for the job
Warning (not a blocker): an unresolved COMPENSATION_MISMATCH flag (BR-03).

Before 2026-10 the interview checks read SubmissionInterview, which is keyed to a client
submission and written by nothing, so no offer could ever pass them.
"""
import logging
from typing import Dict

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_flag import CandidateJobFlag
from app.services.submission_service import check_experience_eligibility

logger = logging.getLogger(__name__)


def check_offer_readiness(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Step 2. Never raises internally on missing data -- a missing
    candidate/submission is itself reported as a real blocker, not an
    exception. Returns {"is_ready": bool, "blockers": [str], "warnings": [str]}."""
    blockers = []
    warnings = []

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        return {"is_ready": False, "blockers": ["Candidate not found."], "warnings": []}

    # BR-01: screen, L1 and L2 passed, not rejected -- the hiring pipeline's OFFER gate
    from app.services.hiring_pipeline_service import PipelineGateBlocked, assert_gate

    try:
        assert_gate(db, candidate_id, "OFFER")
    except PipelineGateBlocked as blocked:
        blockers.extend(blocked.blockers or [f"Candidate is at {blocked.stage}, not ready for an offer."])

    # Check 4 -- BR-03: warning, not a blocker
    comp_flag = (
        db.query(CandidateJobFlag)
        .filter(CandidateJobFlag.candidate_id == candidate_id, CandidateJobFlag.job_id == job_id, CandidateJobFlag.flag_type == "COMPENSATION_MISMATCH", CandidateJobFlag.is_resolved == False)  # noqa: E712
        .first()
    )
    if comp_flag is not None:
        warnings.append("Compensation mismatch flagged -- review before offering.")

    # Check 5 -- the 5-year rule again at offer (CEO: enforced at every step so it is never missed)
    experience_result = check_experience_eligibility(candidate)
    if not experience_result["is_eligible"]:
        blockers.append(f"Candidate does not meet the 5-year experience requirement: {experience_result['message']}")

    # Check 5b -- employment type by country (CEO 2026-10-15): never an offer to a C2C/1099 or a
    # type the candidate's country does not accept (UNKNOWN is confirmed by the offer itself)
    from app.services.employment_type_policy import interview_check

    employment_result = interview_check(candidate)
    if not employment_result["allowed"]:
        blockers.append(employment_result["message"])

    # Check 6 -- hard blocker
    compliance_flag = (
        db.query(CandidateJobFlag)
        .filter(CandidateJobFlag.candidate_id == candidate_id, CandidateJobFlag.job_id == job_id, CandidateJobFlag.flag_type == "COMPLIANCE_BLOCK", CandidateJobFlag.is_resolved == False)  # noqa: E712
        .first()
    )
    if compliance_flag is not None:
        blockers.append("Outstanding compliance flag(s) must be resolved before offering.")

    is_ready = len(blockers) == 0

    # Step 4 -- logged against the candidate's most recent conversation,
    # the real, universal audit log every other story in this codebase
    # uses; a cheap best-effort, never blocks the readiness result itself.
    try:
        conversation = (
            db.query(CandidateConversation)
            .filter(CandidateConversation.candidate_id == candidate_id)
            .order_by(CandidateConversation.id.desc())
            .first()
        )
        if conversation is not None:
            db.add(ConversationEvent(
                conversation_id=conversation.id, event_type="OFFER_READINESS_CHECKED",
                event_data={"candidate_id": candidate_id, "job_id": job_id, "is_ready": is_ready, "blockers": blockers}, triggered_by="system",
            ))
            db.commit()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OfferReadiness] Failed to log OFFER_READINESS_CHECKED for candidate {candidate_id!r}: {exc}")
        db.rollback()

    return {"is_ready": is_ready, "blockers": blockers, "warnings": warnings}

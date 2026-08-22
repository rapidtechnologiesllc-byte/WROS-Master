"""
S-053/HRMS-0453 -- Offer Readiness Check.

Real architecture adaptations:
- No unified "interviews table with job_id" exists. This codebase has
  TWO separate interview systems (see interview_pipeline.py's own
  module docstring): the legacy `Interview` (candidate+job, no L1/L2,
  no outcome) and `SubmissionInterview` (candidate+submission, real
  L1/L2 levels, real PENDING/PASS/FAIL outcome -- exactly what BR-01
  needs). `SubmissionInterview` is the real data source for Checks
  2/3; the legacy `Interview` model has no outcome concept at all and
  is not used here.
- A further, genuine architectural fork: `SubmissionInterview` is keyed
  by `submission_id` -> `Submission.demand_id` (the newer Phase-2
  Demand/Submission pipeline), while `candidate_job_flags`/
  `candidate_job_scores` (S-037/S-038, Checks 4/5/6's real data) are
  keyed by `job_id` -> `Jobs.jobID` (the older, free-text Jobs model).
  There is NO bridge/join key between `Jobs` and `Demand`/`Submission`
  anywhere in this codebase. `check_offer_readiness()` therefore takes
  BOTH identifiers explicitly (`candidate_id`, `job_id` for the
  flags/experience checks, matching the literal spec's own param
  list) and separately resolves "the candidate's most recent
  Submission" (by `candidate_id` alone, ordered by `submitted_at`
  descending, ANY status -- deliberately not filtered to
  interview-eligible statuses the way `calendar_matching_service`'s
  private resolver is, since Check 1 specifically needs to catch a
  WITHDRAWN/REJECTED_BY_CLIENT submission) for the interview-outcome
  checks. A candidate with multiple simultaneous submissions across
  different demands is a real, flagged limitation here, same category
  as S-048's own submission-resolution gap.
- Check 1's "candidate.status WITHDRAWN or REJECTED" has no real data
  source: `Candidate.status` is a free-text field defaulting to
  "Active" with no WITHDRAWN/REJECTED values used anywhere in this
  codebase. The real signal is `Submission.status` (a genuine,
  DB-constrained enum that DOES include `WITHDRAWN`/
  `REJECTED_BY_CLIENT`) on the candidate's resolved submission.
- Check 5 (experience) reuses `submission_service.check_experience_eligibility()`
  directly rather than reimplementing the identical >=60-month
  threshold -- BR-02's own framing ("belt and suspenders,
  re-validating the same rule") makes this the correct reuse, not a
  duplicated check.
- Check 6 (COMPLIANCE_BLOCK): no story in this codebase has ever
  produced a `COMPLIANCE_BLOCK` `CandidateJobFlag` row (added to
  `FLAG_TYPES` by this story, see that model's own docstring) -- the
  check reads for one honestly; it will simply never fire until a
  future story writes one, not silently faked as always-clear.
- A no-show'd interview (S-052's `no_show_confirmed_at` set) has
  `outcome` still `PENDING` (S-052 never touches `outcome`) -- treated
  here as equivalent to "not completed" (a real blocker), which is the
  correct real-world reading and a genuine, deliberate bridge between
  S-052 and S-053, not silently ignored.
- `outcome_recorded_by` (Step 1's own schema sketch) is NOT added --
  no AC/TC exercises it, and `interview_service.set_outcome()` doesn't
  currently take a "who recorded it" param; adding an untested column
  with no real writer would be building ahead of what this story
  actually tests. `outcome_set_at` (already exists) is the real
  "outcome_recorded_at" equivalent.
"""
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.interview_pipeline import SubmissionInterview
from app.models.submission import Submission
from app.services.submission_service import check_experience_eligibility

WITHDRAWN_SUBMISSION_STATUSES = ("WITHDRAWN", "REJECTED_BY_CLIENT")
REQUIRED_LEVELS = ("L1", "L2")  # BR-01


def _resolve_relevant_submission(db: Session, candidate_id: str) -> Optional[Submission]:
    return (
        db.query(Submission)
        .filter(Submission.candidate_id == candidate_id)
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def _current_interview_for_level(db: Session, submission_id: str, level: str) -> Optional[SubmissionInterview]:
    return (
        db.query(SubmissionInterview)
        .filter(SubmissionInterview.submission_id == submission_id, SubmissionInterview.level == level, SubmissionInterview.superseded_at == None)  # noqa: E711
        .order_by(SubmissionInterview.created_at.desc())
        .first()
    )


def check_offer_readiness(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Step 2. Never raises internally on missing data -- a missing
    candidate/submission is itself reported as a real blocker, not an
    exception. Returns {"is_ready": bool, "blockers": [str], "warnings": [str]}."""
    blockers = []
    warnings = []

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        return {"is_ready": False, "blockers": ["Candidate not found."], "warnings": []}

    submission = _resolve_relevant_submission(db, candidate_id)

    # Check 1
    if submission is not None and submission.status in WITHDRAWN_SUBMISSION_STATUSES:
        blockers.append("Candidate has withdrawn or been rejected.")

    # Check 2/3 -- BR-01: both L1 and L2 must be outcome=PASS
    for level in REQUIRED_LEVELS:
        interview = _current_interview_for_level(db, submission.id, level) if submission is not None else None
        if interview is None:
            blockers.append(f"{level} interview not completed.")
        elif interview.no_show_confirmed_at is not None:
            blockers.append(f"Candidate did not join their {level} interview (no-show).")
        elif interview.outcome == "FAIL":
            blockers.append(f"Candidate failed {level} interview.")
        elif interview.outcome != "PASS":
            blockers.append(f"{level} interview not completed.")

    # Check 4 -- BR-03: warning, not a blocker
    comp_flag = (
        db.query(CandidateJobFlag)
        .filter(CandidateJobFlag.candidate_id == candidate_id, CandidateJobFlag.job_id == job_id, CandidateJobFlag.flag_type == "COMPENSATION_MISMATCH", CandidateJobFlag.is_resolved == False)  # noqa: E712
        .first()
    )
    if comp_flag is not None:
        warnings.append("Compensation mismatch flagged -- review before offering.")

    # Check 5 -- BR-02, reused from HRMS-P601 directly
    experience_result = check_experience_eligibility(candidate)
    if not experience_result["is_eligible"]:
        blockers.append("Candidate does not meet 5-year experience requirement.")

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
        logger.warning(f"[OfferReadiness] Failed to log OFFER_READINESS_CHECKED for candidate {candidate_id!r}: {exc}")
        db.rollback()

    return {"is_ready": is_ready, "blockers": blockers, "warnings": warnings}

"""
import logging
HRMS-0711 -- Client Submission Pipeline, Phase 2 Domain 2.

Compliance gates (checkExperienceEligibility / checkMarketProfileRule /
checkEmploymentTypeRule) are HRMS-P601 / HRMS-P605 / HRMS-P606's *hard
block* only. Per this session's confirmed direction:

  - checkExperienceEligibility(): real 60-month gate against
    candidates.total_experience_months. HRMS-P601's Director+BU Head
    sequential override workflow is NOT built -- there is currently no
    way to submit an ineligible candidate, full stop. Flagged as
    follow-up work once EPIC-P6 lands and Director/BU Head roles exist
    in this codebase's RBAC.
  - checkMarketProfileRule(): real gate against the linked Employee's
    status (BENCH/ACTIVE/ALLOCATED), not a `candidates.status` field --
    this codebase doesn't have one, and the actual BENCH/ACTIVE/
    ALLOCATED states already live on Employee (HRMS-0101). A candidate
    with no linked Employee row at all (never converted, HRMS-0708) is
    blocked the same as one with a disallowed status.
  - checkEmploymentTypeRule(): real gate against candidates.employment_type,
    fails closed on UNKNOWN same as C2C, per HRMS-P606.

All three gates run and their results are collected before raising, so a
recruiter sees every blocker at once, per HRMS-0711 BR-01. Every failed
gate is logged to SubmissionViolation. What's explicitly NOT built:
the 3-strike/5-strike compliance-review + account-suspension escalation
that's supposed to read that log (HRMS-P605/P606) and HRMS-0440's full
AI ranking (submission_rank here is caller-supplied, e.g. from the
existing ATSScore.overall_score -- not recomputed by this module).
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.submission import (
    ALLOWED_SUBMISSION_TRANSITIONS,
    Submission,
    SubmissionViolation,
)
from app.services.demand_service import record_placement, transition_demand_status

MIN_EXPERIENCE_MONTHS = 60  # HRMS-P601 -- 5 years, R-01

# HRMS-P605 -- only these Employee statuses may be submitted to a client.
# ACTIVE here is this codebase's equivalent of the doc's ACTIVE_EMPLOYEE.
MARKET_PROFILE_ALLOWED_EMPLOYEE_STATUSES = {"BENCH", "ACTIVE", "ALLOCATED"}

# HRMS-P606 -- only W2_FULLTIME may be submitted; UNKNOWN fails closed
# same as C2C/1099 (BR-02 of that story).
EMPLOYMENT_TYPE_ALLOWED = {"W2_FULLTIME"}

logger = logging.getLogger(__name__)

class SubmissionComplianceError(Exception):
    """Raised with every failed gate's blocker, not just the first."""

    def __init__(self, blockers: List[dict]):
        self.blockers = blockers
        super().__init__(f"Submission blocked: {[b['error'] for b in blockers]}")


class DemandNotOpenForSubmission(Exception):
    pass


class DuplicateSubmission(Exception):
    pass


class InvalidSubmissionTransition(Exception):
    pass


def check_experience_eligibility(candidate: Candidate) -> dict:
    months = candidate.total_experience_months
    if months is None:
        return {
            "is_eligible": False, "status": "INELIGIBLE",
            "error": "EXPERIENCE_INELIGIBLE",
            "message": "Candidate experience has not been verified yet.",
        }
    if months >= MIN_EXPERIENCE_MONTHS:
        return {"is_eligible": True, "status": "ELIGIBLE", "experience_months": months}
    deficit = MIN_EXPERIENCE_MONTHS - months
    return {
        "is_eligible": False, "status": "INELIGIBLE",
        "error": "EXPERIENCE_INELIGIBLE",
        "message": (
            f"Candidate has {months} months of experience. Minimum required is "
            f"{MIN_EXPERIENCE_MONTHS} months (5 years). Deficit: {deficit} months."
        ),
        "experience_months": months, "deficit_months": deficit,
    }


def check_market_profile_rule(db: Session, candidate_id: str) -> dict:
    employee = db.query(Employee).filter(Employee.candidate_id == candidate_id).first()
    if employee is None:
        return {
            "allowed": False, "candidate_status": "NO_EMPLOYEE_RECORD",
            "error": "MARKET_PROFILE_SUBMISSION_BLOCKED",
            "message": "Candidate has not been converted to a BlitzenX employee yet.",
        }
    if employee.status not in MARKET_PROFILE_ALLOWED_EMPLOYEE_STATUSES:
        return {
            "allowed": False, "candidate_status": employee.status,
            "error": "MARKET_PROFILE_SUBMISSION_BLOCKED",
            "message": (
                f"Employee status is {employee.status}. Only BENCH, ACTIVE, or "
                f"ALLOCATED employees may be submitted to clients."
            ),
        }
    return {"allowed": True, "candidate_status": employee.status}


def check_employment_type_rule(candidate: Candidate) -> dict:
    if candidate.employment_type in EMPLOYMENT_TYPE_ALLOWED:
        return {"allowed": True, "employment_type": candidate.employment_type}
    return {
        "allowed": False, "employment_type": candidate.employment_type,
        "error": "C2C_NOT_ACCEPTED",
        "message": "BlitzenX only accepts full-time (W2) candidates.",
    }


def _log_violation(
    db: Session, *, tenant_id: Optional[int], recruiter_user_id: Optional[str],
    candidate_id: str, violation_type: str, candidate_status_at_time: Optional[str],
    blocked_message: str,
) -> None:
    db.add(SubmissionViolation(
        tenant_id=tenant_id, recruiter_user_id=recruiter_user_id, candidate_id=candidate_id,
        violation_type=violation_type, candidate_status_at_time=candidate_status_at_time,
        blocked_message=blocked_message,
    ))


def create_submission(
    db: Session,
    *,
    tenant_id: Optional[int],
    demand: Demand,
    candidate: Candidate,
    submitted_by_user_id: Optional[str] = None,
    submission_rank: Optional[int] = None,
    submitted_as_resume_url: Optional[str] = None,
    source: str = "INTERNAL",
    subvendor_id: Optional[str] = None,
) -> Submission:
    """
    Runs all three compliance gates (BR-01 of HRMS-0711: all violations
    returned, not just the first), then the demand-status and duplicate
    checks. Raises SubmissionComplianceError / DemandNotOpenForSubmission
    / DuplicateSubmission on failure -- never partially inserts.
    """
    blockers: List[dict] = []

    experience = check_experience_eligibility(candidate)
    if not experience["is_eligible"]:
        blockers.append(experience)
        _log_violation(
            db, tenant_id=tenant_id, recruiter_user_id=submitted_by_user_id,
            candidate_id=candidate.candidateID, violation_type="EXPERIENCE_INELIGIBLE",
            candidate_status_at_time=str(candidate.total_experience_months),
            blocked_message=experience["message"],
        )

    market_profile = check_market_profile_rule(db, candidate.candidateID)
    if not market_profile["allowed"]:
        blockers.append(market_profile)
        _log_violation(
            db, tenant_id=tenant_id, recruiter_user_id=submitted_by_user_id,
            candidate_id=candidate.candidateID, violation_type="NO_MARKET_PROFILE",
            candidate_status_at_time=market_profile["candidate_status"],
            blocked_message=market_profile["message"],
        )

    employment_type = check_employment_type_rule(candidate)
    if not employment_type["allowed"]:
        blockers.append(employment_type)
        _log_violation(
            db, tenant_id=tenant_id, recruiter_user_id=submitted_by_user_id,
            candidate_id=candidate.candidateID, violation_type="C2C_NOT_ACCEPTED",
            candidate_status_at_time=employment_type["employment_type"],
            blocked_message=employment_type["message"],
        )

    if blockers:
        db.flush()
        raise SubmissionComplianceError(blockers)

    if demand.status not in ("OPEN", "IN_PROGRESS"):
        raise DemandNotOpenForSubmission(
            f"Cannot submit to demand in status '{demand.status}' -- must be OPEN or IN_PROGRESS."
        )

    # BU Scoping: Check if candidate is already locked to a different BU
    if hasattr(candidate, 'submission_bu_id') and candidate.submission_bu_id:
        demand_bu = demand.business_unit_id if hasattr(demand, 'business_unit_id') else None
        if demand_bu and candidate.submission_bu_id != demand_bu:
            raise SubmissionComplianceError([{
                "error": "BU_LOCKED",
                "message": f"Candidate is already locked to Business Unit {candidate.submission_bu_id}. Cannot submit to different BU."
            }])

    existing = db.query(Submission).filter(
        Submission.tenant_id == tenant_id,
        Submission.demand_id == demand.id,
        Submission.candidate_id == candidate.candidateID,
    ).first()
    if existing:
        raise DuplicateSubmission(
            f"Candidate {candidate.candidateID} is already submitted to demand {demand.id}."
        )

    submission = Submission(
        tenant_id=tenant_id, demand_id=demand.id, client_id=demand.client_id,
        candidate_id=candidate.candidateID, submitted_by_user_id=submitted_by_user_id,
        submission_rank=submission_rank, submitted_as_resume_url=submitted_as_resume_url,
        source=source, subvendor_id=subvendor_id,
    )
    db.add(submission)

    # BU Scoping: Lock candidate to the job's business unit when submitted
    # Once submitted, no other BU can pursue this candidate
    if hasattr(demand, 'business_unit_id') and demand.business_unit_id:
        candidate.submission_bu_id = demand.business_unit_id
        db.merge(candidate)

    if demand.status == "OPEN":
        transition_demand_status(db, demand, "IN_PROGRESS", changed_by=submitted_by_user_id)

    return submission


def update_client_response(
    db: Session,
    submission: Submission,
    new_status: str,
    *,
    client_feedback: Optional[str] = None,
) -> Submission:
    """
    HRMS-0711 step 3 -- PATCH /submissions/{id}/client-response. On
    PLACED, calls demand_service.record_placement() -- the one
    sanctioned increment path, never a bare positions_filled += 1 here.
    """
    current = submission.status
    allowed = ALLOWED_SUBMISSION_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise InvalidSubmissionTransition(
            f"Cannot transition submission from '{current}' to '{new_status}'. "
            f"Allowed from '{current}': {sorted(allowed) or 'none (terminal state)'}"
        )

    submission.status = new_status
    submission.client_feedback = client_feedback
    submission.client_response_at = datetime.utcnow()
    db.add(submission)

    if new_status == "PLACED":
        demand = db.query(Demand).filter(Demand.id == submission.demand_id).first()
        if demand is not None:
            record_placement(db, demand)

    return submission

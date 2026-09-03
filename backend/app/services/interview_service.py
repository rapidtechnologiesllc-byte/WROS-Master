"""
import logging
HRMS-0706 -- Interview Panel Assignment, Phase 2 Domain 2.

get_assigned_interviewer() is the helper HRMS-0448 (Calendar Matching
Engine, now built -- app.services.calendar_matching_service) calls to
know whose calendar to check. create_interview() itself is still
level-agnostic about *how* scheduled_at was decided -- HRMS-0448 calls
it with a real matched UTC datetime; a recruiter can still call it
directly with a manual scheduled_at for any interview HRMS-0448 either
hasn't run for yet or couldn't match.

R-05 (L1 must pass before L2) is enforced here, at creation time -- the
one hard rule from this domain that's cheap to enforce for real without
importing HRMS-P608's full auto-reject + BU Head reversal workflow
(deferred, see app.models.interview_pipeline docstring).
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.submission import Submission

logger = logging.getLogger(__name__)

class InterviewerNotEligible(Exception):
    """BR-01 of HRMS-0706: interviewer must be an ACTIVE employee with WROS access."""


class NoEligibleInterviewer(Exception):
    pass


class L1NotPassed(Exception):
    """R-05."""


class InvalidOutcomeChange(Exception):
    pass


def assign_panel_member(
    db: Session,
    *,
    tenant_id: Optional[int],
    demand_id: str,
    employee: Employee,
    interview_level: str,
    assigned_by: Optional[str] = None,
) -> DemandInterviewPanel:
    if employee.status != "ACTIVE" or not employee.wros_user_id:
        raise InterviewerNotEligible(
            "Interviewer must be an ACTIVE employee with WROS access (wros_user_id set)."
        )

    existing = db.query(DemandInterviewPanel).filter(
        DemandInterviewPanel.tenant_id == tenant_id,
        DemandInterviewPanel.demand_id == demand_id,
        DemandInterviewPanel.interview_level == interview_level,
        DemandInterviewPanel.employee_id == employee.id,
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.assigned_by = assigned_by
            db.add(existing)
        return existing

    panel_member = DemandInterviewPanel(
        tenant_id=tenant_id, demand_id=demand_id, employee_id=employee.id,
        interview_level=interview_level, assigned_by=assigned_by,
    )
    db.add(panel_member)
    return panel_member


def remove_panel_member(db: Session, panel_member: DemandInterviewPanel) -> DemandInterviewPanel:
    panel_member.is_active = False
    db.add(panel_member)
    return panel_member


def get_assigned_interviewer(
    db: Session, *, demand_id: str, interview_level: str, tenant_id: Optional[int] = None,
) -> Optional[DemandInterviewPanel]:
    """
    Returns the least-loaded active panel member for this demand+level
    (round-robin by current PENDING interview count, tie-broken by
    earliest assigned_at), or None if no one is assigned.
    """
    candidates = db.query(DemandInterviewPanel).filter(
        DemandInterviewPanel.tenant_id == tenant_id,
        DemandInterviewPanel.demand_id == demand_id,
        DemandInterviewPanel.interview_level == interview_level,
        DemandInterviewPanel.is_active == True,  # noqa: E712
    ).order_by(DemandInterviewPanel.assigned_at.asc()).all()

    if not candidates:
        return None

    load = {
        panel_id: count for panel_id, count in
        db.query(SubmissionInterview.panel_id, func.count(SubmissionInterview.id))
        .filter(
            SubmissionInterview.panel_id.in_([c.id for c in candidates]),
            SubmissionInterview.outcome == "PENDING",
        )
        .group_by(SubmissionInterview.panel_id)
        .all()
    }
    return min(candidates, key=lambda c: load.get(c.id, 0))


def create_interview(
    db: Session,
    *,
    tenant_id: Optional[int],
    submission: Submission,
    level: str,
    panel: Optional[DemandInterviewPanel] = None,
    scheduled_at=None,
    reschedule_count: int = 0,
    rescheduled_from_interview_id: Optional[str] = None,
) -> SubmissionInterview:
    """
    R-05: an L2 interview cannot be created unless an L1 interview for
    the same submission already has outcome='PASS'.

    reschedule_count/rescheduled_from_interview_id (S-051/HRMS-0451):
    the caller (interview_reschedule_service) is responsible for
    marking the OLD interview's superseded_at BEFORE calling this --
    the partial unique index (ix_one_current_interview_per_level, see
    the model's own docstring) only allows a second CURRENT row for
    the same submission+level once the old one is superseded.
    """
    if level == "L2":
        l1 = db.query(SubmissionInterview).filter(
            SubmissionInterview.submission_id == submission.id,
            SubmissionInterview.level == "L1",
            SubmissionInterview.superseded_at == None,  # noqa: E711 -- the CURRENT L1 in the chain, not a superseded one
        ).first()
        if l1 is None or l1.outcome != "PASS":
            raise L1NotPassed(
                "Cannot schedule an L2 interview until the L1 interview for this "
                "submission has outcome=PASS."
            )

    if panel is None:
        panel = get_assigned_interviewer(
            db, demand_id=submission.demand_id, interview_level=level, tenant_id=tenant_id,
        )
        if panel is None:
            raise NoEligibleInterviewer(
                f"No active {level} interviewer assigned for demand {submission.demand_id}."
            )

    interview = SubmissionInterview(
        tenant_id=tenant_id, submission_id=submission.id, candidate_id=submission.candidate_id,
        level=level, panel_id=panel.id, scheduled_at=scheduled_at,
        reschedule_count=reschedule_count, rescheduled_from_interview_id=rescheduled_from_interview_id,
    )
    db.add(interview)
    return interview


def set_outcome(db: Session, interview: SubmissionInterview, outcome: str) -> SubmissionInterview:
    """Outcome is settable exactly once, PENDING -> PASS/FAIL -- no
    silent re-flip. A real correction path (à la EPIC-07's locked
    scorecard + corrections table) is future scope, not built here."""
    if interview.outcome != "PENDING":
        raise InvalidOutcomeChange(
            f"Interview outcome is already '{interview.outcome}' and cannot be changed."
        )
    if outcome not in ("PASS", "FAIL"):
        raise InvalidOutcomeChange(f"Outcome must be PASS or FAIL, got '{outcome}'.")

    interview.outcome = outcome
    interview.outcome_set_at = datetime.utcnow()
    db.add(interview)
    return interview

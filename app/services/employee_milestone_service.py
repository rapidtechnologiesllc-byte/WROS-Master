"""
S-356/HRMS-0517 -- Employee Milestone Tracker: Personal, Project & Org.

scan_overdue_milestones() is the idempotent, directly-callable function
a nightly job would invoke -- same "cron wiring is deferred, the
function itself is real" posture as every other scheduled-job story in
this codebase (e.g. HRMS-0901's weekly draft job, scan_timesheet_
anomalies()).
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee_milestone import (
    OPEN_MILESTONE_STATUSES,
    EmployeeMilestone,
)
from app.services.performance_store_service import write_performance_event

ON_TIME_COMPLETION_SCORE = 100
LATE_COMPLETION_SCORE = 70


class MilestoneValidationError(Exception):
    pass


class InvalidMilestoneTransition(Exception):
    pass


def create_milestone(
    db: Session, *, milestone_type: str, title: str, target_date: date,
    tenant_id: Optional[int] = None, project_id: Optional[str] = None,
    employee_id: Optional[str] = None, description: Optional[str] = None,
    set_by: Optional[str] = None,
) -> EmployeeMilestone:
    """BR (Not In Scope note): set by RM/BU Head/PM only -- no employee
    self-service creation. Enforced at the API layer (auth dependency),
    not here, same posture as every other role-gated write this
    program."""
    if milestone_type == "PROJECT" and not project_id:
        raise MilestoneValidationError("project_id is required for a PROJECT milestone.")
    if milestone_type in ("PERSONAL", "ORG") and not employee_id:
        raise MilestoneValidationError(f"employee_id is required for a {milestone_type} milestone.")

    milestone = EmployeeMilestone(
        tenant_id=tenant_id, project_id=project_id, employee_id=employee_id,
        milestone_type=milestone_type, title=title, description=description,
        target_date=target_date, set_by=set_by,
    )
    db.add(milestone)
    return milestone


def complete_milestone(
    db: Session, milestone: EmployeeMilestone, *, completion_notes: Optional[str] = None,
    now: Optional[date] = None,
) -> EmployeeMilestone:
    """
    AC-5/BR: completed_date is ALWAYS system-set to today -- there is no
    parameter for a caller-supplied date, so backdating is structurally
    impossible, not just validated against.

    AC-3: PERSONAL/PROJECT completions with an employee_id auto-write a
    MILESTONE_COMPLETED performance event, scored 100 on-time / 70 late
    per the doc's own "punctuality matters" note. ORG milestones and any
    milestone with no employee_id (a pure PROJECT-level checkpoint) are
    not individual performance signals, so they don't write one.
    """
    if milestone.status not in OPEN_MILESTONE_STATUSES:
        raise InvalidMilestoneTransition(
            f"Cannot complete a milestone in status '{milestone.status}'."
        )

    today = now or date.today()
    milestone.status = "COMPLETED"
    milestone.completed_date = today
    milestone.completion_notes = completion_notes
    db.add(milestone)

    if milestone.milestone_type in ("PERSONAL", "PROJECT") and milestone.employee_id:
        on_time = today <= milestone.target_date
        write_performance_event(
            db, employee_id=milestone.employee_id, event_type="MILESTONE_COMPLETED",
            tenant_id=milestone.tenant_id,
            event_data={
                "milestone_id": milestone.id, "title": milestone.title,
                "milestone_type": milestone.milestone_type,
                "score": ON_TIME_COMPLETION_SCORE if on_time else LATE_COMPLETION_SCORE,
                "on_time": on_time,
            },
        )

    return milestone


def scan_overdue_milestones(db: Session, *, tenant_id: Optional[int] = None, now: Optional[date] = None) -> List[EmployeeMilestone]:
    """
    AC-2/AC-4: every open (PENDING/IN_PROGRESS) milestone past its
    target_date flips to OVERDUE and writes a MILESTONE_OVERDUE
    performance event (negative signal for the future AI Assessor,
    HRMS-0518) -- idempotent: an already-OVERDUE milestone is simply not
    matched again on a re-run, no duplicate event.
    """
    today = now or date.today()
    query = db.query(EmployeeMilestone).filter(
        EmployeeMilestone.status.in_(OPEN_MILESTONE_STATUSES),
        EmployeeMilestone.target_date < today,
    )
    if tenant_id is not None:
        query = query.filter(EmployeeMilestone.tenant_id == tenant_id)

    overdue = query.all()
    for milestone in overdue:
        milestone.status = "OVERDUE"
        db.add(milestone)
        if milestone.milestone_type in ("PERSONAL", "PROJECT") and milestone.employee_id:
            write_performance_event(
                db, employee_id=milestone.employee_id, event_type="MILESTONE_OVERDUE",
                tenant_id=milestone.tenant_id,
                event_data={
                    "milestone_id": milestone.id, "title": milestone.title,
                    "milestone_type": milestone.milestone_type, "target_date": milestone.target_date.isoformat(),
                },
            )
    return overdue


def get_employee_milestones(db: Session, employee_id: str) -> List[EmployeeMilestone]:
    return (
        db.query(EmployeeMilestone)
        .filter(EmployeeMilestone.employee_id == employee_id)
        .order_by(EmployeeMilestone.target_date.asc())
        .all()
    )

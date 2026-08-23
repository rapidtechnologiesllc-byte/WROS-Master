"""
S-365/HRMS-0521 -- Buddy Program Graduation Gate: BU Head Approval.

record_graduation_decision() is the one function that ever moves a
buddy_program_records row (and its employee) through GRADUATE/EXTEND/
EXIT -- reuses app.services.employee_service.transition_employee_status()
for the actual Employee.status change rather than setting it directly,
same one-sanctioned-function discipline as everywhere else in this
codebase.

Not built here, flagged rather than silently skipped: the 48-hour BU
Head SLA escalation (Step 3) is a cron-shaped check ("if no decision in
48 hours, escalate to Director") with no scheduler in this codebase --
same "idempotent function exists, scheduling is follow-up" posture as
every other cron-shaped story already in this codebase. A future
build's escalate_overdue_graduation_reviews() would query
buddy_program_records for scorecard-ready-but-undecided rows past 48h
and call send_notification(priority_tier="P0", ...), reusing the real
notification path already built.
"""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.buddy_program import BuddyProgramRecord
from app.models.employee import Employee
from app.services.employee_service import transition_employee_status

MAX_EXTENSIONS = 2  # BR: third review is Graduate or Exit only
EXTENSION_DAYS = 15
MIN_EXTENSION_NOTE_LENGTH = 50
DECISIONS = ("GRADUATE", "EXTEND", "EXIT")


class InvalidGraduationDecision(Exception):
    pass


class ExtensionLimitReached(Exception):
    """BR: max 2 extensions -- the third review only offers Graduate or Exit."""


def can_extend(record: BuddyProgramRecord) -> bool:
    """AC-5/TC-002: whether the [Extend 15 Days] option should even be
    shown -- hidden entirely on the third review, not just rejected
    after the fact."""
    return record.extension_count < MAX_EXTENSIONS


def record_graduation_decision(
    db: Session,
    record: BuddyProgramRecord,
    employee: Employee,
    *,
    decision: str,
    changed_by: str,
    notes: Optional[str] = None,
) -> BuddyProgramRecord:
    """
    decision: one of DECISIONS. `notes` is required (min 50 chars) for
    EXTEND (BR: "log which specific KPIs need improvement"); optional
    for GRADUATE/EXIT.
    """
    if decision not in DECISIONS:
        raise InvalidGraduationDecision(f"decision must be one of {DECISIONS}, got '{decision}'.")

    if decision == "EXTEND":
        if not can_extend(record):
            raise ExtensionLimitReached(
                f"Buddy program record {record.id} has already used {record.extension_count} "
                f"extensions (max {MAX_EXTENSIONS}) -- only Graduate or Exit are available now."
            )
        if not notes or len(notes) < MIN_EXTENSION_NOTE_LENGTH:
            raise InvalidGraduationDecision(
                f"EXTEND requires notes on which KPIs need improvement, at least "
                f"{MIN_EXTENSION_NOTE_LENGTH} characters (got {len(notes) if notes else 0})."
            )

        record.extension_count += 1
        record.expected_end_date = record.expected_end_date + timedelta(days=EXTENSION_DAYS)
        record.status = "EXTENDED"
        record.extension_reason = notes
        employee.buddy_program_status = "EXTENDED"

    elif decision == "GRADUATE":
        record.status = "GRADUATED"
        record.actual_end_date = date.today()
        employee.buddy_program_status = "GRADUATED"
        employee.buddy_program_graduation_date = date.today()
        transition_employee_status(
            db, employee, "SPECIALITY_READY",
            reason="Buddy Program graduation approved by BU Head.", changed_by=changed_by,
        )

    else:  # EXIT
        record.status = "EXITED"
        employee.buddy_program_status = "EXITED"
        transition_employee_status(
            db, employee, "PERFORMANCE_MANAGED",
            reason=notes or "Buddy Program exit -- performance management initiated.", changed_by=changed_by,
        )

    decision_note = f"[{decision}] by {changed_by} on {date.today().isoformat()}"
    if notes:
        decision_note += f": {notes}"
    record.bu_head_decision_notes = (
        f"{record.bu_head_decision_notes}\n{decision_note}" if record.bu_head_decision_notes else decision_note
    )

    db.add(record)
    db.add(employee)
    return record

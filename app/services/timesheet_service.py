"""
HRMS-0901 -- Timesheet Submission -- and HRMS-0902 -- Timesheet
Approval Workflow.

Scheduled jobs described in both stories (TimesheetCreationJob every
Monday 6 AM, TimesheetApprovalReminderJob daily) are NOT wired to
APScheduler in this pass -- create_weekly_draft() is the idempotent
function a cron would call; wiring the actual cron trigger is follow-up
work, not built here. Likewise HRMS-0902's `timesheet.approved` event
publish and employee/approver email notifications are not built --
no event bus exists in this codebase, and the notification would go
through EmailService directly per this session's established pattern
(see app.services.client_service.assign_account_manager's docstring for
the same caveat re: HRMS-0113 not actually existing yet).

Role gating (HRMS-0902 BR-01: only RM/Admin may approve) is an API-
layer concern -- no REST endpoints exist yet for this domain, matching
every other Phase 2 entity built this session (Employee/Client/Demand/
Submission/Interview). Whoever builds the endpoint must add that check;
these functions trust the caller.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import (
    MAX_SUBMISSION_LOOKBACK_WEEKS,
    MAX_WEEKLY_HOURS,
    Timesheet,
    TimesheetEntry,
)


class AllocationNotActive(Exception):
    """BR-04: bench employees (no active allocation) don't get timesheets."""


class InvalidTimesheetEntry(Exception):
    pass


class TimesheetNotEditable(Exception):
    """BR-03 of HRMS-0902: an APPROVED timesheet's entries are immutable."""


class InvalidTimesheetTransition(Exception):
    pass


class StaleTimesheetSubmission(Exception):
    """BR-02: no submissions for weeks more than 4 calendar weeks past."""


def create_weekly_draft(
    db: Session, allocation: EmployeeAllocation, week_starting_date: date,
    *, tenant_id: Optional[int] = None,
) -> Timesheet:
    """Idempotent -- returns the existing DRAFT/SUBMITTED/etc. timesheet
    for this employee+allocation+week if one already exists, rather than
    erroring or duplicating (the UNIQUE constraint would catch a
    duplicate insert anyway, but this makes the weekly-cron call site
    trivial: just call this every Monday, no existence check needed)."""
    if allocation.status != "ACTIVE":
        raise AllocationNotActive(
            f"Allocation {allocation.id} is not ACTIVE -- bench employees do not get timesheets."
        )
    if week_starting_date.weekday() != 0:
        raise InvalidTimesheetEntry("week_starting_date must be a Monday.")

    existing = db.query(Timesheet).filter(
        Timesheet.tenant_id == tenant_id,
        Timesheet.employee_id == allocation.employee_id,
        Timesheet.allocation_id == allocation.id,
        Timesheet.week_starting_date == week_starting_date,
    ).first()
    if existing:
        return existing

    timesheet = Timesheet(
        tenant_id=tenant_id, employee_id=allocation.employee_id, allocation_id=allocation.id,
        week_starting_date=week_starting_date,
    )
    db.add(timesheet)
    return timesheet


def upsert_entries(db: Session, timesheet: Timesheet, entries: List[dict]) -> Timesheet:
    """
    entries: list of {entry_date, hours, entry_type, notes}. Enforces
    BR-01 (60h weekly cap) and "no future dates" at this layer too, not
    just at submit -- matching the doc's own PUT /entries validation.
    """
    if timesheet.status == "APPROVED":
        raise TimesheetNotEditable("Approved timesheets are immutable -- use the dispute process instead.")

    today = date.today()
    by_date = {e.entry_date: e for e in db.query(TimesheetEntry).filter(
        TimesheetEntry.timesheet_id == timesheet.id
    ).all()}

    for entry in entries:
        entry_date = entry["entry_date"]
        hours = entry["hours"]
        entry_type = entry.get("entry_type", "BILLABLE")

        if entry_date > today:
            raise InvalidTimesheetEntry(f"Cannot log hours for a future date: {entry_date}.")
        if hours < 0 or hours > 24:
            raise InvalidTimesheetEntry(f"Hours for {entry_date} must be between 0 and 24, got {hours}.")

        existing = by_date.get(entry_date)
        if existing:
            existing.hours = hours
            existing.entry_type = entry_type
            existing.notes = entry.get("notes")
            db.add(existing)
        else:
            new_entry = TimesheetEntry(
                timesheet_id=timesheet.id, entry_date=entry_date,
                hours=hours, entry_type=entry_type, notes=entry.get("notes"),
            )
            db.add(new_entry)
            by_date[entry_date] = new_entry

    total = sum(float(e.hours) for e in by_date.values())
    if total > MAX_WEEKLY_HOURS:
        raise InvalidTimesheetEntry(
            f"Total hours for the week ({total}) exceed the {MAX_WEEKLY_HOURS}-hour weekly maximum."
        )

    billable = sum(float(e.hours) for e in by_date.values() if e.entry_type == "BILLABLE")
    timesheet.total_hours = total
    timesheet.billable_hours = billable
    timesheet.non_billable_hours = total - billable
    db.add(timesheet)
    return timesheet


def submit_timesheet(db: Session, timesheet: Timesheet) -> Timesheet:
    if timesheet.status != "DRAFT":
        raise InvalidTimesheetTransition(f"Cannot submit a timesheet in status '{timesheet.status}'.")

    entry_count = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).count()
    if entry_count == 0 or float(timesheet.total_hours) <= 0:
        raise InvalidTimesheetEntry("Cannot submit a timesheet with no logged hours.")

    weeks_ago = (date.today() - timesheet.week_starting_date).days // 7
    if weeks_ago > MAX_SUBMISSION_LOOKBACK_WEEKS:
        raise StaleTimesheetSubmission(
            f"Timesheet week ({timesheet.week_starting_date}) is more than "
            f"{MAX_SUBMISSION_LOOKBACK_WEEKS} weeks in the past -- cannot submit."
        )

    timesheet.status = "SUBMITTED"
    timesheet.submitted_at = datetime.utcnow()
    db.add(timesheet)
    return timesheet


def approve_timesheet(db: Session, timesheet: Timesheet, approved_by: Optional[str] = None) -> Timesheet:
    if timesheet.status != "SUBMITTED":
        raise InvalidTimesheetTransition(f"Cannot approve a timesheet in status '{timesheet.status}'.")

    timesheet.status = "APPROVED"
    timesheet.approved_by = approved_by
    timesheet.approved_at = datetime.utcnow()
    db.add(timesheet)
    return timesheet


def reject_timesheet(db: Session, timesheet: Timesheet, reason: str) -> Timesheet:
    if timesheet.status != "SUBMITTED":
        raise InvalidTimesheetTransition(f"Cannot reject a timesheet in status '{timesheet.status}'.")
    if len(reason or "") < 20:
        raise InvalidTimesheetEntry("Rejection reason must be at least 20 characters.")

    timesheet.status = "REJECTED"
    timesheet.rejection_reason = reason
    db.add(timesheet)
    return timesheet


def reopen_for_editing(db: Session, timesheet: Timesheet) -> Timesheet:
    """HRMS-0902 BR-02: a REJECTED timesheet returns to DRAFT so the
    employee can correct and re-submit. rejection_reason is preserved,
    not cleared, so it stays visible even once back in DRAFT."""
    if timesheet.status != "REJECTED":
        raise InvalidTimesheetTransition(f"Cannot reopen a timesheet in status '{timesheet.status}'.")

    timesheet.status = "DRAFT"
    db.add(timesheet)
    return timesheet


def bulk_approve(db: Session, timesheets: List[Timesheet], approved_by: Optional[str] = None) -> dict:
    approved = 0
    failed = []
    for ts in timesheets:
        try:
            approve_timesheet(db, ts, approved_by=approved_by)
            approved += 1
        except InvalidTimesheetTransition as exc:
            failed.append({"id": ts.id, "reason": str(exc)})
    return {"approved": approved, "failed": failed}

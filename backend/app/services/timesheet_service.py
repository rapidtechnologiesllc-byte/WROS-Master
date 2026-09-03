"""
HRMS-0901 -- Timesheet Submission -- and HRMS-0902 -- Timesheet
import logging
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
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.task import Task
from app.models.timesheet import (
    MAX_SUBMISSION_LOOKBACK_WEEKS,
    MAX_WEEKLY_HOURS,
    Timesheet,
    TimesheetEntry,
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

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


def create_weekly_draft_for_task(
    db: Session, task: Task, employee_id: str, week_starting_date: date,
    *, tenant_id: Optional[int] = None,
) -> Timesheet:
    """Backlog item, 2026-08-05 (Task<->Timesheet tie): the
    allocation-less sibling of create_weekly_draft() -- for internal
    Task work (an HR ticket, an IT request) with no client allocation
    to bill against. A separate function rather than an optional
    parameter on create_weekly_draft() so that function's existing
    signature/callers (many unrelated stories' test fixtures) are
    completely untouched. Same idempotent-by-lookup posture as
    create_weekly_draft()."""
    if week_starting_date.weekday() != 0:
        raise InvalidTimesheetEntry("week_starting_date must be a Monday.")

    existing = db.query(Timesheet).filter(
        Timesheet.tenant_id == tenant_id,
        Timesheet.employee_id == employee_id,
        Timesheet.task_id == task.id,
        Timesheet.week_starting_date == week_starting_date,
    ).first()
    if existing:
        return existing

    timesheet = Timesheet(
        tenant_id=tenant_id, employee_id=employee_id, task_id=task.id,
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

    # HRMS-0902: Send approval notifications to employee and approver.
    # This is async-friendly but runs inline for now (no event bus).
    # Notification failures do NOT block the approval.
    try:
        employee = db.query(Employee).filter(Employee.id == timesheet.employee_id).first()
        if employee and employee.email:
            # Calculate total hours from timesheet entries
            total_hours = sum(entry.hours or 0 for entry in timesheet.entries)
            week_starting = timesheet.week_starting_date.strftime("%Y-%m-%d") if timesheet.week_starting_date else "unknown"

            # Get approver name (fallback to ID if not found)
            approver_name = approved_by or "HR/Manager"
            if approved_by:
                approver = db.query(Employee).filter(Employee.email == approved_by).first()
                if approver:
                    approver_name = f"{approver.first_name} {approver.last_name}".strip() or approver_name

            EmailService.notify_timesheet_approved(
                employee_email=employee.email,
                employee_name=f"{employee.first_name} {employee.last_name}".strip() or "Employee",
                approver_email=approved_by or "admin@blitzenx.com",
                approver_name=approver_name,
                week_starting_date=week_starting,
                total_hours=total_hours,
            )
            logger.info(f"[Timesheet] Approval notifications sent for timesheet {timesheet.id}")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        # Log but don't raise — notifications should never block business logic
        logger.warning(f"[Timesheet] Failed to send approval notifications for {timesheet.id}: {e}")

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


def create_weekly_draft_batch(db: Session) -> dict:
    """
    Auto-creates weekly timesheet drafts for all active employees.
    Runs weekly (Monday 00:00 UTC) to pre-populate timesheets.
    Idempotent: if a timesheet already exists for an employee+week, it's skipped.

    Returns: dict with counts (created, skipped, errors)
    """
    from datetime import datetime, timedelta
    from app.models.employee import Employee
    from app.models.resource_management import EmployeeAllocation

    today = date.today()
    # Calculate the Monday of the current week
    week_starting_date = today - timedelta(days=today.weekday())

    created = 0
    skipped = 0
    errors = []

    # Get all active employees with active allocations
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.status == "ACTIVE"
    ).all()

    for allocation in allocations:
        try:
            timesheet = create_weekly_draft(
                db, allocation, week_starting_date, tenant_id=allocation.tenant_id
            )
            # Check if this is a newly created timesheet or an existing one
            if timesheet.created_at and (datetime.utcnow() - timesheet.created_at).total_seconds() < 300:
                created += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            errors.append({
                "allocation_id": allocation.id,
                "employee_id": allocation.employee_id,
                "error": str(exc)
            })

            db.commit()

    return {
        "created": created,
        "skipped": skipped,
        "errors": len(errors),
        "error_details": errors if errors else None,
        "week_starting": str(week_starting_date)
    }

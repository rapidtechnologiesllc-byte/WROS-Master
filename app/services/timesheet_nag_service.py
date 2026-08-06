"""
EPIC-16 -- Timesheet Nag Cascade. Mechanical pattern reused from the
S-355 design already scoped this session (scheduled dispatch -> one
reminder -> escalation-on-repeated-non-response, tracked against the
non-responder) -- applied here to timesheet submission.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet
from app.models.timesheet_nag import TimesheetNagLog
from app.models.user import Users
from app.services.notification_service import ChannelNotConfigured, send_notification

DEFAULT_ESCALATION_DAYS = 3


def scan_missing_timesheets(db: Session, *, week_starting_date: date, tenant_id: Optional[int] = None) -> List[Employee]:
    """Employees with an ACTIVE allocation covering this week who have
    no SUBMITTED or APPROVED timesheet for it -- a DRAFT never
    submitted still counts as missing."""
    allocation_query = db.query(EmployeeAllocation).filter(EmployeeAllocation.status == "ACTIVE")
    if tenant_id is not None:
        allocation_query = allocation_query.filter(EmployeeAllocation.tenant_id == tenant_id)
    employee_ids = {a.employee_id for a in allocation_query.all()}

    submitted_query = db.query(Timesheet.employee_id).filter(
        Timesheet.week_starting_date == week_starting_date, Timesheet.status.in_(("SUBMITTED", "APPROVED")),
    )
    submitted_employee_ids = {row[0] for row in submitted_query.all()}

    missing_ids = employee_ids - submitted_employee_ids
    if not missing_ids:
        return []
    return db.query(Employee).filter(Employee.id.in_(missing_ids)).all()


def trigger_timesheet_nag(
    db: Session, employee: Employee, *, week_starting_date: date,
    escalation_days: int = DEFAULT_ESCALATION_DAYS, tenant_id: Optional[int] = None, now: Optional[datetime] = None,
) -> Optional[TimesheetNagLog]:
    """Idempotent per (employee, week) via the DB unique constraint.
    First call nags the employee directly (P2); a later call, once
    escalation_days have passed since the last nag and the timesheet
    is still missing, escalates to the employee's reporting manager
    (P1) -- never re-nags more often than that. Returns None once a
    real SUBMITTED/APPROVED timesheet exists for that week (resolved,
    nothing left to nag)."""
    now = now or datetime.utcnow()

    already_submitted = (
        db.query(Timesheet)
        .filter(
            Timesheet.employee_id == employee.id, Timesheet.week_starting_date == week_starting_date,
            Timesheet.status.in_(("SUBMITTED", "APPROVED")),
        )
        .first()
    )
    log = (
        db.query(TimesheetNagLog)
        .filter(TimesheetNagLog.employee_id == employee.id, TimesheetNagLog.week_starting_date == week_starting_date)
        .first()
    )

    if already_submitted:
        if log and not log.resolved:
            log.resolved = True
            db.add(log)
            db.commit()
        return None

    employee_user = db.query(Users).filter(Users.UserEmail == employee.email).first()

    if log is None:
        log = TimesheetNagLog(
            tenant_id=tenant_id, employee_id=employee.id, week_starting_date=week_starting_date,
            escalation_level=1, last_nagged_at=now,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        if employee_user:
            try:
                send_notification(
                    db, calling_context_tenant_id=tenant_id, recipient=employee_user, priority_tier="P2",
                    message=f"Your timesheet for the week of {week_starting_date} hasn't been submitted yet.",
                )
            except ChannelNotConfigured:
                pass
        return log

    if log.resolved:
        return None

    days_since_last_nag = (now - log.last_nagged_at).days if log.last_nagged_at else escalation_days
    if log.escalation_level == 1 and days_since_last_nag >= escalation_days:
        log.escalation_level = 2
        log.last_nagged_at = now
        db.add(log)
        db.commit()
        db.refresh(log)
        if employee.reporting_manager_user_id:
            manager = db.query(Users).filter(Users.UserID == employee.reporting_manager_user_id).first()
            if manager:
                try:
                    send_notification(
                        db, calling_context_tenant_id=tenant_id, recipient=manager, priority_tier="P1",
                        message=f"{employee.first_name} {employee.last_name}'s timesheet for the week of {week_starting_date} is still not submitted after {escalation_days}+ days.",
                    )
                except ChannelNotConfigured:
                    pass
        return log

    return log


def run_timesheet_nag_job(db: Session) -> dict:
    """Scheduler wrapper, 2026-08-06 -- this logic existed and was fully
    tested but was never actually registered in app.core.scheduler,
    same "built, never wired to run" gap as ar_followup_service's own
    job wrapper below. Runs org-wide (scan_missing_timesheets/
    trigger_timesheet_nag are called with no tenant_id filter -- each
    Employee's own tenant_id is what gets stamped on the resulting
    TimesheetNagLog/notification), current week only (Monday-anchored,
    matching Timesheet.week_starting_date's own convention)."""
    today = date.today()
    week_starting_date = today - timedelta(days=today.weekday())
    processed = 0
    for employee in scan_missing_timesheets(db, week_starting_date=week_starting_date):
        if trigger_timesheet_nag(db, employee, week_starting_date=week_starting_date, tenant_id=employee.tenant_id) is not None:
            processed += 1
    return {"processed": processed}

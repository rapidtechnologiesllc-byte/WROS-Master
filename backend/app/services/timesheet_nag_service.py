"""
EPIC-16 -- Timesheet Nag Cascade (reworked CEO 2026-10-22).

Daily (scheduled job timesheet_reminders) for the week that just ended:
  - who owes a timesheet: everyone whose allocation (ACTIVE, or ENDED during/after that week)
    covered at least one day of it, and who has no SUBMITTED/APPROVED timesheet on that
    allocation for that week -- a DRAFT never submitted is still missing;
  - first run: the employee is emailed (send_staff_email, the working Graph path) and told in
    Flash; TIMESHEET_NAG_ESCALATION_DAYS later, still missing, their approver
    (timesheet_approval_service.resolve_approver) is emailed and told in Flash;
  - one log row per employee-week (uq_timesheet_nag_employee_week) and deterministic email keys:
    no reminder is ever sent twice for the same level;
  - nothing is skipped silently: an employee with no login goes straight to their approver, and
    an employee with no approver either is reported in the job result and the log.
"""
from datetime import date, datetime, timedelta
import logging
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet
from app.models.timesheet_nag import TimesheetNagLog
from app.models.user import Users

logger = logging.getLogger(__name__)


def scan_missing_timesheets(db: Session, *, week_starting_date: date, tenant_id: Optional[int] = None) -> List[Employee]:
    """Employees with an allocation covering any day of the week and no SUBMITTED/APPROVED
    timesheet on that allocation for it (a DRAFT never submitted counts as missing)."""
    week_end = week_starting_date + timedelta(days=6)
    query = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.status.in_(("ACTIVE", "ENDED")),
        EmployeeAllocation.start_date <= week_end,
        or_(EmployeeAllocation.end_date.is_(None), EmployeeAllocation.end_date >= week_starting_date),
    )
    if tenant_id is not None:
        query = query.filter(EmployeeAllocation.tenant_id == tenant_id)
    allocations = query.all()
    if not allocations:
        return []
    done = {(row[0], row[1]) for row in db.query(Timesheet.employee_id, Timesheet.allocation_id).filter(
        Timesheet.week_starting_date == week_starting_date, Timesheet.status.in_(("SUBMITTED", "APPROVED")),
        Timesheet.allocation_id.in_([a.id for a in allocations]))}
    missing_ids = {a.employee_id for a in allocations if (a.employee_id, a.id) not in done}
    if not missing_ids:
        return []
    return db.query(Employee).filter(Employee.id.in_(missing_ids), Employee.status != "EXITED").all()


def _still_missing(db: Session, employee: Employee, week_starting_date: date) -> bool:
    return employee.id in {e.id for e in scan_missing_timesheets(db, week_starting_date=week_starting_date,
                                                                  tenant_id=employee.tenant_id)}


def _tell(db: Session, user: Users, *, key: str, subject: str, text: str, link: str) -> None:
    """Email (queued; raises if it cannot be queued) and a Flash event."""
    from app.services.flash_conversation_service import post_event
    from app.services.staff_mail_service import queue_staff_email

    post_event(db, user.UserID, user.tenant_id, text, {"kind": "timesheet_reminder", "link": link})
    db.commit()
    queue_staff_email(user, key=key, subject=subject, paragraphs=[text], link_path=link, link_label="Open")


def trigger_timesheet_nag(
    db: Session, employee: Employee, *, week_starting_date: date,
    escalation_days: Optional[int] = None, tenant_id: Optional[int] = None, now: Optional[datetime] = None,
) -> Optional[TimesheetNagLog]:
    """One step of the cascade for one employee-week; idempotent. Returns None when the week is
    no longer missing (the log is resolved)."""
    from app.services.timesheet_approval_service import NoTimesheetApprover, resolve_approver

    now = now or datetime.utcnow()
    escalation_days = settings.TIMESHEET_NAG_ESCALATION_DAYS if escalation_days is None else escalation_days
    log = db.query(TimesheetNagLog).filter(TimesheetNagLog.employee_id == employee.id,
                                           TimesheetNagLog.week_starting_date == week_starting_date).first()
    if not _still_missing(db, employee, week_starting_date):
        if log and not log.resolved:
            log.resolved = True
            db.commit()
        return None

    name = f"{employee.first_name} {employee.last_name}".strip()
    login = db.get(Users, employee.wros_user_id) if employee.wros_user_id else None
    week = week_starting_date.isoformat()
    if log is None or log.resolved:
        # first reminder, or missing again after a rejection/reopen: start over with the employee
        cycle = f"r{now:%Y%m%d%H%M}" if log is not None else "0"  # a restart is a new reminder
        if log is None:
            log = TimesheetNagLog(tenant_id=tenant_id or employee.tenant_id, employee_id=employee.id,
                                  week_starting_date=week_starting_date)
            db.add(log)
        log.resolved, log.escalation_level, log.last_nagged_at = False, 1, now
        db.commit()
        if login is not None:
            _tell(db, login, key=f"ts-nag-{employee.id}-{week}-1-{cycle}",
                  subject=f"Timesheet missing: week of {week}",
                  text=f"Your timesheet for the week of {week} has not been submitted. Fill it in and submit it.",
                  link=f"/my-timesheet?week={week}")
            return log
        logger.error(f"[TimesheetNag] {employee.id} owes week {week} but has no login: escalating at once")
        escalate_now = True
    else:
        escalate_now = log.escalation_level == 1 and (now - log.last_nagged_at).days >= escalation_days
    if not escalate_now:
        return log
    try:
        approver = resolve_approver(db, employee)
    except NoTimesheetApprover as exc:
        logger.error(f"[TimesheetNag] {employee.id} week {week}: {exc}")
        raise
    first_nag = f"{log.last_nagged_at:%Y%m%d%H%M}"  # one escalation per reminder cycle
    log.escalation_level, log.last_nagged_at = 2, now
    db.commit()
    _tell(db, approver, key=f"ts-nag-{employee.id}-{week}-2-{first_nag}",
          subject=f"Timesheet still missing: {name}, week of {week}",
          text=(f"{name}'s timesheet for the week of {week} is still not submitted"
                + (f" after {escalation_days} day(s) of reminders." if login else " and they have no login to submit it.")),
          link="/timesheets")
    return log


def run_timesheet_nag_job(db: Session, today: Optional[date] = None) -> Dict:
    """Daily job (scheduled_jobs: timesheet_reminders). Nags about the week that has just ended
    (Monday-anchored): the current week isn't due yet. Each employee is isolated, so one failure
    doesn't stop reminders to everyone else; every failure is in the result and the log."""
    today = today or date.today()
    week_starting_date = today - timedelta(days=today.weekday() + 7)
    processed, failed = 0, []
    for employee in scan_missing_timesheets(db, week_starting_date=week_starting_date):
        try:
            if trigger_timesheet_nag(db, employee, week_starting_date=week_starting_date,
                                     tenant_id=employee.tenant_id) is not None:
                processed += 1
        except Exception as exc:
            db.rollback()
            failed.append(employee.id)
            logger.error(f"[TimesheetNag] {employee.id} week {week_starting_date}: {exc}", exc_info=True)
    return {"week_starting_date": week_starting_date.isoformat(), "processed": processed,
            "failed": len(failed), "failed_employee_ids": failed}

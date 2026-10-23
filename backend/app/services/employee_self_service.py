"""
Employee self-service -- timesheet entry against an employee's own
active project allocation. Real gap found 2026-08-04: the existing
Timesheet engine (timesheet_service.py, real and fully built --
create/submit/approve/reject/bulk-approve, anomaly detection, dispute
resolution) is entirely HR/Admin-operated. Every existing endpoint is
gated to get_current_hr_or_admin, which -- despite its name -- doesn't
actually check role (only "not a candidate"), and none of them scope
results to "the caller's own record": an employee_id/allocation_id is
taken as a client-supplied filter, trusted as-is. That's fine for an
HR-driven flow; it's not safe to open to every employee as-is.

This module is the real ownership boundary that was missing: every
function here resolves the CALLER's own Employee record (via
Employee.wros_user_id, same pattern task/buddy_program/executive_signal
already use) and only ever touches allocations/timesheets that belong
to that employee -- never a client-supplied employee_id.
"""
import logging
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import Timesheet
from app.models.user import Users

logger = logging.getLogger(__name__)

class NoLinkedEmployeeRecord(Exception):
    pass

class NotYourAllocation(Exception):
    pass

class NotYourTimesheet(Exception):
    pass

class WeekOutsideWindow(Exception):
    """The requested week is not a Monday, is in the future, or is older than the self-service window."""

NO_LINKED_EMPLOYEE_MESSAGE = (
    "Your login isn't linked to an employee record, so there is no timesheet for you yet. "
    "Ask HR to add you on the Employees screen (Import employees or Add employee)."
)

def resolve_current_employee(db: Session, current_user: Users) -> Employee:
    employee = db.query(Employee).filter(Employee.wros_user_id == current_user.UserID).first()
    if not employee:
        logger.info(f"[MyTimesheet] user {current_user.UserID} has no linked employee record")
        raise NoLinkedEmployeeRecord(NO_LINKED_EMPLOYEE_MESSAGE)
    return employee

def get_my_active_allocations(db: Session, employee: Employee) -> List[EmployeeAllocation]:
    return db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status == "ACTIVE",
    ).order_by(EmployeeAllocation.start_date.desc()).all()

def _current_week_monday(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today - timedelta(days=today.weekday())

def self_service_back_weeks() -> int:
    """settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS, never past the submission window (a week the
    employee could open but never submit is a trap): misconfiguration fails loudly."""
    from app.core.config import settings
    from app.models.timesheet import MAX_SUBMISSION_LOOKBACK_WEEKS

    weeks = settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS
    if weeks < 0 or weeks > MAX_SUBMISSION_LOOKBACK_WEEKS:
        raise RuntimeError(
            f"TIMESHEET_SELF_SERVICE_BACK_WEEKS={weeks} must be between 0 and the "
            f"{MAX_SUBMISSION_LOOKBACK_WEEKS}-week submission window.")
    return weeks

def allowed_weeks(today: Optional[date] = None) -> List[date]:
    """The Mondays an employee may fill: this week first, then each earlier week in the window."""
    monday = _current_week_monday(today)
    return [monday - timedelta(weeks=n) for n in range(self_service_back_weeks() + 1)]

def _check_week(week_starting: date, today: Optional[date]) -> date:
    weeks = allowed_weeks(today)
    if week_starting.weekday() != 0:
        raise WeekOutsideWindow(f"{week_starting} is not a Monday: a timesheet week starts on Monday.")
    if week_starting > weeks[0]:
        raise WeekOutsideWindow(f"The week of {week_starting} has not started yet.")
    if week_starting < weeks[-1]:
        raise WeekOutsideWindow(
            f"The week of {week_starting} is more than {len(weeks) - 1} week(s) back; "
            "ask your approver or HR to handle older weeks.")
    return week_starting

def get_or_start_my_week_timesheet(db: Session, employee: Employee, allocation_id: str, *,
                                   week_starting: Optional[date] = None, today: Optional[date] = None) -> Timesheet:
    """The draft for one week (this week when week_starting is None), created if missing."""
    from app.services.timesheet_service import create_weekly_draft

    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == allocation_id).first()
    if not allocation or allocation.employee_id != employee.id:
        raise NotYourAllocation(f"Allocation {allocation_id!r} does not belong to you.")

    monday = _check_week(week_starting, today) if week_starting else _current_week_monday(today)
    if (allocation.end_date and monday > allocation.end_date) or monday + timedelta(days=6) < allocation.start_date:
        raise WeekOutsideWindow(
            f"The week of {monday} is outside this allocation ({allocation.start_date} to "
            f"{allocation.end_date or 'open'}).")
    timesheet = create_weekly_draft(db, allocation, monday, tenant_id=allocation.tenant_id)
    db.commit()
    db.refresh(timesheet)
    return timesheet

def own_timesheet(db: Session, employee: Employee, timesheet_id: str) -> Timesheet:
    timesheet = db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
    if not timesheet or timesheet.employee_id != employee.id:
        raise NotYourTimesheet(f"Timesheet {timesheet_id!r} does not belong to you.")
    return timesheet

def submit_my_entries(db: Session, employee: Employee, timesheet_id: str, entries: List[dict]) -> Timesheet:
    from app.services.timesheet_service import upsert_entries

    timesheet = own_timesheet(db, employee, timesheet_id)
    upsert_entries(db, timesheet, entries)
    db.commit()
    db.refresh(timesheet)
    return timesheet

def get_my_timesheet_history(db: Session, employee: Employee, *, limit: int = 12) -> List[Timesheet]:
    return db.query(Timesheet).filter(Timesheet.employee_id == employee.id).order_by(
        Timesheet.week_starting_date.desc()
    ).limit(limit).all()

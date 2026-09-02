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
import logging
HR-driven flow; it's not safe to open to every employee as-is.

This module is the real ownership boundary that was missing: every
function here resolves the CALLER's own Employee record (via
Employee.wros_user_id, same pattern task/buddy_program/executive_signal
already use) and only ever touches allocations/timesheets that belong
to that employee -- never a client-supplied employee_id.
"""
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


def resolve_current_employee(db: Session, current_user: Users) -> Employee:
    employee = db.query(Employee).filter(Employee.wros_user_id == current_user.UserID).first()
    if not employee:
        raise NoLinkedEmployeeRecord(f"No employee record is linked to user {current_user.UserID!r}.")
    return employee


def get_my_active_allocations(db: Session, employee: Employee) -> List[EmployeeAllocation]:
    return db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status == "ACTIVE",
    ).order_by(EmployeeAllocation.start_date.desc()).all()


def _current_week_monday(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today - timedelta(days=today.weekday())


def get_or_start_my_current_week_timesheet(db: Session, employee: Employee, allocation_id: str, *, today: Optional[date] = None) -> Timesheet:
    from app.services.timesheet_service import create_weekly_draft

    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == allocation_id).first()
    if not allocation or allocation.employee_id != employee.id:
        raise NotYourAllocation(f"Allocation {allocation_id!r} does not belong to you.")

    monday = _current_week_monday(today)
    timesheet = create_weekly_draft(db, allocation, monday, tenant_id=allocation.tenant_id)
    db.commit()
    db.refresh(timesheet)
    return timesheet


def _get_own_timesheet_or_raise(db: Session, employee: Employee, timesheet_id: str) -> Timesheet:
    timesheet = db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
    if not timesheet or timesheet.employee_id != employee.id:
        raise NotYourTimesheet(f"Timesheet {timesheet_id!r} does not belong to you.")
    return timesheet


def submit_my_entries(db: Session, employee: Employee, timesheet_id: str, entries: List[dict]) -> Timesheet:
    from app.services.timesheet_service import upsert_entries

    timesheet = _get_own_timesheet_or_raise(db, employee, timesheet_id)
    upsert_entries(db, timesheet, entries)
    db.commit()
    db.refresh(timesheet)
    return timesheet


def submit_my_timesheet(db: Session, employee: Employee, timesheet_id: str) -> Timesheet:
    from app.services.timesheet_service import submit_timesheet

    timesheet = _get_own_timesheet_or_raise(db, employee, timesheet_id)
    submit_timesheet(db, timesheet)
    db.commit()
    db.refresh(timesheet)
    return timesheet


def get_my_timesheet_history(db: Session, employee: Employee, *, limit: int = 12) -> List[Timesheet]:
    return db.query(Timesheet).filter(Timesheet.employee_id == employee.id).order_by(
        Timesheet.week_starting_date.desc()
    ).limit(limit).all()

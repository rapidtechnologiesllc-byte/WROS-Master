"""Employment changes an HR user makes on an employee (CEO 2026-10-24): serving notice, exit,
leave. Each goes through transition_employee_status (ALLOWED_STATUS_TRANSITIONS + history) and
carries its consequences through the chain:

- notice: the last working day is recorded (Employee.exit_date); deployment is unchanged, they keep
  working their allocation until they leave.
- exit (terminated): from any working status (an immediate exit passes through NOTICE_PERIOD so
  the history shows both). Every ACTIVE allocation ends on the exit date (no timesheets, invoices
  or revenue after it), they leave the bench pool, and their WROS login is deactivated (records kept).
  A placement still waiting for margin approval must be decided first: refused, not dropped.
- leave / back from leave: back from leave returns them to their allocation, or to the bench.

The caller commits.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.user import Users
from app.services.employee_service import place_unallocated_joiner, transition_employee_status

ACTIONS = ("START_NOTICE", "RECORD_EXIT", "START_LEAVE", "END_LEAVE")


class EmploymentChangeRefused(ValueError):
    pass


def _active_allocations(db: Session, employee: Employee):
    return db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == employee.id,
                                               EmployeeAllocation.status == "ACTIVE").all()


def change_employment(db: Session, employee: Employee, action: str, *, effective_date: Optional[date],
                      reason: str, changed_by: str) -> Employee:
    from app.services.employee_allocation_service import end_allocation
    from app.services.resource_management_service import remove_employee_from_bench

    if action not in ACTIONS:
        raise EmploymentChangeRefused(f"Unknown employment change {action!r}; one of {ACTIONS}")
    if not (reason or "").strip():
        raise EmploymentChangeRefused("A reason is required.")

    if action == "START_NOTICE":
        if effective_date is None:
            raise EmploymentChangeRefused("The last working day is required.")
        if effective_date < date.today():
            raise EmploymentChangeRefused("The last working day cannot be in the past; record the exit instead.")
        transition_employee_status(db, employee, "NOTICE_PERIOD", reason=reason, changed_by=changed_by)
        employee.exit_date = effective_date
        return employee

    if action == "RECORD_EXIT":
        exit_date = effective_date or date.today()
        if exit_date > date.today():
            raise EmploymentChangeRefused("An exit is recorded on or after the last working day; "
                                          "for a future date start the notice period instead.")
        pending = db.query(EmployeeAllocation.id).filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "PENDING_MARGIN_APPROVAL").first()
        if pending is not None:
            raise EmploymentChangeRefused("A placement for this employee is waiting for margin approval: "
                                          "approve or reject it before recording the exit.")
        if employee.status != "NOTICE_PERIOD":
            transition_employee_status(db, employee, "NOTICE_PERIOD", reason=f"Immediate exit: {reason}",
                                       changed_by=changed_by)
        for allocation in _active_allocations(db, employee):
            end_allocation(db, allocation, employee,
                           end_date=min(exit_date, allocation.end_date or exit_date), changed_by=changed_by)
        remove_employee_from_bench(db, employee)
        transition_employee_status(db, employee, "EXITED", reason=reason, changed_by=changed_by)
        employee.exit_date = exit_date
        if employee.wros_user_id:
            user = db.query(Users).filter(Users.UserID == employee.wros_user_id).first()
            if user is not None and user.terminated_at is None:
                user.terminated_at = datetime.utcnow()
                user.terminated_by_user_id = changed_by
        return employee

    if action == "START_LEAVE":
        transition_employee_status(db, employee, "ON_LEAVE", reason=reason, changed_by=changed_by)
        return employee

    # END_LEAVE: back to the allocation they hold, or (billable, none) to the bench
    transition_employee_status(db, employee, "ACTIVE", reason=reason, changed_by=changed_by)
    if _active_allocations(db, employee):
        transition_employee_status(db, employee, "ALLOCATED", reason="Back from leave onto their allocation",
                                   changed_by=changed_by)
    else:
        place_unallocated_joiner(db, employee, changed_by=changed_by, bench_since=date.today())
    return employee

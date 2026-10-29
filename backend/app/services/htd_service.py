"""Hire-Train-Deploy (CEO 2026-10-24): a non-Guidewire hire is trained for 6+ months before they can be
deployed. While on the track they are not on the bench (not deployable) and their payroll is a
training cost of its own in the P&L (revenue_chain_service: htd_cost), never revenue and never bench.

- start: on the track from a date (first phase INDUCTION unless given); a person on the bench leaves
  the bench pool and becomes ACTIVE (not bench)
- phase: move through HTD_PHASES; COMPLETED or EXITED ends the training
- end (completed, exited or taken off): the end date is recorded so past months keep their HTD cost;
  a billable person with no allocation goes to the bench from that day

The start and end dates are never cleared: they are the history the P&L reads. The caller commits.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.employee import HTD_PHASES, Employee

DONE_PHASES = ("COMPLETED", "EXITED")


class HtdRefused(ValueError):
    pass


def _after_training(db: Session, employee: Employee, changed_by: Optional[str], day: date) -> None:
    from app.services.bench_service import has_active_allocation
    from app.services.employee_service import place_unallocated_joiner

    if employee.status == "ACTIVE" and employee.is_billable and not has_active_allocation(db, employee):
        place_unallocated_joiner(db, employee, changed_by=changed_by, bench_since=day)


def update_htd(db: Session, employee: Employee, *, on_track: bool, phase: Optional[str] = None,
               start: Optional[date] = None, changed_by: Optional[str] = None, today: Optional[date] = None) -> None:
    from app.services.employee_service import transition_employee_status
    from app.services.resource_management_service import remove_employee_from_bench

    today = today or date.today()
    if not on_track:
        if employee.htd_track:
            employee.htd_track = False
            if employee.htd_start_date and not employee.htd_end_date:
                employee.htd_end_date = today
            _after_training(db, employee, changed_by, today)
        return

    phase = phase or (employee.htd_phase if employee.htd_track else None) or HTD_PHASES[0]
    if phase not in HTD_PHASES:
        raise HtdRefused(f"HTD phase must be one of {list(HTD_PHASES)}")
    was_training = bool(employee.htd_track) and employee.htd_phase not in DONE_PHASES
    restarting = not employee.htd_track or employee.htd_phase in DONE_PHASES
    employee.htd_track = True
    employee.htd_phase = phase
    if restarting or start:
        employee.htd_start_date = start or today
        employee.htd_end_date = None
    if phase in DONE_PHASES:
        if was_training or not employee.htd_end_date:
            employee.htd_end_date = today
            _after_training(db, employee, changed_by, today)
        return
    # training: not deployable, so not on the bench
    remove_employee_from_bench(db, employee)
    if employee.status == "BENCH":
        transition_employee_status(db, employee, "ACTIVE", reason="Started Hire-Train-Deploy training",
                                   changed_by=changed_by)

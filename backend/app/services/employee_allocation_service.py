"""
HRMS-0507 -- allocate/end-allocation, the one write path that moves an
employee off (or back onto) the bench. Per 04-RESOURCE-MANAGEMENT.md's
own framing, this is always a distinct human decision, never automatic
import logging
-- there is no agent or ranking logic here (that's Phase 4 Part A).

Reuses app.services.employee_service.transition_employee_status() for
the actual status change rather than setting Employee.status directly,
so the transition-validity + history-logging guarantee stays in the one
place it already lives.

Phase 4 Part B wiring: mark_employee_on_bench()/remove_employee_from_
bench() keep app.models.resource_management.BenchPoolEntry in sync with
every BENCH/ALLOCATED transition this module already makes -- not a
separate scheduled job, so bench_pool can never drift out of sync with
Employee.status. log_allocation_conflict() records a permanent audit
row the moment AllocationOverCapacity is about to be raised.
"""
import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.services.employee_service import transition_employee_status
from app.services.resource_management_service import (
    log_allocation_conflict,
    mark_employee_on_bench,
    remove_employee_from_bench,
)

logger = logging.getLogger(__name__)

class EmployeeAlreadyAllocated(Exception):
    pass


class AllocationOverCapacity(Exception):
    """HRMS-0803 BR-0803-01: overlapping allocations summing over 100%
    utilization are blocked, hard -- not just a warning."""


class BuddyProgramNotGraduated(Exception):
    """S-365/HRMS-0521 BR: no client deployment while an employee is
    actively mid-Buddy-Program (IN_PROGRESS/EXTENDED)."""


# S-365's BR reads as a blanket "buddy_program_status=GRADUATED required
# for allocation," which read literally would also block every employee
# who never entered a Buddy Program at all (buddy_program_status
# defaults to NOT_STARTED) -- including every employee this codebase's
# own pre-existing allocation tests already allocate successfully.
# Scoped here to the two states that mean "actively mid-program, not
# yet cleared" (IN_PROGRESS, EXTENDED) rather than blocking NOT_STARTED
# too, which would silently invalidate already-tested behavior for a
# reading the doc doesn't unambiguously require. Flagged, not decided
# unilaterally as final -- confirm with whoever owns onboarding whether
# NOT_STARTED should also block.
_BUDDY_PROGRAM_BLOCKING_STATUSES = ("IN_PROGRESS", "EXTENDED")


def allocate_employee_to_project(
    db: Session,
    *,
    tenant_id: Optional[int],
    employee: Employee,
    demand: Demand,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    utilization_pct: Optional[float] = None,
    client_reporting_manager_contact_id: Optional[str] = None,
    timesheet_approver_email: Optional[str] = None,
    billing_rate_usd_cents: Optional[int] = None,
    changed_by: Optional[str] = None,
    project=None,
    role: Optional[str] = None,
    allow_concurrent: bool = False,
) -> EmployeeAllocation:
    """
    allow_concurrent=False (default, unchanged from before HRMS-0803
    existed) preserves the original single-active-allocation-at-a-time
    behavior -- HRMS-0901 itself calls multi-allocation support "future
    scope," so nothing that depended on that invariant breaks.

    allow_concurrent=True is HRMS-0803's real behavior: multiple ACTIVE
    allocations are permitted, but the sum of utilization_pct across
    every ACTIVE allocation whose date range overlaps this one must not
    exceed 100 -- checked here, hard-blocked, not a soft warning.
    """
    if employee.buddy_program_status in _BUDDY_PROGRAM_BLOCKING_STATUSES:
        raise BuddyProgramNotGraduated(
            f"Employee {employee.id} must complete Buddy Program graduation "
            f"(current status: {employee.buddy_program_status}) before client deployment."
        )

    start = start_date or date.today()

    if not allow_concurrent:
        existing_active = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
        ).first()
        if existing_active:
            raise EmployeeAlreadyAllocated(
                f"Employee {employee.id} already has an active allocation ({existing_active.id}) -- "
                f"end it before creating a new one."
            )
    else:
        overlapping = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
        ).all()
        overlapping_total = sum(
            float(a.utilization_pct or 100) for a in overlapping
            if a.end_date is None or a.end_date >= start
        )
        new_pct = float(utilization_pct or 100)
        if overlapping_total + new_pct > 100:
            log_allocation_conflict(
                db, employee,
                conflicting_allocation_ids=[a.id for a in overlapping],
                attempted_utilization_pct=new_pct,
                existing_utilization_pct=overlapping_total,
            )
            raise AllocationOverCapacity(
                f"Employee {employee.id} already has {overlapping_total:.0f}% overlapping "
                f"allocation -- adding {new_pct:.0f}% would exceed 100%."
            )

    allocation = EmployeeAllocation(
        tenant_id=tenant_id, employee_id=employee.id, demand_id=demand.id, client_id=demand.client_id,
        project_id=project.id if project else None, role=role,
        start_date=start, end_date=end_date, utilization_pct=utilization_pct,
        client_reporting_manager_contact_id=client_reporting_manager_contact_id,
        timesheet_approver_email=timesheet_approver_email,
        billing_rate_usd_cents=billing_rate_usd_cents or demand.billing_rate_usd_cents,
        # S-358/HRMS-0519: denormalized from the project at allocation-
        # creation time -- "who is at PwC right now" without a join.
        si_partner=project.si_partner if project else None,
    )
    db.add(allocation)

    if employee.status in ("BENCH", "ACTIVE"):
        was_on_bench = employee.status == "BENCH"
        transition_employee_status(
            db, employee, "ALLOCATED",
            reason=f"Allocated to demand {demand.id}", changed_by=changed_by,
        )
        if was_on_bench:
            remove_employee_from_bench(db, employee)

    return allocation


def end_allocation(
    db: Session,
    allocation: EmployeeAllocation,
    employee: Employee,
    *,
    end_date: Optional[date] = None,
    changed_by: Optional[str] = None,
) -> EmployeeAllocation:
    allocation.status = "ENDED"
    allocation.end_date = end_date or date.today()
    db.add(allocation)

    if employee.status == "ALLOCATED":
        # Part B item 1: bench only when there's genuinely no immediate
        # next allocation -- relevant when allow_concurrent=True let this
        # employee hold more than one ACTIVE allocation at once; ending
        # just one of several shouldn't bench them (status OR bench_pool)
        # while another is still live.
        still_has_active = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == employee.id,
            EmployeeAllocation.status == "ACTIVE",
        ).first()
        if not still_has_active:
            transition_employee_status(
                db, employee, "BENCH",
                reason=f"Allocation {allocation.id} ended", changed_by=changed_by,
            )
            mark_employee_on_bench(db, employee)

    return allocation

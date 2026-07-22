"""
HRMS-0507 -- allocate/end-allocation, the one write path that moves an
employee off (or back onto) the bench. Per 04-RESOURCE-MANAGEMENT.md's
own framing, this is always a distinct human decision, never automatic
-- there is no agent or ranking logic here (that's Phase 4).

Reuses app.services.employee_service.transition_employee_status() for
the actual status change rather than setting Employee.status directly,
so the transition-validity + history-logging guarantee stays in the one
place it already lives.
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.services.employee_service import transition_employee_status


class EmployeeAlreadyAllocated(Exception):
    pass


class AllocationOverCapacity(Exception):
    """HRMS-0803 BR-0803-01: overlapping allocations summing over 100%
    utilization are blocked, hard -- not just a warning."""


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
    )
    db.add(allocation)

    if employee.status in ("BENCH", "ACTIVE"):
        transition_employee_status(
            db, employee, "ALLOCATED",
            reason=f"Allocated to demand {demand.id}", changed_by=changed_by,
        )

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
        transition_employee_status(
            db, employee, "BENCH",
            reason=f"Allocation {allocation.id} ended", changed_by=changed_by,
        )

    return allocation

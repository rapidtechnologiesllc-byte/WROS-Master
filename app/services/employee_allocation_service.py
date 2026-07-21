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


def allocate_employee_to_project(
    db: Session,
    *,
    tenant_id: Optional[int],
    employee: Employee,
    demand: Demand,
    start_date: Optional[date] = None,
    utilization_pct: Optional[float] = None,
    client_reporting_manager_contact_id: Optional[str] = None,
    timesheet_approver_email: Optional[str] = None,
    billing_rate_usd_cents: Optional[int] = None,
    changed_by: Optional[str] = None,
) -> EmployeeAllocation:
    existing_active = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id,
        EmployeeAllocation.status == "ACTIVE",
    ).first()
    if existing_active:
        raise EmployeeAlreadyAllocated(
            f"Employee {employee.id} already has an active allocation ({existing_active.id}) -- "
            f"end it before creating a new one."
        )

    allocation = EmployeeAllocation(
        tenant_id=tenant_id, employee_id=employee.id, demand_id=demand.id, client_id=demand.client_id,
        start_date=start_date or date.today(), utilization_pct=utilization_pct,
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

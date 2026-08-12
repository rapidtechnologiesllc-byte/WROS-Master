"""
S-251 (Allocate Employee to Project) + S-252 (Allocation Conflict
Detection) — API Endpoints
=========================================================================
Prefix: /allocations
Tag:    allocations

Wires app.services.employee_allocation_service (real, tested backend,
pre-existing this codebase -- HRMS-0507/HRMS-0803) to real HTTP routes.
No REST layer previously existed. S-252's conflict detection is not a
separate function to build -- AllocationOverCapacity is already raised
by allocate_employee_to_project() itself when allow_concurrent=True and
the sum of utilization would exceed 100%; this endpoint surfaces that
as a 409, not a second implementation.

Auth: get_current_hr_or_admin.

Routes:
  POST   /allocations               Allocate an employee to a demand.
  GET    /allocations                List allocations (optional employee_id/demand_id filter).
  POST   /allocations/{id}/end      End an allocation (bench transition
                                     handled internally by end_allocation()).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.rbac import BusinessUnit
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.user import Users
from app.schemas.allocation import (
    AllocationItem,
    AllocationListResponse,
    AllocationDropdownsResponse,
    CreateAllocationRequest,
    DropdownItem,
    EndAllocationRequest,
)
from app.services.employee_allocation_service import (
    AllocationOverCapacity,
    BuddyProgramNotGraduated,
    EmployeeAlreadyAllocated,
    allocate_employee_to_project,
    end_allocation,
)

router = APIRouter(prefix="/allocations", tags=["allocations"])


def _to_item(db: Session, allocation: EmployeeAllocation) -> AllocationItem:
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    demand = db.query(Demand).filter(Demand.id == allocation.demand_id).first()
    client = db.query(Client).filter(Client.id == allocation.client_id).first()

    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )
    client_name = client.company_name if client else "(unknown client)"

    recruiter_name = None
    if demand and demand.assigned_recruiter_employee_id:
        recruiter = db.query(Employee).filter(Employee.id == demand.assigned_recruiter_employee_id).first()
        if recruiter:
            recruiter_name = f"{recruiter.first_name} {recruiter.last_name}".strip()

    business_unit_name = None
    if demand and demand.assigned_bu_id:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == demand.assigned_bu_id).first()
        if bu:
            business_unit_name = bu.name

    return AllocationItem(
        id=allocation.id,
        employee_id=allocation.employee_id,
        employee_name=employee_name,
        demand_id=allocation.demand_id,
        demand_job_title=demand.job_title if demand else "(unknown demand)",
        client_id=allocation.client_id,
        client_name=client_name,
        project_id=allocation.project_id,
        si_partner=allocation.si_partner,
        status=allocation.status,
        utilization_pct=float(allocation.utilization_pct) if allocation.utilization_pct is not None else None,
        start_date=allocation.start_date,
        end_date=allocation.end_date,
        role=allocation.role,
        billing_rate_usd_cents=allocation.billing_rate_usd_cents,
        work_location=demand.work_location if demand else None,
        assigned_recruiter_name=recruiter_name,
        business_unit_name=business_unit_name,
        created_at=allocation.created_at,
    )


@router.post("", response_model=AllocationItem, summary="Allocate an employee to a project (demand)")
def create_allocation(
    body: CreateAllocationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    demand = db.query(Demand).filter(Demand.id == body.demand_id).first()
    if demand is None:
        raise HTTPException(status_code=404, detail="Demand not found.")
    project = None
    if body.project_id:
        project = db.query(Project).filter(Project.id == body.project_id).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")

    try:
        allocation = allocate_employee_to_project(
            db, tenant_id=current_user.tenant_id, employee=employee, demand=demand,
            start_date=body.start_date, end_date=body.end_date,
            utilization_pct=body.utilization_pct, role=body.role, project=project,
            allow_concurrent=body.allow_concurrent, changed_by=current_user.UserID,
        )
    except EmployeeAlreadyAllocated as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BuddyProgramNotGraduated as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AllocationOverCapacity as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    return _to_item(db, allocation)


@router.get("/dropdowns/for-create", response_model=AllocationDropdownsResponse, summary="Get employees and demands for allocation form")
def get_allocation_dropdowns(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    employees = db.query(Employee).filter(Employee.tenant_id == current_user.tenant_id).order_by(Employee.created_at.desc()).all()
    demands = db.query(Demand).filter(Demand.tenant_id == current_user.tenant_id).order_by(Demand.created_at.desc()).all()

    employee_items = [
        DropdownItem(
            id=e.id,
            name=f"{e.first_name} {e.last_name}".strip() if e.first_name or e.last_name else "(no name)"
        )
        for e in employees
    ]
    demand_items = [
        DropdownItem(
            id=d.id,
            name=f"{d.job_title}" if d.job_title else "(no title)"
        )
        for d in demands
    ]

    return AllocationDropdownsResponse(employees=employee_items, demands=demand_items)


@router.get("", response_model=AllocationListResponse, summary="List allocations")
def list_allocations(
    employee_id: Optional[str] = None,
    demand_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    query = db.query(EmployeeAllocation).filter(EmployeeAllocation.tenant_id == current_user.tenant_id)
    if employee_id:
        query = query.filter(EmployeeAllocation.employee_id == employee_id)
    if demand_id:
        query = query.filter(EmployeeAllocation.demand_id == demand_id)
    allocations = query.order_by(EmployeeAllocation.created_at.desc()).all()
    return AllocationListResponse(allocations=[_to_item(db, a) for a in allocations])


@router.post("/{allocation_id}/end", response_model=AllocationItem, summary="End an allocation")
def end_allocation_endpoint(
    allocation_id: str,
    body: EndAllocationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == allocation_id).first()
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found.")
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    allocation = end_allocation(
        db, allocation, employee, end_date=body.end_date, changed_by=current_user.UserID,
    )
    db.commit()
    db.refresh(allocation)
    return _to_item(db, allocation)

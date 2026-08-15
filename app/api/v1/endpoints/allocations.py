"""
S-314 — Project Allocation Engine
S-251 (Allocate Employee to Project) + S-252 (Allocation Conflict Detection)
=========================================================================
Prefix: /allocations
Tag:    allocations

Wires app.services.employee_allocation_service (HRMS-0507/HRMS-0803/HRMS-0812)
to HTTP routes. Core methods:
  - allocate_employee_to_project() — Create allocations
  - get_available_projects() — List available projects
  - check_capacity() — Check employee capacity

Auth: get_current_hr_or_admin for all endpoints.

Routes:
  POST   /allocations                   Allocate an employee to a demand/project.
  POST   /allocations/check-capacity    Pre-allocation validation (capacity check).
  GET    /allocations                   List allocations (employee_id/demand_id filter).
  GET    /allocations/projects          Get available projects for allocation.
  POST   /allocations/{id}/end          End an allocation.
  GET    /allocations/dropdowns/for-create  Get employees/demands for form.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    AllocationCheckRequest,
    AllocationCheckResponse,
    AvailableProjectsResponse,
    CapacityCheckRequest,
    CapacityCheckResponse,
    CreateAllocationRequest,
    DropdownItem,
    EndAllocationRequest,
    ProjectItem,
)
from app.services.employee_allocation_service import (
    AllocationOverCapacity,
    BuddyProgramNotGraduated,
    EmployeeAlreadyAllocated,
    allocate_employee_to_project,
    check_capacity,
    end_allocation,
    get_available_projects,
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


@router.get("/projects", response_model=AvailableProjectsResponse, summary="Get available projects for allocation")
def get_projects_for_allocation(
    employee_id: Optional[str] = Query(None, description="Filter to exclude projects with allocations for this employee"),
    status: Optional[str] = Query(None, description="Filter by project status (ACTIVE, PLANNING, COMPLETED, etc. or ALL)"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Get list of projects available for allocation.

    Optional Filters:
      - employee_id: Exclude projects where this employee already has an active allocation
      - status: Filter by project status (defaults to ACTIVE)
    """
    projects = get_available_projects(
        db,
        tenant_id=current_user.tenant_id,
        employee_id=employee_id,
        status_filter=status,
    )

    project_items = []
    for proj in projects:
        client = db.query(Client).filter(Client.id == proj.client_id).first()
        project_items.append(
            ProjectItem(
                id=proj.id,
                name=proj.name,
                client_id=proj.client_id,
                client_name=client.company_name if client else None,
                status=proj.status,
                delivery_engine=proj.delivery_engine,
                si_partner=proj.si_partner,
                start_date=proj.start_date,
                end_date=proj.end_date,
                billing_type=proj.billing_type,
                currency=proj.currency,
            )
        )

    return AvailableProjectsResponse(
        projects=project_items,
        total_count=len(projects),
        filtered_count=len(project_items),
    )


@router.post("/check-capacity", response_model=CapacityCheckResponse, summary="Check employee allocation capacity")
def check_capacity_endpoint(
    body: CapacityCheckRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Check if an employee has capacity for a new allocation.

    Returns:
      - has_capacity: True if employee can accept the proposed allocation
      - current_utilization_pct: Current % allocation (sum of all overlapping active allocations)
      - available_capacity_pct: Remaining % capacity
      - active_allocation_count: Number of active allocations
    """
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    has_capacity, current_utilization, available_capacity = check_capacity(
        db,
        employee_id=body.employee_id,
        additional_utilization_pct=body.additional_utilization_pct,
        proposed_start_date=body.proposed_start_date,
    )

    active_allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == body.employee_id,
        EmployeeAllocation.status == "ACTIVE",
    ).all()

    return CapacityCheckResponse(
        employee_id=body.employee_id,
        has_capacity=has_capacity,
        current_utilization_pct=current_utilization,
        available_capacity_pct=available_capacity,
        total_with_proposed_pct=current_utilization + body.additional_utilization_pct,
        active_allocation_count=len(active_allocations),
    )


@router.post("/validate", response_model=AllocationCheckResponse, summary="Validate allocation before creation")
def validate_allocation(
    body: AllocationCheckRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    """
    Comprehensive pre-allocation validation.

    Checks:
      - Employee exists and is in valid status
      - Demand exists
      - Capacity is available
      - No conflicting allocations (if allow_concurrent=False)
      - Buddy program status (if applicable)

    Returns detailed validation result with conflict_reasons if invalid.
    """
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    demand = db.query(Demand).filter(Demand.id == body.demand_id).first()
    if demand is None:
        raise HTTPException(status_code=404, detail="Demand not found.")

    conflict_reasons = []
    warnings = []
    is_valid = True

    # Check buddy program status
    if employee.buddy_program_status in ("IN_PROGRESS", "EXTENDED"):
        conflict_reasons.append(
            f"Employee must complete Buddy Program graduation before client deployment "
            f"(current status: {employee.buddy_program_status})"
        )
        is_valid = False

    # Check capacity
    utilization_pct = body.utilization_pct or 100.0
    has_capacity, current_utilization, available_capacity = check_capacity(
        db,
        employee_id=body.employee_id,
        additional_utilization_pct=utilization_pct,
        proposed_start_date=body.proposed_start_date,
    )

    if not has_capacity and not body.allow_concurrent:
        conflict_reasons.append(
            f"Employee has {current_utilization:.0f}% utilization; "
            f"adding {utilization_pct:.0f}% exceeds 100% limit"
        )
        is_valid = False
    elif not has_capacity and body.allow_concurrent:
        warnings.append(
            f"Concurrent allocation: total utilization will be "
            f"{current_utilization + utilization_pct:.0f}%"
        )

    # Check for existing single allocation (if allow_concurrent=False)
    if not body.allow_concurrent:
        existing_active = db.query(EmployeeAllocation).filter(
            EmployeeAllocation.employee_id == body.employee_id,
            EmployeeAllocation.status == "ACTIVE",
        ).first()
        if existing_active:
            conflict_reasons.append(
                f"Employee already has active allocation ({existing_active.id}); "
                f"end it before creating new one"
            )
            is_valid = False

    return AllocationCheckResponse(
        is_valid=is_valid,
        employee_id=body.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}".strip(),
        has_capacity=has_capacity,
        current_utilization_pct=current_utilization,
        available_capacity_pct=available_capacity,
        proposed_utilization_pct=utilization_pct,
        conflict_reasons=conflict_reasons,
        warnings=warnings,
    )


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

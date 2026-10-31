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

Auth: the role template's allocations permission decides the actions; the
business unit decides the records (CEO 2026-10-12, app.core.data_scope):
an allocation is visible when its employee's BU (who owns the person) OR its
client's BU (who owns the revenue) is in the caller's scope.

Routes:
  POST   /allocations               Allocate an employee to a demand.
  GET    /allocations                List allocations (optional employee_id/demand_id filter).
  POST   /allocations/{id}/end      End an allocation (bench transition
                                     handled internally by end_allocation()).
  PATCH  /allocations/{id}          Extend / shorten, new bill rate, utilization, billable --
                                     with a reason; history kept (allocation_changes). Every
                                     placement rule and the margin guard run on the new values.
  GET    /allocations/{id}/history  Who changed what, when, old -> new, why.
  PUT    /allocations/{id}/renewal  Renewal status / owner / note.
  GET    /allocations/renewals      ACTIVE allocations ending within N days, with renewal state
                                     (Demand vs Bench > Renewals; resource-forecast view).
  POST   /allocations/margin-preview  The margin guard's verdict on terms being typed (live in the form).
  GET    /allocations/margin-approvals  Placements / changes waiting for margin approval.
  POST   /allocations/changes/{id}/approve | /reject  The approver's decision, with a reason
                                     (authority: role level + business unit, margin_guard_service).
  PUT    /allocations/{id}/client-billing  The placement's client timesheet approver and
                                     client PO (work order) -- gap 3, CEO 2026-10-23.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.data_scope import allocation_filter, bu_filter, client_filter, job_filter
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import AllocationChange, EmployeeAllocation
from app.models.project import Project
from app.models.user import Users
from app.models.work_order import WorkOrder
from app.schemas.allocation import (
    AllocationChangeItem,
    AllocationEditResponse,
    AllocationHistoryResponse,
    AllocationItem,
    AllocationListResponse,
    AllocationDropdownsResponse, JobDropdownItem, ProjectDropdownItem,
    CreateAllocationRequest,
    DropdownItem,
    EndAllocationRequest,
    MarginApprovalListResponse,
    MarginCheck,
    MarginDecisionRequest,
    MarginPreviewRequest,
    RenewalItem,
    RenewalListResponse,
    RenewalUpdateRequest,
    UpdateAllocationRequest,
    PlacementBillingRequest,
)
from app.services import allocation_renewal_service as renewals
from app.services import employee_standing as standing
from app.services import margin_guard_service as margin_guard
from app.services.deployment_readiness_service import EmployeeNotDeployable
from app.services.work_order_service import WorkOrderValidationError, set_placement_billing
from app.services.employee_allocation_service import (
    AllocationEditInvalid,
    AllocationNeedsClient,
    AllocationNotEditable,
    AllocationOverCapacity,
    MarginApprovalForbidden,
    ProjectClientMismatch,
    EmployeeAlreadyAllocated,
    allocate_employee_to_project,
    decide_margin_change,
    edit_allocation,
    end_allocation,
)

router = APIRouter(prefix="/allocations", tags=["allocations"])

def _user_names(db: Session, ids) -> dict:
    ids = {i for i in ids if i}
    return dict(db.query(Users.UserID, Users.UserName).filter(Users.UserID.in_(ids)).all()) if ids else {}


def _num(value) -> Optional[float]:
    return float(value) if value is not None else None


def _change_item(db: Session, change: AllocationChange, names: Optional[dict] = None) -> AllocationChangeItem:
    names = names if names is not None else _user_names(db, (change.changed_by_user_id, change.approver_user_id))
    return AllocationChangeItem(
        id=change.id, allocation_id=change.allocation_id, change_type=change.change_type, status=change.status,
        old_values=change.old_values, new_values=change.new_values or {}, effective_from=change.effective_from,
        reason=change.reason, changed_by_user_id=change.changed_by_user_id,
        changed_by_name=names.get(change.changed_by_user_id), changed_at=change.changed_at,
        margin_pct=_num(change.margin_pct), margin_check=change.margin_check,
        min_margin_pct=_num(change.min_margin_pct), hard_floor_pct=_num(change.hard_floor_pct),
        approval_level=change.approval_level, approver_user_id=change.approver_user_id,
        approver_name=names.get(change.approver_user_id), task_id=change.task_id,
        decided_by_user_id=change.decided_by_user_id, decided_at=change.decided_at,
        decision_reason=change.decision_reason,
    )


def _margin_of(change: Optional[AllocationChange]) -> Optional[MarginCheck]:
    """The margin verdict stored on a history row, as the API shows it."""
    if change is None or change.margin_check is None:
        return None
    flags = ["NO_MARGIN_FLOOR_CONFIGURED"] if change.margin_check == margin_guard.NO_FLOOR_CONFIGURED else []
    if change.loaded_hourly_cost_usd_cents is None and change.margin_check != margin_guard.NOT_BILLABLE:
        flags.append("NO_COST_DATA")
    return MarginCheck(
        margin_check=change.margin_check, margin_pct=_num(change.margin_pct),
        loaded_hourly_cost_usd_cents=change.loaded_hourly_cost_usd_cents,
        min_margin_pct=_num(change.min_margin_pct), hard_floor_pct=_num(change.hard_floor_pct),
        margin_policy_id=change.margin_policy_id, approval_level=margin_guard.APPROVAL_FOR.get(change.margin_check),
        message=margin_guard.describe(change.margin_check, _num(change.margin_pct), _num(change.min_margin_pct),
                                      _num(change.hard_floor_pct)),
        flags=flags,
    )


def _by_id(db: Session, model, column, ids) -> dict:
    ids = {i for i in ids if i is not None}
    return {getattr(row, column.key): row for row in db.query(model).filter(column.in_(ids))} if ids else {}


def _lookups(db: Session, allocations) -> dict:
    """Everything the list rows show, one query per table for any number of allocations (it was
    up to eight queries per row)."""
    demands = _by_id(db, Demand, Demand.id, [a.demand_id for a in allocations])
    pending = {}
    ids = [a.id for a in allocations]
    if ids:
        for change in db.query(AllocationChange).filter(AllocationChange.allocation_id.in_(ids),
                                                        AllocationChange.status == "PENDING_APPROVAL"):
            pending.setdefault(change.allocation_id, change)
    return {
        "employees": _by_id(db, Employee, Employee.id,
                            [a.employee_id for a in allocations]
                            + [d.assigned_recruiter_employee_id for d in demands.values()]),
        "demands": demands,
        "clients": _by_id(db, Client, Client.id, [a.client_id for a in allocations]),
        "units": _by_id(db, BusinessUnit, BusinessUnit.id, [d.assigned_bu_id for d in demands.values()]),
        "projects": _by_id(db, Project, Project.id, [a.project_id for a in allocations]),
        "work_orders": _by_id(db, WorkOrder, WorkOrder.id, [a.work_order_id for a in allocations]),
        "pending": pending,
    }


def _to_item(db: Session, allocation: EmployeeAllocation,
             margin_change: Optional[AllocationChange] = None, lookups: Optional[dict] = None) -> AllocationItem:
    if lookups is None:
        lookups = _lookups(db, [allocation])
    employee = lookups["employees"].get(allocation.employee_id)
    demand = lookups["demands"].get(allocation.demand_id)
    client = lookups["clients"].get(allocation.client_id)

    employee_name = (
        f"{employee.first_name} {employee.last_name}".strip() if employee else "(unknown employee)"
    )
    client_name = client.company_name if client else "(unknown client)"
    today = date.today()
    days_left = (allocation.end_date - today).days if allocation.end_date else None
    ending = allocation.status == "ACTIVE" and standing.ending_soon(allocation.end_date, allocation.renewal_status, today)

    recruiter = lookups["employees"].get(demand.assigned_recruiter_employee_id) if demand else None
    recruiter_name = f"{recruiter.first_name} {recruiter.last_name}".strip() if recruiter else None
    bu = lookups["units"].get(demand.assigned_bu_id) if demand else None
    business_unit_name = bu.name if bu else None
    project = lookups["projects"].get(allocation.project_id)
    pending = lookups["pending"].get(allocation.id)
    work_order = lookups["work_orders"].get(allocation.work_order_id)
    return AllocationItem(
        project_name=project.name if project else None,
        renewal_status=allocation.renewal_status, renewal_owner_user_id=allocation.renewal_owner_user_id,
        renewal_note=allocation.renewal_note,
        margin_pct=_num(allocation.margin_pct), margin_check=allocation.margin_check,
        pending_change=_change_item(db, pending) if pending is not None else None,
        margin=_margin_of(margin_change),
        timesheet_approver_email=allocation.timesheet_approver_email,
        work_order_id=allocation.work_order_id,
        po_number=work_order.po_number if work_order else None,
        po_end_date=work_order.end_date if work_order else None,
        id=allocation.id,
        employee_id=allocation.employee_id,
        employee_name=employee_name,
        demand_id=allocation.demand_id,
        demand_job_title=demand.job_title if demand else (allocation.role or "Project work"),
        client_id=allocation.client_id,
        client_name=client_name,
        project_id=allocation.project_id,
        si_partner=allocation.si_partner,
        status=allocation.status,
        # Not set means full time: the rule every capacity, cost and revenue calculation applies
        utilization_pct=float(allocation.utilization_pct) if allocation.utilization_pct is not None else 100.0,
        start_date=allocation.start_date,
        end_date=allocation.end_date,
        days_left=days_left,
        ending_soon=ending,
        role=allocation.role,
        billing_rate_usd_cents=allocation.billing_rate_usd_cents,
        billable=bool(allocation.billable),
        work_location=demand.work_location if demand else None,
        assigned_recruiter_name=recruiter_name,
        business_unit_name=business_unit_name,
        created_at=allocation.created_at,
    )

def _visible_employee_or_404(db: Session, employee_id: str, user: Users) -> Employee:
    employee = db.query(Employee).filter(
        Employee.id == employee_id, Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id),
    ).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


def _visible_demands(db: Session, user: Users):
    """Live client jobs of the caller's tenant inside their business units (the job's own BU,
    and its client's BU)."""
    return db.query(Demand).filter(
        Demand.tenant_id == user.tenant_id, Demand.client_id.isnot(None),
        Demand.is_deleted.is_(False), Demand.status != "CANCELLED",
        job_filter(db, user, Demand.jobID), client_filter(db, user, Demand.client_id),
    )


def _get_allocation_or_404(db: Session, allocation_id: str, user: Users) -> EmployeeAllocation:
    """One allocation of the caller's tenant whose employee's BU or client's BU is in scope."""
    allocation = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.id == allocation_id, EmployeeAllocation.tenant_id == user.tenant_id,
        allocation_filter(db, user),
    ).first()
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found.")
    return allocation


@router.post(
    "",
    response_model=AllocationItem,
    summary="Allocate an employee to a project (demand)",
    dependencies=[Depends(require_resource_permission("allocations", "create"))]
)
def create_allocation(
    body: CreateAllocationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employee = _visible_employee_or_404(db, body.employee_id, current_user)
    if not body.demand_id and not body.project_id:
        raise HTTPException(status_code=422, detail="Choose the client job (Staff Aug) or the project.")
    demand = None
    if body.demand_id:
        demand = db.query(Demand).filter(
            Demand.id == body.demand_id, Demand.tenant_id == current_user.tenant_id,
            job_filter(db, current_user, Demand.jobID), client_filter(db, current_user, Demand.client_id),
        ).first()
        if demand is None:
            raise HTTPException(status_code=404, detail="Demand not found.")
    project = None
    if body.project_id:
        project = db.query(Project).filter(
            Project.id == body.project_id, Project.tenant_id == current_user.tenant_id,
            client_filter(db, current_user, Project.client_id),
        ).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")

    try:
        allocation = allocate_employee_to_project(
            db, tenant_id=current_user.tenant_id, employee=employee, demand=demand,
            start_date=body.start_date, end_date=body.end_date,
            utilization_pct=body.utilization_pct, role=body.role, project=project,
            allow_concurrent=body.allow_concurrent, changed_by=current_user.UserID,
            billing_rate_usd_cents=body.billing_rate_usd_cents, billable=body.billable,
        )
        if body.timesheet_approver_email or body.work_order_id:
            set_placement_billing(db, allocation, approver_email=body.timesheet_approver_email,
                                  work_order_id=body.work_order_id)
    except WorkOrderValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except EmployeeAlreadyAllocated as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except EmployeeNotDeployable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AllocationOverCapacity as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (AllocationNeedsClient, ProjectClientMismatch, AllocationEditInvalid) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    from app.services.action_emails.allocations import notify_allocated

    notify_allocated(db, allocation, actor=current_user)
    created = db.query(AllocationChange).filter(AllocationChange.allocation_id == allocation.id,
                                                AllocationChange.change_type == "CREATE").first()
    return _to_item(db, allocation, margin_change=created)

@router.get(
    "/dropdowns/for-create",
    response_model=AllocationDropdownsResponse,
    summary="Get employees and demands for allocation form",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def get_allocation_dropdowns(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    employees = db.query(Employee).filter(
        Employee.tenant_id == current_user.tenant_id, Employee.status != "EXITED",
        bu_filter(db, current_user, Employee.bu_id),
    ).order_by(Employee.created_at.desc()).all()
    # Allocations bill a client, so only client jobs that are still live -- and only the
    # caller's business units' jobs (CEO 2026-10-12)
    demands = _visible_demands(db, current_user).order_by(Demand.created_at.desc()).all()
    clients = {c.id: c.company_name for c in db.query(Client).filter(Client.id.in_({d.client_id for d in demands}))}
    projects = {p.id: p.name for p in db.query(Project).filter(Project.id.in_({d.project_id for d in demands if d.project_id}))}

    employee_items = [
        DropdownItem(
            id=e.id,
            name=f"{e.first_name} {e.last_name}".strip() if e.first_name or e.last_name else "(no name)"
        )
        for e in employees
    ]
    demand_items = [
        JobDropdownItem(
            id=d.id, name=d.job_title or "(no title)", client_id=d.client_id, client_name=clients.get(d.client_id),
            project_id=d.project_id, project_name=projects.get(d.project_id),
            billing_rate_usd_cents=d.billing_rate_usd_cents, status=d.status,
        )
        for d in demands
    ]

    # Project work is allocated to the project itself (CEO 2026-10-24): live projects of the caller's clients
    live_projects = db.query(Project).filter(
        Project.tenant_id == current_user.tenant_id, Project.status.in_(("PLANNING", "ACTIVE", "ON_HOLD")),
        Project.client_id.isnot(None), client_filter(db, current_user, Project.client_id),
    ).order_by(Project.name).all()
    project_clients = {c.id: c.company_name for c in db.query(Client).filter(
        Client.id.in_({p.client_id for p in live_projects}))} if live_projects else {}
    project_items = [ProjectDropdownItem(id=p.id, name=p.name, client_id=p.client_id,
                                         client_name=project_clients.get(p.client_id),
                                         delivery_engine=p.delivery_engine, is_billable=bool(p.is_billable))
                     for p in live_projects]

    return AllocationDropdownsResponse(employees=employee_items, demands=demand_items, projects=project_items)

@router.get(
    "",
    response_model=AllocationListResponse,
    summary="List allocations",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def list_allocations(
    employee_id: Optional[str] = None,
    demand_id: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.tenant_id == current_user.tenant_id, allocation_filter(db, current_user),
    )
    if employee_id:
        query = query.filter(EmployeeAllocation.employee_id == employee_id)
    if demand_id:
        query = query.filter(EmployeeAllocation.demand_id == demand_id)
    if client_id:
        query = query.filter(EmployeeAllocation.client_id == client_id)
    allocations = query.order_by(EmployeeAllocation.created_at.desc()).all()
    lookups = _lookups(db, allocations)
    return AllocationListResponse(allocations=[_to_item(db, a, lookups=lookups) for a in allocations])

@router.post(
    "/{allocation_id}/end",
    response_model=AllocationItem,
    summary="End an allocation",
    dependencies=[Depends(require_resource_permission("allocations", "create"))]
)
def end_allocation_endpoint(
    allocation_id: str,
    body: EndAllocationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    allocation = _get_allocation_or_404(db, allocation_id, current_user)
    employee = db.query(Employee).filter(Employee.id == allocation.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")

    try:
        allocation = end_allocation(
            db, allocation, employee, end_date=body.end_date, changed_by=current_user.UserID,
        )
    except AllocationNotEditable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    from app.services.action_emails.allocations import notify_allocation_ended

    notify_allocation_ended(db, allocation, actor=current_user)
    return _to_item(db, allocation)


# --------------------------------------------------------------------------- renewals

@router.get(
    "/renewals",
    response_model=RenewalListResponse,
    summary="Active allocations ending within N days, with their renewal state",
    dependencies=[Depends(require_resource_permission("resource-forecast", "view"))]
)
def list_renewals(
    days: Optional[int] = Query(None, ge=1, le=730),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    days = days or settings.RENEWAL_LIST_DAYS
    query = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.tenant_id == current_user.tenant_id, allocation_filter(db, current_user))
    allocations = renewals.ending_within(query, days).all()
    return RenewalListResponse(days=days, alert_days=renewals.alert_thresholds(),
                               renewals=[RenewalItem(**row) for row in renewals.renewal_rows(db, allocations)])


@router.put(
    "/{allocation_id}/renewal",
    response_model=RenewalItem,
    summary="Set an allocation's renewal status, owner or note",
    dependencies=[Depends(require_resource_permission("allocations", "edit"))]
)
def update_renewal(
    allocation_id: str,
    body: RenewalUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    allocation = _get_allocation_or_404(db, allocation_id, current_user)
    try:
        renewals.update_renewal(
            db, allocation, user=current_user, status=body.renewal_status,
            owner_user_id=body.owner_user_id or None, clear_owner=body.owner_user_id == "",
            note=body.note, reason=body.reason)
    except renewals.RenewalUpdateInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    return RenewalItem(**renewals.renewal_rows(db, [allocation])[0])


# --------------------------------------------------------------------------- margin guard

def _visible_project_or_404(db: Session, project_id: str, user: Users) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == user.tenant_id,
                                       client_filter(db, user, Project.client_id)).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.post(
    "/margin-preview",
    response_model=MarginCheck,
    summary="The margin guard's verdict on the terms in the allocation form",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def margin_preview(
    body: MarginPreviewRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    if body.allocation_id:
        allocation = _get_allocation_or_404(db, body.allocation_id, current_user)
        employee = db.query(Employee).filter(Employee.id == allocation.employee_id).one()
        project_id, client_id, role = allocation.project_id, allocation.client_id, allocation.role
        rate = body.billing_rate_usd_cents or allocation.billing_rate_usd_cents
        billable = allocation.billable if body.billable is None else body.billable
        on = body.start_date or max(date.today(), allocation.start_date)
    elif body.employee_id and body.project_id and not body.demand_id:
        # project work: the project names the client, the form the role and bill rate
        employee = _visible_employee_or_404(db, body.employee_id, current_user)
        project = _visible_project_or_404(db, body.project_id, current_user)
        project_id, client_id, role = project.id, project.client_id, body.role
        rate = body.billing_rate_usd_cents
        billable = body.billable if body.billable is not None else bool(project.is_billable)
        on = body.start_date or date.today()
    else:
        if not body.employee_id or not body.demand_id:
            raise HTTPException(status_code=422, detail="Pick the employee and the client job or project first.")
        employee = _visible_employee_or_404(db, body.employee_id, current_user)
        demand = _visible_demands(db, current_user).filter(Demand.id == body.demand_id).first()
        if demand is None:
            raise HTTPException(status_code=404, detail="Demand not found.")
        project_ref = body.project_id or demand.project_id
        project = _visible_project_or_404(db, project_ref, current_user) if project_ref else None
        project_id, client_id, role = (project.id if project else None), demand.client_id, body.role
        rate = body.billing_rate_usd_cents or demand.billing_rate_usd_cents
        billable = body.billable if body.billable is not None else (bool(project.is_billable) if project else True)
        on = body.start_date or date.today()
    result = margin_guard.evaluate(db, tenant_id=current_user.tenant_id, employee=employee, project_id=project_id,
                                   client_id=client_id, role=role, bill_rate_usd_cents=rate, billable=billable, on=on)
    return MarginCheck(**result.as_dict())


@router.get(
    "/margin-approvals",
    response_model=MarginApprovalListResponse,
    summary="Placements and allocation changes waiting for margin approval",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def list_margin_approvals(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    changes = (db.query(AllocationChange)
               .join(EmployeeAllocation, EmployeeAllocation.id == AllocationChange.allocation_id)
               .filter(AllocationChange.status == "PENDING_APPROVAL",
                       EmployeeAllocation.tenant_id == current_user.tenant_id, allocation_filter(db, current_user))
               .order_by(AllocationChange.changed_at).all())
    names = _user_names(db, [c.changed_by_user_id for c in changes] + [c.approver_user_id for c in changes])
    return MarginApprovalListResponse(approvals=[_change_item(db, c, names) for c in changes])


def _decide(db: Session, change_id: str, user: Users, approve: bool, reason: str) -> AllocationItem:
    change = (db.query(AllocationChange)
              .join(EmployeeAllocation, EmployeeAllocation.id == AllocationChange.allocation_id)
              .filter(AllocationChange.id == change_id, EmployeeAllocation.tenant_id == user.tenant_id,
                      allocation_filter(db, user)).first())
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found.")
    try:
        decide_margin_change(db, change, user, approve=approve, reason=reason)
    except MarginApprovalForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except AllocationEditInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (AllocationNotEditable, EmployeeNotDeployable, AllocationOverCapacity, EmployeeAlreadyAllocated) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    from app.services.action_emails.allocations import notify_margin_decision

    notify_margin_decision(db, change, actor=user)
    allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == change.allocation_id).one()
    return _to_item(db, allocation)


@router.post(
    "/changes/{change_id}/approve",
    response_model=AllocationItem,
    summary="Approve a placement or change below the margin floor",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def approve_margin_change(
    change_id: str,
    body: MarginDecisionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return _decide(db, change_id, current_user, True, body.reason)


@router.post(
    "/changes/{change_id}/reject",
    response_model=AllocationItem,
    summary="Reject a placement or change below the margin floor",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def reject_margin_change(
    change_id: str,
    body: MarginDecisionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return _decide(db, change_id, current_user, False, body.reason)


# --------------------------------------------------------------------------- edit + history

@router.patch(
    "/{allocation_id}",
    response_model=AllocationEditResponse,
    summary="Extend / shorten, change the bill rate, utilization or billable flag (with a reason)",
    dependencies=[Depends(require_resource_permission("allocations", "edit"))]
)
def update_allocation(
    allocation_id: str,
    body: UpdateAllocationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    allocation = _get_allocation_or_404(db, allocation_id, current_user)
    changes = {key: getattr(body, key) for key in ("end_date", "billing_rate_usd_cents", "utilization_pct", "billable")
               if key in body.model_fields_set}
    try:
        change = edit_allocation(db, allocation, changes=changes, reason=body.reason,
                                 effective_from=body.effective_from, changed_by=current_user.UserID)
    except AllocationEditInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (AllocationNotEditable, EmployeeNotDeployable, AllocationOverCapacity, EmployeeAlreadyAllocated) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    from app.services.action_emails.allocations import notify_allocation_changed

    notify_allocation_changed(db, allocation, change, actor=current_user)
    return AllocationEditResponse(allocation=_to_item(db, allocation, margin_change=change),
                                  change=_change_item(db, change))


@router.get(
    "/{allocation_id}/history",
    response_model=AllocationHistoryResponse,
    summary="The allocation's history: who changed what, when, old -> new and why",
    dependencies=[Depends(require_resource_permission("allocations", "view"))]
)
def allocation_history(
    allocation_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    allocation = _get_allocation_or_404(db, allocation_id, current_user)
    changes = (db.query(AllocationChange).filter(AllocationChange.allocation_id == allocation.id)
               .order_by(AllocationChange.changed_at.desc(), AllocationChange.id).all())
    names = _user_names(db, [c.changed_by_user_id for c in changes] + [c.approver_user_id for c in changes])
    return AllocationHistoryResponse(changes=[_change_item(db, c, names) for c in changes])
@router.put(
    "/{allocation_id}/client-billing",
    response_model=AllocationItem,
    summary="Set the placement's client timesheet approver and client PO (work order)",
    dependencies=[Depends(require_resource_permission("allocations", "create"))]
)
def set_client_billing_endpoint(
    allocation_id: str,
    body: PlacementBillingRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The approver must be one of the client's TIMESHEET_APPROVER contacts when the client has any;
    the PO must be the same client's (app.services.work_order_service.set_placement_billing)."""
    allocation = _get_allocation_or_404(db, allocation_id, current_user)
    sent = body.dict(exclude_unset=True)
    kwargs = {}
    if "timesheet_approver_email" in sent:
        kwargs["approver_email"] = sent["timesheet_approver_email"]
    if "work_order_id" in sent:
        kwargs["work_order_id"] = sent["work_order_id"]
    try:
        set_placement_billing(db, allocation, **kwargs)
    except WorkOrderValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(allocation)
    return _to_item(db, allocation)

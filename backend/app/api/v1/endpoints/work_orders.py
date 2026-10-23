"""
Work Order API Endpoints (DEFECT-1: Work Order / PO Model; gap 3, CEO 2026-10-23)

A Work Order (aka PO, SOW, or Engagement Record) is the signed authority
to bill for a placed candidate/employee against a specific client demand.
A placement (allocation) links to its work order: the PO number is printed
on the invoice, and hours after the PO's end date are not invoiced.

Auth: the role template's work-orders permission decides the actions; the
business unit decides the records (app.core.data_scope): a work order belongs
to its client's BU. Any other id is 404.

Routes:
  POST   /work-orders                    Create a work order.
  GET    /work-orders                    List (optional status/client_id/demand_id/project_id/employee_id).
  GET    /work-orders/{id}               One work order.
  PATCH  /work-orders/{id}               Update the mutable fields (end date, pay rate, links, contact).
  POST   /work-orders/{id}/end           ACTIVE/PAUSED -> ENDED (optional end date).
  POST   /work-orders/{id}/pause         ACTIVE -> PAUSED.
  POST   /work-orders/{id}/resume        PAUSED -> ACTIVE.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.data_scope import client_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.user import Users
from app.models.work_order import WorkOrder
from app.core.logging import logger
from app.schemas.work_order import (
    CreateWorkOrderRequest,
    EndWorkOrderRequest,
    UpdateWorkOrderRequest,
    WorkOrderItem,
    WorkOrderListResponse,
)
from app.services.work_order_service import (
    WorkOrderValidationError,
    create_work_order,
    end_work_order,
    pause_work_order,
    resume_work_order,
    update_work_order,
)

router = APIRouter(prefix="/work-orders", tags=["work_orders"])


def _to_item(db: Session, wo: WorkOrder) -> WorkOrderItem:
    """Convert WorkOrder model to API response item."""
    client = db.get(Client, wo.client_id)
    placements = db.query(EmployeeAllocation.id).filter(EmployeeAllocation.work_order_id == wo.id).count()
    return WorkOrderItem(
        id=wo.id,
        tenant_id=wo.tenant_id,
        po_number=wo.po_number,
        sow_reference=wo.sow_reference,
        demand_id=wo.demand_id,
        client_id=wo.client_id,
        client_name=client.company_name if client else None,
        employee_id=wo.employee_id,
        project_id=wo.project_id,
        billing_rate_usd_cents=wo.billing_rate_usd_cents,
        pay_rate_usd_cents=wo.pay_rate_usd_cents,
        start_date=wo.start_date,
        end_date=wo.end_date,
        invoicing_contact_email=wo.invoicing_contact_email,
        invoicing_contact_name=wo.invoicing_contact_name,
        status=wo.status,
        placement_count=placements,
        created_at=wo.created_at.isoformat() if wo.created_at else None,
        updated_at=wo.updated_at.isoformat() if wo.updated_at else None,
    )


def _get_work_order_or_404(db: Session, work_order_id: str, user: Users) -> WorkOrder:
    work_order = db.query(WorkOrder).filter(
        WorkOrder.id == work_order_id, WorkOrder.tenant_id == user.tenant_id,
        client_filter(db, user, WorkOrder.client_id),
    ).first()
    if work_order is None:
        raise HTTPException(status_code=404, detail="Work order not found.")
    return work_order


def _save(db: Session, work_order: WorkOrder, step) -> WorkOrderItem:
    try:
        step()
    except WorkOrderValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(work_order)
    return _to_item(db, work_order)


@router.post(
    "",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "create"))]
)
def create_work_order_endpoint(
    req: CreateWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """
    Create a new Work Order: the client's signed authority (PO) to bill a placement.

    Required fields: po_number, demand_id (the client's job), client_id (bill-to),
    billing_rate_usd_cents, start_date. The rest can be filled in later.
    """
    if db.query(Client.id).filter(Client.id == req.client_id, Client.tenant_id == current_user.tenant_id,
                                  client_filter(db, current_user, Client.id)).first() is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    try:
        wo = create_work_order(
            db,
            tenant_id=current_user.tenant_id,
            po_number=req.po_number,
            demand_id=req.demand_id,
            client_id=req.client_id,
            billing_rate_usd_cents=req.billing_rate_usd_cents,
            start_date=req.start_date,
            sow_reference=req.sow_reference,
            employee_id=req.employee_id,
            project_id=req.project_id,
            pay_rate_usd_cents=req.pay_rate_usd_cents,
            end_date=req.end_date,
            invoicing_contact_email=req.invoicing_contact_email,
            invoicing_contact_name=req.invoicing_contact_name,
        )
    except WorkOrderValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(wo)
    logger.info(f"[WorkOrders] created {wo.id} PO {wo.po_number} client {wo.client_id} by {current_user.UserID}")
    return _to_item(db, wo)


@router.get(
    "",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("work-orders", "view"))]
)
def list_work_orders(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, ENDED, PAUSED)"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    demand_id: Optional[str] = Query(None, description="Filter by demand ID"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """Work orders of the caller's tenant whose client is in the caller's business units."""
    query = db.query(WorkOrder).filter(WorkOrder.tenant_id == current_user.tenant_id,
                                       client_filter(db, current_user, WorkOrder.client_id))
    for column, value in ((WorkOrder.status, status), (WorkOrder.client_id, client_id),
                          (WorkOrder.demand_id, demand_id), (WorkOrder.project_id, project_id),
                          (WorkOrder.employee_id, employee_id)):
        if value:
            query = query.filter(column == value)
    work_orders = query.order_by(WorkOrder.start_date.desc(), WorkOrder.created_at.desc()).all()
    return WorkOrderListResponse(work_orders=[_to_item(db, wo) for wo in work_orders])


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "view"))]
)
def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    return _to_item(db, _get_work_order_or_404(db, work_order_id, current_user))


@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "edit"))]
)
def update_work_order_endpoint(
    work_order_id: str,
    body: UpdateWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """Extend the end date (a PO extension), set the pay rate, link the employee or project,
    change the invoicing contact or status. The PO number and bill rate never change: a new
    PO is a new work order."""
    work_order = _get_work_order_or_404(db, work_order_id, current_user)
    return _save(db, work_order, lambda: update_work_order(db, work_order, **body.dict(exclude_unset=True)))


@router.post(
    "/{work_order_id}/end",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "edit"))]
)
def end_work_order_endpoint(
    work_order_id: str,
    body: Optional[EndWorkOrderRequest] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    work_order = _get_work_order_or_404(db, work_order_id, current_user)
    return _save(db, work_order, lambda: end_work_order(db, work_order, body.end_date if body else None))


@router.post(
    "/{work_order_id}/pause",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "edit"))]
)
def pause_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    work_order = _get_work_order_or_404(db, work_order_id, current_user)
    return _save(db, work_order, lambda: pause_work_order(db, work_order))


@router.post(
    "/{work_order_id}/resume",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work-orders", "edit"))]
)
def resume_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    work_order = _get_work_order_or_404(db, work_order_id, current_user)
    return _save(db, work_order, lambda: resume_work_order(db, work_order))

"""
Work Order API Endpoints (DEFECT-1: Work Order / PO Model)

Work Order / PO / Engagement Records

A Work Order (aka PO, SOW, or Engagement Record) is the signed authority
to bill for a placed candidate/employee against a specific client demand.

Routes:
  POST   /work-orders                              Create a work order.
  GET    /work-orders                              List (optional status/client_id/demand_id filter).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.models.work_order import WorkOrder
from app.core.logging import logger
from app.schemas.work_order import (
    CreateWorkOrderRequest,
    UpdateWorkOrderRequest,
    WorkOrderItem,
    WorkOrderListResponse,
    EndWorkOrderRequest,
    PauseWorkOrderRequest,
    ResumeWorkOrderRequest,
)
from app.services.work_order_service import (
    WorkOrderValidationError,
    create_work_order,
    update_work_order,
    get_work_order_by_id,
    get_work_orders_by_demand,
    get_work_orders_by_project,
    get_work_orders_by_employee,
    get_work_orders_by_client,
    get_all_work_orders,
    end_work_order,
    pause_work_order,
    resume_work_order,
)

router = APIRouter(prefix="/work-orders", tags=["work_orders"])

def _to_item(wo: WorkOrder) -> WorkOrderItem:
    """Convert WorkOrder model to API response item."""
    return WorkOrderItem(
        id=wo.id,
        tenant_id=wo.tenant_id,
        po_number=wo.po_number,
        sow_reference=wo.sow_reference,
        demand_id=wo.demand_id,
        client_id=wo.client_id,
        employee_id=wo.employee_id,
        project_id=wo.project_id,
        billing_rate_usd_cents=wo.billing_rate_usd_cents,
        pay_rate_usd_cents=wo.pay_rate_usd_cents,
        start_date=wo.start_date,
        end_date=wo.end_date,
        invoicing_contact_email=wo.invoicing_contact_email,
        invoicing_contact_name=wo.invoicing_contact_name,
        status=wo.status,
        created_at=wo.created_at.isoformat() if wo.created_at else None,
        updated_at=wo.updated_at.isoformat() if wo.updated_at else None,
    )

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
    Create a new Work Order.

    A Work Order represents the signed authority to bill for a placed
    candidate/employee against a specific client demand.

    Required fields:
    - po_number: Client-assigned PO number
    - demand_id: Link to Demand
    - client_id: Bill-to Client
    - billing_rate_usd_cents: Billing rate (USD cents)
    - start_date: Work start date

    Optional fields can be populated later as employee is hired/project created.
    """
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
        db.commit()
        db.refresh(wo)
        return _to_item(wo)
    except WorkOrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create work order: {str(e)}")

@router.get(
    "",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("work-orders", "view"))]
)
def list_work_orders(
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, ENDED, PAUSED)"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    demand_id: Optional[str] = Query(None, description="Filter by demand ID"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """
    List Work Orders for the current tenant.

    Optional filters:
    - status: Filter by status (ACTIVE, ENDED, PAUSED)
    - client_id: Filter by client ID
    - demand_id: Filter by demand ID
    """
    try:
        # Get all work orders for tenant
        work_orders = get_all_work_orders(db, current_user.tenant_id, status=status)

        # Apply optional filters
        if client_id:
            work_orders = [wo for wo in work_orders if wo.client_id == client_id]
        if demand_id:
            work_orders = [wo for wo in work_orders if wo.demand_id == demand_id]

        return WorkOrderListResponse(work_orders=[_to_item(wo) for wo in work_orders])
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list work orders: {str(e)}")


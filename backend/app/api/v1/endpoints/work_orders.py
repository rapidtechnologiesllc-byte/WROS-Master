"""
import logging
Work Order API Endpoints (DEFECT-1: Work Order / PO Model)

HRMS-0XXX -- Work Order / PO / Engagement Records

A Work Order (aka PO, SOW, or Engagement Record) is the signed authority
to bill for a placed candidate/employee against a specific client demand.

Routes:
  POST   /work-orders                              Create a work order.
  GET    /work-orders                              List (optional status/client_id/demand_id filter).
  GET    /work-orders/{id}                         Get one work order.
  PUT    /work-orders/{id}                         Update a work order.
  GET    /work-orders/by-demand/{demand_id}       Get work orders for a demand.
  GET    /work-orders/by-project/{project_id}     Get work orders for a project.
  GET    /work-orders/by-employee/{employee_id}   Get work orders for an employee.
  GET    /work-orders/by-client/{client_id}       Get work orders for a client.
  POST   /work-orders/{id}/end                     End a work order.
  POST   /work-orders/{id}/pause                   Pause a work order.
  POST   /work-orders/{id}/resume                  Resume a work order.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.models.work_order import WorkOrder
from app.schemas.work_order import (
from app.core.logging import logger
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
    dependencies=[Depends(require_resource_permission("unknown", "create"))]
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
    dependencies=[Depends(require_resource_permission("unknown", "view"))]
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


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work_orders", "view"))]
)
def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """Get a specific Work Order by ID."""
    try:
        wo = get_work_order_by_id(db, work_order_id, current_user.tenant_id)
        if not wo:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")
        return _to_item(wo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get work order: {str(e)}")


@router.put(
    "/{work_order_id}",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work_orders", "update"))]
)
def update_work_order_endpoint(
    work_order_id: str,
    req: UpdateWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """
    Update a Work Order.

    Only the following fields can be updated:
    - pay_rate_usd_cents: Set when employee is hired
    - end_date: If work ends early
    - employee_id: Link employee after hire
    - project_id: Link project when created
    - invoicing_contact_email/name: Update billing contact
    - status: ACTIVE, ENDED, or PAUSED

    PO number and billing rate are immutable (signed agreement).
    """
    try:
        wo = get_work_order_by_id(db, work_order_id, current_user.tenant_id)
        if not wo:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")

        wo = update_work_order(
            db,
            wo,
            pay_rate_usd_cents=req.pay_rate_usd_cents,
            end_date=req.end_date,
            employee_id=req.employee_id,
            project_id=req.project_id,
            invoicing_contact_email=req.invoicing_contact_email,
            invoicing_contact_name=req.invoicing_contact_name,
            status=req.status,
        )
        db.commit()
        db.refresh(wo)
        return _to_item(wo)
    except HTTPException:
        raise
    except WorkOrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update work order: {str(e)}")


@router.get(
    "/by-demand/{demand_id}",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("by-demand", "view"))]
)
def get_work_orders_by_demand_endpoint(
    demand_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """Get all Work Orders for a specific demand."""
    try:
        work_orders = get_work_orders_by_demand(db, demand_id, current_user.tenant_id)
        return WorkOrderListResponse(work_orders=[_to_item(wo) for wo in work_orders])
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get work orders: {str(e)}")


@router.get(
    "/by-project/{project_id}",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("by-project", "view"))]
)
def get_work_orders_by_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """Get all Work Orders linked to a specific project."""
    try:
        work_orders = get_work_orders_by_project(db, project_id, current_user.tenant_id)
        return WorkOrderListResponse(work_orders=[_to_item(wo) for wo in work_orders])
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get work orders: {str(e)}")


@router.get(
    "/by-employee/{employee_id}",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("by-employee", "view"))]
)
def get_work_orders_by_employee_endpoint(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """Get all Work Orders for a specific employee."""
    try:
        work_orders = get_work_orders_by_employee(db, employee_id, current_user.tenant_id)
        return WorkOrderListResponse(work_orders=[_to_item(wo) for wo in work_orders])
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get work orders: {str(e)}")


@router.get(
    "/by-client/{client_id}",
    response_model=WorkOrderListResponse,
    dependencies=[Depends(require_resource_permission("by-client", "view"))]
)
def get_work_orders_by_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderListResponse:
    """Get all Work Orders for a specific client."""
    try:
        work_orders = get_work_orders_by_client(db, client_id, current_user.tenant_id)
        return WorkOrderListResponse(work_orders=[_to_item(wo) for wo in work_orders])
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get work orders: {str(e)}")


@router.post(
    "/{work_order_id}/end",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work_orders", "create"))]
)
def end_work_order_endpoint(
    work_order_id: str,
    req: EndWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """End a Work Order and optionally set the end date."""
    try:
        wo = get_work_order_by_id(db, work_order_id, current_user.tenant_id)
        if not wo:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")

        wo = end_work_order(db, wo, req.end_date)
        db.commit()
        db.refresh(wo)
        return _to_item(wo)
    except HTTPException:
        raise
    except WorkOrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to end work order: {str(e)}")


@router.post(
    "/{work_order_id}/pause",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work_orders", "create"))]
)
def pause_work_order_endpoint(
    work_order_id: str,
    req: PauseWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """Pause a Work Order."""
    try:
        wo = get_work_order_by_id(db, work_order_id, current_user.tenant_id)
        if not wo:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")

        wo = pause_work_order(db, wo)
        db.commit()
        db.refresh(wo)
        return _to_item(wo)
    except HTTPException:
        raise
    except WorkOrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to pause work order: {str(e)}")


@router.post(
    "/{work_order_id}/resume",
    response_model=WorkOrderItem,
    dependencies=[Depends(require_resource_permission("work_orders", "create"))]
)
def resume_work_order_endpoint(
    work_order_id: str,
    req: ResumeWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> WorkOrderItem:
    """Resume a paused Work Order."""
    try:
        wo = get_work_order_by_id(db, work_order_id, current_user.tenant_id)
        if not wo:
            raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")

        wo = resume_work_order(db, wo)
        db.commit()
        db.refresh(wo)
        return _to_item(wo)
    except HTTPException:
        raise
    except WorkOrderValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to resume work order: {str(e)}")

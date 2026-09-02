"""
import logging
COMPLETE INVOICE API ENDPOINTS - Production Grade

Full invoice lifecycle management from creation through revenue recognition.
"""
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.invoice_management_service import (
    create_invoice,
    add_line_item,
    remove_line_item,
    approve_invoice,
    send_invoice,
    mark_invoice_paid,
    cancel_invoice,
    get_invoices,
    get_invoice_detail,
    get_invoice_totals_by_status,
    get_outstanding_invoices,
    get_invoices_by_opportunity,
)
from app.services.revenue_recognition_service import recognize_revenue_from_paid_invoice

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================
logger = logging.getLogger(__name__)

class LineItemCreate(BaseModel):
    employee_id: str
    timesheet_id: str
    hours: float = Field(gt=0)
    billing_rate_usd_cents: int = Field(gt=0)
    cost_usd_cents: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "employee_id": "emp_001",
                "timesheet_id": "ts_001",
                "hours": 40.0,
                "billing_rate_usd_cents": 150000,  # $150/hour
            }
        }


class LineItemResponse(BaseModel):
    id: str
    employee_id: str
    timesheet_id: str
    hours: float
    rate_usd_cents: int
    amount_usd_cents: int

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    project_id: str
    client_id: str
    business_unit_id: Optional[int] = None
    opportunity_id: Optional[str] = None
    client_owner_id: Optional[str] = None
    billing_period_start: date
    billing_period_end: date
    currency: str = "USD"

    class Config:
        schema_extra = {
            "example": {
                "project_id": "proj_001",
                "client_id": "client_001",
                "business_unit_id": 1,
                "opportunity_id": "opp_001",
                "billing_period_start": "2026-08-01",
                "billing_period_end": "2026-08-31",
            }
        }


class InvoiceResponse(BaseModel):
    id: str
    opportunity_id: Optional[str]
    project_id: str
    client_id: str
    business_unit_id: Optional[int]
    client_owner_id: Optional[str]
    status: str
    total_usd_cents: int
    billing_period_start: date
    billing_period_end: date
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetailResponse(InvoiceResponse):
    line_items: List[LineItemResponse] = []
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InvoiceApproveRequest(BaseModel):
    approved_by: str = Field(description="User ID or email of approver")

    class Config:
        schema_extra = {"example": {"approved_by": "user@example.com"}}


class InvoiceStatusResponse(BaseModel):
    DRAFT: int
    APPROVED: int
    SENT: int
    PAID: int
    CANCELLED: int

    class Config:
        schema_extra = {"example": {"DRAFT": 0, "APPROVED": 5, "SENT": 10, "PAID": 100}}


class OutstandingInvoiceResponse(BaseModel):
    invoice_id: str
    client_id: str
    amount: int
    sent_date: datetime
    days_overdue: int
    status: str

    class Config:
        from_attributes = True


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Create Invoice",
    description="Create a new invoice in DRAFT status"
)
def create_new_invoice(
    body: InvoiceCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new invoice for a project.

    Required fields:
    - project_id: Project to invoice
    - client_id: Client to bill
    - billing_period: Start and end dates

    Optional fields:
    - opportunity_id: Link to opportunity for classification
    - client_owner_id: P&L attribution

    Returns: Invoice in DRAFT status
    """
    try:
        invoice = create_invoice(
            db,
            tenant_id=None,  # TODO: Get from context
            project_id=body.project_id,
            client_id=body.client_id,
            business_unit_id=body.business_unit_id,
            opportunity_id=body.opportunity_id,
            billing_period_start=body.billing_period_start,
            billing_period_end=body.billing_period_end,
            client_owner_id=body.client_owner_id,
            currency=body.currency,
        )

        db.commit()
        return invoice

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="Get Invoice Details",
    description="Get complete invoice with all line items"
)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """
    Get invoice details including all line items, status, and timeline.
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)

        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        return invoice

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "",
    response_model=List[InvoiceResponse],
    summary="List Invoices",
    description="Get invoices with optional filtering"
)
def list_invoices(
    project_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    business_unit_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List invoices with optional filtering by:
    - project_id
    - client_id
    - business_unit_id
    - status (DRAFT, APPROVED, SENT, PAID, CANCELLED)
    - billing_period date range
    """
    try:
        invoices = get_invoices(
            db,
            project_id=project_id,
            client_id=client_id,
            business_unit_id=business_unit_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

        return invoices

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{invoice_id}/add-line-item",
    response_model=LineItemResponse,
    status_code=201,
    summary="Add Line Item",
    description="Add timesheet line item to invoice (DRAFT only)"
)
def add_invoice_line_item(
    invoice_id: str,
    body: LineItemCreate,
    db: Session = Depends(get_db),
):
    """
    Add a line item to an invoice.

    Only DRAFT invoices can have line items added.
    Line item amount is calculated as: hours × billing_rate

    Returns: Created line item with calculated amount
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        line_item = add_line_item(
            db,
            invoice,
            employee_id=body.employee_id,
            timesheet_id=body.timesheet_id,
            hours=body.hours,
            billing_rate_usd_cents=body.billing_rate_usd_cents,
            cost_usd_cents=body.cost_usd_cents,
        )

        db.commit()
        return line_item

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{invoice_id}/line-items/{line_item_id}",
    status_code=204,
    summary="Remove Line Item",
    description="Remove a line item from invoice (DRAFT only)"
)
def remove_invoice_line_item(
    invoice_id: str,
    line_item_id: str,
    db: Session = Depends(get_db),
):
    """
    Remove a line item from an invoice.

    Only DRAFT invoices can have line items removed.
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        remove_line_item(db, invoice, line_item_id)

        db.commit()
        return None

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{invoice_id}/approve",
    response_model=InvoiceResponse,
    summary="Approve Invoice",
    description="Approve invoice (DRAFT → APPROVED)"
)
def approve_new_invoice(
    invoice_id: str,
    body: InvoiceApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Approve an invoice.

    Validates:
    - Invoice is DRAFT status
    - All line items present and valid
    - No timesheet disputes
    - Period not locked

    Returns: Updated invoice in APPROVED status
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        invoice = approve_invoice(db, invoice, approved_by=body.approved_by)

        db.commit()
        return invoice

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceResponse,
    summary="Send Invoice",
    description="Send invoice to client (APPROVED → SENT)"
)
def send_new_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """
    Send invoice to client.

    Transitions: APPROVED → SENT
    Action: Email invoice to client

    Returns: Updated invoice in SENT status
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        invoice = send_invoice(db, invoice)

        db.commit()
        return invoice

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{invoice_id}/mark-paid",
    response_model=InvoiceDetailResponse,
    summary="Mark Invoice Paid",
    description="Mark invoice as paid and trigger revenue recognition"
)
def mark_paid(
    invoice_id: str,
    db: Session = Depends(get_db),
):
    """
    Mark invoice as PAID and trigger revenue recognition.

    ⚠️ CRITICAL: This is where revenue is recognized!

    Workflow:
    1. Update invoice status to PAID
    2. Trigger revenue_recognition_service.recognize_revenue_from_paid_invoice()
    3. Create immutable Revenue record
    4. Calculate margin and alert if negative
    5. Apply partner revenue share if applicable
    6. Update P&L dashboards

    Returns: Updated invoice with recognized revenue

    ⚠️ IMMUTABLE: After marking paid, revenue record cannot be changed
    (adjustments create new records instead)
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        invoice, revenue = mark_invoice_paid(db, invoice)

        db.commit()

        # Return invoice details including recognized revenue info
        return invoice

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceResponse,
    summary="Cancel Invoice",
    description="Cancel invoice and create adjustment record"
)
def cancel_new_invoice(
    invoice_id: str,
    reason: str = Query(description="Reason for cancellation"),
    db: Session = Depends(get_db),
):
    """
    Cancel an invoice.

    Creates adjustment record (negative amount) for audit trail.
    Original invoice is never modified - only marked as CANCELLED.

    Allowed from any status.

    Returns: Updated invoice in CANCELLED status
    """
    try:
        invoice = get_invoice_detail(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

        cancel_invoice(db, invoice, reason)

        db.commit()
        return invoice

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/opportunity/{opportunity_id}/invoices",
    response_model=List[InvoiceResponse],
    summary="Get Opportunity Invoices",
    description="Get all invoices for an opportunity"
)
def get_opportunity_invoices(
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    """
    Get all invoices linked to an opportunity.

    An opportunity can have multiple invoices as the project progresses.
    All invoices from the same opportunity are attributed to the same
    client_owner (P&L owner).

    Returns: List of invoices in chronological order
    """
    try:
        invoices = get_invoices_by_opportunity(db, opportunity_id)

        if not invoices:
            raise HTTPException(
                status_code=404,
                detail=f"No invoices found for opportunity {opportunity_id}"
            )

        return invoices

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/business-unit/{business_unit_id}/status-summary",
    response_model=InvoiceStatusResponse,
    summary="Invoice Status Summary",
    description="Get invoice count by status for a business unit"
)
def get_status_summary(
    business_unit_id: int,
    db: Session = Depends(get_db),
):
    """
    Get count of invoices by status.

    Used for dashboard overview:
    - DRAFT: Work in progress
    - APPROVED: Ready to send
    - SENT: Awaiting payment
    - PAID: Recognized revenue
    - CANCELLED: Cancelled/reversed

    Returns: Count of invoices in each status
    """
    try:
        totals = get_invoice_totals_by_status(db, business_unit_id)

        return {
            "DRAFT": totals.get("DRAFT", 0),
            "APPROVED": totals.get("APPROVED", 0),
            "SENT": totals.get("SENT", 0),
            "PAID": totals.get("PAID", 0),
            "CANCELLED": totals.get("CANCELLED", 0),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/business-unit/{business_unit_id}/outstanding",
    response_model=List[OutstandingInvoiceResponse],
    summary="Outstanding Invoices",
    description="Get invoices sent but not yet paid (aged)"
)
def get_outstanding(
    business_unit_id: int,
    days_overdue: int = Query(30, ge=1),
    db: Session = Depends(get_db),
):
    """
    Get outstanding invoices (sent but not yet paid).

    Shows aging: how long invoice has been sent without payment.
    Useful for cash flow and collections monitoring.

    Returns: List of outstanding invoices sorted by age
    """
    try:
        invoices = get_outstanding_invoices(db, business_unit_id, days_overdue)

        return invoices

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

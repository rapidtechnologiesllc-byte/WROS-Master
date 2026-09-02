"""
HRMS-0316 -- Invoice Generation, Calculation, Sending & Payment Tracking
REST API Endpoints
import logging
=========================================================================

Prefix: /api/v1/invoices
Tag: invoices
Auth: All endpoints require get_current_internal_user

Routes:
  POST   /invoices/generate          Generate DRAFT invoice from approved timesheets
  GET    /invoices/{id}/calculate    Calculate bill amount for an invoice
  POST   /invoices/{id}/send         Approve and send invoice to client
  POST   /invoices/{id}/pay          Record payment against invoice
  GET    /invoices/{id}              Get invoice details with line items
  GET    /invoices                   List invoices (filter by status, client)
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id
from app.models.user import Users
from app.schemas.invoice_s316 import (
    GenerateInvoiceRequest,
    GenerateInvoiceResponse,
    SendInvoiceRequest,
    SendInvoiceResponse,
    CalculateBillAmountResponse,
    TrackPaymentRequest,
    TrackPaymentResponse,
    InvoiceDetailResponse,
    InvoiceListResponse,
    InvoiceLineItemResponse,
    ErrorResponse,
)
from app.services.invoice_s316_service import (
    InvoiceS316Service,
    InvoiceError,
    UnapprovedTimesheetBlocksInvoice,
    OpenDisputeBlocksInvoice,
    InvalidInvoiceTransition,
    InvoicePaymentError,
)
from app.models.invoice import Invoice, InvoiceLineItem

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _to_line_item_response(li: InvoiceLineItem) -> InvoiceLineItemResponse:
    """Convert database line item to response schema."""
    return InvoiceLineItemResponse(
        id=li.id,
        invoice_id=li.invoice_id,
        employee_id=li.employee_id,
        timesheet_id=li.timesheet_id,
        hours=float(li.hours),
        rate_usd_cents=li.rate_usd_cents,
        amount_usd_cents=li.amount_usd_cents,
    )


def _to_invoice_response(db: Session, invoice: Invoice, tenant_id: int) -> InvoiceDetailResponse:
    """Convert database invoice to response schema."""
    line_items = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).all()

    return InvoiceDetailResponse(
        id=invoice.id,
        status=invoice.status,
        billing_period_start=invoice.billing_period_start,
        billing_period_end=invoice.billing_period_end,
        project_id=invoice.project_id,
        client_id=invoice.client_id,
        opportunity_id=invoice.opportunity_id,
        bu_context_id=invoice.bu_context_id,
        total_usd_cents=invoice.total_usd_cents,
        currency=invoice.currency,
        approved_by=invoice.approved_by,
        approved_at=invoice.approved_at,
        sent_at=invoice.sent_at,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
        line_items=[_to_line_item_response(li) for li in line_items],
        tenant_id=tenant_id,
    )


# ============================================================================
# POST /invoices/generate
# ============================================================================

@router.post(
    "/generate",
    response_model=GenerateInvoiceResponse,
    status_code=201,
    summary="Generate a DRAFT invoice from approved timesheets",
    responses={
        409: {"model": ErrorResponse, "description": "Unapproved timesheets or disputes block invoice"},
        404: {"model": ErrorResponse, "description": "Project or client not found"},
    },
)
def generate_invoice_endpoint(
    body: GenerateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Generate a DRAFT invoice for a project and billing period.

    Enforces R-10: All timesheets in the period must be APPROVED.
    Enforces BR-02: No open disputes in the period.

    Raises:
    - 409 Conflict: If unapproved timesheets exist (R-10)
    - 409 Conflict: If open disputes exist (BR-02)
    - 404 Not Found: If project or client not found
    - 400 Bad Request: If period end is before start
    """
    service = InvoiceS316Service()

    try:
        invoice = service.generate_invoice(
            db,
            tenant_id=current_user.tenant_id,
            project_id=body.project_id,
            client_id=body.client_id,
            billing_period_start=body.billing_period_start,
            billing_period_end=body.billing_period_end,
            opportunity_id=body.opportunity_id,
            bu_context_id=body.bu_context_id,
            currency=body.currency,
        )
        db.commit()
        db.refresh(invoice)

        # Get line items for response
        line_items = db.query(InvoiceLineItem).filter(
            InvoiceLineItem.invoice_id == invoice.id
        ).all()

        return GenerateInvoiceResponse(
            invoice_id=invoice.id,
            status=invoice.status,
            billing_period_start=invoice.billing_period_start,
            billing_period_end=invoice.billing_period_end,
            project_id=invoice.project_id,
            client_id=invoice.client_id,
            total_usd_cents=invoice.total_usd_cents,
            currency=invoice.currency,
            line_item_count=len(line_items),
            billable_hours=sum(float(li.hours) for li in line_items),
            line_items=[_to_line_item_response(li) for li in line_items],
            created_at=invoice.created_at,
            tenant_id=current_user.tenant_id,
        )

    except UnapprovedTimesheetBlocksInvoice as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
    except OpenDisputeBlocksInvoice as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )
    except InvoiceError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(exc)}",
        )


# ============================================================================
# GET /invoices/{id}/calculate
# ============================================================================

@router.get(
    "/{invoice_id}/calculate",
    response_model=CalculateBillAmountResponse,
    summary="Calculate bill amount for an invoice",
)
def calculate_bill_amount_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Calculate the total billed amount for an invoice.

    Returns breakdown of subtotal, tax, and total in USD cents.
    """
    service = InvoiceS316Service()

    try:
        result = service.calculate_bill_amount(
            db,
            invoice_id=invoice_id,
            tenant_id=current_user.tenant_id,
        )
        return CalculateBillAmountResponse(**result)

    except InvoiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}")


# ============================================================================
# POST /invoices/{id}/send
# ============================================================================

@router.post(
    "/{invoice_id}/send",
    response_model=SendInvoiceResponse,
    summary="Approve and send invoice to client",
    responses={
        409: {"model": ErrorResponse, "description": "Invalid status transition"},
        404: {"model": ErrorResponse, "description": "Invoice not found"},
    },
)
def send_invoice_endpoint(
    invoice_id: str,
    body: SendInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Approve and send an invoice to the client.

    Transitions: DRAFT → APPROVED → SENT
    - Requires Finance approval (approved_by user ID)
    - Sends email to client
    - Updates status to SENT

    Raises:
    - 409 Conflict: If invoice not in DRAFT status
    - 404 Not Found: If invoice not found
    - 400 Bad Request: If client email cannot be determined
    """
    service = InvoiceS316Service()

    try:
        invoice = service.send_invoice(
            db,
            invoice_id=invoice_id,
            tenant_id=current_user.tenant_id,
            approved_by=body.approved_by,
            sent_by=body.sent_by,
            client_email=body.client_email,
        )
        db.commit()
        db.refresh(invoice)

        # Get client email for response
        from app.models.client import Client
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        client_email = body.client_email or (
            next((c.email for c in client.contacts if c.is_primary), None)
            if client and client.contacts else None
        )

        return SendInvoiceResponse(
            invoice_id=invoice.id,
            status=invoice.status,
            approved_by=invoice.approved_by,
            approved_at=invoice.approved_at,
            sent_at=invoice.sent_at,
            total_usd_cents=invoice.total_usd_cents,
            client_email=client_email or "unknown",
            currency=invoice.currency,
            tenant_id=current_user.tenant_id,
        )

    except InvalidInvoiceTransition as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except InvoiceError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}")


# ============================================================================
# POST /invoices/{id}/pay
# ============================================================================

@router.post(
    "/{invoice_id}/pay",
    response_model=TrackPaymentResponse,
    summary="Record payment against invoice",
    responses={
        409: {"model": ErrorResponse, "description": "Invalid status for payment"},
        404: {"model": ErrorResponse, "description": "Invoice not found"},
    },
)
def track_payment_endpoint(
    invoice_id: str,
    body: TrackPaymentRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Record a payment against an invoice.

    Handles partial and full payments:
    - Partial: Keeps status SENT, tracks amount paid
    - Full: Transitions to PAID, triggers revenue recognition

    Raises:
    - 409 Conflict: If invoice not in SENT or PAID status
    - 404 Not Found: If invoice not found
    - 400 Bad Request: If payment amount invalid
    """
    service = InvoiceS316Service()

    try:
        result = service.track_payment(
            db,
            invoice_id=invoice_id,
            tenant_id=current_user.tenant_id,
            amount_received_usd_cents=body.amount_received_usd_cents,
            payment_date=body.payment_date,
            payment_method=body.payment_method,
            reference_number=body.reference_number,
        )
        db.commit()

        return TrackPaymentResponse(
            tenant_id=current_user.tenant_id,
            **result,
        )

    except InvalidInvoiceTransition as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except InvoicePaymentError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except InvoiceError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}")


# ============================================================================
# GET /invoices/{id}
# ============================================================================

@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="Get invoice details with all line items",
)
def get_invoice_endpoint(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Get full invoice details including all line items.

    Raises:
    - 404 Not Found: If invoice not found or belongs to different tenant
    """
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.tenant_id == current_user.tenant_id,
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return _to_invoice_response(db, invoice, current_user.tenant_id)


# ============================================================================
# GET /invoices
# ============================================================================

@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List invoices with optional filters",
)
def list_invoices_endpoint(
    status: Optional[str] = Query(None, description="Filter by status (DRAFT, APPROVED, SENT, PAID)"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    List invoices for the current tenant with optional filtering.

    Query Parameters:
    - status: Filter by invoice status
    - client_id: Filter by client
    - project_id: Filter by project
    - limit: Max results per page (default 100)
    - offset: Pagination offset (default 0)
    """
    query = db.query(Invoice).filter(Invoice.tenant_id == current_user.tenant_id)

    filters_applied = {}
    if status:
        query = query.filter(Invoice.status == status)
        filters_applied["status"] = status
    if client_id:
        query = query.filter(Invoice.client_id == client_id)
        filters_applied["client_id"] = client_id
    if project_id:
        query = query.filter(Invoice.project_id == project_id)
        filters_applied["project_id"] = project_id

    # Order by most recent first
    total_count = query.count()
    invoices = query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()

    return InvoiceListResponse(
        invoices=[_to_invoice_response(db, inv, current_user.tenant_id) for inv in invoices],
        total_count=total_count,
        filtered_by=filters_applied if filters_applied else None,
    )

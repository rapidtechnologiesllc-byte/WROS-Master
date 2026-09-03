"""
HRMS-0316 -- Invoice Generation, Calculation, Sending & Payment Tracking
Pydantic Schemas for Request/Response Validation
import logging
=========================================================================

All monetary values use USD cents (BIGINT per R-09).
All responses include tenant_id for audit/compliance tracking.
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================
logger = logging.getLogger(__name__)

class GenerateInvoiceRequest(BaseModel):
    """Request to generate a DRAFT invoice from approved timesheets."""

    project_id: str = Field(..., description="Project ID to invoice for")
    client_id: str = Field(..., description="Client ID to invoice")
    billing_period_start: date = Field(..., description="Start of billing period (usually Monday)")
    billing_period_end: date = Field(..., description="End of billing period (usually Sunday)")
    opportunity_id: Optional[str] = Field(None, description="Optional opportunity reference for P&L")
    bu_context_id: Optional[int] = Field(None, description="Optional BU context for cost tracking")
    currency: str = Field("USD", description="Billing currency (USD, EUR, GBP, etc.)")

    @validator("billing_period_start", "billing_period_end")
    def validate_dates(cls, v):
        if not isinstance(v, date):
            raise ValueError("Must be a valid date")
        return v

    @validator("billing_period_end")
    def validate_end_after_start(cls, v, values):
        if "billing_period_start" in values and v <= values["billing_period_start"]:
            raise ValueError("billing_period_end must be after billing_period_start")
        return v

    class Config:
        schema_extra = {
            "example": {
                "project_id": "proj-12345",
                "client_id": "client-67890",
                "billing_period_start": "2026-08-01",
                "billing_period_end": "2026-08-31",
                "currency": "USD",
            }
        }


class SendInvoiceRequest(BaseModel):
    """Request to approve and send an invoice to client."""

    approved_by: str = Field(..., description="User ID of Finance approver")
    sent_by: str = Field(..., description="User ID who marks as sent")
    client_email: Optional[str] = Field(None, description="Email to send to (fetched from client if None)")

    class Config:
        schema_extra = {
            "example": {
                "approved_by": "user-finance-001",
                "sent_by": "user-admin-001",
                "client_email": "billing@acme.com",
            }
        }


class TrackPaymentRequest(BaseModel):
    """Request to record a payment against an invoice."""

    amount_received_usd_cents: int = Field(..., gt=0, description="Amount received in USD cents (must be positive)")
    payment_date: datetime = Field(..., description="Date payment was received")
    payment_method: str = Field(..., description="Payment method (check, wire, ACH, credit_card, etc.)")
    reference_number: Optional[str] = Field(None, description="Optional payment reference (check #, wire ref, etc.)")

    @validator("amount_received_usd_cents")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v > 999_999_999_99:  # ~$10M (safety check)
            raise ValueError("Amount exceeds maximum allowed")
        return v

    class Config:
        schema_extra = {
            "example": {
                "amount_received_usd_cents": 50000000,  # $500,000.00
                "payment_date": "2026-08-15T10:30:00Z",
                "payment_method": "wire",
                "reference_number": "WIRE-2026-08-15-001",
            }
        }


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class InvoiceLineItemResponse(BaseModel):
    """A single line item on an invoice."""

    id: str = Field(..., description="Line item ID")
    invoice_id: str = Field(..., description="Parent invoice ID")
    employee_id: str = Field(..., description="Employee ID")
    timesheet_id: str = Field(..., description="Timesheet ID (audit trail)")
    hours: float = Field(..., ge=0, description="Billable hours")
    rate_usd_cents: int = Field(..., gt=0, description="Billing rate in USD cents")
    amount_usd_cents: int = Field(..., ge=0, description="Line total in USD cents (hours * rate)")

    class Config:
        schema_extra = {
            "example": {
                "id": "li-abc123",
                "invoice_id": "inv-xyz789",
                "employee_id": "emp-001",
                "timesheet_id": "ts-week1",
                "hours": 40.0,
                "rate_usd_cents": 5000,  # $50/hr
                "amount_usd_cents": 200000,  # $2,000.00
            }
        }


class GenerateInvoiceResponse(BaseModel):
    """Response after generating an invoice."""

    invoice_id: str = Field(..., description="Generated invoice ID")
    status: str = Field(..., description="Invoice status (DRAFT)")
    billing_period_start: date
    billing_period_end: date
    project_id: str
    client_id: str
    total_usd_cents: int = Field(..., ge=0, description="Total invoice amount in USD cents")
    currency: str
    line_item_count: int = Field(..., ge=0, description="Number of line items")
    billable_hours: float = Field(..., ge=0, description="Total billable hours")
    line_items: List[InvoiceLineItemResponse] = []
    created_at: datetime
    tenant_id: int

    class Config:
        schema_extra = {
            "example": {
                "invoice_id": "inv-12345",
                "status": "DRAFT",
                "billing_period_start": "2026-08-01",
                "billing_period_end": "2026-08-31",
                "project_id": "proj-001",
                "client_id": "client-001",
                "total_usd_cents": 500000,  # $5,000.00
                "currency": "USD",
                "line_item_count": 2,
                "billable_hours": 100.0,
                "line_items": [],
                "created_at": "2026-08-15T10:30:00Z",
                "tenant_id": 1,
            }
        }


class CalculateBillAmountResponse(BaseModel):
    """Response from bill amount calculation."""

    invoice_id: str
    subtotal_usd_cents: int = Field(..., ge=0, description="Sum of line items in USD cents")
    tax_usd_cents: int = Field(..., ge=0, description="Tax amount in USD cents")
    total_usd_cents: int = Field(..., ge=0, description="Total amount due in USD cents")
    line_item_count: int = Field(..., ge=0)
    billable_hours: float = Field(..., ge=0)
    currency: str
    status: str = Field(..., description="Current invoice status")

    class Config:
        schema_extra = {
            "example": {
                "invoice_id": "inv-12345",
                "subtotal_usd_cents": 500000,
                "tax_usd_cents": 0,
                "total_usd_cents": 500000,
                "line_item_count": 2,
                "billable_hours": 100.0,
                "currency": "USD",
                "status": "DRAFT",
            }
        }


class SendInvoiceResponse(BaseModel):
    """Response after sending an invoice."""

    invoice_id: str
    status: str = Field(..., description="Invoice status (SENT)")
    approved_by: str
    approved_at: datetime
    sent_at: datetime
    total_usd_cents: int
    client_email: str = Field(..., description="Email invoice was sent to")
    currency: str
    tenant_id: int

    class Config:
        schema_extra = {
            "example": {
                "invoice_id": "inv-12345",
                "status": "SENT",
                "approved_by": "user-finance-001",
                "approved_at": "2026-08-15T10:30:00Z",
                "sent_at": "2026-08-15T10:31:00Z",
                "total_usd_cents": 500000,
                "client_email": "billing@acme.com",
                "currency": "USD",
                "tenant_id": 1,
            }
        }


class TrackPaymentResponse(BaseModel):
    """Response after recording a payment."""

    invoice_id: str
    amount_received_usd_cents: int = Field(..., gt=0, description="Amount recorded")
    total_paid_usd_cents: int = Field(..., ge=0, description="Total paid to date")
    remaining_usd_cents: int = Field(..., ge=0, description="Amount still due")
    status: str = Field(..., description="Invoice status (SENT or PAID)")
    is_fully_paid: bool = Field(..., description="True if invoice is fully paid")
    payment_date: str = Field(..., description="ISO format payment date")
    payment_method: str
    reference_number: Optional[str] = None
    tenant_id: int

    class Config:
        schema_extra = {
            "example": {
                "invoice_id": "inv-12345",
                "amount_received_usd_cents": 250000,
                "total_paid_usd_cents": 250000,
                "remaining_usd_cents": 250000,
                "status": "SENT",
                "is_fully_paid": False,
                "payment_date": "2026-08-15T10:30:00Z",
                "payment_method": "wire",
                "reference_number": "WIRE-2026-08-15-001",
                "tenant_id": 1,
            }
        }


class InvoiceDetailResponse(BaseModel):
    """Full invoice details with all line items."""

    id: str = Field(..., description="Invoice ID")
    status: str = Field(..., description="Invoice status (DRAFT, APPROVED, SENT, PAID)")
    billing_period_start: date
    billing_period_end: date
    project_id: str
    client_id: str
    opportunity_id: Optional[str] = None
    bu_context_id: Optional[int] = None
    total_usd_cents: int = Field(..., ge=0, description="Total in USD cents")
    currency: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    line_items: List[InvoiceLineItemResponse] = []
    tenant_id: int

    class Config:
        schema_extra = {
            "example": {
                "id": "inv-12345",
                "status": "SENT",
                "billing_period_start": "2026-08-01",
                "billing_period_end": "2026-08-31",
                "project_id": "proj-001",
                "client_id": "client-001",
                "opportunity_id": "opp-001",
                "bu_context_id": 1,
                "total_usd_cents": 500000,
                "currency": "USD",
                "approved_by": "user-finance-001",
                "approved_at": "2026-08-15T10:30:00Z",
                "sent_at": "2026-08-15T10:31:00Z",
                "paid_at": None,
                "created_at": "2026-08-14T09:00:00Z",
                "line_items": [],
                "tenant_id": 1,
            }
        }


class InvoiceListResponse(BaseModel):
    """List of invoices."""

    invoices: List[InvoiceDetailResponse] = []
    total_count: int = Field(..., ge=0, description="Total invoices matching filter")
    filtered_by: Optional[dict] = None

    class Config:
        schema_extra = {
            "example": {
                "invoices": [],
                "total_count": 0,
                "filtered_by": {"status": "SENT", "client_id": "client-001"},
            }
        }


# ============================================================================
# ERROR RESPONSE SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error message")
    timestamp: datetime
    tenant_id: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "error": "UnapprovedTimesheetBlocksInvoice",
                "detail": "Cannot generate invoice: found 2 unapproved timesheets",
                "timestamp": "2026-08-15T10:30:00Z",
                "tenant_id": 1,
            }
        }

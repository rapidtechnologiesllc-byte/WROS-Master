"""Pydantic schemas -- HRMS-0907 (Invoice Generation, Status Tracking) API."""
import logging

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class GenerateInvoiceRequest(BaseModel):
    project_id: str
    period_start: date
    period_end: date

class InvoiceLineItemItem(BaseModel):
    id: str
    employee_id: str
    timesheet_id: str
    hours: float
    rate_usd_cents: int
    amount_usd_cents: int
    employee_name: Optional[str] = None
    po_number: Optional[str] = None

class InvoiceItem(BaseModel):
    id: str
    project_id: str
    client_id: str
    billing_period_start: date
    billing_period_end: date
    status: str
    total_usd_cents: int
    currency: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    line_items: List[InvoiceLineItemItem] = []
    # How the invoice reaches the client: EMAIL (QUEUED -> DRAFTED -> SENT) or EXTERNAL
    delivery_channel: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_to: Optional[str] = None
    # compliance: the real invoice number, its issuing company, the client PO(s), the due date
    invoice_number: Optional[str] = None
    issuing_company_id: Optional[str] = None
    issuing_company_name: Optional[str] = None
    po_numbers: Optional[str] = None
    due_date: Optional[date] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None

class RecordExternalDeliveryRequest(BaseModel):
    note: str  # how it was delivered, e.g. "uploaded to the client's Ariba portal"

class RecordPaymentRequest(BaseModel):
    paid_on: date
    amount_usd_cents: int
    reference: str  # bank / UTR / cheque reference

class MarkPaidRequest(BaseModel):
    paid_on: Optional[date] = None  # defaults to today

class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceItem]

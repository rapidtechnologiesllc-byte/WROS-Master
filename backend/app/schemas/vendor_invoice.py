"""Pydantic schemas -- sub-vendor invoices and pay-when-paid (vendor_invoice_service)."""
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SubVendorCreate(BaseModel):
    company_name: str
    contact_email: str
    contact_phone: Optional[str] = None
    tax_id: Optional[str] = None


class SubVendorItem(BaseModel):
    id: str
    company_name: str
    contact_email: str
    status: str
    contractors: int = 0
    payment_terms_days: int = 30
    w9_status: str = "NOT_REQUESTED"
    is_1099: bool = True
    receives_new_roles: bool = True
    has_tax_id: bool = False
    last_paid_on: Optional[str] = None
    unpaid_bills: int = 0
    open_balance_usd_cents: int = 0
    paid_this_year_usd_cents: int = 0


class SubVendorUpdate(BaseModel):
    contact_email: Optional[str] = None
    payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    w9_status: Optional[Literal["NOT_REQUESTED", "REQUESTED", "RECEIVED"]] = None
    is_1099: Optional[bool] = None
    receives_new_roles: Optional[bool] = None
    tax_id: Optional[str] = None


class SubmissionAccept(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SubmissionReject(BaseModel):
    note: str


class ContractorSet(BaseModel):
    employee_id: str
    sub_vendor_id: str
    hourly_rate_usd_cents: int


class ContractorItem(BaseModel):
    employee_id: str
    name: str
    employment_type: str
    sub_vendor_id: Optional[str] = None
    sub_vendor_name: Optional[str] = None
    hourly_rate_usd_cents: Optional[int] = None


class ContractorsResponse(BaseModel):
    contractors: List[ContractorItem]
    employees: List[ContractorItem]  # everyone who could be made a contractor


class EligibleTimesheet(BaseModel):
    timesheet_id: str
    employee_id: str
    employee_name: str
    week_starting_date: str
    hours: float
    rate_usd_cents: int
    amount_usd_cents: int


class EligibleTimesheetsResponse(BaseModel):
    timesheets: List[EligibleTimesheet]
    expected_usd_cents: int


class VendorInvoiceCreate(BaseModel):
    sub_vendor_id: str
    vendor_invoice_number: str
    invoice_date: date
    period_start: date
    period_end: date
    amount_usd_cents: int
    note: Optional[str] = None


class VendorInvoiceApprove(BaseModel):
    note: Optional[str] = None


class VendorInvoiceReject(BaseModel):
    reason: str


class VendorInvoicePay(BaseModel):
    paid_on: date
    reference: str


class VendorInvoiceLineItem(BaseModel):
    employee_name: str
    week_starting_date: str
    hours: float
    rate_usd_cents: int
    amount_usd_cents: int


class VendorInvoiceItem(BaseModel):
    id: str
    due_date: Optional[str] = None
    sub_vendor_id: str
    sub_vendor_name: Optional[str] = None
    vendor_invoice_number: str
    invoice_date: str
    period_start: str
    period_end: str
    status: str
    amount_usd_cents: int
    expected_usd_cents: int
    variance_usd_cents: int
    note: Optional[str] = None
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    payment_reference: Optional[str] = None
    rejected_reason: Optional[str] = None
    client_paid: bool
    payment_blockers: List[str] = []
    lines: List[VendorInvoiceLineItem] = []


class VendorInvoiceListResponse(BaseModel):
    vendor_invoices: List[VendorInvoiceItem]
    owed_usd_cents: int  # approved, not yet paid
    payable_now_usd_cents: int  # approved and the client has paid

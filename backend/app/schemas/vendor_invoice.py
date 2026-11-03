"""Pydantic schemas -- sub-vendor invoices and pay-when-paid (vendor_invoice_service)."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel


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

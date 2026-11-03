"""Sub-vendor invoices (CEO 2026-11-02: "unable to add a sub vendor invoice which we need to do the
payment ... we need to make sure we got the payment from the client and then initiate the payment to
the sub vendor" / "make sure it is connected to the full P&L").

A contractor (Employee.employment_type CONTRACT) supplied by a sub-vendor (Employee.sub_vendor_id)
is paid through the vendor at Employee.vendor_hourly_rate_usd_cents. The vendor's invoice for a
period is one VendorInvoice with one line per approved timesheet it covers, so each line traces to
the same timesheet the client is billed for (InvoiceLineItem.timesheet_id). Pay-when-paid: a vendor
invoice can be paid only when every one of its timesheets is on a client invoice that is PAID
(vendor_invoice_service.payment_readiness). Its line amounts are the contractor's delivery cost in
the P&L (revenue_chain_service).
"""
import uuid

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func

from app.models.base import Base

VENDOR_INVOICE_STATUSES = ("RECEIVED", "APPROVED", "PAID", "REJECTED")


def _new_uuid() -> str:
    return str(uuid.uuid4())


class VendorInvoice(Base):
    __tablename__ = "vendor_invoices"
    __table_args__ = (
        Index("uq_vendor_invoice_number", "sub_vendor_id", "vendor_invoice_number", unique=True),
    )

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    sub_vendor_id = Column(String(512), ForeignKey("sub_vendor_accounts.id"), nullable=False, index=True)
    vendor_invoice_number = Column(String(128), nullable=False)  # the number on the vendor's invoice
    invoice_date = Column(Date, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(Enum(*VENDOR_INVOICE_STATUSES, name="vendor_invoice_status", native_enum=False,
                         create_constraint=True), nullable=False, default="RECEIVED")
    # what the vendor billed vs approved hours x the contractor's vendor rate
    amount_usd_cents = Column(Integer, nullable=False)
    expected_usd_cents = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    approved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(String(255), nullable=True)
    rejected_reason = Column(Text, nullable=True)


class VendorInvoiceLine(Base):
    """One approved timesheet on a vendor invoice. A timesheet is on at most one live (not
    rejected) vendor invoice: vendor_invoice_service checks it before adding a line."""
    __tablename__ = "vendor_invoice_lines"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    vendor_invoice_id = Column(String(512), ForeignKey("vendor_invoices.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    timesheet_id = Column(String(512), ForeignKey("timesheets.id"), nullable=False, index=True)
    hours = Column(Numeric(6, 2), nullable=False)
    rate_usd_cents = Column(Integer, nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)

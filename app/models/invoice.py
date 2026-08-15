"""
HRMS-0907 -- Invoice Generation, Status Tracking & PDF Export. Phase 2
Domain 4.

PDF export and automatic sending are explicitly out of scope for this
build (PDF rendering is a frontend/reporting concern, consistent with
no REST endpoints/UI existing yet for anything this session; "Sent" is
always an explicit human action per the story's own "Not In Scope"
note, never automatic regardless of Finance approval).

Generation itself enforces R-10 ("unapproved timesheet blocks invoice
generation") for real -- see app.services.invoice_service.generate_invoice(),
which also blocks on any open HRMS-0904 timesheet dispute in the
period, extending that story's own BR-02.
"""
import uuid

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES


def _new_uuid() -> str:
    return str(uuid.uuid4())


INVOICE_STATUSES = ("DRAFT", "APPROVED", "SENT", "PAID")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    # Business Unit Context assignment — unified reference to BU + partner + head + HR manager
    # Denormalized for easier querying and reporting by BU
    bu_context_id = Column(Integer, ForeignKey("business_unit_context.id"), nullable=True, index=True)

    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)

    status = Column(
        Enum(*INVOICE_STATUSES, name="invoice_status", native_enum=False, create_constraint=True),
        nullable=False, default="DRAFT",
    )
    # R-09: BIGINT USD cents storage; currency is the client's display currency only.
    total_usd_cents = Column(Integer, nullable=False, default=0)
    currency = Column(
        Enum(*BILLING_CURRENCIES, name="invoice_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD",
    )

    # HRMS-0907 BR-0907-02: Draft->Approved always an explicit Finance-role action.
    approved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    # "Not In Scope": Sent is always explicit, even after approval -- no auto-send.
    sent_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    bu_context = relationship("BusinessUnitContext", foreign_keys=[bu_context_id], lazy="select")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    # One line item per employee per timesheet (one work-week) in the
    # billing period -- the timesheet is the audit trail back to the
    # exact approved hours this line item bills for.
    timesheet_id = Column(String(36), ForeignKey("timesheets.id"), nullable=False)

    hours = Column(Numeric(6, 2), nullable=False)
    rate_usd_cents = Column(Integer, nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)

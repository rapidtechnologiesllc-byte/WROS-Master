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
import logging
import uuid

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, func,
)

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES

def _new_uuid() -> str:
    return str(uuid.uuid4())

INVOICE_STATUSES = ("DRAFT", "APPROVED", "SENT", "PAID")

logger = logging.getLogger(__name__)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    project_id = Column(String(512), ForeignKey("projects.id"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)

    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)

    status = Column(
        Enum(*INVOICE_STATUSES, name="invoice_status", native_enum=False, create_constraint=True),
        nullable=False, default="DRAFT",
    )
    # R-09: BIGINT USD cents storage; currency is the client's display currency only.
    total_usd_cents = Column(Integer, nullable=False, default = 0)
    currency = Column(
        Enum(*BILLING_CURRENCIES, name="invoice_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD",
    )

    # HRMS-0907 BR-0907-02: Draft->Approved always an explicit Finance-role action.
    approved_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    # "Not In Scope": Sent is always explicit, even after approval -- no auto-send.
    sent_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    # Compliance (CEO 2026-10-23): the company that issues it (the client's contracting company;
    # NULL = the tenant itself), stored at generation; a gapless number per issuing company
    # (invoice_numbering); the client's PO number(s) from the placements' work orders; and the due
    # date = sent date + the client's payment terms, stored when it is sent (AR ages by it).
    issuing_company_id = Column(String(512), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_seq = Column(Integer, nullable=True)
    invoice_number = Column(String(64), nullable=True)
    po_numbers = Column(String(512), nullable=True)
    due_date = Column(Date, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("uq_invoice_number_per_tenant", "tenant_id", "invoice_number", unique=True),
    )


class InvoiceNumberSequence(Base):
    """The last number issued per issuing company (issuer_key: the company id, or "tenant:<id>"
    when the tenant itself issues). Taken under a row lock inside the generating transaction, so
    numbers are sequential and gapless: a rolled-back generation rolls its number back too."""
    __tablename__ = "invoice_number_sequences"

    issuer_key = Column(String(512), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    company_id = Column(String(512), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    last_number = Column(Integer, nullable=False, default=0)

class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    invoice_id = Column(String(512), ForeignKey("invoices.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False)
    # One line item per employee per timesheet (one work-week) in the
    # billing period -- the timesheet is the audit trail back to the
    # exact approved hours this line item bills for.
    timesheet_id = Column(String(512), ForeignKey("timesheets.id"), nullable=False)

    hours = Column(Numeric(6, 2), nullable=False)
    rate_usd_cents = Column(Integer, nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)
    # the client PO this line bills against (the allocation's work order), printed on the line
    po_number = Column(String(512), nullable=True)

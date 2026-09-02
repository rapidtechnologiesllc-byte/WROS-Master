"""
HRMS-0907 -- Invoice Generation, Status Tracking. R-10 ("unapproved
timesheet blocks invoice generation") is a named platform hard rule
this session already tracks -- generate_invoice() enforces it directly
rather than waiting on HRMS-0605's full TimesheetRevenueProcessor
pipeline (which doesn't exist): every Timesheet whose allocation is
scoped to this project and whose week falls in the billing period must
be APPROVED, with no exceptions, or generation is blocked outright.
Also extends HRMS-0904's BR-02 (an open dispute blocks the period)
for real, since TimesheetDispute already exists.
"""
from datetime import datetime
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.timesheet import Timesheet
from app.services.timesheet_dispute_service import has_open_dispute

logger = logging.getLogger(__name__)

class UnapprovedTimesheetBlocksInvoice(Exception):
    """R-10: no exceptions, no bypass."""


class OpenDisputeBlocksInvoice(Exception):
    """HRMS-0904 BR-02."""


class InvalidInvoiceTransition(Exception):
    pass


def _timesheets_in_period(db: Session, project: Project, period_start, period_end) -> List[Timesheet]:
    return db.query(Timesheet).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(
        EmployeeAllocation.project_id == project.id,
        Timesheet.week_starting_date >= period_start,
        Timesheet.week_starting_date <= period_end,
    ).all()


def generate_invoice(
    db: Session, project: Project, *, period_start, period_end, tenant_id: Optional[int] = None,
) -> Invoice:
    """
    R-10: EVERY timesheet in scope must be APPROVED, no partial
    invoicing around a stuck one. Collects all violations (unapproved +
    disputed) before raising, same "show every blocker at once"
    discipline as submission_service.create_submission().
    """
    timesheets = _timesheets_in_period(db, project, period_start, period_end)

    unapproved = [ts.id for ts in timesheets if ts.status != "APPROVED"]
    if unapproved:
        raise UnapprovedTimesheetBlocksInvoice(
            f"Cannot generate invoice -- {len(unapproved)} timesheet(s) in this period are not APPROVED: {unapproved}"
        )

    disputed = [ts.id for ts in timesheets if has_open_dispute(db, ts)]
    if disputed:
        raise OpenDisputeBlocksInvoice(
            f"Cannot generate invoice -- {len(disputed)} timesheet(s) in this period have an open dispute: {disputed}"
        )

    invoice = Invoice(
        tenant_id=tenant_id or project.tenant_id, project_id=project.id, client_id=project.client_id,
        billing_period_start=period_start, billing_period_end=period_end, currency=project.currency,
    )
    db.add(invoice)
    db.flush()

    total = 0
    for ts in timesheets:
        allocation = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == ts.allocation_id).first()
        rate = (allocation.billing_rate_usd_cents or 0) if allocation else 0
        hours = float(ts.billable_hours)
        amount = round(rate * hours)
        total += amount

        db.add(InvoiceLineItem(
            invoice_id=invoice.id, employee_id=ts.employee_id, timesheet_id=ts.id,
            hours=hours, rate_usd_cents=rate, amount_usd_cents=amount,
        ))

    invoice.total_usd_cents = total
    db.add(invoice)
    return invoice


def approve_invoice(db: Session, invoice: Invoice, *, approved_by: str) -> Invoice:
    """BR-0907-02: Draft->Approved is always an explicit Finance-role action."""
    if invoice.status != "DRAFT":
        raise InvalidInvoiceTransition(f"Cannot approve an invoice in status '{invoice.status}'.")
    invoice.status = "APPROVED"
    invoice.approved_by = approved_by
    invoice.approved_at = datetime.utcnow()
    db.add(invoice)
    return invoice


def send_invoice(db: Session, invoice: Invoice) -> Invoice:
    """"Not In Scope": no automatic sending, even after Finance approval --
    always a distinct, deliberate human action."""
    if invoice.status != "APPROVED":
        raise InvalidInvoiceTransition(f"Cannot send an invoice in status '{invoice.status}'.")
    invoice.status = "SENT"
    invoice.sent_at = datetime.utcnow()
    db.add(invoice)
    return invoice


def mark_invoice_paid(db: Session, invoice: Invoice) -> Invoice:
    if invoice.status != "SENT":
        raise InvalidInvoiceTransition(f"Cannot mark an invoice paid from status '{invoice.status}'.")
    invoice.status = "PAID"
    invoice.paid_at = datetime.utcnow()
    db.add(invoice)
    return invoice

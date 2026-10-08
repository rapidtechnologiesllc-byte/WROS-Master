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

from app.core.config import settings
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

class MissingBillRate(Exception):
    """Billable hours on an allocation with no bill rate: the invoice would be wrong, so it isn't created."""

class NothingToInvoice(Exception):
    """No timesheets for the project in the period: an empty invoice is never created."""

class AlreadyInvoiced(Exception):
    """A timesheet already sits on another invoice: billing it again would charge the client twice."""

class MissingBillingContact(Exception):
    """The client has no active ACCOUNTS contact to email the invoice to."""

INVOICE_EMAIL_TASK = "send_invoice_email"

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
    if not timesheets:
        raise NothingToInvoice(
            "Cannot generate invoice -- no timesheets for this project in this period. Employees are billed through "
            "their allocation to the project's job; check that the people working on it are allocated and have submitted time."
        )

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

    already = sorted({
        row[0] for row in db.query(InvoiceLineItem.timesheet_id).filter(
            InvoiceLineItem.timesheet_id.in_([ts.id for ts in timesheets])
        ).all()
    })
    if already:
        raise AlreadyInvoiced(
            f"Cannot generate invoice -- {len(already)} timesheet(s) in this period are already on an invoice: {already}. "
            "Use the existing invoice, or pick a period that hasn't been billed."
        )

    allocations = {
        a.id: a for a in db.query(EmployeeAllocation).filter(
            EmployeeAllocation.id.in_({ts.allocation_id for ts in timesheets if ts.allocation_id})
        )
    }
    unpriced = sorted({
        ts.employee_id for ts in timesheets
        if float(ts.billable_hours or 0) > 0 and not (allocations.get(ts.allocation_id) and allocations[ts.allocation_id].billing_rate_usd_cents)
    })
    if unpriced:
        raise MissingBillRate(
            f"Cannot generate invoice -- {len(unpriced)} employee(s) have billable hours but no bill rate on their allocation "
            f"({unpriced}). Set the client bill rate on the job (or the allocation) first."
        )

    invoice = Invoice(
        tenant_id=tenant_id or project.tenant_id, project_id=project.id, client_id=project.client_id,
        billing_period_start=period_start, billing_period_end=period_end, currency=project.currency,
    )
    db.add(invoice)
    db.flush()

    total = 0
    for ts in timesheets:
        allocation = allocations.get(ts.allocation_id)
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

def billing_contact_email(db: Session, client_id: str) -> str:
    """The client's active ACCOUNTS contact (primary first). Never guesses another contact."""
    from app.models.client import ClientContact

    contact = db.query(ClientContact).filter(
        ClientContact.client_id == client_id, ClientContact.role_type == "ACCOUNTS",
        ClientContact.is_active.is_(True),
    ).order_by(ClientContact.is_primary.desc(), ClientContact.created_at).first()
    if contact is None or not contact.email:
        raise MissingBillingContact(
            "This client has no active ACCOUNTS contact. Add the client's accounts-payable email as a contact "
            "with role ACCOUNTS, then send again."
        )
    return contact.email


def request_invoice_email(db: Session, invoice: Invoice, *, requested_by: Optional[str]):
    """Queue the invoice email to the client's accounts contact. The invoice stays
    APPROVED until the email has really gone out; the handler then marks it SENT.
    Asking again while a send is already queued changes nothing."""
    from app.models.invoice_delivery import InvoiceDelivery

    if invoice.status != "APPROVED":
        raise InvalidInvoiceTransition(f"Cannot send an invoice in status '{invoice.status}'.")
    if not invoice.total_usd_cents:
        raise InvalidInvoiceTransition("Cannot send an invoice with a zero total.")
    to_address = billing_contact_email(db, invoice.client_id)

    delivery = db.query(InvoiceDelivery).filter(InvoiceDelivery.invoice_id == invoice.id).with_for_update().first()
    if delivery is not None and delivery.status in ("QUEUED", "DRAFTED") and _send_still_queued(db, delivery):
        return delivery
    if delivery is None:
        delivery = InvoiceDelivery(invoice_id=invoice.id, tenant_id=invoice.tenant_id, request_count=1)
        db.add(delivery)
    elif delivery.status in ("QUEUED", "DRAFTED"):
        delivery.request_count += 1  # the earlier attempt failed for good: start a fresh one
    delivery.channel, delivery.to_address, delivery.requested_by = "EMAIL", to_address, requested_by
    delivery.requested_at, delivery.mailbox = datetime.utcnow(), settings.FINANCE_MAILBOX
    if delivery.status != "DRAFTED":
        delivery.status = "QUEUED"
    db.commit()

    from app.services.thunder_mail.cadence_service import enqueue_once
    enqueue_once(INVOICE_EMAIL_TASK, invoice_email_task_id(delivery),
                 {"invoice_id": invoice.id, "request": delivery.request_count}, invoice.tenant_id)
    logger.info(f"[Invoice] email queued invoice={invoice.id} to={to_address} request={delivery.request_count}")
    return delivery


def invoice_email_task_id(delivery) -> str:
    return f"invoice-email-{delivery.invoice_id}-{delivery.request_count}"


def _send_still_queued(db: Session, delivery) -> bool:
    from app.models.channel_queue import ChannelQueueItem

    row = db.query(ChannelQueueItem.status).filter(ChannelQueueItem.id == invoice_email_task_id(delivery)).first()
    return row is not None and str(row[0]).upper() not in ("FAILED", "DEAD_LETTER", "COMPLETED")


def mark_invoice_sent(db: Session, invoice: Invoice, *, sent_at: Optional[datetime] = None) -> Invoice:
    if invoice.status != "APPROVED":
        raise InvalidInvoiceTransition(f"Cannot send an invoice in status '{invoice.status}'.")
    invoice.status = "SENT"
    invoice.sent_at = sent_at or datetime.utcnow()
    db.add(invoice)
    return invoice


def record_external_delivery(db: Session, invoice: Invoice, *, recorded_by: Optional[str], note: str) -> Invoice:
    """Finance submitted the invoice another way (client portal, hand delivery)."""
    from app.models.invoice_delivery import InvoiceDelivery

    if not (note or "").strip():
        raise InvalidInvoiceTransition("Say how the invoice was delivered (e.g. 'uploaded to client's Ariba portal').")
    mark_invoice_sent(db, invoice)
    delivery = db.query(InvoiceDelivery).filter(InvoiceDelivery.invoice_id == invoice.id).first()
    if delivery is None:
        delivery = InvoiceDelivery(invoice_id=invoice.id, tenant_id=invoice.tenant_id)
        db.add(delivery)
    delivery.channel, delivery.status, delivery.sent_at = "EXTERNAL", "SENT", invoice.sent_at
    delivery.requested_by, delivery.note = recorded_by, note.strip()
    return invoice


def mark_invoice_paid(db: Session, invoice: Invoice, *, paid_at: Optional[datetime] = None) -> Invoice:
    """SENT -> PAID and recognise the revenue in the same transaction."""
    from app.services.revenue_chain_service import recognize_revenue

    if invoice.status != "SENT":
        raise InvalidInvoiceTransition(f"Cannot mark an invoice paid from status '{invoice.status}'.")
    invoice.status = "PAID"
    invoice.paid_at = paid_at or datetime.utcnow()
    db.add(invoice)
    db.flush()
    recognize_revenue(db, invoice)
    return invoice

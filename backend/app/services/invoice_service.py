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
from datetime import datetime, timedelta
import logging
from typing import List, Optional, Tuple

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

class InvoiceApproverNotAllowed(Exception):
    """Only Finance at Senior Manager level or above may approve an invoice."""

# CEO decision 2026-10-10: every invoice is reviewed by a person in Finance at Senior Manager
# or above (Senior Manager, Director, VP, CFO...). Levels are the 17-level org hierarchy
# (org_hierarchy_validator.HIERARCHY_LEVELS: 9 = Senior Manager). No admin bypass.
def is_invoice_approver(db: Session, user) -> bool:
    """Finance at Senior Manager level or above (CEO decision 2026-10-10). No super-user
    bypass: approving what a client is billed is Finance's call, not an administrator's."""
    from app.core import authority

    return authority.is_finance_leader(db, user)

def invoice_approvers(db: Session, tenant_id: Optional[int]) -> list:
    """Everyone who may approve invoices, most junior first (they get the review task)."""
    from app.core import authority
    from app.models.user import Users

    query = db.query(Users).filter(Users.terminated_at.is_(None))
    if tenant_id is not None:
        query = query.filter(Users.tenant_id == tenant_id)
    users = [u for u in query.order_by(Users.CreatedAt).all() if is_invoice_approver(db, u)]
    return sorted(users, key=lambda u: authority.level(db, u))

class AlreadyInvoiced(Exception):
    """A timesheet already sits on another invoice: billing it again would charge the client twice."""

class MissingBillingContact(Exception):
    """The client has no active ACCOUNTS contact to email the invoice to."""

INVOICE_EMAIL_TASK = "send_invoice_email"

def _timesheets_in_period(db: Session, project: Project, period_start, period_end) -> List[Timesheet]:
    """Every week that overlaps the period: a week can straddle two months, and its days
    are billed to the month they fall in."""
    return db.query(Timesheet).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(
        EmployeeAllocation.project_id == project.id,
        Timesheet.week_starting_date >= period_start - timedelta(days=6),
        Timesheet.week_starting_date <= period_end,
    ).all()


def billable_hours_in(db: Session, timesheet: Timesheet, period_start, period_end) -> float:
    """Billable hours of this timesheet dated inside the period. Hours entered without
    daily entries are dated to the week's Monday."""
    from app.models.timesheet import TimesheetEntry

    entries = db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == timesheet.id).all()
    if not entries:
        return float(timesheet.billable_hours or 0) if period_start <= timesheet.week_starting_date <= period_end else 0.0
    return sum(float(e.hours) for e in entries if e.entry_type == "BILLABLE" and period_start <= e.entry_date <= period_end)


def _already_billed(db: Session, timesheets: List[Timesheet], period_start, period_end) -> Tuple[set, dict]:
    """(timesheets already on an invoice for an overlapping period, hours already invoiced per timesheet)."""
    ids = [ts.id for ts in timesheets]
    rows = db.query(InvoiceLineItem.timesheet_id, InvoiceLineItem.hours, Invoice.billing_period_start,
                    Invoice.billing_period_end).join(Invoice, Invoice.id == InvoiceLineItem.invoice_id).filter(
        InvoiceLineItem.timesheet_id.in_(ids)).all() if ids else []
    overlapping, hours = set(), {}
    for timesheet_id, line_hours, start, end in rows:
        hours[timesheet_id] = hours.get(timesheet_id, 0.0) + float(line_hours or 0)
        if start <= period_end and end >= period_start:
            overlapping.add(timesheet_id)
    return overlapping, hours


def generate_invoice(
    db: Session, project: Project, *, period_start, period_end, tenant_id: Optional[int] = None,
) -> Invoice:
    """
    R-10: EVERY timesheet in scope must be APPROVED, no partial invoicing around a stuck one;
    all blockers are reported at once. Hours are billed by the day they were worked, so a
    week straddling two months is split between them. A timesheet is never billed twice:
    not for an overlapping period, and never beyond its approved billable hours. The
    project row is locked so two simultaneous generations cannot both bill it.
    """
    if period_end < period_start:
        raise ValueError("The billing period ends before it starts.")
    db.query(Project.id).filter(Project.id == project.id).with_for_update().first()
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

    overlapping, invoiced_hours = _already_billed(db, timesheets, period_start, period_end)
    to_bill = []
    for ts in timesheets:
        if ts.id in overlapping:
            continue
        remaining = float(ts.billable_hours or 0) - invoiced_hours.get(ts.id, 0.0)
        hours = round(min(billable_hours_in(db, ts, period_start, period_end), max(remaining, 0.0)), 2)
        if hours > 0:
            to_bill.append((ts, hours))
    if not to_bill:
        if overlapping:
            raise AlreadyInvoiced(
                f"Cannot generate invoice -- {len(overlapping)} timesheet(s) in this period are already on an invoice: "
                f"{sorted(overlapping)}. Use the existing invoice, or pick a period that hasn't been billed."
            )
        raise NothingToInvoice("Cannot generate invoice -- no billable hours in this period.")

    allocations = {
        a.id: a for a in db.query(EmployeeAllocation).filter(
            EmployeeAllocation.id.in_({ts.allocation_id for ts, _ in to_bill})
        )
    }
    unpriced = sorted({ts.employee_id for ts, _ in to_bill if not allocations[ts.allocation_id].billing_rate_usd_cents})
    if unpriced:
        raise MissingBillRate(
            f"Cannot generate invoice -- {len(unpriced)} employee(s) have billable hours but no bill rate on their allocation "
            f"({unpriced}). Set the client bill rate on the job (or the allocation) first."
        )
    foreign = sorted({a.id for a in allocations.values() if a.client_id and a.client_id != project.client_id})
    if foreign:
        raise ValueError(f"Allocation(s) {foreign} belong to a different client than project {project.id}; "
                         "fix the allocation before invoicing.")

    # every amount is USD cents (R-09); the invoice says so rather than labelling USD with
    # the client's display currency
    invoice = Invoice(
        tenant_id=project.tenant_id or tenant_id, project_id=project.id, client_id=project.client_id,
        billing_period_start=period_start, billing_period_end=period_end, currency="USD",
    )
    db.add(invoice)
    db.flush()

    total = 0
    for ts, hours in to_bill:
        rate = allocations[ts.allocation_id].billing_rate_usd_cents
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
    """BR-0907-02: Draft->Approved is always an explicit action by Finance at Senior Manager
    level or above (is_invoice_approver) -- never automatic, never anyone else."""
    from app.models.user import Users

    if invoice.status != "DRAFT":
        raise InvalidInvoiceTransition(f"Cannot approve an invoice in status '{invoice.status}'.")
    approver = db.query(Users).filter(Users.UserID == approved_by).first() if approved_by else None
    if not is_invoice_approver(db, approver):
        raise InvoiceApproverNotAllowed(
            "Only Finance at Senior Manager level or above (Senior Manager, Director, VP, CFO) can approve invoices.")
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

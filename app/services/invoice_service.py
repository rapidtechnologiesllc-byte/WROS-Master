"""
Invoice Management Service.

Handles:
- Invoice creation from timesheets (aggregation)
- Invoice status transitions with revenue recognition
- Invoice approval workflow (Finance role)
- Line item generation from timesheet data
- Integration with opportunity for P&L attribution
"""
from datetime import datetime, date
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLineItem, INVOICE_STATUSES
from app.models.opportunity import Opportunity
from app.models.project import Project
from app.models.client import Client
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.employee import Employee
from app.services.revenue_recognition_service import recognize_revenue_from_paid_invoice


class InvoiceError(Exception):
    pass


class InvalidInvoiceTransition(Exception):
    pass


# Invoice status transitions
INVOICE_TRANSITIONS = {
    "DRAFT": {"APPROVED"},
    "APPROVED": {"SENT"},
    "SENT": {"PAID"},
    "PAID": set(),  # terminal state
}


def create_invoice(
    db: Session,
    *,
    tenant_id: Optional[int],
    project_id: str,
    client_id: str,
    opportunity_id: Optional[str],
    business_unit_id: Optional[int],
    billing_period_start: date,
    billing_period_end: date,
    currency: str = "USD",
) -> Invoice:
    """
    Create a new invoice in DRAFT status.

    Args:
        db: Database session
        project_id: Project this invoice bills for
        client_id: Client being billed
        opportunity_id: Opportunity that originated this work (optional)
        business_unit_id: BU for P&L tracking
        billing_period_start: Start of billing period
        billing_period_end: End of billing period
        currency: Billing currency

    Returns:
        Invoice object (not yet committed)
    """
    invoice = Invoice(
        tenant_id=tenant_id,
        project_id=project_id,
        client_id=client_id,
        opportunity_id=opportunity_id,
        business_unit_id=business_unit_id,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        currency=currency,
        status="DRAFT",
    )
    db.add(invoice)
    return invoice


def add_line_item(
    db: Session,
    invoice: Invoice,
    *,
    employee_id: str,
    timesheet_id: str,
    hours: float,
    rate_usd_cents: int,
) -> InvoiceLineItem:
    """
    Add a line item to an invoice (from timesheet entry).

    Args:
        db: Database session
        invoice: Invoice to add to
        employee_id: Employee who worked
        timesheet_id: Timesheet this came from
        hours: Number of hours billed
        rate_usd_cents: Billing rate in USD cents

    Returns:
        InvoiceLineItem object
    """
    amount_usd_cents = int(rate_usd_cents * hours)

    line_item = InvoiceLineItem(
        invoice_id=invoice.id,
        employee_id=employee_id,
        timesheet_id=timesheet_id,
        hours=hours,
        rate_usd_cents=rate_usd_cents,
        amount_usd_cents=amount_usd_cents,
    )
    db.add(line_item)

    # Update invoice total
    invoice.total_usd_cents += amount_usd_cents

    return line_item


def transition_invoice_status(
    db: Session,
    invoice: Invoice,
    new_status: str,
    *,
    approved_by: Optional[str] = None,
) -> Invoice:
    """
    Transition invoice through its status lifecycle.

    Transitions:
    - DRAFT → APPROVED (Finance approval)
    - APPROVED → SENT (Finance marks as sent to client)
    - SENT → PAID (Finance marks as paid)

    When transitioning to PAID, revenue is recognized.

    Args:
        db: Database session
        invoice: Invoice to transition
        new_status: Target status
        approved_by: User ID who approved (required for APPROVED transition)

    Returns:
        Updated invoice

    Raises:
        InvalidInvoiceTransition: If transition not allowed
    """
    allowed_transitions = INVOICE_TRANSITIONS.get(invoice.status, set())
    if new_status not in allowed_transitions:
        raise InvalidInvoiceTransition(
            f"Cannot transition invoice {invoice.id} from '{invoice.status}' to '{new_status}'. "
            f"Allowed transitions: {sorted(allowed_transitions) or 'none (terminal state)'}"
        )

    invoice.status = new_status

    # Record approval metadata
    if new_status == "APPROVED":
        if not approved_by:
            raise InvoiceError("approved_by required when transitioning to APPROVED status")
        invoice.approved_by = approved_by
        invoice.approved_at = datetime.utcnow()

    elif new_status == "SENT":
        invoice.sent_at = datetime.utcnow()

    elif new_status == "PAID":
        invoice.paid_at = datetime.utcnow()
        # Trigger revenue recognition when invoice is marked PAID
        recognize_revenue_from_paid_invoice(db, invoice)

    db.add(invoice)
    return invoice


def get_invoices_by_project(db: Session, project_id: str) -> List[Invoice]:
    """Get all invoices for a project."""
    return db.query(Invoice).filter(Invoice.project_id == project_id).all()


def get_invoices_by_client(db: Session, client_id: str, status: Optional[str] = None) -> List[Invoice]:
    """Get invoices for a client, optionally filtered by status."""
    query = db.query(Invoice).filter(Invoice.client_id == client_id)
    if status:
        query = query.filter(Invoice.status == status)
    return query.all()


def get_invoices_by_opportunity(db: Session, opportunity_id: str) -> List[Invoice]:
    """Get all invoices traced to an opportunity."""
    return db.query(Invoice).filter(Invoice.opportunity_id == opportunity_id).all()


def get_invoice_totals_by_status(db: Session, business_unit_id: int) -> Dict[str, int]:
    """
    Get total invoice amounts by status for P&L reporting.

    Returns:
        {
            'DRAFT': total_usd_cents,
            'APPROVED': total_usd_cents,
            'SENT': total_usd_cents,
            'PAID': total_usd_cents,
        }
    """
    invoices = db.query(Invoice).filter(Invoice.business_unit_id == business_unit_id).all()

    totals = {}
    for status in INVOICE_STATUSES:
        totals[status] = sum(
            inv.total_usd_cents for inv in invoices if inv.status == status
        )

    return totals


def get_outstanding_invoices(db: Session, business_unit_id: int) -> int:
    """Get total value of invoices not yet paid (SENT status)."""
    invoices = db.query(Invoice).filter(
        Invoice.business_unit_id == business_unit_id,
        Invoice.status == "SENT"
    ).all()

    return sum(inv.total_usd_cents for inv in invoices)


def get_revenue_by_client_and_service(db: Session, business_unit_id: int) -> Dict[str, Dict[str, int]]:
    """
    Get revenue breakdown by client and service.

    Returns:
        {
            'client_name': {
                'service_name': total_usd_cents,
                ...
            },
            ...
        }
    """
    # Get paid invoices (these have recognized revenue)
    invoices = db.query(Invoice).filter(
        Invoice.business_unit_id == business_unit_id,
        Invoice.status == "PAID"
    ).all()

    breakdown = {}
    for invoice in invoices:
        client = db.query(Client).filter(Client.id == invoice.client_id).first()
        if not client:
            continue

        client_name = client.name or "Unknown"
        if client_name not in breakdown:
            breakdown[client_name] = {}

        # Get service from opportunity if available
        service = "Unknown"
        if invoice.opportunity_id:
            opp = db.query(Opportunity).filter(Opportunity.id == invoice.opportunity_id).first()
            if opp and opp.service:
                service = opp.service

        breakdown[client_name][service] = breakdown[client_name].get(service, 0) + invoice.total_usd_cents

    return breakdown

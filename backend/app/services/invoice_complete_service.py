"""
HRMS-0315 -- Invoice Generation & Management (Phase 3)
Complete invoice lifecycle: generation from timesheets → approval → sending → payment tracking.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.invoice import Invoice, InvoiceStatus
from app.models.timesheet import Timesheet
from app.models.allocation import EmployeeAllocation
from app.models.client import Client
import logging
from app.models.project import Project

logger = logging.getLogger(__name__)

class InvoiceCompleteService:
    """Manages complete invoice lifecycle from generation to payment."""

    def generate_invoice_from_timesheets(
        self,
        db: Session,
        client_id: str,
        project_id: str,
        tenant_id: int,
        period_start: datetime,
        period_end: datetime,
        bill_rate_usd_cents: int
    ) -> dict:
        """Generate invoice from approved timesheets."""
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.tenant_id == tenant_id
        ).first()

        if not client:
            return {"status": "error", "message": "Client not found"}

        # Get all approved timesheets in period
        timesheets = db.query(Timesheet).filter(
            Timesheet.tenant_id == tenant_id,
            Timesheet.approved_at >= period_start,
            Timesheet.approved_at <= period_end,
            Timesheet.status == "APPROVED"
        ).all()

        if not timesheets:
            return {"status": "error", "message": "No approved timesheets found for period"}

        # Calculate total hours and amount
        total_hours = sum(ts.total_hours for ts in timesheets)
        total_amount_usd_cents = int(total_hours * bill_rate_usd_cents)

        # Create invoice
        invoice = Invoice(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            client_id=client_id,
            project_id=project_id,
            invoice_number=self._generate_invoice_number(db, tenant_id),
            status=InvoiceStatus.DRAFT,
            period_start=period_start,
            period_end=period_end,
            total_hours=total_hours,
            bill_rate_usd_cents=bill_rate_usd_cents,
            subtotal_usd_cents=total_amount_usd_cents,
            tax_usd_cents=int(total_amount_usd_cents * Decimal("0.1")),  # 10% tax
            total_usd_cents=total_amount_usd_cents + int(total_amount_usd_cents * Decimal("0.1")),
            created_at=datetime.utcnow()
        )

        # Link timesheets to invoice
        for ts in timesheets:
            ts.invoice_id = invoice.id

        db.add(invoice)
        db.commit()

        return {
            "status": "success",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "client_id": client_id,
            "total_hours": float(total_hours),
            "bill_rate": bill_rate_usd_cents,
            "total_amount": invoice.total_usd_cents,
            "timesheets_included": len(timesheets)
        }

    def send_invoice_to_client(
        self,
        db: Session,
        invoice_id: str,
        tenant_id: int,
        client_email: str,
        payment_terms_days: int = 30
    ) -> dict:
        """Send invoice to client."""
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id
        ).first()

        if not invoice:
            return {"status": "error", "message": "Invoice not found"}

        if invoice.status != InvoiceStatus.APPROVED:
            return {"status": "error", "message": "Only approved invoices can be sent"}

        # Calculate due date
        due_date = datetime.utcnow() + timedelta(days=payment_terms_days)

        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.utcnow()
        invoice.sent_to_email = client_email
        invoice.due_date = due_date

        db.commit()

        return {
            "status": "success",
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "sent_to": client_email,
            "sent_at": invoice.sent_at.isoformat(),
            "due_date": due_date.isoformat(),
            "amount_due": invoice.total_usd_cents
        }

    def record_payment(
        self,
        db: Session,
        invoice_id: str,
        tenant_id: int,
        amount_received_usd_cents: int,
        payment_date: datetime,
        payment_method: str,
        reference_number: str = None
    ) -> dict:
        """Record payment received for invoice."""
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id
        ).first()

        if not invoice:
            return {"status": "error", "message": "Invoice not found"}

        if invoice.status not in [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]:
            return {"status": "error", "message": "Invoice cannot receive payment in current status"}

        # Update payment info
        invoice.amount_paid_usd_cents = (invoice.amount_paid_usd_cents or 0) + amount_received_usd_cents
        invoice.last_payment_date = payment_date
        invoice.payment_method = payment_method
        invoice.payment_reference = reference_number

        # Determine status
        if invoice.amount_paid_usd_cents >= invoice.total_usd_cents:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = payment_date
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        db.commit()

        remaining = invoice.total_usd_cents - invoice.amount_paid_usd_cents

        return {
            "status": "success",
            "invoice_id": invoice_id,
            "amount_received": amount_received_usd_cents,
            "total_received": invoice.amount_paid_usd_cents,
            "amount_remaining": max(0, remaining),
            "invoice_status": invoice.status,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None
        }

    def approve_invoice(
        self,
        db: Session,
        invoice_id: str,
        tenant_id: int,
        approved_by: str
    ) -> dict:
        """Approve invoice before sending to client."""
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id
        ).first()

        if not invoice:
            return {"status": "error", "message": "Invoice not found"}

        if invoice.status != InvoiceStatus.DRAFT:
            return {"status": "error", "message": "Only draft invoices can be approved"}

        invoice.status = InvoiceStatus.APPROVED
        invoice.approved_at = datetime.utcnow()
        invoice.approved_by = approved_by

        db.commit()

        return {
            "status": "success",
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "approved_at": invoice.approved_at.isoformat(),
            "approved_by": approved_by,
            "ready_to_send": True
        }

    def get_invoice_summary(
        self,
        db: Session,
        invoice_id: str,
        tenant_id: int
    ) -> dict:
        """Get complete invoice details."""
        invoice = db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id
        ).first()

        if not invoice:
            return None

        return {
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "client_id": invoice.client_id,
            "project_id": invoice.project_id,
            "status": invoice.status,
            "period": f"{invoice.period_start.date()} to {invoice.period_end.date()}",
            "total_hours": float(invoice.total_hours),
            "bill_rate": invoice.bill_rate_usd_cents,
            "subtotal": invoice.subtotal_usd_cents,
            "tax": invoice.tax_usd_cents,
            "total": invoice.total_usd_cents,
            "amount_paid": invoice.amount_paid_usd_cents or 0,
            "amount_due": max(0, invoice.total_usd_cents - (invoice.amount_paid_usd_cents or 0)),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None
        }

    def _generate_invoice_number(self, db: Session, tenant_id: int) -> str:
        """Generate unique invoice number."""
        count = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).count()
        return f"INV-{datetime.now().year}-{count + 1:05d}"

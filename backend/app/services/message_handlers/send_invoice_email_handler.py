"""Message Handler: send_invoice_email

Emails an APPROVED invoice to the client's ACCOUNTS contact from
FINANCE_MAILBOX, then marks the invoice SENT. Queued by
invoice_service.request_invoice_email.

Anything that stops the email going out (no Graph credentials or
permission) raises DeliveryDeferred, so the message stays PENDING as "not
sent" and the invoice stays APPROVED. Draft-then-send makes retries safe:
the draft id is committed before sending and checked with is_draft before
any resend, so a crash between the two never emails the client twice.

Compensation: nothing is rolled back on failure. An unsent draft stays in
the mailbox's Drafts folder and the next attempt sends that same draft.
"""
import html
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.invoice_delivery import InvoiceDelivery
from app.models.location import Location
from app.models.tenant import Tenant
from app.services.invoice_service import mark_invoice_sent
from app.services.message_handlers.base_message_handler import time_bound
from app.services.thunder_mail.graph_mailbox import GraphMailbox

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45


def _money(cents: int, currency: str) -> str:
    return f"{currency} {cents / 100:,.2f}"


def _issuer(db: Session, invoice: Invoice) -> str:
    """Our billing entity, stored on the invoice at generation (the client's contracting company);
    no company means the tenant itself issues it."""
    if invoice.issuing_company_id:
        company = db.query(Location).filter(Location.id == invoice.issuing_company_id).first()
        if company is None:
            raise ValueError(f"Invoice {invoice.id}'s issuing company {invoice.issuing_company_id} does not exist")
        return company.name
    tenant = db.query(Tenant).filter(Tenant.id == invoice.tenant_id).first()
    if tenant is None:
        raise ValueError(f"Invoice {invoice.id} has no issuing company (no contracting company or tenant)")
    return tenant.name


def render_invoice_email(db: Session, invoice: Invoice) -> Dict[str, str]:
    client = db.query(Client).filter(Client.id == invoice.client_id).first()
    if client is None:
        raise ValueError(f"Invoice {invoice.id} has no client")
    if not invoice.invoice_number:
        raise ValueError(f"Invoice {invoice.id} has no invoice number")
    issuer = _issuer(db, invoice)
    items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    names = {e.id: f"{e.first_name} {e.last_name or ''}".strip()
             for e in db.query(Employee).filter(Employee.id.in_({i.employee_id for i in items})).all()}
    currency = invoice.currency or "USD"
    period = f"{invoice.billing_period_start:%d %b %Y} – {invoice.billing_period_end:%d %b %Y}"
    # rendered right before sending: the due date is the one mark_invoice_sent stores (today + terms)
    due = invoice.due_date or (datetime.utcnow().date() + timedelta(days=client.payment_terms_days or 0))
    number = invoice.invoice_number
    with_po = any(i.po_number for i in items)

    rows = "".join(
        f"<tr><td>{html.escape(names.get(i.employee_id, i.employee_id))}</td>"
        + (f"<td>{html.escape(i.po_number or '')}</td>" if with_po else "")
        + f"<td style='text-align:right'>{float(i.hours):,.2f}</td>"
        f"<td style='text-align:right'>{_money(i.rate_usd_cents, currency)}</td>"
        f"<td style='text-align:right'>{_money(i.amount_usd_cents, currency)}</td></tr>"
        for i in items
    )
    bill_to = html.escape(client.company_name)
    if client.billing_address:
        bill_to += "<br>" + html.escape(client.billing_address).replace("\n", "<br>")
    po_line = f"<p><b>PO number</b>: {html.escape(invoice.po_numbers)}</p>" if invoice.po_numbers else ""
    body = (
        f"<p>Hello,</p><p>Please find invoice <b>{html.escape(number)}</b> from {html.escape(issuer)} for services "
        f"in the period {period}.</p>"
        f"<p><b>Bill to</b><br>{bill_to}</p>{po_line}"
        "<table cellpadding='6' style='border-collapse:collapse;border:1px solid #ccc'>"
        "<tr><th align='left'>Consultant</th>" + ("<th align='left'>PO</th>" if with_po else "")
        + "<th>Hours</th><th>Rate</th><th>Amount</th></tr>"
        f"{rows}<tr><td colspan='{4 if with_po else 3}' align='right'><b>Total</b></td>"
        f"<td style='text-align:right'><b>{_money(invoice.total_usd_cents, currency)}</b></td></tr></table>"
        f"<p>Payment terms: {client.payment_terms_days} days. Due date: {due:%d %b %Y}.</p>"
        "<p>Reply to this email with any questions about this invoice.</p>"
        f"<p>Regards,<br>Accounts, {html.escape(issuer)}</p>"
    )
    subject = f"Invoice {number} from {issuer} – {period}" + (f" – PO {invoice.po_numbers}" if invoice.po_numbers else "")
    return {"subject": subject, "html": body}


class SendInvoiceEmailHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, mailbox: Optional[GraphMailbox] = None) -> Dict[str, Any]:
        invoice_id = (message.payload or {}).get("invoice_id")
        if not invoice_id:
            raise ValueError(f"Message {message.id} missing invoice_id")
        logger.info(f"[InvoiceEmail] handler_start invoice={invoice_id} message={message.id}")

        # validation 1-2: the invoice and its delivery exist
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).with_for_update().first()
        delivery = db.query(InvoiceDelivery).filter(InvoiceDelivery.invoice_id == invoice_id).first()
        if invoice is None or delivery is None:
            raise ValueError(f"No invoice/delivery for {invoice_id}")

        # validation 3: still ours to send (an external delivery or an earlier run may have done it)
        if delivery.status == "SENT" or invoice.status in ("SENT", "PAID"):
            logger.info(f"[InvoiceEmail] already delivered invoice={invoice_id} via {delivery.channel}")
            return {"status": "already_sent", "invoice_id": invoice_id}
        if invoice.status != "APPROVED":
            raise ValueError(f"Invoice {invoice_id} is {invoice.status}; only APPROVED invoices are emailed")

        # validation 4: content renders from real data
        content = render_invoice_email(db, invoice)
        mailbox = mailbox or GraphMailbox(delivery.mailbox or settings.FINANCE_MAILBOX)
        if delivery.graph_message_id is None:
            graph_id, _, _ = mailbox.create_draft(delivery.to_address, content["subject"], content["html"],
                                                  f"invoice:{invoice_id}")
            delivery.graph_message_id, delivery.status = graph_id, "DRAFTED"
            db.commit()
            logger.info(f"[InvoiceEmail] drafted invoice={invoice_id} graph_id={graph_id}")
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).with_for_update().one()
            if invoice.status != "APPROVED":  # delivered another way while we drafted: don't send
                logger.info(f"[InvoiceEmail] superseded invoice={invoice_id} now {invoice.status}")
                return {"status": "superseded", "invoice_id": invoice_id}

        if mailbox.is_draft(delivery.graph_message_id):
            mailbox.send(delivery.graph_message_id)

        now = datetime.utcnow()
        mark_invoice_sent(db, invoice, sent_at=now)
        delivery.status, delivery.sent_at = "SENT", now
        db.commit()
        logger.info(f"[InvoiceEmail] handler_complete invoice={invoice_id} to={delivery.to_address}")
        return {"status": "sent", "invoice_id": invoice_id, "to": delivery.to_address,
                "message_sent": True, "delivery_confirmed": True}

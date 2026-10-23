"""Invoice compliance (CEO 2026-10-23): who issues an invoice, its sequential number, its due date.

issuing_company_id(db, client)   the client's contracting company (BX-US / BX-IN); None = the tenant
                                 itself issues (the same rule the invoice email has always used)
assign_number(db, invoice)       stores the issuer and the next number of that issuer's series.
                                 The series row is locked (SELECT ... FOR UPDATE) inside the caller's
                                 transaction: two generations for the same company queue on it, and
                                 a rolled-back generation rolls its number back, so the series is
                                 sequential and gapless per issuing company.
due_date_for(db, invoice, sent)  sent date + the client's payment terms
backfill(db)                     one-time: numbers every existing invoice in creation order, stores
                                 its issuer, and the due date of everything already sent
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceNumberSequence
from app.models.location import Location

logger = logging.getLogger(__name__)


def issuing_company_id(db: Session, client: Client) -> Optional[str]:
    if not client.contracting_company_id:
        return None
    company = db.query(Location.id).filter(Location.id == client.contracting_company_id).first()
    if company is None:
        raise ValueError(f"Client {client.id}'s contracting company {client.contracting_company_id} does not exist; "
                         "fix the client's contracting company before invoicing.")
    return company[0]


def _issuer_key(tenant_id: Optional[int], company_id: Optional[str]) -> str:
    return company_id or f"tenant:{tenant_id}"


def _issuer_code(db: Session, tenant_id: Optional[int], company_id: Optional[str]) -> str:
    if company_id:
        company = db.get(Location, company_id)
        return company.company_code or company.id.split("-")[0].upper()
    return f"T{tenant_id}"


def next_number(db: Session, tenant_id: Optional[int], company_id: Optional[str]) -> int:
    """The next number of this issuer's series, taken under the series row lock (held until the
    caller commits or rolls back)."""
    key = _issuer_key(tenant_id, company_id)
    db.execute(text(
        "INSERT INTO app_schema.invoice_number_sequences (issuer_key, tenant_id, company_id, last_number) "
        "VALUES (:key, :tenant, :company, 0) ON CONFLICT (issuer_key) DO NOTHING"),
        {"key": key, "tenant": tenant_id, "company": company_id})
    row = db.query(InvoiceNumberSequence).filter(InvoiceNumberSequence.issuer_key == key).with_for_update().one()
    row.last_number += 1
    db.flush()
    return row.last_number


def format_number(db: Session, tenant_id: Optional[int], company_id: Optional[str], seq: int) -> str:
    return (f"{settings.INVOICE_NUMBER_PREFIX}-{_issuer_code(db, tenant_id, company_id)}-"
            f"{seq:0{settings.INVOICE_NUMBER_DIGITS}d}")


def assign_number(db: Session, invoice: Invoice, client: Client) -> Invoice:
    if invoice.invoice_number:
        return invoice
    invoice.issuing_company_id = issuing_company_id(db, client)
    invoice.invoice_seq = next_number(db, invoice.tenant_id, invoice.issuing_company_id)
    invoice.invoice_number = format_number(db, invoice.tenant_id, invoice.issuing_company_id, invoice.invoice_seq)
    db.add(invoice)
    return invoice


def due_date_for(db: Session, invoice: Invoice, sent_at: datetime) -> date:
    client = db.get(Client, invoice.client_id)
    if client is None:
        raise ValueError(f"Invoice {invoice.id} has no client")
    return sent_at.date() + timedelta(days=int(client.payment_terms_days or 0))


def backfill(db: Session) -> int:
    """Existing invoices, oldest first: issuer, number, and the due date of those already sent.
    Returns the number of invoices numbered."""
    numbered = 0
    rows = db.query(Invoice).order_by(Invoice.created_at.asc(), Invoice.id.asc()).all()
    clients = {c.id: c for c in db.query(Client).filter(Client.id.in_({i.client_id for i in rows}))} if rows else {}
    for invoice in rows:
        client = clients.get(invoice.client_id)
        if client is None:
            raise ValueError(f"Invoice {invoice.id} has no client {invoice.client_id}")
        if not invoice.invoice_number:
            assign_number(db, invoice, client)
            numbered += 1
        if invoice.due_date is None and invoice.sent_at is not None:
            invoice.due_date = due_date_for(db, invoice, invoice.sent_at)
    db.flush()
    logger.info(f"[InvoiceNumbering] backfilled {numbered} invoice number(s)")
    return numbered

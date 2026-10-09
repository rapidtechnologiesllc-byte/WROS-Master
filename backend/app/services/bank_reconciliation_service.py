"""EPIC-16 -- Bank Reconciliation. See app.models.bank_reconciliation
for why this is manual-entry, not a real bank feed.

A payment is a bank transaction matched to an invoice. Matching a SENT
invoice also marks it PAID on the transaction date, which recognises its
revenue, so cash, the invoice and the P&L never disagree."""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.bank_reconciliation import BankTransaction
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

class BankReconciliationError(Exception):
    pass

def record_bank_transaction(
    db: Session, *, transaction_date, amount_usd_cents: int, description: str,
    created_by: str, tenant_id: Optional[int] = None,
) -> BankTransaction:
    if amount_usd_cents == 0:
        raise BankReconciliationError("amount_usd_cents must not be zero.")
    transaction = BankTransaction(
        tenant_id=tenant_id, transaction_date=transaction_date, amount_usd_cents=amount_usd_cents,
        description=description, created_by=created_by,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

def match_transaction_to_invoice(db: Session, transaction: BankTransaction, invoice: Invoice) -> BankTransaction:
    """Real validation, not a blind link: the transaction amount must
    equal the invoice total, or this isn't a real match -- a partial
    payment or a wrong-invoice guess should never silently reconcile.
    A SENT invoice becomes PAID on the transaction date (revenue recognised)."""
    from app.services.invoice_service import mark_invoice_paid

    if transaction.reconciled:
        raise BankReconciliationError(f"Transaction {transaction.id} is already matched to {transaction.matched_invoice_id}.")
    if transaction.tenant_id != invoice.tenant_id:
        raise BankReconciliationError("Transaction and invoice belong to different tenants.")
    if transaction.amount_usd_cents != invoice.total_usd_cents:
        raise BankReconciliationError(
            f"Transaction amount ({transaction.amount_usd_cents}) does not match "
            f"invoice total ({invoice.total_usd_cents}) -- not a real match."
        )
    if invoice.status not in ("SENT", "PAID"):
        raise BankReconciliationError(f"Invoice {invoice.id} is {invoice.status}; only a sent invoice can be paid.")
    transaction.matched_invoice_id = invoice.id
    transaction.reconciled = True
    db.add(transaction)
    if invoice.status == "SENT":
        mark_invoice_paid(db, invoice, paid_at=datetime.combine(transaction.transaction_date, datetime.min.time()))
    db.commit()
    db.refresh(transaction)
    return transaction


def record_invoice_payment(db: Session, invoice: Invoice, *, paid_on, amount_usd_cents: int,
                           reference: str, recorded_by: str) -> BankTransaction:
    """One step for Finance: the money arrived for this invoice."""
    if not (reference or "").strip():
        raise BankReconciliationError("Give the payment reference (bank/UTR/cheque number).")
    if amount_usd_cents != invoice.total_usd_cents:
        raise BankReconciliationError(
            f"Payment of {amount_usd_cents} doesn't equal the invoice total {invoice.total_usd_cents}; "
            "partial payments aren't supported yet, so record it once the full amount has arrived."
        )
    transaction = BankTransaction(
        tenant_id=invoice.tenant_id, transaction_date=paid_on, amount_usd_cents=amount_usd_cents,
        description=f"Payment for invoice {invoice.id}: {reference.strip()}", created_by=recorded_by,
    )
    db.add(transaction)
    db.flush()
    return match_transaction_to_invoice(db, transaction, invoice)


def get_unreconciled_transactions(db: Session, *, tenant_id: Optional[int] = None) -> List[BankTransaction]:
    query = db.query(BankTransaction).filter(BankTransaction.reconciled.is_(False))
    if tenant_id is not None:
        query = query.filter(BankTransaction.tenant_id == tenant_id)
    return query.order_by(BankTransaction.transaction_date.desc()).all()

def get_unmatched_paid_invoices(db: Session, *, tenant_id: Optional[int] = None) -> List[Invoice]:
    """PAID invoices with no reconciled bank transaction pointing at
    them -- the other direction of the reconciliation gap (money the
    system thinks arrived but no real bank transaction confirms it)."""
    matched_invoice_ids = {
        row[0] for row in db.query(BankTransaction.matched_invoice_id).filter(
            BankTransaction.matched_invoice_id.isnot(None),
        ).all()
    }
    query = db.query(Invoice).filter(Invoice.status == "PAID")
    if tenant_id is not None:
        query = query.filter(Invoice.tenant_id == tenant_id)
    return [inv for inv in query.all() if inv.id not in matched_invoice_ids]

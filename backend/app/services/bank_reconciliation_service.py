from app.core.logging import logger
"""EPIC-16 -- Bank Reconciliation. See app.models.bank_reconciliation
for why this is manual-entry, not a real bank feed."""
import logging
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
    payment or a wrong-invoice guess should never silently reconcile."""
    if transaction.amount_usd_cents != invoice.total_usd_cents:
        raise BankReconciliationError(
            f"Transaction amount ({transaction.amount_usd_cents}) does not match "
            f"invoice total ({invoice.total_usd_cents}) -- not a real match."
        )
    transaction.matched_invoice_id = invoice.id
    transaction.reconciled = True
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


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

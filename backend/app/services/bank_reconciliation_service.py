"""EPIC-16 -- Bank Reconciliation. See app.models.bank_reconciliation
for why this is manual-entry, not a real bank feed.

A payment is a bank transaction matched to an invoice. Matching a SENT
invoice also marks it PAID on the transaction date, which recognises its
revenue, so cash, the invoice and the P&L never disagree."""
import csv
import io
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

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
    already = db.query(BankTransaction.id).filter(BankTransaction.matched_invoice_id == invoice.id,
                                                  BankTransaction.reconciled.is_(True)).first()
    if already is not None:
        raise BankReconciliationError(f"Invoice {invoice.id} is already paid (transaction {already[0]}); "
                                      "a second payment would overstate cash.")
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


# ---- Statement import and suggested matches (Finance confirms every match; nothing is paid by itself) ----

STATEMENT_MAX_ROWS = 2000
DATE_COLUMNS = ("date", "transaction date", "value date", "posting date", "posted date")
AMOUNT_COLUMNS = ("amount", "credit", "deposit", "credit amount", "deposits")
DESCRIPTION_COLUMNS = ("description", "narration", "particulars", "details", "memo", "reference")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y")
AMOUNT_PATTERN = re.compile(r"\d+(\.\d{1,2})?")
AMOUNT_NOISE = re.compile(r"[,$()\s-]")


def _column(headers: List[str], names: Tuple[str, ...]) -> Optional[str]:
    by_name = {(h or "").strip().lower(): h for h in headers}
    return next((by_name[name] for name in names if name in by_name), None)


def _statement_date(value: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise BankReconciliationError(f"date '{value}' is not YYYY-MM-DD, MM/DD/YYYY or DD-Mon-YYYY")


def _statement_cents(value: str) -> int:
    text = (value or "").strip()
    negative = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
    digits = AMOUNT_NOISE.sub("", text)
    if not AMOUNT_PATTERN.fullmatch(digits):
        raise BankReconciliationError(f"amount '{value}' is not a number")
    whole, _, cents = digits.partition(".")
    amount = int(whole) * 100 + int((cents + "00")[:2])
    return -amount if negative else amount


def parse_statement(content: bytes) -> Tuple[List[Dict], List[Dict], int]:
    """A bank statement saved as CSV -> (credits, rows that could not be read, debits left out).
    Raises BankReconciliationError when the file itself cannot be used."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BankReconciliationError(f"The file is not UTF-8 text (save it as CSV UTF-8): {exc}") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    date_col, amount_col = _column(headers, DATE_COLUMNS), _column(headers, AMOUNT_COLUMNS)
    description_col = _column(headers, DESCRIPTION_COLUMNS)
    if not (date_col and amount_col and description_col):
        raise BankReconciliationError(
            "The first line must name a date column (Date), an amount column (Amount or Credit) and a "
            f"description column (Description or Narration); found: {', '.join(h for h in headers if h) or 'nothing'}.")
    lines = [(reader.line_num, line) for line in reader]  # the file's own line numbers: blank lines are skipped
    if len(lines) > STATEMENT_MAX_ROWS:
        raise BankReconciliationError(f"{len(lines)} rows: the limit is {STATEMENT_MAX_ROWS} per file.")
    credits, unread, debits = [], [], 0
    for number, line in lines:
        raw_amount = (line.get(amount_col) or "").strip()
        raw_date = (line.get(date_col) or "").strip()
        if not raw_amount and not raw_date:
            continue  # a blank line
        if not raw_amount:
            debits += 1  # a debit row of a statement with separate debit and credit columns
            continue
        try:
            cents = _statement_cents(raw_amount)
            if cents <= 0:
                debits += 1
                continue
            description = (line.get(description_col) or "").strip()
            if not description:
                raise BankReconciliationError("no description")
            credits.append({"line": number, "transaction_date": _statement_date(raw_date),
                            "amount_usd_cents": cents, "description": description})
        except BankReconciliationError as exc:
            unread.append({"line": number, "reason": str(exc)})
    return credits, unread, debits


def import_statement(db: Session, content: bytes, *, created_by: str, tenant_id: Optional[int]) -> Dict:
    """Record every credit on a statement once: a credit already recorded (same date, amount and
    description) is counted as a duplicate, so the same file can be uploaded again safely."""
    credits, unread, debits = parse_statement(content)
    existing = {(t.transaction_date, t.amount_usd_cents, t.description.strip().lower())
                for t in db.query(BankTransaction).filter(BankTransaction.tenant_id == tenant_id).all()}
    recorded = duplicates = 0
    for row in credits:
        key = (row["transaction_date"], row["amount_usd_cents"], row["description"].lower())
        if key in existing:
            duplicates += 1
            continue
        existing.add(key)
        db.add(BankTransaction(tenant_id=tenant_id, transaction_date=row["transaction_date"],
                               amount_usd_cents=row["amount_usd_cents"], description=row["description"],
                               created_by=created_by))
        recorded += 1
    db.commit()
    logger.info(f"[BankReconciliation] statement import by {created_by}: {recorded} recorded, {duplicates} duplicate(s), "
                f"{len(unread)} unreadable, {debits} debit(s) left out")
    return {"recorded": recorded, "duplicates": duplicates, "debits_left_out": debits, "unread": unread}


def _awaiting_payment(db: Session, tenant_id: Optional[int]) -> List[Invoice]:
    """SENT invoices no reconciled bank transaction has paid."""
    paid_ids = {row[0] for row in db.query(BankTransaction.matched_invoice_id).filter(
        BankTransaction.matched_invoice_id.isnot(None), BankTransaction.reconciled.is_(True)).all()}
    query = db.query(Invoice).filter(Invoice.status == "SENT")
    if tenant_id is not None:
        query = query.filter(Invoice.tenant_id == tenant_id)
    return [invoice for invoice in query.all() if invoice.id not in paid_ids]


def suggested_invoice(transaction: BankTransaction, candidates: List[Invoice]) -> Optional[Invoice]:
    """The invoice this credit most likely pays: the only one for that exact amount, or among several the
    only one whose invoice number is in the bank's description. None when it is not clear."""
    if len(candidates) == 1:
        return candidates[0]
    description = (transaction.description or "").lower()
    named = [i for i in candidates if i.invoice_number and i.invoice_number.lower() in description]
    return named[0] if len(named) == 1 else None


def reconciliation_view(db: Session, *, tenant_id: Optional[int]) -> Dict:
    """What Finance has to settle: each unmatched credit with the sent invoices for exactly that amount and
    the one suggested; and paid invoices no bank transaction confirms."""
    from app.models.client import Client

    awaiting = _awaiting_payment(db, tenant_id)
    unmatched_paid = get_unmatched_paid_invoices(db, tenant_id=tenant_id)
    client_ids = {i.client_id for i in awaiting} | {i.client_id for i in unmatched_paid}
    names = dict(db.query(Client.id, Client.company_name).filter(Client.id.in_(client_ids)).all()) if client_ids else {}

    def invoice_row(invoice: Invoice) -> Dict:
        return {"invoice_id": invoice.id, "invoice_number": invoice.invoice_number, "client_id": invoice.client_id,
                "client_name": names.get(invoice.client_id), "total_usd_cents": invoice.total_usd_cents,
                "due_date": invoice.due_date, "sent_at": invoice.sent_at, "paid_at": invoice.paid_at}

    by_amount: Dict[int, List[Invoice]] = {}
    for invoice in awaiting:
        by_amount.setdefault(invoice.total_usd_cents, []).append(invoice)
    transactions = []
    for transaction in get_unreconciled_transactions(db, tenant_id=tenant_id):
        candidates = by_amount.get(transaction.amount_usd_cents, [])
        suggestion = suggested_invoice(transaction, candidates)
        transactions.append({
            "id": transaction.id, "transaction_date": transaction.transaction_date,
            "amount_usd_cents": transaction.amount_usd_cents, "description": transaction.description,
            "candidates": [invoice_row(i) for i in candidates],
            "suggested_invoice_id": suggestion.id if suggestion is not None else None,
        })
    return {"transactions": transactions, "unmatched_paid_invoices": [invoice_row(i) for i in unmatched_paid],
            "awaiting_payment_count": len(awaiting)}

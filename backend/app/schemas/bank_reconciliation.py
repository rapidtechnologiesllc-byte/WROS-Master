from datetime import date, datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RecordBankTransactionRequest(BaseModel):
    transaction_date: date
    amount_usd_cents: int
    description: str

class MatchTransactionRequest(BaseModel):
    invoice_id: str

class BankTransactionResponse(BaseModel):
    id: int
    transaction_date: date
    amount_usd_cents: int
    description: str
    matched_invoice_id: Optional[str]
    reconciled: bool
    created_by: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class UnmatchedPaidInvoiceResponse(BaseModel):
    invoice_id: str
    client_id: str
    total_usd_cents: int

class ReconciliationInvoice(BaseModel):
    invoice_id: str
    invoice_number: Optional[str]
    client_id: str
    client_name: Optional[str]
    total_usd_cents: int
    due_date: Optional[date]
    sent_at: Optional[datetime]
    paid_at: Optional[datetime]

class ReconciliationTransaction(BaseModel):
    id: int
    transaction_date: date
    amount_usd_cents: int
    description: str
    candidates: List[ReconciliationInvoice]
    suggested_invoice_id: Optional[str]

class ReconciliationResponse(BaseModel):
    transactions: List[ReconciliationTransaction]
    unmatched_paid_invoices: List[ReconciliationInvoice]
    awaiting_payment_count: int

class UnreadStatementLine(BaseModel):
    line: int
    reason: str

class StatementImportResponse(BaseModel):
    recorded: int
    duplicates: int
    debits_left_out: int
    unread: List[UnreadStatementLine]

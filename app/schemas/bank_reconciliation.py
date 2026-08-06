from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


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

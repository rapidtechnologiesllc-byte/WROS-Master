"""
EPIC-16 -- Bank Reconciliation. No real bank feed/API integration
exists anywhere in this codebase -- manual entry, same posture as the
Expense Ledger, Reserve Fund, and Intercompany Ledger. Finance records
what actually cleared the bank; the system matches it against real
Invoice PAID records and surfaces what doesn't reconcile.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    transaction_date = Column(Date, nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)

    matched_invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=True, index=True)
    reconciled = Column(Boolean, nullable=False, default=False)

    created_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

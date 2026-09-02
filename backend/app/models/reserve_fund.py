"""
EPIC-16 -- Reserve Fund Ledger. Append-only (insert-only, same pattern
as ClientHistory/EmployeeEngineHistory) -- a ledger is never edited,
only added to. Real transactions (contributions/withdrawals), not a
single running-balance field, so the full history is always
reconstructable and auditable.
"""
import logging
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func

from app.models.base import Base

RESERVE_FUND_ENTRY_TYPES = ("CONTRIBUTION", "WITHDRAWAL")

logger = logging.getLogger(__name__)

class ReserveFundEntry(Base):
    __tablename__ = "reserve_fund_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    entry_type = Column(
        Enum(*RESERVE_FUND_ENTRY_TYPES, name="reserve_fund_entry_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    amount_usd_cents = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)

    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)

"""
EPIC-16 -- Intercompany Ledger. Real workbook has an Intercompany
Ledger tracking settlements between legal entities (BXIN/BXUS). No
field anywhere on Employee/Client identifies legal entity (same gap
already flagged for Location P&L and Hiring Affordability) -- so this
can't auto-derive settlements from delivery data. Manual-entry ledger
instead, same posture as the Expense Ledger (Avinash: "counted same
like the excel") and Reserve Fund contributions -- Finance records the
real settlement, the system tracks running balance per entity pair.
"""
import logging
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class IntercompanySettlement(Base):
    __tablename__ = "intercompany_settlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    from_entity = Column(String(512), nullable=False)  # e.g. "BXIN", "BXUS" -- free text, no fixed enum yet
    to_entity = Column(String(512), nullable=False)
    amount_usd_cents = Column(Integer, nullable=False)
    settlement_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)

    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

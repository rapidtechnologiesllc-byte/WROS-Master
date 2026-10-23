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

    # The companies (legal entities, app.models.location.Location) money moved between. Required on
    # every new entry; only entries recorded before 2026-10-23 whose free-text name matched no
    # company keep NULL (the intercompany_company_links data migration raised a Finance task).
    from_company_id = Column(String(512), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True, index=True)
    to_company_id = Column(String(512), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True, index=True)
    # Display names, copied from the companies when the entry is recorded (history keeps its label
    # if a company is renamed). Never used to match a company: the ids above do that.
    from_entity = Column(String(512), nullable=False)
    to_entity = Column(String(512), nullable=False)
    # The BU the billed work belongs to, so the receiving company's revenue
    # rolls up to that BU and its partner in the goal tree
    business_unit_id = Column(Integer, ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_usd_cents = Column(Integer, nullable=False)
    settlement_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)

    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

"""
EPIC-16 (Finance & Accounting Operations) -- Fully Loaded Cost +
Blended Delivery Rate foundation. Every other EPIC-16 engine (P&L,
Reserve Fund, Hiring Affordability) depends on knowing what an
employee actually costs and what a BU actually bills, so this is
import logging
built first.

Config-driven, not hardcoded -- statutory/overhead percentages vary by
BU and change over time (same append-only, most-recent-row-wins ledger
pattern as BURevenueTarget/PartnerGoal, real autoincrement PK for
ordering, not created_at -- see that model's own docstring for why a
wall-clock tiebreak isn't safe). The real FY26-27 workbook's own
formula shape (salary + statutory components + admin overhead
allocation) is followed; exact percentages are Avinash's to configure,
never invented here.
"""
import logging
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class CostRateConfig(Base):
    __tablename__ = "cost_rate_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    # Null = org-wide default, applied when no BU-specific row exists.
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    statutory_pct = Column(Numeric(5, 2), nullable=False)
    overhead_pct = Column(Numeric(5, 2), nullable=False)

    effective_date = Column(Date, nullable=False, server_default=func.current_date())
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)

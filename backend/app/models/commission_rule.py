"""Commission Rule Model - Define commission calculation rules for partners/deals"""
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text
from datetime import datetime
import uuid

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class CommissionRule(Base):
    """Commission calculation rule for partners and deals"""

    __tablename__ = "commission_rule"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # Rule scope
    partner_id = Column(String(100), nullable=True, index=True)  # NULL = applies to all partners
    deal_type = Column(String(100), nullable=True, index=True)  # job_placement, sales_deal, referral, etc.

    # Commission calculation
    commission_percent = Column(Float, nullable=False)  # 0-100
    minimum_amount = Column(Float, default=0)
    maximum_amount = Column(Float, nullable=True)  # NULL = no cap
    flat_amount = Column(Float, nullable=True)  # Alternative to percent-based

    # Withholding and taxes
    withholding_percent = Column(Float, default=0)  # Tax withholding
    withholding_type = Column(String(50), default="PERCENTAGE")  # PERCENTAGE or FLAT

    # Rule configuration
    is_active = Column(Boolean, default=True, nullable=False)
    effective_from = Column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to = Column(DateTime, nullable=True)

    # Metadata
    description = Column(Text(), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<CommissionRule {self.partner_id or 'global'}/{self.deal_type or 'all'} {self.commission_percent}%>"

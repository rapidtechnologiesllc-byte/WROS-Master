"""Opportunities model for sales pipeline tracking toward $100M revenue target."""

from sqlalchemy import Column, String, Integer, DateTime, Float, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.models.base import Base


class Opportunities(Base):
    """
    Sales opportunities tracked from initial prospect through closed_won.

    Used by Opportunity Tracker Agent to:
    - Monitor pipeline health toward $100M annual target
    - Alert when deals stall
    - Escalate at-risk deals to Flash
    - Calculate probability-weighted revenue forecast
    """
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)

    # Deal identification
    client_name = Column(String, nullable=False)
    partner_id = Column(String, nullable=False, index=True)  # Partner/sales person who identified it

    # Deal value (stored in USD cents)
    deal_size_usd_cents = Column(Integer, nullable=False)

    # Deal stage progression
    stage = Column(
        String,
        nullable=False,
        default="prospect",
        index=True,
        # Values: prospect, qualified, proposal, negotiation, commitment, closed_won, closed_lost
    )

    # Probability of close (auto-calculated from stage)
    probability = Column(Float, nullable=False, default=0.1)

    # Timeline
    expected_close_date = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    days_in_stage = Column(Integer, nullable=False, default=0)

    # Status tracking
    status = Column(String, nullable=False, default="open", index=True)  # open, closed_won, closed_lost

    # Activity log (JSON array of activities)
    activity_history = Column(JSON, nullable=True, default=[])

    # Notes
    notes = Column(Text, nullable=True)

    __table_args__ = (
        # Multi-column index for common queries
        # (tenant_id, status, stage, last_activity_at)
    )

    def __repr__(self):
        return f"<Opportunity {self.id} - {self.client_name} (${self.deal_size_usd_cents/100:,.0f})>"

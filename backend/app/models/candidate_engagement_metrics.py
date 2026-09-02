"""
import logging
S-070/HRMS-0470 -- Candidate Engagement Health Metrics.

candidate_engagement_metrics: genuinely new table -- one row per
candidate, UPSERTed on every recalculation. Integer-autoincrement PK +
String(50) UserID-as-tenant_id convention, matching every other new
table this round, not the spec's UUID assumption.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)

class CandidateEngagementMetrics(Base):
    __tablename__ = "candidate_engagement_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    response_rate = Column(Numeric(5, 2), nullable=False, default = False)
    avg_response_time_minutes = Column(Integer, nullable=True)
    total_messages_exchanged = Column(Integer, nullable=False, default = False)
    days_to_qualification = Column(Integer, nullable=True)
    avg_sentiment_score = Column(Numeric(3, 2), nullable=True)
    last_inbound_at = Column(DateTime(timezone=False), nullable=True)

    metrics_calculated_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_engagement_metrics"),
    )

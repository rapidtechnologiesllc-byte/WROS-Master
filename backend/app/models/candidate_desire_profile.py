"""
S-348/HRMS-P118 -- Desire Profile Builder.

candidate_desire_profiles: one row per candidate (UNIQUE candidate_id,
per BR "current state only, DesireProfileUpdateJob overwrites" -- no
history table). Same real conventions as candidate_desire_signals:
Integer autoincrement PK, String(50) UserID-as-tenant_id.

desire_ranking is the full sorted array (JSON) -- top_desire_category/
top_desire_score are denormalized copies of desire_ranking[0] for fast
reads without deserializing the array on every list view.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

ENGAGEMENT_LEVELS = ("HOT", "WARM", "COOL", "COLD")
DECISION_URGENCY_LEVELS = ("URGENT", "NORMAL", "SLOW")


class CandidateDesireProfile(Base):
    __tablename__ = "candidate_desire_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False)

    top_desire_category = Column(String(30), nullable=True)
    top_desire_score = Column(Float, nullable=True)
    desire_ranking = Column(JSON, nullable=True)  # [{category, score, signal_count, direction}, ...] desc by score

    primary_fear = Column(String(30), nullable=True)
    primary_fear_score = Column(Float, nullable=True)

    engagement_level = Column(String(10), nullable=True)  # see ENGAGEMENT_LEVELS
    has_competing_offer = Column(Boolean, nullable=False, default=False)
    decision_urgency = Column(String(10), nullable=True)  # see DECISION_URGENCY_LEVELS

    narrative_summary = Column(Text, nullable=True)
    narrative_updated_at = Column(DateTime(timezone=False), nullable=True)
    # S-350/HRMS-P120 -- HR Talking Points, list[str]. Regenerated
    # alongside narrative_summary (same LLM pass, same trigger).
    talking_points = Column(JSON, nullable=True)

    profile_updated_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_candidate_desire_profile_per_candidate"),
    )

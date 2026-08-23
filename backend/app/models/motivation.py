"""
S-349/HRMS-P119 -- Proactive Motivation Engine.

motivation_content_library: BA-approved facts/proof-points per desire
category, one row per (tenant, category) -- real structured table,
not the spec's system_configuration key/value rows (this codebase's
real system_config table uses the OTHER "tenant_id=Integer FK
tenants.id" admin-settings convention, a different, incompatible
tenant model from the candidate-engagement track's own
"tenant_id=String(50) FK users.UserID" convention every desire-*
table this round already uses -- see tenant_ai_config.py's own
docstring for the precedent this follows instead).

motivation_outcomes: one row per proactive message actually sent --
the real "did it work" ledger BR-05/Step 5's learning-feedback-loop
language describes; no ML retraining loop is built (out of scope,
same posture as S-046's "explicitly-NOT-ML" formula), the row is the
honest, queryable outcome record itself.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

TRIGGER_TYPES = ("COMPETING_OFFER", "OFFER_PENDING_RESPONSE", "COOLING_ENGAGEMENT", "DESIRE_SHIFT", "SCHEDULED_NURTURE")


class MotivationContentLibrary(Base):
    __tablename__ = "motivation_content_library"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    desire_category = Column(String(30), nullable=False)
    content_items = Column(JSON, nullable=False)  # list[str], BA-approved facts only

    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "desire_category", name="uq_motivation_content_per_tenant_category"),
    )


class MotivationOutcome(Base):
    __tablename__ = "motivation_outcomes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    trigger_type = Column(String(30), nullable=False)  # see TRIGGER_TYPES
    message_sent = Column(Text, nullable=False)
    desire_category_targeted = Column(String(30), nullable=True)

    sent_at = Column(DateTime(timezone=False), server_default=func.now())
    response_within_24h = Column(Boolean, nullable=True)  # filled by a later check
    engagement_before = Column(String(10), nullable=True)
    engagement_after = Column(String(10), nullable=True)  # filled by a later check
    offer_accepted = Column(Boolean, nullable=True)  # filled once/if the offer is later decided

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

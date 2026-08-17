"""
S-046/HRMS-0446 -- Candidate Abandonment Prediction.

candidate_abandonment_scores: genuinely new table -- one row per
(tenant, candidate), UNIQUE-constrained per the spec's own Step 1 (same
upsert-target shape as CandidateGhostingStatus). Integer-autoincrement
PK + String(50) UserID-as-tenant_id convention, matching every other
new table this round, not the spec's UUID assumption.

Real architecture adaptations (see abandonment_scoring_service module
docstring for the full formula/wiring rationale):
- No event bus -- "publish candidate.high_abandonment_risk, consumed by
  HRMS-0462 Intervention Queue" is not implementable as a formal event
  (no bus exists, and HRMS-0462 doesn't exist anywhere in this
  codebase yet either). is_flagged on this row IS the real, durable,
  queryable signal -- same posture CandidateGhostingStatus already took
  toward HRMS-0445 before that story existed. A recruiter notification
  is also fired directly (via notification_service) since there's no
  queue UI yet to otherwise surface this.
- score_components is a flat JSON breakdown of the 4 weighted
  components (response_rate/sentiment_trend/days_silent/followup_count
  points), for the auditability the spec itself calls for.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class CandidateAbandonmentScore(Base):
    __tablename__ = "candidate_abandonment_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    abandonment_score = Column(Integer, nullable=False)
    score_components = Column(JSON, nullable=True)
    is_flagged = Column(Boolean, nullable=False, server_default="0")
    calculated_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_abandonment_scores"),
    )

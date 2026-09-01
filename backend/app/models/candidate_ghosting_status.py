"""
S-043/HRMS-0443 -- Candidate Ghosting Detection.
S-045/HRMS-0445 -- Reactivation Campaign (reactivation_attempt_count/
last_reactivation_sent_at, added later).

candidate_ghosting_status: genuinely new table -- a real, one-row-per-
(tenant, candidate) ghosting record with its own UNIQUE constraint (per
the spec's own Step 1). Integer-autoincrement PK + String(50)
UserID-as-tenant_id convention, matching every other new table this
round, not the spec's UUID assumption.

S-045 note: reactivation_attempt_count is tracked for observability
only -- per Avinash's explicit override of that story's literal spec
("If no response: keep trying till I succeed -- no candidate should
ever be left"), it is NEVER used as a cutoff/cap. See
reactivation_campaign_service's own module docstring for the full
override rationale.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

DEFAULT_GHOSTING_REASON = "No response after 3 follow-up messages"


class CandidateGhostingStatus(Base):
    __tablename__ = "candidate_ghosting_status"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(256), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    ghosted_at = Column(DateTime(timezone=False), nullable=False)
    ghosting_reason = Column(String(256), nullable=False, server_default=DEFAULT_GHOSTING_REASON)
    reactivation_scheduled_at = Column(DateTime(timezone=False), nullable=True)
    is_reactivated = Column(Boolean, nullable=False, server_default="0")
    reactivated_at = Column(DateTime(timezone=False), nullable=True)

    # S-045/HRMS-0445 -- observability only, never a cutoff. See module docstring.
    reactivation_attempt_count = Column(Integer, nullable=False, server_default="0")
    last_reactivation_sent_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_ghosting_status"),
    )

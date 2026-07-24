"""
S-020/HRMS-0420 -- Engagement SLA Monitoring.

candidate_sla_breaches: a real, new, queryable-and-resolvable ledger --
distinct from the append-only ConversationEvent log (a breach needs to
be found-and-flipped-to-resolved, not just replayed) and distinct from
app.services.conversation_inactivity_service's self-healing 30-hour
reclaim/nudge system (which silently *acts* on staleness rather than
surfacing it on a recruiter dashboard). See sla_monitoring_service's
module docstring for the full scoping rationale.

Uses this codebase's real Integer-autoincrement PK + String(50)
UserID-as-tenant_id conventions (CandidateConversation, ConversationEvent,
MessageTemplate all do this), not the spec's UUID assumption.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

SLA_TYPES = ("FIRST_CONTACT", "RESPONSE_TIME", "NO_CONTACT")


class CandidateSLABreach(Base):
    __tablename__ = "candidate_sla_breaches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    sla_type = Column(String(50), nullable=False)
    breached_at = Column(DateTime(timezone=False), nullable=False)
    resolved_at = Column(DateTime(timezone=False), nullable=True)
    is_resolved = Column(Boolean, nullable=False, server_default="0")

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

"""
S-038/HRMS-0438 -- Compensation Fit Score, Step 2's budget-mismatch flag.

candidate_job_flags: genuinely new table -- a real, queryable "warning
raised against a candidate-job pairing" record, distinct from the
append-only ConversationEvent log (a flag needs to be found-and-
resolved, not just replayed -- same reasoning as candidate_sla_breaches,
S-020). Integer-autoincrement PK + String(50) UserID-as-tenant_id
convention, matching every other new table this round, not the spec's
UUID assumption.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

FLAG_TYPES = ("COMPENSATION_MISMATCH",)
FLAG_SEVERITIES = ("LOW", "MEDIUM", "HIGH")


class CandidateJobFlag(Base):
    __tablename__ = "candidate_job_flags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(50), ForeignKey("jobs.jobID", ondelete="CASCADE"), nullable=False, index=True)

    flag_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, server_default="MEDIUM")
    is_resolved = Column(Boolean, nullable=False, server_default="0")
    resolved_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")

    __table_args__ = (
        Index("ix_candidate_job_flags_lookup", "tenant_id", "candidate_id", "job_id", "flag_type", "is_resolved"),
    )

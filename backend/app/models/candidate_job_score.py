"""
S-037/HRMS-0437 -- Technical Qualification Score.

candidate_job_scores: genuinely new table -- a real, one-row-per-
candidate-per-job scoring record, not derivable from any existing
structure. Integer-autoincrement PK + String(50) UserID-as-tenant_id +
String(50) candidate_id/job_id FKs, matching every other new table this
round -- not the spec's UUID PK assumption.

compensation_score/availability_score/overall_score are real columns
per the spec's own table shape (Step 1), but S-037 only ever computes
technical_score -- left nullable for the later stories that own those
(HRMS-0440 Overall Candidate Score and friends), not computed here.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class CandidateJobScore(Base):
    __tablename__ = "candidate_job_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID", ondelete="CASCADE"), nullable=False, index=True)

    technical_score = Column(Integer, nullable=True)
    compensation_score = Column(Integer, nullable=True)   # not computed by S-037 -- see module docstring
    availability_score = Column(Integer, nullable=True)   # not computed by S-037 -- see module docstring
    overall_score = Column(Integer, nullable=True)         # not computed by S-037 -- see module docstring
    score_breakdown = Column(JSON, nullable=True)

    calculated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", "job_id", name="uq_candidate_job_score"),
    )

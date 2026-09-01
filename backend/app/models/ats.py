"""
ATS Score ORM Model
===================
Persists the ATS score produced for each candidate–job pair so that
HR users can review scores without re-running the LLM pipeline.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class ATSScore(Base):
    __tablename__ = "ats_scores"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # ---------- FK references ----------
    candidate_id = Column(String(50),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        String(50),
        ForeignKey("jobs.jobID", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---------- Dimension scores ----------
    overall_score   = Column(Integer, nullable=False, default = False)  # 0–100
    skills_score    = Column(Integer, nullable=False, default = False)  # 0–25
    experience_score = Column(Integer, nullable=False, default = False) # 0–25
    education_score  = Column(Integer, nullable=False, default = False) # 0–20
    location_score   = Column(Integer, nullable=False, default = False) # 0–15
    culture_fit_score = Column(Integer, nullable=False, default = False) # 0–15

    # ---------- Qualitative output ----------
    profile_summary  = Column(Text, nullable=True)
    strengths        = Column(Text, nullable=True)   # JSON-encoded list
    weaknesses       = Column(Text, nullable=True)   # JSON-encoded list
    recommendation   = Column(String(20), nullable=True)  # Shortlist|Review|Reject
    score_rationale  = Column(Text, nullable=True)
    ats_verdict      = Column(Text, nullable=True)

    # ---------- Meta ----------
    scored_at = Column(DateTime, server_default=func.now(), nullable=False)

    # ---------- Relationships ----------
    candidate = relationship("Candidate", foreign_keys=[candidate_id])
    job       = relationship("Jobs", foreign_keys=[job_id])

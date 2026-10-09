from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base


class InterviewRoundVerdict(Base):
    """The outcome of one interview round (panel): which level it was (screen, L1 technical,
    L2 management) and whether the candidate passed. Computed from interviewer feedback; a
    person decides only when feedback is mixed. Offer and onboarding gates read this."""
    __tablename__ = "interview_round_verdicts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_id = Column(Integer, ForeignKey("interview_panels.id", ondelete="CASCADE"), nullable=False, unique=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True, index=True)
    level = Column(String(10), nullable=False, default="OTHER")      # SCREEN / L1 / L2 / OTHER
    verdict = Column(String(16), nullable=False, default="PENDING")  # PENDING / PASS / FAIL / NEEDS_DECISION
    source = Column(String(10), nullable=False, default="AUTO")      # AUTO / MANUAL
    decided_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

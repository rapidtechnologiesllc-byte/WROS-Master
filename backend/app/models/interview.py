"""
S-311: Interview Decision Engine Models
Core interview models for panel feedback collection and decision making.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, Enum, Float,
    func, Table, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.models.base import Base


FEEDBACK_RECOMMENDATIONS = ("STRONG_YES", "YES", "NO", "STRONG_NO", "ABSTAIN")
INTERVIEW_STATUSES = ("SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW", "RESCHEDULED")
DECISION_OUTCOMES = ("PENDING", "APPROVED", "REJECTED", "APPROVED_WITH_CONDITIONS", "PENDING_REVIEW")


class InterviewFeedback(Base):
    """Feedback from a single interviewer on the interview panel."""
    __tablename__ = "interview_feedbacks"

    id = Column(String(512), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Reference to interview and interviewer
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False, index=True)
    interviewer_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)

    # Interview Feedback Scores (1-5 scale, nullable if not rated)
    technical_score = Column(Integer, nullable=True)  # 1-5
    communication_score = Column(Integer, nullable=True)  # 1-5
    problem_solving_score = Column(Integer, nullable=True)  # 1-5
    culture_fit_score = Column(Integer, nullable=True)  # 1-5

    # Overall Recommendation
    recommendation = Column(
        Enum(*FEEDBACK_RECOMMENDATIONS, name="feedback_recommendation", native_enum=False, create_constraint=True),
        nullable=False,
        default="ABSTAIN"
    )

    # Detailed Notes
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    overall_notes = Column(Text, nullable=True)

    # Timestamps
    submitted_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    interviewer = relationship("Users", foreign_keys=[interviewer_id])


class InterviewDecisionLog(Base):
    """Log of the panel decision made after all feedback is collected."""
    __tablename__ = "interview_decision_logs"

    id = Column(String(512), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Reference to interview
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)

    # Decision Outcome
    outcome = Column(
        Enum(*DECISION_OUTCOMES, name="interview_decision_outcome", native_enum=False, create_constraint=True),
        nullable=False,
        default="PENDING"
    )

    # Voting Analysis
    strong_yes_count = Column(Integer, nullable=False, default = False)
    yes_count = Column(Integer, nullable=False, default = False)
    no_count = Column(Integer, nullable=False, default = False)
    strong_no_count = Column(Integer, nullable=False, default = False)
    abstain_count = Column(Integer, nullable=False, default = False)
    total_panelists = Column(Integer, nullable=False, default = False)

    # Average Scores
    avg_technical_score = Column(Float, nullable=True)
    avg_communication_score = Column(Float, nullable=True)
    avg_problem_solving_score = Column(Float, nullable=True)
    avg_culture_fit_score = Column(Float, nullable=True)

    # Decision Reasoning
    decision_summary = Column(Text, nullable=True)
    decision_rationale = Column(Text, nullable=True)

    # Made by (usually hiring manager or recruiter)
    decided_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime(timezone=False), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    decided_by = relationship("Users", foreign_keys=[decided_by_user_id])


class InterviewPanelDecision(Base):
    """Represents the collective decision from the interview panel."""
    __tablename__ = "interview_panel_decisions"

    id = Column(String(512), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Reference
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False, unique=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)

    # Final Decision
    decision = Column(
        Enum(*DECISION_OUTCOMES, name="panel_decision_enum", native_enum=False, create_constraint=True),
        nullable=False
    )
    decision_made_at = Column(DateTime(timezone=False), nullable=True)
    made_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)

    # Conditions (if approved with conditions)
    conditions = Column(Text, nullable=True)
    conditions_met_at = Column(DateTime(timezone=False), nullable=True)

    # Next Steps
    next_step = Column(String(512), nullable=True)  # OFFER, REJECT, POOL
    next_step_initiated_at = Column(DateTime(timezone=False), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())

    # Relationships
    made_by = relationship("Users", foreign_keys=[made_by_user_id])

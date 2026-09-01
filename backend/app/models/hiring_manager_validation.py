"""
Hiring Manager Validation Models
Manages validation of candidates by hiring managers before interviews
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON, func, Enum, Boolean, Index
from sqlalchemy.orm import relationship
from app.models.base import Base
from enum import Enum as PyEnum


class HMValidationStatus(str, PyEnum):
    """Hiring Manager validation state machine"""
    PENDING = "PENDING"  # Waiting for HM response
    APPROVED = "APPROVED"  # HM approved candidate for interview
    REJECTED = "REJECTED"  # HM rejected, candidate returned to pool
    MAYBE = "MAYBE"  # HM uncertain, escalated for manual review
    EXPIRED = "EXPIRED"  # Timeout reached, auto-escalated
    ESCALATED = "ESCALATED"  # Escalated to HM's manager


class HiringManagerValidation(Base):
    """
    Hiring Manager validation checkpoint.
    Triggered after candidate matches to job, before interview scheduling.
    HM answers questions about candidate fit, experience level, red flags, etc.
    """
    __tablename__ = "hiring_manager_validations"

    id = Column(String(256), primary_key=True, index=True)  # UUID
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    job_id = Column(String(256), ForeignKey("demands.id"), nullable=False, index=True)  # References Demand (job)
    hiring_manager_id = Column(String(256), ForeignKey("users.UserID"), nullable=False, index=True)

    # Validation state machine
    status = Column(
        Enum(HMValidationStatus, name="hm_validation_status", native_enum=False),
        nullable=False,
        server_default=HMValidationStatus.PENDING.value,
        default=HMValidationStatus.PENDING
    )

    # Timeline
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False, index=True)
    due_at = Column(DateTime(timezone=False), nullable=False)  # created_at + hm_validation_timeout_hours
    responded_at = Column(DateTime(timezone=False), nullable=True)

    # Communication tracking
    email_sent_at = Column(DateTime(timezone=False), nullable=True)
    email_reminder_sent_at = Column(DateTime(timezone=False), nullable=True)
    notification_viewed_at = Column(DateTime(timezone=False), nullable=True)  # Dashboard card opened
    response_time_hours = Column(Integer, nullable=True)  # How long to respond (responded_at - created_at)

    # Validation responses (stored as JSONB)
    responses = Column(JSON, nullable=True)  # {q_001: "yes", q_002: "Red flag X", q_003: "Skill Y", q_004: "yes"}
    decision_comment = Column(Text, nullable=True)  # HM's overall comment/reasoning
    decision_score = Column(Integer, nullable=True)  # 1-10 recommendation

    # Downstream impact
    interview_scheduled_at = Column(DateTime(timezone=False), nullable=True)
    interview_id = Column(String(256), ForeignKey("interviews.interviewID"), nullable=True)
    next_candidate_tried = Column(Boolean, nullable=False, server_default="0", default=False)  # If rejected, tried next

    # Escalation tracking
    escalated_to_user_id = Column(String(256), ForeignKey("users.UserID"), nullable=True)  # If escalated to manager
    escalated_at = Column(DateTime(timezone=False), nullable=True)
    escalation_reason = Column(String(256), nullable=True)

    # Audit & metadata
    created_by = Column(String(256), nullable=True)  # Usually "ai_recruiter" system
    last_updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_hm_validation_candidate", "candidate_id"),
        Index("idx_hm_validation_job", "job_id"),
        Index("idx_hm_validation_manager", "hiring_manager_id"),
        Index("idx_hm_validation_status", "status"),
        Index("idx_hm_validation_created_at", "created_at"),
        Index("idx_hm_validation_due_at", "due_at"),
    )

    # Relationships
    candidate = relationship("Candidate", backref="hm_validations", lazy="joined")
    demand = relationship("Demand", backref="hm_validations", lazy="joined")  # Job reference
    hiring_manager = relationship("Users", foreign_keys=[hiring_manager_id], backref="validations_assigned", lazy="joined")
    escalated_to_user = relationship("Users", foreign_keys=[escalated_to_user_id], backref="validations_escalated_to", lazy="joined")
    interview = relationship("Interview", backref="hm_validation", lazy="joined", uselist=False)

    def to_dict(self):
        """Convert to dict for API responses"""
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "responses": self.responses,
            "decision_comment": self.decision_comment,
            "decision_score": self.decision_score,
        }


class HMValidationResponse(Base):
    """
    Individual HM validation Q&A record.
    One row per question for audit trail and future ML training.
    """
    __tablename__ = "hm_validation_responses"

    id = Column(String(256), primary_key=True, index=True)  # UUID
    validation_id = Column(String(256), ForeignKey("hiring_manager_validations.id"), nullable=False, index=True)

    # Question metadata
    question_id = Column(String(256), nullable=False)  # "q_001", "q_002", etc.
    question_text = Column(Text, nullable=False)  # Full question text for audit
    question_type = Column(String(256), nullable=False)  # "yes_no", "yes_no_maybe", "text"

    # Response
    response_value = Column(Text, nullable=True)  # "yes", "no", "maybe", or text response
    response_json = Column(JSON, nullable=True)  # For complex responses (multiple selections, scores)

    # Timing
    response_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    time_to_respond_seconds = Column(Integer, nullable=True)  # How long user thought before answering

    # Metadata
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    __table_args__ = (
        Index("idx_hm_response_validation", "validation_id"),
        Index("idx_hm_response_question", "question_id"),
    )

    validation = relationship("HiringManagerValidation", backref="question_responses", lazy="joined")

    def to_dict(self):
        """Convert to dict for API responses"""
        return {
            "id": self.id,
            "validation_id": self.validation_id,
            "question_id": self.question_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "response_value": self.response_value,
            "response_at": self.response_at.isoformat() if self.response_at else None,
        }

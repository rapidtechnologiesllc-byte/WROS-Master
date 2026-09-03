"""
Thunder Session Model - Manages candidate chat sessions during pre-screening intake
Tracks form state, question progression, resume data, and session persistence
import logging
"""

import logging
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, ForeignKey, JSON, func, Enum, Index
from sqlalchemy.orm import relationship
from app.models.base import Base
import json
from enum import Enum as PyEnum

logger = logging.getLogger(__name__)

class ThunderSessionStatus(str, PyEnum):
    """Session state machine"""
    STARTED = "STARTED"  # User just opened Thunder
    IN_PROGRESS = "IN_PROGRESS"  # Answering questions
    PAUSED = "PAUSED"  # Left mid-flow, will resume later
    COMPLETED = "COMPLETED"  # Finished all questions, submitted
    ABANDONED = "ABANDONED"  # Left without submitting
    ERROR = "ERROR"  # Session hit critical error


class ThunderSession(Base):
    """
    Manages candidate intake sessions via Questia chatbot.
    One session per candidate per career site visit.
    Persists form state for resume-ability.
    """
    __tablename__ = "thunder_sessions"

    id = Column(String(512), primary_key=True, index=True)  # UUID
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=True, index=True)
    candidate_email = Column(String(512), nullable=False, index=True)  # Used if candidate not yet created

    # Session lifecycle
    status = Column(
        Enum(ThunderSessionStatus, name="thunder_session_status", native_enum=False),
        nullable=False,
        server_default=ThunderSessionStatus.STARTED.value,
        default=ThunderSessionStatus.STARTED
    )
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=False), nullable=True)  # When user began answering
    paused_at = Column(DateTime(timezone=False), nullable=True)
    resumed_at = Column(DateTime(timezone=False), nullable=True)  # When user came back
    completed_at = Column(DateTime(timezone=False), nullable=True)
    last_activity_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    # Session context
    device_type = Column(String(512), nullable=True)  # "mobile", "desktop", "tablet"
    browser = Column(String(512), nullable=True)  # "Chrome", "Safari", etc.
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    session_id_client = Column(String(512), nullable=True)  # Browser-side session tracking

    # Progress tracking
    last_question_reached = Column(String(10), nullable=True)  # "Q1", "Q2", ..., "Q12"
    questions_answered = Column(Integer, nullable=False, server_default="0", default = False)
    questions_total = Column(Integer, nullable=False, server_default="12", default=12)  # Total questions in flow
    completion_percentage = Column(Integer, nullable=False, server_default="0", default = False)  # 0-100

    # Form state (persistent across sessions)
    form_state = Column(JSON, nullable=True)  # Current form state for resume
    form_responses = Column(JSON, nullable=True)  # All Q&A pairs

    # Resume management
    resume_url = Column(String(512), nullable=True)  # S3 path
    resume_uploaded_at = Column(DateTime(timezone=False), nullable=True)
    resume_parsed = Column(Boolean, nullable=False, server_default="0", default=False)
    resume_parse_status = Column(String(512), nullable=True)  # "pending", "processing", "success", "failed"
    resume_parsed_data = Column(JSON, nullable=True)  # Extracted skills, experience, etc.

    # Candidate data collected (from Thunder flow)
    candidate_data = Column(JSON, nullable=True)  # {name, email, phone, location, company, title}

    # Location/job context
    candidate_location = Column(String(512), nullable=True)  # From Q2 or parsed from resume
    job_matches = Column(JSON, nullable=True)  # Top N job matches found by AI Recruiter
    selected_job_id = Column(String(512), nullable=True)  # Demand ID if job is selected

    # Screening responses (stored as submitted)
    screening_responses = Column(JSON, nullable=True)  # Full screening data (work auth, agreements, etc.)

    # Error handling
    last_error = Column(String(512), nullable=True)
    error_count = Column(Integer, nullable=False, server_default="0", default = False)
    retry_batch_id = Column(String(512), nullable=True)  # References error batch for retry

    # Downstream pipeline
    submitted = Column(Boolean, nullable=False, server_default="0", default=False)
    submitted_at = Column(DateTime(timezone=False), nullable=True)
    handoff_to_ai_recruiter_at = Column(DateTime(timezone=False), nullable=True)

    # Metadata
    utm_source = Column(String(512), nullable=True)  # Email campaign, LinkedIn, etc.
    utm_campaign = Column(String(512), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_thunder_session_candidate_id", "candidate_id"),
        Index("idx_thunder_session_email", "candidate_email"),
        Index("idx_thunder_session_status", "status"),
        Index("idx_thunder_session_created_at", "created_at"),
        Index("idx_thunder_session_last_activity", "last_activity_at"),
    )

    # Relationships
    candidate = relationship("Candidate", backref="thunder_sessions", lazy="joined")

    def to_dict(self):
        """Convert session to dict for API responses"""
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "candidate_email": self.candidate_email,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completion_percentage": self.completion_percentage,
            "last_question_reached": self.last_question_reached,
            "submitted": self.submitted,
            "resume_url": self.resume_url,
            "candidate_location": self.candidate_location,
        }

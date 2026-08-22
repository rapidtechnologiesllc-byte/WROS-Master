"""
Admin Models - SLM Management
=============================
Models for tracking SLM patterns, updates, and learning
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, BigInteger, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class SLMPattern(Base):
    """
    Stores SLM patterns that map questions to answers
    Tracks usage, accuracy, and who added each pattern
    """

    __tablename__ = "slm_patterns"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)

    # Pattern definition
    pattern = Column(String(255), nullable=False)  # The text pattern to match
    complexity = Column(
        String(50), nullable=False
    )  # 'simple', 'moderate', 'complex'
    lookup_type = Column(
        String(100), nullable=False
    )  # 'job_list', 'candidate_status', etc.

    # Performance tracking
    usage_count = Column(Integer, default=0)  # How many times this pattern was used
    accuracy_percentage = Column(Float, default=100.0)  # Accuracy when used
    last_used_at = Column(DateTime, nullable=True)  # Last time pattern matched

    # Management
    enabled = Column(Boolean, default=True)  # Can be disabled without deleting
    added_by = Column(String(255), nullable=False)  # Admin who added this
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_slm_patterns_tenant_complexity", "tenant_id", "complexity"),
        Index("ix_slm_patterns_enabled", "enabled"),
    )


class SLMPatternUpdate(Base):
    """
    Audit log of SLM pattern changes
    Tracks who made what changes and when
    """

    __tablename__ = "slm_pattern_updates"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)

    pattern_id = Column(Integer, nullable=True)  # Nullable for bulk imports
    action = Column(String(50), nullable=False)  # 'added', 'updated', 'disabled'
    changes = Column(Text, nullable=True)  # JSON of what changed

    added_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_slm_updates_tenant_action", "tenant_id", "action"),)


class SLMQuestionLog(Base):
    """
    Logs each question processed by Thunder
    Used for analytics on which patterns work best
    """

    __tablename__ = "slm_question_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)
    candidate_id = Column(String(255), nullable=False)

    question = Column(Text, nullable=False)
    pattern_id = Column(Integer, nullable=True)  # Which pattern matched (if any)
    complexity = Column(String(50), nullable=False)  # How complex was the question
    source = Column(String(50), nullable=False)  # 'local_slm' or 'claude'

    response_time_ms = Column(Integer, nullable=False)  # How long to answer
    was_accurate = Column(Boolean, nullable=True)  # Did admin mark as accurate
    feedback = Column(Text, nullable=True)  # Admin feedback if inaccurate

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_slm_logs_tenant_source", "tenant_id", "source"),
        Index("ix_slm_logs_candidate", "tenant_id", "candidate_id"),
    )

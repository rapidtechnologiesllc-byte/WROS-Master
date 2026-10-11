"""Unified Learning Event Model - Standard format for all 6 modules

Every interaction across Thunder, Flash, Interview, Offer, Finance, Employee
records outcomes in this unified format for cascade analysis and cross-module learning.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.models.base import Base


class LearningEvent(Base):
    """Unified event log for all learning modules"""
    __tablename__ = "learning_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Event identification
    module = Column(String(50), nullable=False, index=True)  # thunder, flash, interview, offer, finance, employee
    action_type = Column(String(100), nullable=False, index=True)  # email_sent, interview_scheduled, offer_accepted, etc.
    event_id = Column(String(512), nullable=True, index=True)  # Unique ID within module (message_id, interview_id, etc.)

    # Entity identification
    entity_type = Column(String(50), nullable=False)  # candidate, job, interview, offer, project, employee
    entity_id = Column(String(512), nullable=False, index=True)  # candidate_id, job_id, interview_id, offer_id, project_id, employee_id
    secondary_entity_id = Column(String(512), nullable=True)  # job_id for candidate, candidate_id for offer, etc.

    # Segment information (for segment-specific learning)
    segment_id = Column(String(512), nullable=True, index=True)  # segment_name for grouping (e.g., "senior_engineer_us", "fixedprice_tech")

    # Event timing
    event_timestamp = Column(DateTime, nullable=False, index=True)  # When action happened
    recorded_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)  # When outcome was recorded
    expected_outcome_timestamp = Column(DateTime, nullable=True)  # When outcome is expected

    # Predicted outcome (what was expected)
    predicted_outcome = Column(String(100), nullable=True)  # engagement, interview_scheduled, offer_accepted, etc.
    predicted_probability = Column(Float, nullable=True)  # 0.0-1.0 confidence
    predicted_metadata = Column(JSON, nullable=True)  # Factors that drove prediction ({"channel": "email", "confidence_factors": [...]})

    # Actual outcome (what actually happened)
    actual_outcome = Column(String(100), nullable=True)  # email_opened, interview_no_show, offer_rejected, etc.
    actual_success = Column(Boolean, nullable=True)  # True if prediction was correct
    actual_metadata = Column(JSON, nullable=True)  # Details about what happened

    # Confidence gap measurement
    confidence_gap = Column(Float, nullable=True)  # |predicted_probability - actual_result|

    # Learning metadata
    factors_used = Column(JSON, nullable=True)  # Which factors influenced this decision {"channel_weight": 0.4, "timing_weight": 0.3, ...}
    outcome_delay_hours = Column(Float, nullable=True)  # How long before outcome was recorded

    # Cascade tracking
    cascade_source = Column(String(512), nullable=True)  # Which module triggered this (e.g., "flash_match_quality_65" for interview)
    cascade_confidence_impact = Column(Float, nullable=True)  # How much did cascade affect confidence (0.0-1.0)

    # Data quality flags
    is_valid = Column(Boolean, default=True, nullable=False)  # Is this event trustworthy?
    quality_notes = Column(Text, nullable=True)  # Any data quality issues noted

    # Indexes for common queries
    __table_args__ = (
        Index('ix_learning_events_module_action', 'module', 'action_type'),
        Index('ix_learning_events_entity', 'entity_type', 'entity_id'),
        Index('ix_learning_events_segment_timestamp', 'segment_id', 'event_timestamp'),
        Index('ix_learning_events_cascade', 'cascade_source', 'cascade_confidence_impact'),
    )


class LearningEventBatch(Base):
    """Groups of events processed together for weight updates"""
    __tablename__ = "learning_event_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Batch identification
    module = Column(String(50), nullable=False, index=True)
    segment_id = Column(String(512), nullable=True)

    # Batch composition
    event_count = Column(Integer, nullable=False)  # Should be ~50 for weight update batches
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime, nullable=False)

    # Batch metrics
    accuracy = Column(Float, nullable=True)  # Overall accuracy for this batch
    confidence_gap_avg = Column(Float, nullable=True)  # Average gap between predicted and actual

    # Weight update result
    weights_updated = Column(Boolean, default=False)
    weight_changes = Column(JSON, nullable=True)  # What was updated

    # Cascade information
    cascade_failures_detected = Column(Integer, default=0)  # How many cascade failures in batch

    recorded_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class SegmentLearningProfile(Base):
    """Learned patterns for each segment (cached for fast lookup)"""
    __tablename__ = "segment_learning_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Segment identification
    module = Column(String(50), nullable=False)  # thunder, flash, interview, offer, finance, employee
    segment_id = Column(String(512), nullable=False, index=True)

    # Segment metadata
    segment_description = Column(String(512), nullable=True)  # Human-readable (e.g., "Senior Engineer, US, Tech Stack: Python")
    sample_size = Column(Integer, default=0)  # How many operations in segment
    confidence = Column(Float, default=0.0)  # 0.0-1.0 confidence in learned pattern

    # Learned patterns (module-specific, stored as JSON for flexibility)
    learned_patterns = Column(JSON, nullable=True)
    # For Thunder: {"best_channel": "email", "best_hour": 9, "channel_success_rates": {...}}
    # For Flash: {"match_quality_weights": {...}, "interview_conversion_rate": 0.75}
    # For Interview: {"recommended_assessments": [...], "interviewer_accuracy": 0.85}
    # For Offer: {"acceptable_salary_range": [120000, 180000], "benefits_preferred": [...]}
    # For Finance: {"expected_margin_factor": 0.85, "project_type_fit": {...}}
    # For Employee: {"retention_rate_6mo": 0.92, "engagement_drivers": [...]}

    # Recommendations based on learning
    recommendation = Column(Text, nullable=True)  # What should be done for candidates in this segment
    confidence_threshold = Column(Float, default=0.70)  # Min confidence before applying learning

    # Historical tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accuracy = Column(Float, nullable=True)  # Accuracy on last N operations

    # Bias detection
    bias_flags = Column(JSON, nullable=True)  # Any suspected biases detected {"disparity_factor": 1.8, "affected_groups": [...]}

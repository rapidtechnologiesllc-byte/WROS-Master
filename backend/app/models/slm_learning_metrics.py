"""SLM Learning Metrics Models - Track autonomous system learning

Stores metrics from Thunder and Flash agents to enable:
1. Performance trend analysis
2. Agentic learning weight updates
3. Cascade failure prediction
4. Quality score computation
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class SLMMetrics(Base):
    """Composite SLM health score across all orchestrators"""
    __tablename__ = "slm_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Time tracking
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    metric_date = Column(String, nullable=False)  # YYYY-MM-DD format

    # Composite metrics
    slm_health_score = Column(Float, default=50.0, nullable=False)  # 0-100%
    thunder_outreach_success_rate = Column(Float, default=0.0, nullable=False)  # 0-100%
    flash_job_match_quality = Column(Float, default=0.0, nullable=False)  # 0-100%
    flash_interview_conversion_rate = Column(Float, default=0.0, nullable=False)  # 0-100%

    # Operational metrics
    operations_processed = Column(Integer, default=0, nullable=False)
    learning_weights_updated = Column(Boolean, default=False)

    # Analysis
    cascade_risk_detected = Column(Boolean, default=False)
    formation_integrity_score = Column(Float, default=100.0, nullable=False)  # 0-100%
    bottleneck_identified = Column(String, nullable=True)  # e.g., "thunder_outreach"

    # Recommendations
    slm_recommendation = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.0, nullable=False)  # 0-100%


class ThunderLearningMetrics(Base):
    """Thunder autonomous outreach learning metrics"""
    __tablename__ = "thunder_learning_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Channel effectiveness (learned over 50+ operations)
    email_success_rate = Column(Float, default=0.0, nullable=False)  # % of emails opened
    sms_success_rate = Column(Float, default=0.0, nullable=False)  # % of SMS delivered
    whatsapp_success_rate = Column(Float, default=0.0, nullable=False)  # % engaged
    linkedin_success_rate = Column(Float, default=0.0, nullable=False)  # % profile views

    # Optimal timing patterns (learned per candidate)
    best_outreach_hour = Column(Integer, nullable=True)  # 0-23 (UTC)
    best_outreach_day = Column(Integer, nullable=True)  # 0-6 (Monday-Sunday)
    average_response_time_hours = Column(Float, nullable=True)

    # Message personalization
    profile_title = Column(String, nullable=True)  # e.g., "Senior Engineer"
    profile_company = Column(String, nullable=True)  # Last/current company
    profile_experience_years = Column(Integer, nullable=True)

    # Confidence scoring
    recommendation_confidence = Column(Float, default=0.0, nullable=False)  # 0-100%
    operations_analyzed = Column(Integer, default=0, nullable=False)

    # Preferred channel
    recommended_channel = Column(String, nullable=True)  # "email", "sms", "whatsapp", etc.
    recommended_message_template = Column(String, nullable=True)  # e.g., "tech_senior_engineer"


class FlashLearningMetrics(Base):
    """Flash job-matching and orchestration learning metrics"""
    __tablename__ = "flash_learning_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Job-candidate matching quality (learned)
    average_match_quality = Column(Float, default=0.0, nullable=False)  # 0-100%
    skills_match_accuracy = Column(Float, default=0.0, nullable=False)  # How often predicted skills match reality
    experience_match_accuracy = Column(Float, default=0.0, nullable=False)  # Years of experience prediction

    # Interview scheduling patterns (learned)
    interview_scheduling_success_rate = Column(Float, default=0.0, nullable=False)  # % scheduled successfully
    optimal_interview_slot_days = Column(Integer, nullable=True)  # Days from application
    candidate_show_up_rate = Column(Float, default=0.0, nullable=False)  # % attended scheduled interviews
    interview_to_offer_conversion = Column(Float, default=0.0, nullable=False)  # % of interviews → offers

    # Offer generation patterns (learned)
    typical_offer_salary_range = Column(String, nullable=True)  # e.g., "120K-140K"
    offer_acceptance_rate = Column(Float, default=0.0, nullable=False)  # % of offers accepted
    average_negotiation_rounds = Column(Float, default=1.0, nullable=False)

    # Confidence scoring
    recommendation_confidence = Column(Float, default=0.0, nullable=False)  # 0-100%
    operations_analyzed = Column(Integer, default=0, nullable=False)

    # Top candidate profiles (learned patterns)
    top_candidate_profile = Column(String, nullable=True)  # e.g., "mid_level_engineer_from_tech"
    success_candidate_count = Column(Integer, default=0, nullable=False)  # Hired from this job


class LearningWeightUpdate(Base):
    """Records when learning weights are updated (every 50 operations)"""
    __tablename__ = "learning_weight_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    orchestrator = Column(String, nullable=False)  # "thunder" or "flash"

    # Update details
    update_type = Column(String, nullable=False)  # "channel_effectiveness", "interview_timing", etc.
    operations_in_batch = Column(Integer, nullable=False)  # Should be ~50

    # Weight changes
    weight_changes = Column(Text, nullable=False)  # JSON string of {field: old_value → new_value}

    # Validation
    is_valid = Column(Boolean, default=True, nullable=False)
    validation_notes = Column(Text, nullable=True)

    # Audit
    triggered_by_cascade = Column(Boolean, default=False, nullable=False)
    bias_detected = Column(Boolean, default=False, nullable=False)
    bias_details = Column(Text, nullable=True)  # If bias detected, describe it


class LearningRecommendation(Base):
    """SLM recommendations to Thunder/Flash based on learning"""
    __tablename__ = "learning_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Target
    target_orchestrator = Column(String, nullable=False)  # "thunder" or "flash"
    target_entity_id = Column(UUID(as_uuid=True), nullable=True)  # candidate_id or job_id

    # Recommendation
    recommendation_type = Column(String, nullable=False)  # "channel", "timing", "candidate", "job_match"
    recommendation_value = Column(String, nullable=False)  # e.g., "sms", "9:00-10:00", "excellent_match"

    # Confidence
    confidence_score = Column(Float, default=0.0, nullable=False)  # 0-100%

    # Approval status
    approved = Column(Boolean, default=False)
    approved_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Result
    applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)
    result_status = Column(String, nullable=True)  # "success", "failed", "pending"
    result_details = Column(Text, nullable=True)

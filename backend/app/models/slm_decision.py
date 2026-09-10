"""
SLM Decision Model - Accountability & Business Impact Tracking

Records every SLM decision with full traceability:
- Pre-flight analysis (Place 1): What SLM recommended
- Post-flight outcome (Place 2): What actually happened
- Business impact: Candidate affected, 90-day validation plan
- Accountability: Who decided, can it be reversed, audit trail
"""

from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.core.database import Base


class SLMDecision(Base):
    __tablename__ = "slm_decisions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Message reference (FK to ChannelQueueItem)
    message_id = Column(UUID(as_uuid=True), ForeignKey("channel_queue_items.id"), nullable=False)
    message_type = Column(String(100), nullable=False)  # interview_scheduled, offer_generated, etc.

    # Pre-flight analysis (PLACE 1)
    slm_analysis = Column(JSON, nullable=True)  # Pre-flight confidence, risk_level, reasoning
    slm_decision_id_precheck = Column(String(255), nullable=True)  # For linking to pre-flight decision

    # Handler execution details
    handler_name = Column(String(255), nullable=False)  # interview_scheduled_handler, etc.
    handler_duration_ms = Column(Integer, nullable=True)  # How long handler took

    # Post-flight outcome (PLACE 2)
    handler_result = Column(JSON, nullable=True)  # What handler returned
    handler_status = Column(String(50), nullable=True)  # success, failed, escalated

    # Business impact & accountability
    business_impact = Column(JSON, nullable=True)
    # Structure:
    # {
    #   "candidate_affected": True,
    #   "candidate_id": "c123",
    #   "candidates_affected_count": 1,
    #   "start_date": "2026-10-01",
    #   "position_id": "pos_123",
    #   "expected_outcome": "hire",
    #   "validation_method": "90-day performance review",
    #   "cost_impact": 150000,
    #   "risk_flags": []
    # }

    validation_plan = Column(JSON, nullable=True)
    # Structure:
    # {
    #   "validation_method": "90-day performance review",
    #   "success_criteria": ["hire completion", "performance > 70th percentile"],
    #   "validation_date": "2026-12-31",
    #   "validation_result": null (filled after 90 days)
    # }

    accountability = Column(JSON, nullable=True)
    # Structure:
    # {
    #   "decision_maker": "SLM:confidence_0.88",
    #   "can_be_reversed": True,
    #   "override_conditions": ["90_day_eval_shows_poor_fit"],
    #   "audit_trail": [
    #     {"timestamp": "...", "event": "analyzed", "decision": "proceed"},
    #     {"timestamp": "...", "event": "handler_executed", "status": "success"},
    #     {"timestamp": "...", "event": "90_day_eval_complete", "result": "success"}
    #   ]
    # }

    # Confidence & escalation
    slm_confidence = Column(Float, nullable=True)  # 0.0-1.0, from SLM analysis
    risk_level = Column(String(50), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    was_escalated = Column(Boolean, default=False)  # True if SLM said "don't proceed"
    escalation_reason = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    analysis_at = Column(DateTime, nullable=True)  # When SLM analysis completed
    handler_started_at = Column(DateTime, nullable=True)
    handler_completed_at = Column(DateTime, nullable=True)
    outcome_recorded_at = Column(DateTime, nullable=True)
    validated_at = Column(DateTime, nullable=True)  # When 90-day validation completed

    def __repr__(self):
        return (f"<SLMDecision message={self.message_type} "
                f"confidence={self.slm_confidence} "
                f"escalated={self.was_escalated}>")

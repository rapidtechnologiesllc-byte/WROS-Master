"""
Learning Transcript Model - Complete audit log of all system learning

Every decision, prediction, outcome, and weight update is recorded here
for full transparency and audit capability.
"""

from sqlalchemy import Column, String, Float, DateTime, Integer, JSON, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models.base import Base


class LearningTranscript(Base):
    """
    Complete audit log of system learning across all modules.
    Used for transparency and debugging.
    """
    __tablename__ = "learning_transcript"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Event identification
    event_type = Column(String(100), nullable=False)  # opportunity_created, recruitment_triggered, project_assigned, timesheet_recorded, etc.
    module_name = Column(String(50), nullable=False)  # thunder, flash, finance, sales, recruitment, project

    # Entity references
    entity_id = Column(String(36), nullable=True)  # opportunity_id, candidate_id, project_id, etc.
    entity_type = Column(String(50), nullable=True)  # opportunity, candidate, project, timesheet
    related_entities = Column(JSON, nullable=True)  # {opportunity_id: ..., candidate_id: ..., project_id: ...}

    # Decision details
    decision_type = Column(String(100), nullable=False)  # predict_fit, predict_margin, predict_utilization, etc.
    predicted_value = Column(Float, nullable=True)  # confidence score, margin %, utilization %
    predicted_label = Column(String(100), nullable=True)  # "ON_TIME", "HIGH_MARGIN", "AVAILABLE", etc.

    # Prediction factors (what influenced the decision)
    factors = Column(JSON, nullable=False)  # {factor_name: weight, ...}
    factor_values = Column(JSON, nullable=True)  # {factor_name: actual_value, ...}

    # Outcome (what actually happened)
    outcome_recorded = Column(Boolean, default=False)
    actual_value = Column(Float, nullable=True)  # actual margin %, utilization %, etc.
    actual_label = Column(String(100), nullable=True)  # "ON_TIME", "HIGH_MARGIN", "AVAILABLE", etc.
    confidence_gap = Column(Float, nullable=True)  # |predicted - actual|

    # Weight updates (learning signal)
    weights_before = Column(JSON, nullable=True)  # {factor_name: old_weight, ...}
    weights_after = Column(JSON, nullable=True)  # {factor_name: new_weight, ...}
    weight_updates = Column(JSON, nullable=True)  # {factor_name: delta, ...}
    learning_strength = Column(Float, nullable=True)  # How strong was the learning signal? (0-1)

    # Cascade impact (what downstream effects this had)
    cascade_impacts = Column(JSON, nullable=True)  # {module: effect, ...}

    # Metadata
    user_id = Column(String(36), nullable=True)  # Who initiated this decision?
    source = Column(String(50), default="system")  # system, manual_override, api, webhook
    manual_override = Column(Boolean, default=False)  # Was this decision overridden by human?
    override_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    outcome_recorded_at = Column(DateTime, nullable=True)

    # Indices for fast lookup
    __table_args__ = (
        Index('idx_learning_transcript_tenant', 'tenant_id'),
        Index('idx_learning_transcript_entity', 'entity_id', 'entity_type'),
        Index('idx_learning_transcript_module', 'module_name', 'decision_type'),
        Index('idx_learning_transcript_created', 'created_at'),
    )

    def __repr__(self):
        return f"<LearningTranscript {self.id} {self.module_name}.{self.decision_type} → {self.predicted_label}>"


class LearningAuditSummary(Base):
    """
    Aggregated learning summary by module and time period.
    Used for dashboards and reporting.
    """
    __tablename__ = "learning_audit_summary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Summary period
    period = Column(String(20), nullable=False)  # daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Module performance
    module_name = Column(String(50), nullable=False)
    decision_type = Column(String(100), nullable=True)

    # Metrics
    total_decisions = Column(Integer, default=0)
    decisions_with_outcomes = Column(Integer, default=0)
    avg_confidence_gap = Column(Float, nullable=True)  # Average gap (how wrong were we?)
    accuracy_rate = Column(Float, nullable=True)  # % decisions where gap < 0.1
    avg_learning_strength = Column(Float, nullable=True)  # How strong were learning signals?

    # Weight stability
    weights_updated = Column(Integer, default=0)
    avg_weight_delta = Column(Float, nullable=True)  # Average change per update

    # Cascade health
    cascade_failures = Column(Integer, default=0)
    cascade_success_rate = Column(Float, nullable=True)

    # Manual overrides
    manual_overrides = Column(Integer, default=0)
    override_rate = Column(Float, nullable=True)  # % decisions overridden

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_audit_summary_tenant', 'tenant_id'),
        Index('idx_audit_summary_period', 'period_start', 'period_end'),
        Index('idx_audit_summary_module', 'module_name', 'period'),
    )

    def __repr__(self):
        return f"<LearningAuditSummary {self.module_name} {self.period}>"


class LearningCascadeChain(Base):
    """
    Track cascade relationships between decisions.
    Shows how Thunder → Flash → Finance are connected.
    """
    __tablename__ = "learning_cascade_chain"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Chain identification
    chain_id = Column(String(36), nullable=False)  # Groups related decisions
    chain_type = Column(String(100), nullable=False)  # opportunity_to_hire, hire_to_project, etc.

    # Entity references
    entity_id = Column(String(36), nullable=False)  # opportunity_id or candidate_id that ties chain
    entity_type = Column(String(50), nullable=False)

    # Chain steps (ordered)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String(100), nullable=False)  # sales_opportunity, thunder_match, recruitment, project_assignment, etc.
    decision_id = Column(String(36), ForeignKey("learning_transcript.id"), nullable=False)

    # Impact on next step
    confidence_passed_to_next = Column(Float, nullable=True)
    success_probability_input = Column(Float, nullable=True)  # Input to next step prediction

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_cascade_chain_id', 'chain_id'),
        Index('idx_cascade_entity', 'entity_id', 'entity_type'),
        Index('idx_cascade_step', 'step_number', 'chain_type'),
    )

    def __repr__(self):
        return f"<LearningCascadeChain {self.chain_type} step {self.step_number}>"

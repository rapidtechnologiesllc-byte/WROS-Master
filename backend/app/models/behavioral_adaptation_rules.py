"""
Behavioral Adaptation Rules Engine Models

Stores rules DSL that changes agent strategy based on learned conditions.
Example: "If accuracy < 85% for 3 days, increase diversity_bonus weight from 0.1 to 0.3"
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime


class BehavioralAdaptationRule(Base):
    """Rules that trigger behavior changes in agents."""

    __tablename__ = "behavioral_adaptation_rules"

    rule_id = Column(String(512), primary_key=True)
    orchestrator = Column(String(50), nullable=False, index=True)  # Which agent this rule governs
    tenant_id = Column(String(512), nullable=False, index=True)

    # Rule metadata
    rule_name = Column(String(512), nullable=False)  # "Accuracy Crisis Response", "Throughput Optimization"
    rule_description = Column(Text)
    rule_category = Column(String(50))  # ACCURACY, THROUGHPUT, CALIBRATION, FORMATION_HEALTH, COST_OPTIMIZATION
    rule_priority = Column(String(50))  # CRITICAL, HIGH, MEDIUM, LOW

    # Condition: When does this rule trigger?
    # Example: metric=accuracy, operator=<, threshold=0.80, window_minutes=1440 (last 24h)
    trigger_metric = Column(String(255))  # accuracy, throughput, calibration, health, cascade_count
    trigger_operator = Column(String(50))  # <, >, ==, !=, IN, NOT_IN
    trigger_threshold = Column(Float)
    trigger_window_minutes = Column(Integer)  # Look back this many minutes
    trigger_check_frequency_minutes = Column(Integer, default=5)  # Check every N minutes

    # Optional: AND condition (metric2)
    trigger_metric_2 = Column(String(255), nullable=True)
    trigger_operator_2 = Column(String(50), nullable=True)
    trigger_threshold_2 = Column(Float, nullable=True)
    trigger_logic = Column(String(10), default="AND")  # AND or OR

    # Action: What changes when rule triggers?
    # Example: change weight_field "diversity_bonus" from 0.1 to 0.3
    action_type = Column(String(50))  # CHANGE_WEIGHT, CHANGE_ALLOCATION, ESCALATE_ALERT, ROLLBACK_VARIANT, ADJUST_THRESHOLDS
    action_target_field = Column(String(255), nullable=True)  # Which field to change (e.g., "diversity_bonus", "experiment_allocation")
    action_from_value = Column(Float, nullable=True)  # Current value
    action_to_value = Column(Float, nullable=True)  # New value

    # Gradual vs immediate
    action_transition_type = Column(String(50), default="IMMEDIATE")  # IMMEDIATE, GRADUAL_5MIN, GRADUAL_15MIN, GRADUAL_1HOUR

    # Action metadata
    action_justification = Column(Text)  # Why this action (for audit trail)
    action_reversible = Column(Boolean, default=True)  # Can this be undone?
    action_rollback_trigger = Column(String(255), nullable=True)  # What metric indicates rollback needed?

    # Rule status
    is_active = Column(Boolean, default=True)
    triggered_count = Column(Integer, default=0)  # How many times has this fired?
    last_triggered_at = Column(DateTime, nullable=True)

    # Manual overrides
    manually_disabled_at = Column(DateTime, nullable=True)
    manually_disabled_reason = Column(Text, nullable=True)
    manually_disabled_by = Column(String(255), nullable=True)  # User ID

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rule_executions = relationship("RuleExecution", back_populates="rule")


class RuleExecution(Base):
    """Every time a rule fires, log exactly what happened."""

    __tablename__ = "rule_executions"

    execution_id = Column(String(512), primary_key=True)
    rule_id = Column(String(512), ForeignKey("behavioral_adaptation_rules.rule_id", ondelete="CASCADE"), index=True)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Execution context
    orchestrator = Column(String(50), nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)

    # What triggered it
    trigger_metric_value = Column(Float)  # The actual value that triggered
    trigger_metric_value_2 = Column(Float, nullable=True)  # Optional second metric

    # What changed
    field_changed = Column(String(255))
    old_value = Column(Float)
    new_value = Column(Float)

    # How it was applied
    execution_status = Column(String(50))  # EXECUTED, PARTIALLY_EXECUTED, FAILED, SKIPPED
    execution_failure_reason = Column(Text, nullable=True)  # If failed, why?

    # Impact measured
    metric_before_action = Column(Float, nullable=True)  # Metric value before change
    metric_after_action = Column(Float, nullable=True)  # Metric value after change (measured 5 min later)
    metric_improvement = Column(Float, nullable=True)  # (after - before) / before * 100

    # Downstream effects
    cascade_signals_triggered = Column(Integer, default=0)  # Did this cause other rules to fire?
    formation_health_impact = Column(Float, nullable=True)  # Impact on Phalanx health

    # Rollback tracking
    was_rolled_back = Column(Boolean, default=False)
    rolled_back_at = Column(DateTime, nullable=True)
    rollback_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    rule = relationship("BehavioralAdaptationRule", back_populates="rule_executions")


class RuleAuditLog(Base):
    """Historical audit of all rule management actions (enable/disable/modify)."""

    __tablename__ = "rule_audit_logs"

    audit_id = Column(String(512), primary_key=True)
    rule_id = Column(String(512), ForeignKey("behavioral_adaptation_rules.rule_id", ondelete="SET NULL"), nullable=True)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Who did what
    action = Column(String(50))  # CREATED, ENABLED, DISABLED, MODIFIED, EXECUTED, ROLLED_BACK
    action_by = Column(String(255), nullable=True)  # User ID (null if system-triggered)
    action_at = Column(DateTime, default=datetime.utcnow)

    # What changed
    old_rule_config = Column(JSON, nullable=True)  # Full rule before modification
    new_rule_config = Column(JSON, nullable=True)  # Full rule after modification

    # Reason documented
    audit_reason = Column(Text, nullable=True)  # Why was this action taken?

    created_at = Column(DateTime, default=datetime.utcnow)

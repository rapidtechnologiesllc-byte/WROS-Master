from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from datetime import datetime
from app.models.base import Base


class BehavioralAdaptationRule(Base):
    """Tracks behavioral adaptation rules learned by orchestrators."""
    __tablename__ = "behavioral_adaptation_rules"

    id = Column(Integer, primary_key=True)
    orchestrator_id = Column(String(100), nullable=False, index=True)
    rule_name = Column(String(200), nullable=False)
    rule_type = Column(String(50), nullable=False)  # candidate_quality, response_time, success_rate, etc.
    condition = Column(Text, nullable=False)  # Condition that triggers rule (e.g., "success_rate < 0.5")
    action = Column(Text, nullable=False)  # Action to take (e.g., "reduce_batch_size_by_10_percent")
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BehavioralAdaptationRule {self.rule_name} success_rate={self.success_count}/{self.execution_count}>"


class RuleExecution(Base):
    """Logs each time a behavioral adaptation rule is executed."""
    __tablename__ = "rule_executions"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, nullable=False, index=True)
    orchestrator_id = Column(String(100), nullable=False)
    execution_timestamp = Column(DateTime, default=datetime.utcnow)
    trigger_context = Column(JSON, nullable=True)  # Context that triggered the rule
    action_taken = Column(Text, nullable=True)
    outcome = Column(String(50), nullable=True)  # SUCCESS, FAILURE, PARTIAL
    impact_metric = Column(Float, nullable=True)  # Metric improvement from executing this rule
    cascade_effect = Column(String(255), nullable=True)  # Did this rule trigger other rules?
    duration_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<RuleExecution rule={self.rule_id} outcome={self.outcome}>"

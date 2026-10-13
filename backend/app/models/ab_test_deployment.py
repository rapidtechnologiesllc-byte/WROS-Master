from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, Enum
from datetime import datetime
import enum
from app.models.base import Base


class ABTestDeployment(Base):
    """Tracks A/B test deployments for route allocation strategies."""
    __tablename__ = "ab_test_deployments"

    id = Column(Integer, primary_key=True)
    orchestrator_id = Column(String(100), nullable=False, index=True)
    test_name = Column(String(200), nullable=False)
    test_type = Column(String(50), nullable=False)  # thompson_sampling, epsilon_greedy, ucb
    variant_a_name = Column(String(100), nullable=False)
    variant_b_name = Column(String(100), nullable=False)
    allocation_method = Column(String(50), default="thompson_sampling")
    current_allocation_a = Column(Float, default=0.5)  # Proportion to variant A
    current_allocation_b = Column(Float, default=0.5)  # Proportion to variant B
    total_samples = Column(Integer, default=0)
    variant_a_samples = Column(Integer, default=0)
    variant_b_samples = Column(Integer, default=0)
    variant_a_success = Column(Integer, default=0)
    variant_b_success = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ABTestDeployment {self.test_name} {self.variant_a_name}:{self.current_allocation_a:.2f} vs {self.variant_b_name}:{self.current_allocation_b:.2f}>"


class ABTestDecision(Base):
    """Tracks individual allocation decisions during A/B test."""
    __tablename__ = "ab_test_decisions"

    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, nullable=False, index=True)
    decision_timestamp = Column(DateTime, default=datetime.utcnow)
    orchestrator_id = Column(String(100), nullable=False)
    variant_chosen = Column(String(100), nullable=False)  # variant_a or variant_b
    success = Column(Boolean, nullable=True)  # True if variant performed well, False otherwise
    confidence = Column(Float, nullable=True)  # Confidence in the allocation decision
    decision_reason = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<ABTestDecision {self.variant_chosen} success={self.success}>"


class ABTestStageMetrics(Base):
    """Metrics for each stage of the A/B test."""
    __tablename__ = "ab_test_stage_metrics"

    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, nullable=False, index=True)
    stage_num = Column(Integer, nullable=False)
    stage_duration_seconds = Column(Integer, nullable=True)
    variant_a_conversion_rate = Column(Float, nullable=True)
    variant_b_conversion_rate = Column(Float, nullable=True)
    variant_a_avg_outcome = Column(Float, nullable=True)
    variant_b_avg_outcome = Column(Float, nullable=True)
    statistical_significance = Column(Float, nullable=True)  # p-value
    winner = Column(String(100), nullable=True)  # variant_a, variant_b, or TIE
    recorded_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ABTestStageMetrics stage={self.stage_num} winner={self.winner}>"

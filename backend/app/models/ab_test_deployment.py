"""
A/B Test Deployment Models - Safe weight variant testing

3-stage rollout with automatic rollback based on performance and formation health.
Uses Thompson sampling to adaptively allocate traffic to winner.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime


class ABTestDeployment(Base):
    """A/B test of weight variant across stages."""

    __tablename__ = "ab_test_deployments"

    test_id = Column(String(512), primary_key=True)
    population_id = Column(String(512), ForeignKey("genetic_weight_populations.population_id", ondelete="CASCADE"))

    # Test configuration
    orchestrator = Column(String(50), nullable=False, index=True)  # thunder, flash, interview, offer, finance
    tenant_id = Column(String(512), nullable=False, index=True)

    # Variants
    baseline_chromosome_id = Column(String(512), nullable=False)  # Current live weights
    variant_chromosome_id = Column(String(512), nullable=False)  # New weights being tested

    # Stage progression
    current_stage = Column(String(50), default="EXPERIMENT")  # EXPERIMENT, EXPAND, FULL_ROLLOUT, COMPLETED, ROLLED_BACK
    stage_start_time = Column(DateTime)
    stage_duration_seconds = Column(Integer)  # How long to run this stage

    # Traffic allocation (Thompson sampling)
    experiment_allocation = Column(Float, default=0.05)  # 5% traffic in Stage 1
    expand_allocation = Column(Float, default=0.25)  # 25% traffic in Stage 2
    baseline_decisions_count = Column(Integer, default=0)
    variant_decisions_count = Column(Integer, default=0)

    # Stage success criteria
    stage_target_decisions = Column(Integer)  # How many decisions before advancing
    stage_required_improvement = Column(Float)  # Accuracy improvement needed (e.g., 0.02 for 2%)
    stage_allow_rollback = Column(Boolean, default=True)

    # Performance tracking
    baseline_accuracy = Column(Float, nullable=True)
    variant_accuracy = Column(Float, nullable=True)
    accuracy_improvement = Column(Float, nullable=True)

    baseline_calibration = Column(Float, nullable=True)
    variant_calibration = Column(Float, nullable=True)
    calibration_improvement = Column(Float, nullable=True)

    baseline_throughput = Column(Float, nullable=True)
    variant_throughput = Column(Float, nullable=True)

    # Phalanx health monitoring (hard stop condition)
    baseline_formation_health = Column(Float, nullable=True)
    variant_formation_health = Column(Float, nullable=True)
    formation_health_threshold = Column(Float, default=0.70)  # Rollback if <70%

    # Rollback decision
    rolled_back = Column(Boolean, default=False)
    rollback_reason = Column(String(512), nullable=True)
    rollback_at = Column(DateTime, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    decisions = relationship("ABTestDecision", back_populates="test")
    population = relationship("GeneticWeightPopulation", back_populates="ab_tests")


class ABTestDecision(Base):
    """Each decision made during A/B test."""

    __tablename__ = "ab_test_decisions"

    decision_id = Column(String(512), primary_key=True)
    test_id = Column(String(512), ForeignKey("ab_test_deployments.test_id", ondelete="CASCADE"), index=True)

    # Which variant handled this decision
    variant = Column(String(50))  # "baseline" or "variant"
    stage = Column(String(50))  # EXPERIMENT, EXPAND, FULL_ROLLOUT

    # Decision outcome
    predicted_confidence = Column(Float)  # Model's confidence (0-1)
    actual_success = Column(Boolean)  # Did decision succeed?

    # Metrics
    execution_time_ms = Column(Integer, nullable=True)
    confidence_gap = Column(Float)  # |predicted - actual|

    # Impact tracking
    downstream_conversions = Column(JSON)  # Track cascade (this decision → downstream outcomes)
    error_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    test = relationship("ABTestDeployment", back_populates="decisions")


class ABTestStageMetrics(Base):
    """Aggregated metrics per stage."""

    __tablename__ = "ab_test_stage_metrics"

    stage_metric_id = Column(String(512), primary_key=True)
    test_id = Column(String(512), ForeignKey("ab_test_deployments.test_id", ondelete="CASCADE"), index=True)
    stage = Column(String(50))  # EXPERIMENT, EXPAND, FULL_ROLLOUT

    # Traffic
    baseline_count = Column(Integer, default=0)
    variant_count = Column(Integer, default=0)

    # Performance
    baseline_accuracy = Column(Float)
    variant_accuracy = Column(Float)
    accuracy_improvement = Column(Float)

    baseline_calibration = Column(Float)
    variant_calibration = Column(Float)

    # Statistical significance
    p_value = Column(Float, nullable=True)  # Is improvement significant?
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)

    # Decision to advance/rollback
    decision = Column(String(50))  # ADVANCE, HALT, ROLLBACK
    decision_reason = Column(Text)
    decision_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

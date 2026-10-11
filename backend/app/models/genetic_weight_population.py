"""
Genetic Weight Population Models - Track evolving weight generations

Stores population of weight chromosomes, fitness scores, and evolution history.
Each generation produces 30 candidate weight sets; best performers survive.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import uuid


class GeneticWeightPopulation(Base):
    """Stores a generation of weight candidates."""

    __tablename__ = "genetic_weight_populations"

    population_id = Column(String(512), primary_key=True)
    generation_number = Column(Integer, nullable=False, index=True)
    orchestrator = Column(String(50), nullable=False, index=True)  # thunder, flash, interview, offer, finance
    tenant_id = Column(String(512), nullable=False, index=True)

    # Population metadata
    population_size = Column(Integer, default=30)
    generation_fitness_scores = Column(JSON)  # {chromosome_id: fitness_score}
    best_performer_id = Column(String(512), nullable=True)  # Which chromosome is best
    average_fitness = Column(Float)
    fitness_improvement = Column(Float, nullable=True)  # vs. previous generation

    # Evolution parameters used
    mutation_rate = Column(Float, default=0.15)
    crossover_type = Column(String(50), default="uniform")  # uniform, single_point
    elite_rate = Column(Float, default=0.20)

    # Convergence tracking
    generations_without_improvement = Column(Integer, default=0)
    has_converged = Column(Boolean, default=False)

    # Status
    status = Column(String(50), default="GENERATED")  # GENERATED, STAGED_FOR_AB_TEST, AB_TESTING, DEPLOYED, ROLLED_BACK
    ab_test_id = Column(String(512), nullable=True, index=True)  # Which A/B test deployed this
    deployed_at = Column(DateTime, nullable=True)

    # Metrics from actual deployment
    accuracy_improvement = Column(Float, nullable=True)  # vs. baseline
    calibration_gap_improvement = Column(Float, nullable=True)  # vs. baseline
    throughput_impact = Column(Float, nullable=True)  # % change

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chromosomes = relationship("GeneticWeightChromosome", back_populates="population")
    ab_tests = relationship("ABTestDeployment", back_populates="population")


class GeneticWeightChromosome(Base):
    """A single weight candidate in a population."""

    __tablename__ = "genetic_weight_chromosomes"

    chromosome_id = Column(String(512), primary_key=True)
    population_id = Column(String(512), ForeignKey("genetic_weight_populations.population_id", ondelete="CASCADE"))

    # The actual weights
    weight_schema = Column(JSON, nullable=False)  # {channel_weights, timing_weights, confidence_thresholds, bias_corrections}

    # Fitness evaluation
    fitness_score = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)  # 0-1
    calibration = Column(Float, nullable=True)  # 0-1 (1 = perfectly calibrated)
    throughput = Column(Float, nullable=True)  # decisions per minute
    diversity_bonus = Column(Float, default=0.0)  # Encourages population diversity

    # Selection status
    is_elite = Column(Boolean, default=False)
    selected_for_crossover = Column(Boolean, default=False)
    is_best_performer = Column(Boolean, default=False)

    # Genealogy (for understanding evolution)
    parent_1_id = Column(String(512), nullable=True)  # Which chromosome in previous generation
    parent_2_id = Column(String(512), nullable=True)
    mutation_applied = Column(Boolean, default=False)

    # Performance when deployed
    decisions_evaluated = Column(Integer, default=0)
    success_rate = Column(Float, nullable=True)  # When deployed in A/B test

    created_at = Column(DateTime, default=datetime.utcnow)
    population = relationship("GeneticWeightPopulation", back_populates="chromosomes")


class WeightDeploymentHistory(Base):
    """Audit trail of all weight deployments."""

    __tablename__ = "weight_deployment_history"

    deployment_id = Column(String(512), primary_key=True)
    generation_number = Column(Integer, nullable=False, index=True)
    orchestrator = Column(String(50), nullable=False, index=True)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Which weight was deployed
    chromosome_id = Column(String(512), nullable=False)
    weight_schema = Column(JSON, nullable=False)  # Snapshot of deployed weights

    # Deployment details
    deployed_at = Column(DateTime, default=datetime.utcnow)
    deployment_stage = Column(String(50))  # EXPERIMENT, EXPAND, FULL_ROLLOUT
    ab_test_id = Column(String(512), nullable=True)

    # Performance
    performance_metrics = Column(JSON)  # {accuracy, calibration, throughput, etc.}
    rollback_reason = Column(String(512), nullable=True)
    rolled_back = Column(Boolean, default=False)
    rolled_back_at = Column(DateTime, nullable=True)

    # Behavioral changes triggered
    rules_triggered = Column(JSON)  # [{rule_name, action, timestamp}]
    signals_sent = Column(JSON)  # [{signal_type, destination_orchestrator, timestamp}]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

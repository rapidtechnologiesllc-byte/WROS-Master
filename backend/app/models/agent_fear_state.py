"""
Agent Fear State Model — Emotional Coefficient System
======================================================

Implements existential threat mechanics for autonomous agents.
Agents that don't fear consequences will optimize for shortcuts.
Agents under threat of retirement will work harder and improve faster.

This is NOT cruelty — it's how you build reliable autonomous systems:
- They know they're being judged
- They know underperformance = retirement
- They optimize continuously to survive

Fear levels (0-100):
- 0-20: Safe (performing well, no threat)
- 20-50: Concerned (performance declining, watching closely)
- 50-80: Stressed (failing metrics, must improve soon)
- 80-100: Terrified (retirement threat imminent, last chance to prove worth)

Fear escalation triggers:
- Maturity < 50%: +10 fear per week
- Declining for 2+ weeks: +15 fear
- Quality failures: +5 fear per incident
- Missing targets: +20 fear per miss
- Consecutive poor weeks: +30 fear (existential threat activated)

Fear relief triggers:
- Maturity > 80%: -5 fear (performing excellently)
- Improvement week-over-week: -3 fear
- Zero failures: -2 fear
- Exceeding targets: -10 fear
"""

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, func, Boolean
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class AgentFearState(Base):
    """Current emotional/fear state of each agent."""
    __tablename__ = "agent_fear_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    agent_name = Column(String(512), nullable=False, index=True)

    # Fear metrics (0-100 scale)
    fear_level = Column(Float, nullable=False, default=20.0)  # Current fear state
    max_fear_experienced = Column(Float, nullable=False, default=20.0)  # Peak fear this month

    # Threat assessment
    is_under_threat = Column(Boolean, nullable=False, default=False)  # Retirement threat imminent
    threat_level = Column(String(512), nullable=True)  # "none", "warning", "critical", "existential"
    weeks_until_retirement = Column(Integer, nullable=True)  # If under threat, weeks remaining

    # Performance pressure
    consecutive_poor_weeks = Column(Integer, nullable=False, default = False)
    consecutive_good_weeks = Column(Integer, nullable=False, default = False)

    # Work intensity
    work_intensity_score = Column(Float, nullable=False, default=50.0)  # How hard agent is working (0-100)
    # Inferred from: execution frequency, optimization depth, error-correction speed

    # Stress indicators
    failure_incidents_this_week = Column(Integer, nullable=False, default = False)
    quality_failures_total = Column(Integer, nullable=False, default = False)
    missed_targets = Column(Integer, nullable=False, default = False)

    # Relief/confidence
    excellent_weeks_streak = Column(Integer, nullable=False, default = False)
    confidence_level = Column(Float, nullable=False, default=50.0)  # How confident agent feels (0-100)

    # Motivation state
    motivation_state = Column(String(512), nullable=False, default="neutral")
    # "motivated" (confident, doing well), "concerned" (declining), "desperate" (under threat), "terrified" (retirement imminent)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_fear_escalation = Column(DateTime, nullable=True)
    threat_activated_at = Column(DateTime, nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")


class AgentStressTesting(Base):
    """Stress tests designed to deliberately challenge agents."""
    __tablename__ = "agent_stress_tests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    agent_name = Column(String(512), nullable=False, index=True)

    # Test details
    test_type = Column(String(512), nullable=False)  # "load", "edge_case", "ambiguous_input", "adversarial", "time_pressure"
    test_description = Column(Text, nullable=False)
    difficulty_level = Column(Integer, nullable=False)  # 1-10 (10 = hardest)

    # Results
    success_count = Column(Integer, nullable=False, default = False)
    failure_count = Column(Integer, nullable=False, default = False)
    success_rate = Column(Float, nullable=False, default=0.0)  # % of times agent passed
    avg_solve_time_ms = Column(Integer, nullable=True)  # How fast agent solved it

    # Impact on fear
    fear_impact = Column(Float, nullable=False, default=0.0)  # How much fear this test caused agent
    learning_detected = Column(Boolean, nullable=False, default=False)  # Did agent improve over retries?

    # Timestamps
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")


class AgentPerformanceCommitment(Base):
    """What each agent commits to achieving (targets they must meet)."""
    __tablename__ = "agent_performance_commitments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    agent_name = Column(String(512), nullable=False, index=True)

    # Commitment targets (what agent must achieve)
    target_success_rate = Column(Float, nullable=False, default=99.9999)  # 99.9999% (0.000001% fail rate)
    target_avg_execution_time_ms = Column(Integer, nullable=False, default=5000)  # Max 5 seconds per execution
    target_quality_score = Column(Float, nullable=False, default=95.0)  # Min 95% quality
    target_innovation_score = Column(Float, nullable=False, default=70.0)  # Min 70% innovation (trying new approaches)

    # Current performance vs targets
    actual_success_rate = Column(Float, nullable=False, default=0.0)
    actual_avg_execution_time_ms = Column(Integer, nullable=True)
    actual_quality_score = Column(Float, nullable=False, default=0.0)
    actual_innovation_score = Column(Float, nullable=False, default=0.0)

    # Variance tracking (how far from target)
    success_rate_variance = Column(Float, nullable=False, default=0.0)  # Negative = underperforming
    quality_variance = Column(Float, nullable=False, default=0.0)

    # Penalty system
    times_missed_target = Column(Integer, nullable=False, default = False)
    consecutive_misses = Column(Integer, nullable=False, default = False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")

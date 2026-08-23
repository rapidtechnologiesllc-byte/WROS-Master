"""Agent State Target Model - Strategic alignment & performance accountability."""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from datetime import datetime
from app.models.base import Base


class AgentStateTarget(Base):
    """Agent's strategic contribution, targets, and accountability metrics."""

    __tablename__ = "agent_state_targets"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, unique=True)
    agent_domain = Column(String, nullable=False)  # e.g., "recruitment", "finance", "hr"
    agent_tier = Column(String, nullable=False)  # tier_1_core, tier_2_resource, etc.

    # STRATEGIC ALIGNMENT
    contributes_to_revenue = Column(Boolean, default=False)  # feeds $100M goal
    contributes_to_headcount = Column(Boolean, default=False)  # feeds 2000 employee goal
    strategic_importance = Column(String, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    how_helps_grow = Column(Text)  # "Recruits candidates → converts to employees → scales headcount"

    # 2030 LONG-TERM TARGET
    target_2030_value = Column(Float)  # e.g., 2000 (for headcount agents)
    target_2030_unit = Column(String)  # "headcount", "USD", "candidates", "%", "days"
    target_2030_deadline = Column(String, default="2030-12-31")

    # FY TARGET (current fiscal year)
    fy_year = Column(Integer)  # 2026, 2027, etc.
    fy_target_value = Column(Float)  # e.g., 250 (for this year)
    fy_target_unit = Column(String)  # same as 2030_unit
    fy_deadline = Column(String)  # "2026-12-31"

    # MINIMUM ACCEPTABLE PERFORMANCE (kill switch threshold)
    min_success_rate = Column(Float, default=95.0)  # % — below this: consider kill switch
    min_executions_per_day = Column(Integer, default = True)
    min_quality_score = Column(Float, default=70.0)  # 0-100

    # ACCELERATION REQUIREMENTS
    acceleration_multiplier_for_2030 = Column(Float)  # How many times faster to hit 2030
    acceleration_multiplier_for_fy = Column(Float)  # How many times faster to hit FY

    # STATUS
    status = Column(String, default="OPERATIONAL")  # OPERATIONAL, IN_DEVELOPMENT, PLANNED, BETA, DEPRECATED, DISABLED
    enabled = Column(Boolean, default=True)
    kill_switch_reason = Column(Text)  # Why was it disabled
    disabled_at = Column(DateTime, default=None)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentActualPerformance(Base):
    """Daily actual performance vs targets."""

    __tablename__ = "agent_actual_performance"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD

    # ACTUAL ACHIEVEMENT
    actual_value = Column(Float)  # e.g., 48 candidates hired this month
    actual_unit = Column(String)  # should match target unit

    # METRICS
    success_rate = Column(Float)  # 0-100%
    executions_count = Column(Integer)  # how many times ran
    avg_execution_time_ms = Column(Integer)
    error_count = Column(Integer, default = False)
    quality_score = Column(Float)  # 0-100

    # CALCULATED FIELDS
    progress_to_fy_pct = Column(Float)  # % toward FY target
    progress_to_2030_pct = Column(Float)  # % toward 2030 target

    created_at = Column(DateTime, default=datetime.utcnow)


class AgentFearScore(Base):
    """Agent stress/anxiety based on gap from targets."""

    __tablename__ = "agent_fear_scores"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, unique=True)
    date = Column(String, nullable=False)  # YYYY-MM-DD

    # FEAR CALCULATION: 20 + (gap_pct * 0.8)
    # If 42% behind: 20 + 42*0.8 = 53.6
    fear_score = Column(Float)  # 0-100

    # BREAKDOWN
    base_fear = Column(Float, default=20.0)  # baseline
    gap_from_fy_target = Column(Float)  # % behind FY
    gap_from_2030_target = Column(Float)  # % behind 2030 trajectory

    # STRESS LEVELS (motivation states)
    stress_level = Column(String)  # motivated (0-20), neutral (20-40), concerned (40-60), desperate (60-80), terrified (80+)

    # THREAT ASSESSMENT
    threat_level = Column(String)  # none, warning (50-70), critical (70-80), existential (80+)
    is_kill_switch_candidate = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class AgentIssue(Base):
    """Current issues blocking agent progress."""

    __tablename__ = "agent_issues"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)

    issue_description = Column(Text)  # "Only running 4x/week instead of daily"
    severity = Column(String)  # CRITICAL, HIGH, MEDIUM, LOW
    blocking = Column(Boolean, default=False)  # Does this block progress to goal?

    potential_impact = Column(Text)  # "Losing 500 candidates/month due to slow screening"
    root_cause = Column(Text)  # "Rate limiting on LinkedIn API"

    created_at = Column(DateTime, default=datetime.utcnow)


class AgentImprovement(Base):
    """Actions to improve agent toward targets."""

    __tablename__ = "agent_improvements"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)

    action = Column(Text)  # "Run daily instead of 4x/week"
    expected_impact = Column(Text)  # "Potential +1500 candidates/month"
    effort_estimate = Column(String)  # LOW, MEDIUM, HIGH
    effort_days = Column(Integer)  # Days to implement
    owner = Column(String)  # Who fixes it
    priority = Column(String)  # CRITICAL, HIGH, MEDIUM, LOW

    created_at = Column(DateTime, default=datetime.utcnow)

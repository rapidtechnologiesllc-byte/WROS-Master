import logging
"""Database migration: Create Agent State tracking tables."""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import os

Base = declarative_base()

logger = logging.getLogger(__name__)

class AgentStateTarget(Base):
    """Agent's strategic targets and accountability metrics."""
    __tablename__ = "agent_state_targets"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, unique=True)
    agent_domain = Column(String, nullable=False)
    agent_tier = Column(String, nullable=False)

    contributes_to_revenue = Column(Boolean, default=False)
    contributes_to_headcount = Column(Boolean, default=False)
    strategic_importance = Column(String, default="MEDIUM")
    how_helps_grow = Column(Text)

    target_2030_value = Column(Float)
    target_2030_unit = Column(String)
    target_2030_deadline = Column(String, default="2030-12-31")

    fy_year = Column(Integer)
    fy_target_value = Column(Float)
    fy_target_unit = Column(String)
    fy_deadline = Column(String)

    min_success_rate = Column(Float, default=95.0)
    min_executions_per_day = Column(Integer, default=1)
    min_quality_score = Column(Float, default=70.0)

    acceleration_multiplier_for_2030 = Column(Float)
    acceleration_multiplier_for_fy = Column(Float)

    status = Column(String, default="OPERATIONAL")
    enabled = Column(Boolean, default=True)
    kill_switch_reason = Column(Text)
    disabled_at = Column(DateTime, default=None)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentActualPerformance(Base):
    """Daily actual performance tracking."""
    __tablename__ = "agent_actual_performance"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)
    date = Column(String, nullable=False)

    actual_value = Column(Float)
    actual_unit = Column(String)

    success_rate = Column(Float)
    executions_count = Column(Integer)
    avg_execution_time_ms = Column(Integer)
    error_count = Column(Integer, default=0)
    quality_score = Column(Float)

    progress_to_fy_pct = Column(Float)
    progress_to_2030_pct = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

class AgentFearScore(Base):
    """Agent stress/anxiety tracking."""
    __tablename__ = "agent_fear_scores"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, unique=True)
    date = Column(String, nullable=False)

    fear_score = Column(Float)
    base_fear = Column(Float, default=20.0)
    gap_from_fy_target = Column(Float)
    gap_from_2030_target = Column(Float)

    stress_level = Column(String)
    threat_level = Column(String)
    is_kill_switch_candidate = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

class AgentIssue(Base):
    """Current issues blocking agent progress."""
    __tablename__ = "agent_issues"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)

    issue_description = Column(Text)
    severity = Column(String)
    blocking = Column(Boolean, default=False)

    potential_impact = Column(Text)
    root_cause = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

class AgentImprovement(Base):
    """Recommended improvements for agents."""
    __tablename__ = "agent_improvements"

    id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False)

    action = Column(Text)
    expected_impact = Column(Text)
    effort_estimate = Column(String)
    effort_days = Column(Integer)
    owner = Column(String)
    priority = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)

def run_migration():
    """Execute migration to create agent state tables.

    Requires DATABASE_URL environment variable set to a PostgreSQL connection string.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable must be set. "
            "PostgreSQL is the only supported database."
        )
    if not db_url.startswith("postgresql://"):
        raise ValueError(
            f"DATABASE_URL must use PostgreSQL protocol. Got: {db_url.split('://')[0]}://..."
        )

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    print("[OK] Agent State tables created successfully")

if __name__ == "__main__":
    run_migration()

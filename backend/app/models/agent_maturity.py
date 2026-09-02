"""
Agent Maturity Tracking — Performance Metrics & Learning Curves
import logging
================================================================

Tracks agent performance over time for the Reporting/Oversight agent.
Enables identification of agents that are improving vs. stagnating vs. declining.

Models:
- AgentMaturityLevel: Current capability snapshot (updated weekly)
- AgentPerformanceMetric: Weekly performance rollup (for trends & history)
"""

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, func, Boolean
)
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)

class AgentMaturityLevel(Base):
    """
    Current maturity/capability level of each agent.
    Updated weekly by the reporting agent based on execution metrics.
    """
    __tablename__ = "agent_maturity_levels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)

    agent_name = Column(String(512), nullable=False, index=True)  # e.g., "Recruitment", "Resource Manager", etc.
    maturity_level = Column(Float, nullable=False, default=0.0)  # 0-100 scale
    success_rate = Column(Float, nullable=False, default=0.0)  # % of successful executions
    avg_execution_time_ms = Column(Integer, nullable=True)  # Average execution time in milliseconds
    total_executions = Column(Integer, nullable=False, default = False)  # Total executions tracked
    total_successes = Column(Integer, nullable=False, default = False)  # Total successful executions
    quality_score = Column(Float, nullable=True)  # LLM-assessed quality (0-100)

    # Trend tracking
    previous_week_maturity = Column(Float, nullable=True)  # For calculating week-over-week change
    improvement_percentage = Column(Float, nullable=True)  # (current - previous) / previous * 100
    trend_direction = Column(String(20), nullable=True, default="stable")  # "improving", "stable", "declining"

    # Status & lifecycle
    is_active = Column(Boolean, nullable=False, default=True)
    is_retired = Column(Boolean, nullable=False, default=False)
    retirement_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), index=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)
    last_calculated_at = Column(DateTime, nullable=True)  # When metrics were last recalculated

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")


class AgentPerformanceMetric(Base):
    """
    Weekly performance snapshots for trend analysis and historical tracking.
    Allows visualization of agent improvement over time.
    """
    __tablename__ = "agent_performance_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)

    agent_name = Column(String(512), nullable=False, index=True)
    week_starting = Column(DateTime, nullable=False, index=True)  # Monday of the week

    # Performance metrics
    executions_count = Column(Integer, nullable=False, default = False)
    success_count = Column(Integer, nullable=False, default = False)
    failure_count = Column(Integer, nullable=False, default = False)
    success_rate = Column(Float, nullable=False, default=0.0)  # %

    # Quality metrics
    avg_execution_time_ms = Column(Integer, nullable=True)
    min_execution_time_ms = Column(Integer, nullable=True)
    max_execution_time_ms = Column(Integer, nullable=True)
    quality_score = Column(Float, nullable=True)  # 0-100

    # Context
    top_error_type = Column(String(512), nullable=True)  # Most common error
    error_count = Column(Integer, nullable=False, default = False)
    notes = Column(Text, nullable=True)  # Reporting agent's notes on performance

    # Maturity assessment
    maturity_level = Column(Float, nullable=False, default=0.0)  # 0-100
    maturity_change = Column(Float, nullable=True)  # Change from previous week

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    calculated_at = Column(DateTime, nullable=False, server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")

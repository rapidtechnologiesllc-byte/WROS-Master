"""
Agent Maturity Schemas — Admin Dashboard
========================================
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AgentMaturityLevelResponse(BaseModel):
    """Current maturity snapshot for an agent."""
    id: int
    agent_name: str
    maturity_level: float  # 0-100
    success_rate: float  # %
    avg_execution_time_ms: Optional[int]
    total_executions: int
    total_successes: int
    quality_score: Optional[float]

    # Trend
    improvement_percentage: Optional[float]  # Week-over-week %
    trend_direction: Optional[str]  # "improving", "stable", "declining"

    # Status
    is_active: bool
    is_retired: bool
    retirement_reason: Optional[str]

    last_updated: datetime
    last_calculated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentPerformanceMetricResponse(BaseModel):
    """Weekly performance snapshot."""
    id: int
    agent_name: str
    week_starting: datetime

    executions_count: int
    success_count: int
    failure_count: int
    success_rate: float

    avg_execution_time_ms: Optional[int]
    min_execution_time_ms: Optional[int]
    max_execution_time_ms: Optional[int]
    quality_score: Optional[float]

    top_error_type: Optional[str]
    error_count: int

    maturity_level: float
    maturity_change: Optional[float]

    class Config:
        from_attributes = True


class AgentMaturityDashboardResponse(BaseModel):
    """Complete dashboard view with current status + trend."""
    agent_name: str
    current_maturity: AgentMaturityLevelResponse
    recent_metrics: list[AgentPerformanceMetricResponse]  # Last 12 weeks

    # Summary stats
    trend: str  # "improving", "stable", "declining"
    improvement_rate: float  # % per week
    weeks_improving: int  # Consecutive weeks of improvement
    status: str  # "active", "retired", "struggling"


class AllAgentsMaturitiesResponse(BaseModel):
    """Dashboard for all agents."""
    agents: list[AgentMaturityLevelResponse]
    last_calculated: datetime
    next_calculation: datetime


class RetireAgentRequest(BaseModel):
    """Request to retire an underperforming agent."""
    agent_name: str
    reason: str  # e.g., "Maturity declined for 4+ consecutive weeks"


class RetireAgentResponse(BaseModel):
    """Response when agent is retired."""
    agent_name: str
    status: str
    message: str
    retired_at: datetime

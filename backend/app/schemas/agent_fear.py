"""
Agent Fear State Schemas
========================
import logging
"""

import logging
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.logging import logger

logger = logging.getLogger(__name__)

class AgentFearStateResponse(BaseModel):
    """Current fear state of an agent."""
    agent_name: str
    fear_level: float  # 0-100
    motivation_state: str  # motivated, neutral, concerned, desperate, terrified
    is_under_threat: bool
    threat_level: Optional[str]  # none, warning, critical, existential
    weeks_until_retirement: Optional[int]
    max_fear_experienced: float
    consecutive_poor_weeks: int
    consecutive_good_weeks: int
    work_intensity_score: float  # How hard agent is working
    confidence_level: float
    last_updated: datetime

    class Config:
        from_attributes = True


class FearDashboardResponse(BaseModel):
    """Dashboard showing all agents under threat."""
    agents_under_threat: list[dict]
    count_terrified: int  # Fear > 80
    count_desperate: int  # Fear 60-80
    count_at_risk: int  # Fear 50-60


class RetirementEligibilityResponse(BaseModel):
    """Check if agent should be retired."""
    eligible_for_retirement: bool
    reasons: list[str]
    fear_level: float
    success_rate: float
    quality_score: Optional[float]


class AgentPerformanceCommitmentResponse(BaseModel):
    """Agent's performance targets and current vs actual."""
    agent_name: str
    target_success_rate: float  # 99.9999%
    target_avg_execution_time_ms: int
    target_quality_score: float
    target_innovation_score: float

    actual_success_rate: float
    actual_avg_execution_time_ms: Optional[int]
    actual_quality_score: float
    actual_innovation_score: float

    success_rate_variance: float
    quality_variance: float
    times_missed_target: int
    consecutive_misses: int

    class Config:
        from_attributes = True

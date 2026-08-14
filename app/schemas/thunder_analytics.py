"""Pydantic Schemas -- S-071/HRMS-0471 AI Recruiter Performance Analytics."""
from typing import List, Optional

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    qualification_rate: int
    escalation_rate: float
    ghosting_rate: float
    avg_days_to_qualify: Optional[float] = None
    avg_messages_per_candidate: float
    human_intervention_rate: float
    human_dependency_target_pct: int
    candidates_reached: int
    candidates_responded: int
    jobs_connected_to_thunder: int


class TrendPoint(BaseModel):
    date: str
    qualifications: int
    escalations: int
    ghostings: int
    new_candidates: int


class TopRiskCandidate(BaseModel):
    candidate_id: str
    name: str
    drop_risk_score: int
    risk_level: str


class AgentActionsBreakdown(BaseModel):
    thunder_actions: int
    human_actions: int
    thunder_pct: float


class ThunderAnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    trends: List[TrendPoint]
    top_risk_candidates: List[TopRiskCandidate]
    agent_actions_breakdown: AgentActionsBreakdown

"""Pydantic Schemas -- S-063/HRMS-0463 Candidate Risk Dashboard."""
import logging
from typing import List

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RiskSummary(BaseModel):
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class CandidateAtRisk(BaseModel):
    candidate_id: str
    name: str
    drop_risk_score: int
    risk_level: str
    stage: str
    top_risk_signal: str


class SentimentTrendPoint(BaseModel):
    date: str
    avg_positive_pct: int
    avg_negative_pct: int


class StageRiskBreakdown(BaseModel):
    stage: str
    avg_risk_score: int
    candidate_count: int


class RiskDashboardResponse(BaseModel):
    risk_summary: RiskSummary
    candidates_at_risk: List[CandidateAtRisk]
    sentiment_trend: List[SentimentTrendPoint]
    stage_risk_breakdown: List[StageRiskBreakdown]

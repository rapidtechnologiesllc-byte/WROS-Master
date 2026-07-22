"""
Pydantic schemas — HRMS-1105 (canonical S-320) Resource Management Agent API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ScanTriggerResponse(BaseModel):
    core_pull_events_triggered: int
    recommendations_created: int


class RecommendationItem(BaseModel):
    id: str
    status: str
    confidence_pct: float
    rationale: Optional[str] = None
    created_at: Optional[datetime] = None
    pursued_by: Optional[str] = None
    pursued_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    employee_id: str
    employee_name: str
    employee_current_title: Optional[str] = None
    employee_delivery_engine: Optional[str] = None

    demand_id: str
    demand_job_title: str
    client_name: Optional[str] = None


class RecommendationQueueResponse(BaseModel):
    recommendations: List[RecommendationItem]


class RecommendationActionResponse(BaseModel):
    message: str
    recommendation: RecommendationItem


class ApproveRecommendationResponse(BaseModel):
    message: str
    recommendation: RecommendationItem
    allocation_id: str

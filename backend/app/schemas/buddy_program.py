from app.core.logging import logger
"""Pydantic schemas -- S-364 Buddy KPI Tracking + S-365 Graduation Gate."""
from datetime import date, datetime
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BuddyProgramRecordCreateRequest(BaseModel):
    employee_id: str
    buddy_engineer_user_id: str
    program_start_date: date
    expected_end_date: date


class BuddyProgramRecordResponse(BaseModel):
    id: str
    employee_id: str
    buddy_engineer_user_id: str
    program_start_date: date
    expected_end_date: date
    actual_end_date: Optional[date]
    status: str
    extension_count: int
    extension_reason: Optional[str]
    bu_head_decision_notes: Optional[str]

    class Config:
        from_attributes = True


class WeeklyScoresSubmitRequest(BaseModel):
    week_number: int
    scores: Dict[int, int]  # kpi_number -> score (1-5)


class ScorecardResponse(BaseModel):
    buddy_record_id: str
    complete_weeks: List[int]
    incomplete_weeks: List[int]
    per_kpi_averages: Dict[int, float]
    category_averages: Dict[str, Optional[float]]
    weighted_overall_score: Optional[float]
    trajectory: Optional[str]
    lowest_scoring_kpis: List[dict]


class GraduationDecisionRequest(BaseModel):
    notes: Optional[str] = None

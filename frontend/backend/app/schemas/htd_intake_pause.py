"""Pydantic schemas -- S-359/HRMS-P511 (HTD Intake Pause Engine) API."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CalculateMonthlyMetricRequest(BaseModel):
    month: date  # any date within the target month; normalized to month_start


class MonthlyMetricItem(BaseModel):
    id: str
    month_start: date
    cohort_size: int
    converted: int
    conversion_rate: Optional[float] = None


class HtdIntakeStatusResponse(BaseModel):
    is_paused: bool
    paused_at: Optional[datetime] = None
    pause_reason: Optional[str] = None


class ResumeIntakeRequest(BaseModel):
    audit_findings: str = Field(..., min_length=200)
    corrective_actions: str = Field(..., min_length=200)


class PauseLogItem(BaseModel):
    id: str
    action: str
    reason: Optional[str] = None
    audit_findings: Optional[str] = None
    corrective_actions: Optional[str] = None
    resumed_by: Optional[str] = None
    created_at: Optional[datetime] = None


class PauseLogResponse(BaseModel):
    entries: List[PauseLogItem]

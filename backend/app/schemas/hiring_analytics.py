"""Hiring analytics: source of hire, recruiter results, open positions against hires."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class FunnelRow(BaseModel):
    label: str
    recruiter_id: Optional[str] = None
    added: int
    interviewed: int
    offered: int
    accepted: int
    hired: int
    rejected: int
    hire_rate_pct: Optional[float]
    avg_days_to_offer: Optional[float]


class PositionRow(BaseModel):
    job_id: str
    title: Optional[str]
    positions: int
    hired: int
    offers_out: int
    in_progress: int
    still_to_hire: int
    opened_on: Optional[date]


class PositionTotals(BaseModel):
    positions: int
    hired: int
    offers_out: int
    in_progress: int
    still_to_hire: int


class HiringAnalyticsResponse(BaseModel):
    date_from: date
    date_to: date
    totals: FunnelRow
    sources: List[FunnelRow]
    recruiters: List[FunnelRow]
    positions: List[PositionRow]
    position_totals: PositionTotals

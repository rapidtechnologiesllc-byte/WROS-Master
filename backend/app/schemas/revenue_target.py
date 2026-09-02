from datetime import datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BUTargetCreateRequest(BaseModel):
    business_unit_id: int
    target_period: str
    fiscal_year: int
    target_amount_usd_cents: int
    notes: Optional[str] = None


class BUTargetVsActualResponse(BaseModel):
    business_unit_id: int
    target_period: str
    fiscal_year: int
    target_amount_usd_cents: int
    actual_usd_cents: int
    variance_usd_cents: int
    status: str


class PartnerGoalCreateRequest(BaseModel):
    partner_user_id: str
    target_period: str
    fiscal_year: int
    target_amount_usd_cents: int
    notes: Optional[str] = None


class PartnerGoalItem(BaseModel):
    id: int
    partner_user_id: str
    target_period: str
    fiscal_year: int
    target_amount_usd_cents: int
    created_by: Optional[str]
    created_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class PartnerYearPosition(BaseModel):
    fiscal_year: int
    target_amount_usd_cents: int
    actual_usd_cents: int
    variance_usd_cents: int
    cumulative_deficit_usd_cents: int
    current_fy_surplus_usd_cents: int


class PartnerMultiYearPositionResponse(BaseModel):
    partner_user_id: str
    years: list[PartnerYearPosition]
    cumulative_deficit_usd_cents: int
    current_fy_surplus_usd_cents: int


class BUDashboardBucket(BaseModel):
    business_unit_id: Optional[int]
    pipeline_usd_cents: int
    won_usd_cents: int
    weighted_forecast_usd_cents: int


class ExecutiveRevenueDashboardResponse(BaseModel):
    total_pipeline_usd_cents: int
    won_usd_cents: int
    lost_usd_cents: int
    weighted_forecast_usd_cents: int
    by_business_unit: list[BUDashboardBucket]


class PipelineCoverageResponse(BaseModel):
    revenue_target_usd_cents: int
    coverage_ratio: Optional[float]

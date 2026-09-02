from datetime import datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ForecastVsActualResponse(BaseModel):
    business_unit_id: Optional[int]
    year: int
    month: int
    actual_usd_cents: int
    forecast_usd_cents: int
    variance_usd_cents: int
    status: str


class ForecastVsActualTrendResponse(BaseModel):
    business_unit_id: Optional[int]
    year: int
    months: list[ForecastVsActualResponse]


class PipelineLeakageFlagItem(BaseModel):
    id: str
    pattern_type: str
    business_unit_id: Optional[int]
    opportunity_id: Optional[str]
    demand_id: Optional[str]
    revenue_leakage_flag_id: Optional[str]
    sub_vendor_request_id: Optional[str]
    estimated_impact_usd_cents: Optional[int]
    detail: Optional[str]
    detected_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]

    class Config:
        from_attributes = True


class PipelineLeakageScanResponse(BaseModel):
    flags: list[PipelineLeakageFlagItem]
    total_estimated_impact_usd_cents: int


class ResolveLeakageFlagRequest(BaseModel):
    resolution_note: Optional[str] = None

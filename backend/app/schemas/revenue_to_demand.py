import logging
from typing import Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class RevenueToDemandProjectionResponse(BaseModel):
    business_unit_id: int
    year: int
    month: int
    current_headcount: int
    trailing_avg_monthly_revenue_usd_cents: int
    revenue_per_head_usd_cents: Optional[int]
    forecast_usd_cents: int
    projected_headcount_needed: Optional[float]
    open_demand_headcount: int
    workforce_gap: Optional[float]

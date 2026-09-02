from datetime import date, datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SetCostRateConfigRequest(BaseModel):
    business_unit_id: Optional[int] = None
    statutory_pct: float
    overhead_pct: float
    effective_date: Optional[date] = None
    notes: Optional[str] = None


class CostRateConfigResponse(BaseModel):
    id: int
    business_unit_id: Optional[int]
    statutory_pct: float
    overhead_pct: float
    effective_date: date
    created_by: Optional[str]
    created_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class FullyLoadedCostResponse(BaseModel):
    employee_id: str
    base_salary_usd_cents: Optional[int]
    fully_loaded_cost_usd_cents: Optional[int]


class BlendedDeliveryRateResponse(BaseModel):
    business_unit_id: int
    year: int
    month: int
    blended_delivery_rate_usd_cents_per_hour: Optional[float]

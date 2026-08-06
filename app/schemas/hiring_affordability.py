from typing import Optional

from pydantic import BaseModel


class HiringAffordabilityResponse(BaseModel):
    business_unit_id: int
    affordable: Optional[bool]
    current_margin_pct: Optional[float]
    projected_margin_pct: Optional[float]
    proposed_monthly_fully_loaded_cost_usd_cents: Optional[int] = None
    reason: Optional[str]

from typing import Optional

from pydantic import BaseModel


class BuPnlResponse(BaseModel):
    business_unit_id: int
    year: int
    month: int
    revenue_usd_cents: int
    cost_usd_cents: Optional[int]
    gross_margin_usd_cents: Optional[int]
    margin_pct: Optional[float]
    cost_data_complete: bool

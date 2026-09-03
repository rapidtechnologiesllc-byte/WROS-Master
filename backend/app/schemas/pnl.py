import logging
from typing import Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class BuPnlResponse(BaseModel):
    business_unit_id: int
    year: int
    month: int
    revenue_usd_cents: int
    cost_usd_cents: Optional[int]
    gross_margin_usd_cents: Optional[int]
    margin_pct: Optional[float]
    cost_data_complete: bool


class BuPnlSummaryItem(BuPnlResponse):
    business_unit_name: str


class OrgPnlSummaryResponse(BaseModel):
    year: int
    month: int
    total_revenue_usd_cents: int
    total_cost_usd_cents: Optional[int]
    total_gross_margin_usd_cents: Optional[int]
    margin_pct: Optional[float]
    org_cost_data_complete: bool
    by_business_unit: list[BuPnlSummaryItem]

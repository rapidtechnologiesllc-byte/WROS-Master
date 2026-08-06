from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IncentiveRuleCreateRequest(BaseModel):
    partner_user_id: str
    incentive_type: str
    amount_usd_cents: Optional[int] = None
    revenue_share_pct: Optional[float] = None
    trigger_description: Optional[str] = None


class IncentiveRuleItem(BaseModel):
    id: str
    partner_user_id: str
    incentive_type: str
    amount_usd_cents: Optional[int]
    revenue_share_pct: Optional[float]
    trigger_description: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class IncentiveEventItem(BaseModel):
    id: str
    rule_id: str
    partner_user_id: str
    client_id: Optional[str]
    amount_usd_cents: int
    status: str
    triggered_at: Optional[datetime]
    paid_at: Optional[datetime]
    period_year: Optional[int] = None
    period_month: Optional[int] = None

    class Config:
        from_attributes = True


class IncentiveEventListResponse(BaseModel):
    events: list[IncentiveEventItem]


class RevenueShareCalculationResponse(BaseModel):
    event: Optional[IncentiveEventItem]
    already_calculated: bool

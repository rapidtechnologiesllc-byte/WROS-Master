from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RecordReserveFundEntryRequest(BaseModel):
    entry_type: str
    amount_usd_cents: int
    period_year: int
    period_month: int
    business_unit_id: Optional[int] = None
    notes: Optional[str] = None


class ReserveFundEntryResponse(BaseModel):
    id: int
    business_unit_id: Optional[int]
    entry_type: str
    amount_usd_cents: int
    period_year: int
    period_month: int
    created_by: Optional[str]
    created_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ReserveFundStatusResponse(BaseModel):
    business_unit_id: int
    balance_usd_cents: int
    target_usd_cents: Optional[int]
    gap_usd_cents: Optional[int]
    pct_funded: Optional[float]

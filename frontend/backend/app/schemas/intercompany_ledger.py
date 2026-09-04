from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class RecordIntercompanySettlementRequest(BaseModel):
    from_entity: str
    to_entity: str
    amount_usd_cents: int
    settlement_date: date
    reason: str


class IntercompanySettlementResponse(BaseModel):
    id: int
    from_entity: str
    to_entity: str
    amount_usd_cents: int
    settlement_date: date
    reason: str
    created_by: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class EntityNetPositionResponse(BaseModel):
    entity: str
    net_position_usd_cents: int

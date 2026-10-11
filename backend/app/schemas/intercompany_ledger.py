from datetime import date, datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RecordIntercompanySettlementRequest(BaseModel):
    from_entity: str
    to_entity: str
    amount_usd_cents: int
    settlement_date: date
    reason: str
    # BU the billed work belongs to (counts toward that BU / partner in the receiving company)
    business_unit_id: Optional[int] = None

class IntercompanySettlementResponse(BaseModel):
    id: int
    from_entity: str
    to_entity: str
    amount_usd_cents: int
    settlement_date: date
    reason: str
    business_unit_id: Optional[int] = None
    created_by: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class EntityNetPositionResponse(BaseModel):
    entity: str
    net_position_usd_cents: int

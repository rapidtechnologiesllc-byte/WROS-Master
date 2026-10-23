from datetime import date, datetime
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RecordIntercompanySettlementRequest(BaseModel):
    # the paying and the receiving company (Location ids); names are taken from the companies
    from_company_id: str
    to_company_id: str
    amount_usd_cents: int
    settlement_date: date
    reason: str
    # BU the billed work belongs to (counts toward that BU / partner in the receiving company)
    business_unit_id: Optional[int] = None

class LinkSettlementCompaniesRequest(BaseModel):
    from_company_id: str
    to_company_id: str

class IntercompanySettlementResponse(BaseModel):
    id: int
    from_company_id: Optional[str] = None  # None only on an old entry no company name matched
    to_company_id: Optional[str] = None
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

class CompanyNetPositionResponse(BaseModel):
    company_id: str
    entity: str  # the company's name
    net_position_usd_cents: int

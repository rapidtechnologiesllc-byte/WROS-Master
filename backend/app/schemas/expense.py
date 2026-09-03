from datetime import date, datetime
import logging
from typing import Optional

from pydantic import BaseModel
from app.core.logging import logger

logger = logging.getLogger(__name__)

class ExpenseCreateRequest(BaseModel):
    purpose: str
    expense_category: str
    amount_usd_cents: int
    expense_date: date
    client_id: Optional[str] = None
    conference_name: Optional[str] = None
    investment_label: Optional[str] = None
    travel_type: Optional[str] = None
    trip_label: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    receipt_ref: Optional[str] = None

class ExpenseItem(BaseModel):
    id: str
    logged_by_user_id: str
    business_unit_id: Optional[int]
    purpose: str
    client_id: Optional[str]
    conference_name: Optional[str]
    investment_label: Optional[str]
    expense_category: str
    travel_type: Optional[str]
    trip_label: Optional[str]
    amount_usd_cents: int
    location: Optional[str]
    description: Optional[str]
    receipt_ref: Optional[str]
    expense_date: date
    payment_status: str
    approved_by: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class ExpenseListResponse(BaseModel):
    expenses: list[ExpenseItem]

class ClientInvestmentPositionResponse(BaseModel):
    client_id: str
    company_name: str
    status: str
    prospect_since: Optional[datetime]
    converted_on: Optional[datetime]
    total_expense_usd_cents: int
    total_revenue_usd_cents: int
    net_position_usd_cents: int
    breakeven_date: Optional[date]
    expense_count: int

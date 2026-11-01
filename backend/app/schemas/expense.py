from datetime import date, datetime
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ClientSplit(BaseModel):
    """One client's part of a split: by percent, or by amount (every line the same way)."""
    client_id: str
    percent: Optional[float] = None
    amount_usd_cents: Optional[int] = None

class ExpenseCreateRequest(BaseModel):
    purpose: str
    expense_category: str
    amount_usd_cents: int
    expense_date: date
    # who the spend is on: INTERNAL / CLIENT (client_id) / SPLIT (client_splits)
    spend_for: Optional[str] = None
    client_id: Optional[str] = None
    client_splits: Optional[List[ClientSplit]] = None
    event_id: Optional[str] = None  # the shared conference (GET/POST /expense-events)
    investment_label: Optional[str] = None
    travel_type: Optional[str] = None
    trip_label: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    receipt_ref: Optional[str] = None

class ExpenseAttributionRequest(BaseModel):
    spend_for: str
    client_id: Optional[str] = None
    client_splits: Optional[List[ClientSplit]] = None
    event_id: Optional[str] = None

class ExpenseShareItem(BaseModel):
    client_id: str
    company_name: Optional[str] = None
    share_bps: int
    amount_usd_cents: int

    class Config:
        from_attributes = True

class ExpenseItem(BaseModel):
    id: str
    logged_by_user_id: str
    business_unit_id: Optional[int]
    purpose: str
    spend_for: Optional[str] = None
    client_id: Optional[str]
    client_name: Optional[str] = None
    client_shares: List[ExpenseShareItem] = []
    event_id: Optional[str] = None
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
    manager_approval_status: Optional[str] = None  # PENDING -> APPROVED/REJECTED (counts in P&L once APPROVED)
    manager_approved_by: Optional[str] = None
    payment_status: str
    approved_by: Optional[str]
    created_at: Optional[datetime]
    receipt_check_status: Optional[str] = None  # NOT_ATTACHED / MATCHED / MISMATCH / UNREADABLE
    receipt_check_detail: Optional[str] = None
    receipt_content_type: Optional[str] = None

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

class ExpenseEventCreateRequest(BaseModel):
    name: str
    year: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    confirm_new: bool = False  # "this really is a different event" after a near-match warning

class ExpenseEventItem(BaseModel):
    id: str
    name: str
    year: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    location: Optional[str] = None
    match_score: Optional[float] = None
    created: Optional[bool] = None

    class Config:
        from_attributes = True

class ExpenseEventListResponse(BaseModel):
    events: List[ExpenseEventItem]

class ExpenseEventMergeRequest(BaseModel):
    into_event_id: str

class EventClientCost(BaseModel):
    client_id: Optional[str]
    company_name: Optional[str]
    amount_usd_cents: int

class EventPersonCost(BaseModel):
    user_id: str
    name: str
    amount_usd_cents: int

class ExpenseEventSummaryResponse(BaseModel):
    event_id: str
    name: str
    year: int
    start_date: Optional[date]
    end_date: Optional[date]
    location: Optional[str]
    total_usd_cents: int
    approved_usd_cents: int
    pending_usd_cents: int
    expense_count: int
    by_client: List[EventClientCost]
    by_person: List[EventPersonCost]

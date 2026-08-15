from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseCreateRequest(BaseModel):
    purpose: str = Field(..., description="Expense purpose (CLIENT_CURRENT, CLIENT_PROSPECT, CONFERENCE, INVESTMENT, OTHER)")
    expense_category: str = Field(..., description="Expense category (TRAVEL, MEALS, LODGING, ENTERTAINMENT, OTHER)")
    amount_usd_cents: int = Field(..., gt=0, description="Amount in USD cents (must be positive)")
    expense_date: date = Field(..., description="Date the expense was incurred")
    receipt_ref: str = Field(..., description="Receipt reference (mandatory)")
    client_id: Optional[str] = Field(None, description="Required for CLIENT_CURRENT/CLIENT_PROSPECT purposes")
    conference_name: Optional[str] = Field(None, description="Required for CONFERENCE purpose")
    investment_label: Optional[str] = Field(None, description="Required for INVESTMENT purpose")
    travel_type: Optional[str] = Field(None, description="Travel type (AIRFARE, GROUND_TRANSPORT, HOTEL, MEALS, OTHER)")
    trip_label: Optional[str] = Field(None, description="Label for grouping related trip expenses")
    location: Optional[str] = Field(None, description="Location of the expense")
    description: Optional[str] = Field(None, description="Detailed description of the expense")


class ExpenseItem(BaseModel):
    id: str
    logged_by_user_id: str
    tenant_id: Optional[int] = None
    bu_context_id: Optional[int] = None
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
    receipt_ref: str
    expense_date: date
    manager_approval_status: str
    manager_approved_by: Optional[str]
    manager_approved_at: Optional[datetime]
    payment_status: str
    approved_by: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ExpenseApproveRequest(BaseModel):
    """Request to approve an expense at the manager level."""
    pass


class ExpenseReimbursementRequest(BaseModel):
    """Request to mark an expense as reimbursed."""
    pass


class ExpenseReimbursementStatus(BaseModel):
    """Response showing reimbursement status and timeline."""
    id: str
    logged_by_user_id: str
    amount_usd_cents: int
    expense_date: date
    manager_approval_status: str
    manager_approved_at: Optional[datetime]
    payment_status: str
    approved_at: Optional[datetime]
    reimbursed_at: Optional[datetime]
    days_pending: int
    days_awaiting_manager: int
    days_awaiting_finance: int
    is_fully_processed: bool


class ExpenseListResponse(BaseModel):
    expenses: list[ExpenseItem]


class ExpenseReimbursementTrackingResponse(BaseModel):
    """Response for tracking multiple reimbursements."""
    total_count: int
    pending_count: int
    approved_count: int
    reimbursed_count: int
    total_amount_usd_cents: int
    pending_amount_usd_cents: int
    reimbursements: list[ExpenseReimbursementStatus]


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

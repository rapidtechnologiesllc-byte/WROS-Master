"""
Partner/BU spend tracking, 2026-08-05.
Prefix: /expenses

POST /expenses                       -- self-service: log YOUR OWN expense
GET  /expenses/mine                  -- your own logged expenses
GET  /expenses                       -- all expenses (revenue.view -- BU Head/Partner/Finance/CEO review)
POST /expenses/{id}/approve          -- revenue.view_pnl (approval authority)
GET  /clients/{client_id}/investment-position -- full prospect-to-breakeven history

Create is deliberately self-service only (get_current_internal_user,
not an admin-gated dependency) -- Avinash: "the expense is logged by
employee so they need to login to their portal and add their expense."
logged_by_user_id is always the authenticated caller, never a request
field, same ownership boundary as the existing self-service timesheet.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.expense import ExpenseRecord
from app.models.user import Users
from app.schemas.expense import (
    ClientInvestmentPositionResponse, ExpenseCreateRequest, ExpenseItem, ExpenseListResponse,
)
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, get_client_investment_position, log_expense,
    mark_expense_paid,
)

router = APIRouter(tags=["expenses"])


@router.post("/expenses", response_model=ExpenseItem, status_code=201)
def create_expense(
    body: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    try:
        expense = log_expense(
            db, logged_by_user=current_user, purpose=body.purpose,
            expense_category=body.expense_category, amount_usd_cents=body.amount_usd_cents,
            expense_date=body.expense_date, client_id=body.client_id,
            conference_name=body.conference_name, investment_label=body.investment_label,
            travel_type=body.travel_type, trip_label=body.trip_label, location=body.location,
            description=body.description, receipt_ref=body.receipt_ref,
        )
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return expense


@router.get("/expenses/mine", response_model=ExpenseListResponse)
def list_my_expenses(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    expenses = (
        db.query(ExpenseRecord)
        .filter(ExpenseRecord.logged_by_user_id == current_user.UserID)
        .order_by(ExpenseRecord.expense_date.desc())
        .all()
    )
    return ExpenseListResponse(expenses=expenses)


@router.get("/expenses", response_model=ExpenseListResponse)
def list_all_expenses(
    client_id: Optional[str] = None,
    purpose: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    query = db.query(ExpenseRecord)
    if client_id:
        query = query.filter(ExpenseRecord.client_id == client_id)
    if purpose:
        query = query.filter(ExpenseRecord.purpose == purpose)
    expenses = query.order_by(ExpenseRecord.expense_date.desc()).all()
    return ExpenseListResponse(expenses=expenses)


@router.post("/expenses/{expense_id}/approve", response_model=ExpenseItem)
def approve_expense_endpoint(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    return approve_expense(db, expense, approved_by=current_user.UserID)


@router.post("/expenses/{expense_id}/mark-paid", response_model=ExpenseItem)
def mark_expense_paid_endpoint(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    try:
        return mark_expense_paid(db, expense)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/clients/{client_id}/investment-position", response_model=ClientInvestmentPositionResponse)
def get_investment_position(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    try:
        return get_client_investment_position(db, client_id)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

"""
Partner/BU spend tracking, 2026-08-05.
import logging
Prefix: /expenses

POST /expenses                       -- self-service: log YOUR OWN expense
GET  /expenses/mine                  -- your own logged expenses
GET  /expenses                       -- all expenses (revenue.view -- BU Head/Partner/Finance/CEO review)
POST /expenses/{id}/manager-approve  -- the assigned manager (or finance): counts in the P&L from now
POST /expenses/{id}/manager-reject   -- the assigned manager (or finance): never counts
POST /expenses/{id}/approve          -- finance approval for payment (after the manager)
POST /expenses/{id}/mark-paid        -- finance: reimbursed
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
    ExpenseValidationError, approve_expense, approve_manager_step, can_review_as_manager,
    get_client_investment_position, log_expense, mark_expense_paid, reject_manager_step,
)

router = APIRouter(tags=["expenses"])

@router.post(
    "/expenses",
    response_model=ExpenseItem,
    status_code=201,
    dependencies=[Depends(require_resource_permission("expenses", "create"))]
)
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

@router.get(
    "/expenses/mine",
    response_model=ExpenseListResponse,
    dependencies=[Depends(require_resource_permission("expenses", "view"))]
)
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

@router.get(
    "/expenses",
    response_model=ExpenseListResponse,
    dependencies=[Depends(require_resource_permission("expenses", "view"))]
)
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

def _expense_or_404(db: Session, expense_id: str, user: Users) -> ExpenseRecord:
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id,
                                             ExpenseRecord.tenant_id == user.tenant_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    return expense


@router.post(
    "/expenses/{expense_id}/manager-approve",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("expenses", "view"))]
)
def manager_approve_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    expense = _expense_or_404(db, expense_id, current_user)
    if not can_review_as_manager(db, expense, current_user):
        raise HTTPException(status_code=403, detail="Only the assigned manager or finance can review this expense.")
    try:
        return approve_manager_step(db, expense, approved_by=current_user.UserID)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/expenses/{expense_id}/manager-reject",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("expenses", "view"))]
)
def manager_reject_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    expense = _expense_or_404(db, expense_id, current_user)
    if not can_review_as_manager(db, expense, current_user):
        raise HTTPException(status_code=403, detail="Only the assigned manager or finance can review this expense.")
    try:
        return reject_manager_step(db, expense, rejected_by=current_user.UserID)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/expenses/{expense_id}/approve",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("expenses", "create"))]
)
def approve_expense_endpoint(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    expense = _expense_or_404(db, expense_id, current_user)
    try:
        return approve_expense(db, expense, approved_by=current_user.UserID)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/expenses/{expense_id}/mark-paid",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("expenses", "create"))]
)
def mark_expense_paid_endpoint(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    expense = _expense_or_404(db, expense_id, current_user)
    try:
        return mark_expense_paid(db, expense)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get(
    "/clients/{client_id}/investment-position",
    response_model=ClientInvestmentPositionResponse,
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
def get_investment_position(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    try:
        return get_client_investment_position(db, client_id)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

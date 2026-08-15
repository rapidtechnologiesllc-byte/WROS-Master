"""
Partner/BU spend tracking, 2026-08-05.
Prefix: /expenses

POST /expenses                              -- self-service: submit YOUR OWN expense
GET  /expenses/mine                         -- your own logged expenses
GET  /expenses/track-reimbursement          -- track your reimbursement status
GET  /expenses/track-reimbursement/all      -- track all reimbursements (manager/finance only)
GET  /expenses                              -- all expenses (revenue.view -- BU Head/Partner/Finance/CEO review)
POST /expenses/{id}/approve/manager         -- manager approval step
POST /expenses/{id}/approve/finance         -- finance approval (after manager approves)
POST /expenses/{id}/reimburse               -- mark as reimbursed (finance only)
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
from app.core.dependencies import get_current_internal_user, require_permission
from app.models.expense import ExpenseRecord
from app.models.user import Users
from app.schemas.expense import (
    ClientInvestmentPositionResponse, ExpenseCreateRequest, ExpenseItem, ExpenseListResponse,
    ExpenseReimbursementTrackingResponse,
)
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, approve_manager_step, get_client_investment_position,
    log_expense, mark_expense_paid, track_reimbursement,
)

router = APIRouter(tags=["expenses"])


@router.post("/expenses", response_model=ExpenseItem, status_code=201)
def submit_expense(
    body: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Submit an expense for reimbursement.

    Self-service endpoint: expense is always logged by the authenticated user.
    Creates the expense and automatically assigns it to the employee's manager
    for approval via a Task.
    """
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
    """List all expenses logged by the current user."""
    expenses = (
        db.query(ExpenseRecord)
        .filter(ExpenseRecord.logged_by_user_id == current_user.UserID)
        .order_by(ExpenseRecord.expense_date.desc())
        .all()
    )
    return ExpenseListResponse(expenses=expenses)


@router.get("/expenses/track-reimbursement", response_model=ExpenseReimbursementTrackingResponse)
def track_my_reimbursement(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Track your own expense reimbursement status and timeline.

    Returns summary and detailed breakdown of:
    - Time spent awaiting manager approval
    - Time spent awaiting finance approval
    - Total time in system
    """
    return track_reimbursement(db, user_id=current_user.UserID)


@router.get("/expenses/track-reimbursement/all", response_model=ExpenseReimbursementTrackingResponse)
def track_all_reimbursements(
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view")),
):
    """Track all expense reimbursements (manager/finance only).

    Returns summary and detailed breakdown of all expenses in the system.
    """
    return track_reimbursement(db)


@router.get("/expenses", response_model=ExpenseListResponse)
def list_all_expenses(
    client_id: Optional[str] = None,
    purpose: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view")),
):
    """List all expenses (revenue.view permission required).

    Optional filters:
    - client_id: Filter by client
    - purpose: Filter by purpose (CLIENT_CURRENT, CLIENT_PROSPECT, CONFERENCE, INVESTMENT, OTHER)
    - status: Filter by payment status (PENDING, APPROVED, REIMBURSED)
    """
    query = db.query(ExpenseRecord)
    if client_id:
        query = query.filter(ExpenseRecord.client_id == client_id)
    if purpose:
        query = query.filter(ExpenseRecord.purpose == purpose)
    if status:
        query = query.filter(ExpenseRecord.payment_status == status)
    expenses = query.order_by(ExpenseRecord.expense_date.desc()).all()
    return ExpenseListResponse(expenses=expenses)


@router.post("/expenses/{expense_id}/approve/manager", response_model=ExpenseItem)
def approve_expense_manager_step(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("employee.manage")),
):
    """Manager approval step in the expense workflow.

    Called by the employee's manager to approve/reject an expense.
    After manager approval, the expense moves to finance for final approval.
    """
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    try:
        return approve_manager_step(db, expense, approved_by=current_user.UserID)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/expenses/{expense_id}/approve/finance", response_model=ExpenseItem)
def approve_expense_finance_step(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    """Finance approval step in the expense workflow.

    Called by finance to approve an already manager-approved expense.
    After finance approval, the expense is ready to be marked as reimbursed.
    Finance is notified via email, and a Task is created to mark it paid.
    """
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    try:
        return approve_expense(db, expense, approved_by=current_user.UserID)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/expenses/{expense_id}/reimburse", response_model=ExpenseItem)
def reimburse_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_permission("revenue.view_pnl")),
):
    """Mark an approved expense as reimbursed.

    Called by finance after payment has been processed.
    Completes the approval workflow and closes the associated Task.
    """
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
    current_user: Users = Depends(require_permission("revenue.view")),
):
    """Get full prospect-to-breakeven investment position for a client.

    Returns:
    - Total spend on client (from prospect era through current)
    - Total revenue billed (from invoices)
    - Net position (revenue - expense)
    - Conversion date (prospect to active)
    - Breakeven date (when relationship turned net-positive)
    """
    try:
        return get_client_investment_position(db, client_id)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

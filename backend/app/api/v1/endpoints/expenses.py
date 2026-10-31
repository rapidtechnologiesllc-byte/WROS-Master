"""
Partner/BU spend tracking, 2026-08-05.
Prefix: /expenses

POST /expenses                       -- self-service: log YOUR OWN expense
GET  /expenses/mine                  -- your own logged expenses
GET  /expenses                       -- all expenses (revenue.view -- BU Head/Partner/Finance/CEO review)
POST /expenses/{id}/manager-approve  -- the assigned manager (or finance): counts in the P&L from now
POST /expenses/{id}/manager-reject   -- the assigned manager (or finance): never counts
POST /expenses/{id}/approve          -- finance approval for payment (after the manager)
POST /expenses/{id}/mark-paid        -- finance: reimbursed
GET  /clients/{client_id}/investment-position -- full prospect-to-breakeven history
PATCH /expenses/{id}/attribution     -- who the spend is on (and its conference), until it is decided
GET  /expense-events?q=              -- the team's shared conferences, closest match first
POST /expense-events                 -- pick-or-add a conference (same name+year = the same event)
GET  /expense-events/{id}/summary    -- one conference's cost: total, per client, per person
POST /expense-events/{id}/merge      -- finance: fold a duplicate conference into another

Create is deliberately self-service only (get_current_internal_user,
not an admin-gated dependency) -- Avinash: "the expense is logged by
employee so they need to login to their portal and add their expense."
logged_by_user_id is always the authenticated caller, never a request
field, same ownership boundary as the existing self-service timesheet.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.data_scope import client_bu_id, ensure_visible, expense_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.expense import ExpenseRecord
from app.models.user import Users
from app.schemas.expense import (
    ClientInvestmentPositionResponse, ExpenseAttributionRequest, ExpenseCreateRequest, ExpenseEventCreateRequest,
    ExpenseEventItem, ExpenseEventListResponse, ExpenseEventMergeRequest, ExpenseEventSummaryResponse, ExpenseItem,
    ExpenseListResponse,
)
from app.services.expense_event_service import (
    ExpenseEventError, NearDuplicateEventError, event_rollup, find_or_create_event, get_event, merge_events,
    search_events,
)
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, approve_manager_step, can_review_as_manager,
    get_client_investment_position, log_expense, mark_expense_paid, reject_manager_step, update_attribution,
)

router = APIRouter(tags=["expenses"])

@router.post(
    "/expenses",
    response_model=ExpenseItem,
    status_code=201,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))]  # self-service
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
            expense_date=body.expense_date, client_id=body.client_id, spend_for=body.spend_for,
            client_splits=[s.model_dump() for s in body.client_splits] if body.client_splits else None,
            event_id=body.event_id, investment_label=body.investment_label,
            travel_type=body.travel_type, trip_label=body.trip_label, location=body.location,
            description=body.description, receipt_ref=body.receipt_ref,
        )
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return expense

@router.get(
    "/expenses/mine",
    response_model=ExpenseListResponse,
    dependencies=[Depends(require_resource_permission("my-expenses", "view"))]  # self-service
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
    query = db.query(ExpenseRecord).filter(
        ExpenseRecord.tenant_id == current_user.tenant_id, expense_filter(db, current_user),
    )
    if client_id:  # its whole-client expenses and the splits that include it
        from app.models.expense import ExpenseClientShare

        query = query.filter(or_(ExpenseRecord.client_id == client_id, ExpenseRecord.id.in_(
            select(ExpenseClientShare.expense_id).where(ExpenseClientShare.client_id == client_id))))
    if purpose:
        query = query.filter(ExpenseRecord.purpose == purpose)
    expenses = query.order_by(ExpenseRecord.expense_date.desc()).all()
    return ExpenseListResponse(expenses=expenses)

def _expense_or_404(db: Session, expense_id: str, user: Users) -> ExpenseRecord:
    """One expense of the caller's tenant inside their business units (its client's BU, else its
    own BU -- app.core.data_scope), or one whose approval task is assigned to the caller (the
    logger's manager reviews it wherever it is attributed). Any other id is 404."""
    from app.models.task import Task

    assigned_to_me = ExpenseRecord.id.in_(select(Task.expense_id).where(
        Task.assigned_to_user_id == user.UserID, Task.expense_id.isnot(None)))
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id,
                                             ExpenseRecord.tenant_id == user.tenant_id,
                                             or_(expense_filter(db, user), assigned_to_me)).first()
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
    from app.models.client import Client

    if db.query(Client.id).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first() is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    ensure_visible(db, current_user, client_bu_id(db, client_id), f"Client {client_id!r}")
    try:
        return get_client_investment_position(db, client_id)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/expenses/{expense_id}/receipt",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
async def upload_expense_receipt(
    expense_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Attach the receipt to your own expense; it is read and checked straight away
    (app.services.expense_receipt_service)."""
    from app.services.expense_receipt_service import ReceiptError, attach_and_check

    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id,
                                             ExpenseRecord.tenant_id == current_user.tenant_id,
                                             ExpenseRecord.logged_by_user_id == current_user.UserID).first()
    if expense is None:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    try:
        return attach_and_check(db, expense, file.filename, file.content_type, await file.read())
    except ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/expenses/{expense_id}/receipt")
def download_expense_receipt(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The receipt file: the person who logged it, their reviewer, or anyone who may see the expense."""
    import os

    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id,
                                             ExpenseRecord.tenant_id == current_user.tenant_id,
                                             ExpenseRecord.logged_by_user_id == current_user.UserID).first() \
        or _expense_or_404(db, expense_id, current_user)
    if not expense.receipt_file_path or not os.path.isfile(expense.receipt_file_path):
        raise HTTPException(status_code=404, detail="No receipt attached")
    return FileResponse(expense.receipt_file_path, media_type=expense.receipt_content_type)


@router.patch(
    "/expenses/{expense_id}/attribution",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "view"))],
)
def update_expense_attribution(
    expense_id: str,
    body: ExpenseAttributionRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Who the spend is on: the person who logged it (until the manager decides) or its reviewer
    (until Finance approves). Same rules as logging it."""
    expense = db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id,
                                             ExpenseRecord.tenant_id == current_user.tenant_id,
                                             ExpenseRecord.logged_by_user_id == current_user.UserID).first() \
        or _expense_or_404(db, expense_id, current_user)
    try:
        return update_attribution(
            db, expense, current_user, spend_for=body.spend_for, client_id=body.client_id,
            client_splits=[s.model_dump() for s in body.client_splits] if body.client_splits else None,
            event_id=body.event_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _event_item(event, score=None, created=None) -> ExpenseEventItem:
    item = ExpenseEventItem.model_validate(event)
    item.match_score, item.created = score, created
    return item


@router.get(
    "/expense-events",
    response_model=ExpenseEventListResponse,
    dependencies=[Depends(require_resource_permission("my-expenses", "view"))],
)
def list_expense_events(
    q: Optional[str] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The tenant's conferences, closest to `q` first ("Namic-2026" finds "NAMIC 2026")."""
    return ExpenseEventListResponse(
        events=[_event_item(e, score) for e, score in search_events(db, current_user.tenant_id, q, year)])


@router.post(
    "/expense-events",
    response_model=ExpenseEventItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def create_expense_event(
    body: ExpenseEventCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Pick-or-add: the same name and year returns the team's existing event; a near match is a
    409 with the matches unless confirm_new."""
    try:
        event, created = find_or_create_event(
            db, tenant_id=current_user.tenant_id, name=body.name, year=body.year, start_date=body.start_date,
            end_date=body.end_date, location=body.location, created_by_user_id=current_user.UserID,
            confirm_new=body.confirm_new)
    except NearDuplicateEventError as exc:
        raise HTTPException(status_code=409, detail={
            "message": str(exc), "matches": [_event_item(e).model_dump(mode="json") for e in exc.matches]})
    except ExpenseEventError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(event)
    return _event_item(event, created=created)


@router.get(
    "/expense-events/{event_id}/summary",
    response_model=ExpenseEventSummaryResponse,
    dependencies=[Depends(require_resource_permission("expenses", "view"))],
)
def expense_event_summary(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """One conference's cost over the expenses the caller may see (their business units)."""
    try:
        event = get_event(db, current_user.tenant_id, event_id)
    except ExpenseEventError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    expenses = db.query(ExpenseRecord).filter(ExpenseRecord.event_id == event.id,
                                              ExpenseRecord.tenant_id == current_user.tenant_id,
                                              expense_filter(db, current_user)).all()
    return event_rollup(db, event, expenses)


@router.post(
    "/expense-events/{event_id}/merge",
    response_model=ExpenseEventItem,
    dependencies=[Depends(require_resource_permission("expenses", "create"))],
)
def merge_expense_event(
    event_id: str,
    body: ExpenseEventMergeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(require_resource_permission("revenue", "view")),
):
    """Finance: two events are the same conference -- move this one's expenses to the other."""
    from app.models.expense import ExpenseEvent

    source = db.query(ExpenseEvent).filter(ExpenseEvent.id == event_id,
                                           ExpenseEvent.tenant_id == current_user.tenant_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id!r} not found.")
    try:
        target = get_event(db, current_user.tenant_id, body.into_event_id)
        merge_events(db, source, target)
    except ExpenseEventError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _event_item(target)

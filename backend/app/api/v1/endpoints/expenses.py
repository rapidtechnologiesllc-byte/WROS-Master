"""
Partner/BU spend tracking, 2026-08-05.
Prefix: /expenses

POST /expenses                       -- self-service: log YOUR OWN expense (or, with expenses:create on
                                        the role template, one for an employee: expense_for_employee_id)
GET  /expenses/employees             -- expenses:create: the employees you may upload expenses for
POST /expenses/from-receipt          -- expenses:create: one receipt -> one expense for an employee
                                        (bulk upload sends one file per call; each answers created /
                                        needs review / failed with the reasons)
PUT  /expenses/{id}                  -- correct your own expense, until Finance approves it
GET  /expenses/{id}                  -- one expense with its receipts and check (owner or reviewer)
POST /expenses/{id}/receipts         -- add one or more receipts to your own expense
GET  /expenses/{id}/receipts/{rid}   -- one receipt's file
DELETE /expenses/{id}/receipts/{rid} -- remove a receipt from your own expense
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

On behalf (2026-11-24): Accounts uploads receipts for employees. That needs the expenses:create
grant on a role template (never a role name), and the employee must be in the uploader's
business units and have a login. The expense is then the employee's (logged_by_user_id), with
the uploader kept in uploaded_by_user_id; neither may approve it.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.data_scope import bu_filter, can_see_bu, client_bu_id, ensure_visible, expense_filter
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.employee import Employee
from app.models.expense import ExpenseRecord
from app.models.user import Users
from app.schemas.expense import (
    ExpenseEmployeeListResponse, ReceiptUploadResult,
    ClientInvestmentPositionResponse, ExpenseAttributionRequest, ExpenseCreateRequest, ExpenseEventCreateRequest,
    ExpenseEventItem, ExpenseEventListResponse, ExpenseEventMergeRequest, ExpenseEventSummaryResponse, ExpenseItem,
    ExpenseListResponse, ExpenseRejectRequest, ExpenseUpdateRequest, ExpenseVisitCreateRequest,
    ExpenseVisitDetail, ExpenseVisitDraftItem, ExpenseVisitDraftSubmitRequest, ExpenseVisitUpdateRequest,
)
from app.services.expense_event_service import (
    ExpenseEventError, NearDuplicateEventError, event_rollup, find_or_create_event, get_event, merge_events,
    search_events,
)
from app.services.expense_service import (
    ExpenseValidationError, approve_expense, approve_manager_step, can_review_as_manager,
    get_client_investment_position, log_expense, mark_expense_paid, reject_manager_step, update_attribution,
    update_expense,
)

router = APIRouter(tags=["expenses"])

ON_BEHALF_GRANT = ("expenses", "create")  # role-template permission to log expenses for employees


def _employee_in_scope(db: Session, user: Users, employee_id: str) -> Optional[Employee]:
    """The employee, in the caller's tenant and business units; None otherwise (one answer for
    "doesn't exist" and "not yours to see")."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None or (employee.tenant_id is not None and employee.tenant_id != user.tenant_id):
        return None
    return employee if can_see_bu(db, user, employee.bu_id) else None


def _owner_for(db: Session, user: Users, employee_id: Optional[str]) -> Users:
    """Who the expense is for: the caller, or (with the role-template grant) the employee they name.
    403 without the grant, 404 outside their scope, 400 when the employee has no login yet."""
    from app.services.role_template_permission_service import RoleTemplatePermissionService as perms

    if not employee_id:
        return user
    if db.query(Employee.id).filter(Employee.id == employee_id, Employee.wros_user_id == user.UserID).first():
        return user  # their own employee record
    employee = _employee_in_scope(db, user, employee_id)
    if not perms.has_permission(db, user.UserID, *ON_BEHALF_GRANT, user.tenant_id):
        raise HTTPException(status_code=403, detail="Your role does not allow logging expenses for other employees.")
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee {employee_id!r} not found.")
    owner = db.query(Users).filter(Users.UserID == employee.wros_user_id, Users.terminated_at.is_(None)).first() \
        if employee.wros_user_id else None
    if owner is None:
        raise HTTPException(status_code=400, detail=(
            f"{employee.first_name} {employee.last_name or ''}".strip()
            + " has no WROS login yet, so the expense can't be theirs; create their login first."))
    return owner

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
    owner = _owner_for(db, current_user, body.expense_for_employee_id)
    try:
        expense = log_expense(
            db, logged_by_user=owner, uploaded_by=current_user if owner is not current_user else None,
            purpose=body.purpose,
            expense_category=body.expense_category, amount_usd_cents=body.amount_usd_cents,
            expense_date=body.expense_date, expense_end_date=body.expense_end_date,
            client_id=body.client_id, spend_for=body.spend_for,
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


@router.get(
    "/expenses/employees",
    response_model=ExpenseEmployeeListResponse,
    dependencies=[Depends(require_resource_permission(*ON_BEHALF_GRANT))],
)
def list_expense_employees(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The employees the caller may upload expenses for: still employed, with a login, in their
    tenant and business units."""
    rows = (
        db.query(Employee)
        .filter(Employee.tenant_id == current_user.tenant_id, Employee.exit_date.is_(None),
                Employee.wros_user_id.isnot(None), bu_filter(db, current_user, Employee.bu_id))
        .order_by(Employee.first_name, Employee.last_name)
        .all()
    )
    return ExpenseEmployeeListResponse(employees=[
        {"id": e.id, "name": f"{e.first_name} {e.last_name or ''}".strip(), "email": e.email,
         "business_unit_id": e.bu_id} for e in rows])


@router.post(
    "/expenses/from-receipt",
    response_model=ReceiptUploadResult,
    dependencies=[Depends(require_resource_permission(*ON_BEHALF_GRANT))],
)
async def create_expense_from_receipt(
    file: UploadFile = File(...),
    expense_for_employee_id: str = Form(...),
    purpose: str = Form("OTHER"),
    expense_category: str = Form("OTHER"),
    spend_for: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    event_id: Optional[str] = Form(None),
    amount_usd_cents: Optional[int] = Form(None),
    expense_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Bulk upload, one file per call (the web server limits each request): the receipt is read and
    becomes one expense for the employee, checked by the same rules as any receipt. Amount and date
    typed here are checked against the receipt; left empty, the receipt's own are used. The answer
    always says what happened to this file -- created, needs review (reasons) or failed (reason)."""
    from app.services.expense_receipt_service import create_from_receipt

    try:
        owner = _owner_for(db, current_user, expense_for_employee_id)
    except HTTPException as exc:
        return ReceiptUploadResult(filename=file.filename, status="FAILED", reasons=[str(exc.detail)])
    fields = {"purpose": purpose, "expense_category": expense_category, "spend_for": spend_for or None,
              "client_id": client_id or None, "event_id": event_id or None, "amount_usd_cents": amount_usd_cents,
              "expense_date": expense_date or None, "description": description or None}
    return create_from_receipt(db, uploader=current_user, owner=owner, filename=file.filename,
                               content_type=file.content_type, data=await file.read(), fields=fields)

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


def _own_expense(db: Session, expense_id: str, user: Users) -> Optional[ExpenseRecord]:
    """An expense that is the caller's, or that they uploaded for an employee."""
    return db.query(ExpenseRecord).filter(ExpenseRecord.id == expense_id, ExpenseRecord.tenant_id == user.tenant_id,
                                          or_(ExpenseRecord.logged_by_user_id == user.UserID,
                                              ExpenseRecord.uploaded_by_user_id == user.UserID)).first()


def _own_expense_or_404(db: Session, expense_id: str, user: Users) -> ExpenseRecord:
    expense = _own_expense(db, expense_id, user)
    if expense is None:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id!r} not found.")
    return expense


@router.get(
    "/expenses/{expense_id}",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))],
)
def get_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """One expense for its review: the person who logged it, the manager reviewing it, or anyone who
    may see it."""
    return _own_expense(db, expense_id, current_user) or _expense_or_404(db, expense_id, current_user)


@router.put(
    "/expenses/{expense_id}",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def edit_expense(
    expense_id: str,
    body: ExpenseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Correct your own expense, until Finance approves it."""
    expense = _own_expense_or_404(db, expense_id, current_user)
    try:
        return update_expense(
            db, expense, current_user, purpose=body.purpose, expense_category=body.expense_category,
            amount_usd_cents=body.amount_usd_cents, expense_date=body.expense_date,
            expense_end_date=body.expense_end_date, spend_for=body.spend_for, client_id=body.client_id,
            client_splits=[s.model_dump() for s in body.client_splits] if body.client_splits else None,
            event_id=body.event_id, investment_label=body.investment_label, travel_type=body.travel_type,
            trip_label=body.trip_label, location=body.location, description=body.description,
            receipt_ref=body.receipt_ref)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# A manager reviews from My Tasks: being the assigned reviewer (or finance) is what is checked, not a
# finance screen's permission, or most managers could open the task and not decide it.
@router.post(
    "/expenses/{expense_id}/manager-approve",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
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
    dependencies=[Depends(require_resource_permission("my-tasks", "view"))]
)
def manager_reject_expense(
    expense_id: str,
    body: Optional[ExpenseRejectRequest] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    expense = _expense_or_404(db, expense_id, current_user)
    if not can_review_as_manager(db, expense, current_user):
        raise HTTPException(status_code=403, detail="Only the assigned manager or finance can review this expense.")
    try:
        return reject_manager_step(db, expense, rejected_by=current_user.UserID, reason=body.reason if body else None)
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
        return mark_expense_paid(db, expense, paid_by=current_user.UserID)
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

    expense = _own_expense_or_404(db, expense_id, current_user)
    try:
        return attach_and_check(db, expense, file.filename, file.content_type, await file.read())
    except ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/expenses/{expense_id}/receipts",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
async def add_expense_receipts(
    expense_id: str,
    files: List[UploadFile] = File(...),
    check: bool = True,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Add receipts to your own expense. check=false holds the check until the last of a batch sent
    one file at a time."""
    from app.services.expense_receipt_service import ReceiptError, attach_receipts

    expense = _own_expense_or_404(db, expense_id, current_user)
    try:
        return attach_receipts(db, expense, [(f.filename, f.content_type, await f.read()) for f in files],
                               user=current_user, check=check)
    except ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---- visits (CEO 2026-11-14): one visit, one line per receipt (app.services.expense_visit_service)
def _own_visit_or_404(db: Session, visit_id: str, user: Users):
    from app.models.expense import ExpenseVisit

    visit = db.query(ExpenseVisit).filter(ExpenseVisit.id == visit_id, ExpenseVisit.tenant_id == user.tenant_id,
                                          ExpenseVisit.owner_user_id == user.UserID).first()
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id!r} not found.")
    return visit


def _visit_response(db: Session, visit) -> dict:
    from app.services.expense_visit_service import visit_detail

    db.refresh(visit)
    return visit_detail(visit)


@router.post(
    "/expenses/visits",
    response_model=ExpenseVisitDetail,
    status_code=201,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def create_expense_visit(
    body: ExpenseVisitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """A visit or trip of your own; its receipts become its lines."""
    from app.services.expense_visit_service import create_visit

    try:
        visit = create_visit(
            db, current_user, name=body.name, purpose=body.purpose, spend_for=body.spend_for,
            client_id=body.client_id,
            client_splits=[s.model_dump() for s in body.client_splits] if body.client_splits else None,
            event_id=body.event_id, investment_label=body.investment_label, location=body.location,
            start_date=body.start_date, end_date=body.end_date)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _visit_response(db, visit)


@router.get(
    "/expenses/visits/{visit_id}",
    response_model=ExpenseVisitDetail,
    dependencies=[Depends(require_resource_permission("my-expenses", "view"))],
)
def get_expense_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return _visit_response(db, _own_visit_or_404(db, visit_id, current_user))


@router.put(
    "/expenses/visits/{visit_id}",
    response_model=ExpenseVisitDetail,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def update_expense_visit(
    visit_id: str,
    body: ExpenseVisitUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.expense_visit_service import update_visit

    visit = _own_visit_or_404(db, visit_id, current_user)
    try:
        update_visit(db, visit, name=body.name, location=body.location, start_date=body.start_date,
                     end_date=body.end_date)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _visit_response(db, visit)


@router.post(
    "/expenses/visits/{visit_id}/receipts",
    response_model=List[ExpenseVisitDraftItem],
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
async def add_expense_visit_receipts(
    visit_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Each receipt waits for its description, filled in from what it says."""
    from app.services.expense_receipt_service import ReceiptError
    from app.services.expense_visit_service import add_receipts, draft_prefill

    visit = _own_visit_or_404(db, visit_id, current_user)
    try:
        drafts = add_receipts(db, visit, [(f.filename, f.content_type, await f.read()) for f in files])
    except ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [{"id": d.id, "file_name": d.file_name, "content_type": d.content_type, "read_error": d.read_error,
             **draft_prefill(d)} for d in drafts]


def _own_draft_or_404(visit, draft_id: str):
    draft = next((d for d in visit.drafts if d.id == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Receipt {draft_id!r} not found on this visit.")
    return draft


@router.post(
    "/expenses/visits/{visit_id}/drafts/{draft_id}",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def submit_expense_visit_draft(
    visit_id: str,
    draft_id: str,
    body: ExpenseVisitDraftSubmitRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The receipt becomes its own expense line and goes to your manager like any expense."""
    from app.services.expense_receipt_service import ReceiptError
    from app.services.expense_visit_service import submit_draft

    visit = _own_visit_or_404(db, visit_id, current_user)
    draft = _own_draft_or_404(visit, draft_id)
    try:
        return submit_draft(db, visit, draft, current_user, description=body.description,
                            expense_category=body.expense_category, amount_usd_cents=body.amount_usd_cents,
                            expense_date=body.expense_date, expense_end_date=body.expense_end_date,
                            travel_type=body.travel_type)
    except (ExpenseValidationError, ReceiptError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/expenses/visits/{visit_id}/drafts/{draft_id}",
    response_model=ExpenseVisitDetail,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def delete_expense_visit_draft(
    visit_id: str,
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.expense_visit_service import remove_draft

    visit = _own_visit_or_404(db, visit_id, current_user)
    remove_draft(db, _own_draft_or_404(visit, draft_id))
    return _visit_response(db, visit)


@router.get(
    "/expenses/visits/{visit_id}/drafts/{draft_id}/file",
    dependencies=[Depends(require_resource_permission("my-expenses", "view"))],
)
def download_expense_visit_draft(
    visit_id: str,
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    draft = _own_draft_or_404(_own_visit_or_404(db, visit_id, current_user), draft_id)
    return FileResponse(draft.file_path, media_type=draft.content_type, filename=draft.file_name or "receipt")


@router.delete(
    "/expenses/{expense_id}",
    status_code=204,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def delete_own_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Take one of your own expense lines off, until Finance approves it."""
    from app.services.expense_visit_service import remove_line

    try:
        remove_line(db, _own_expense_or_404(db, expense_id, current_user), current_user)
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/expenses/{expense_id}/receipts/{receipt_id}",
    response_model=ExpenseItem,
    dependencies=[Depends(require_resource_permission("my-expenses", "create"))],
)
def delete_expense_receipt(
    expense_id: str,
    receipt_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.services.expense_receipt_service import ReceiptError, remove_receipt

    expense = _own_expense_or_404(db, expense_id, current_user)
    try:
        return remove_receipt(db, expense, receipt_id, user=current_user)
    except ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/expenses/{expense_id}/receipts/{receipt_id}")
def download_one_receipt(
    expense_id: str,
    receipt_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """One receipt's file: the person who logged it, their reviewer, or anyone who may see the expense."""
    import os

    expense = _own_expense(db, expense_id, current_user) or _expense_or_404(db, expense_id, current_user)
    receipt = next((r for r in expense.receipts if r.id == receipt_id), None)
    if receipt is None or not os.path.isfile(receipt.file_path):
        raise HTTPException(status_code=404, detail="Receipt not found")
    return FileResponse(receipt.file_path, media_type=receipt.content_type)


@router.get("/expenses/{expense_id}/receipt")
def download_expense_receipt(
    expense_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """The receipt file: the person who logged it, their reviewer, or anyone who may see the expense."""
    import os

    expense = _own_expense(db, expense_id, current_user) or _expense_or_404(db, expense_id, current_user)
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
    expense = _own_expense(db, expense_id, current_user) or _expense_or_404(db, expense_id, current_user)
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

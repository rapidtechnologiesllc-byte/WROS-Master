"""
Client list + create.

The GET here originally powered filter dropdowns only, on the
(incorrect, corrected 2026-08-05) assumption that a create path already
existed "elsewhere" -- confirmed by grep it did not: no `Client(...)`
row was ever instantiated anywhere in this codebase except one internal
helper in partner_intent_service.py. POST /clients is the first real
create path, via app.services.client_service.create_client() -- see
that function's own docstring for the BU-attribution-locking rule it
enforces (Avinash's 2026-08-05 "client attribution locking" law: a
client's BU is derived from the creating user's own BU, never a
caller-supplied field).

Gated the same way as GET /users/all (get_current_internal_user): any
internal user needs to see real client names to filter by them, this
isn't sensitive data on its own the way markup_rate_pct etc. are.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.client import Client, ClientContact
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.schemas.client import (
    ClientContactAddRequest, ClientContactResponse, ClientContactsListResponse,
    ClientCreateRequest, ClientCreateResponse, ClientDetailResponse, ClientListItem,
    ClientListResponse, ClientUpdateRequest,
)
from app.services.client_service import (
    ClientValidationError, DuplicateClientError, add_client_contact, assign_account_manager,
    create_client, update_client_details,
)

router = APIRouter(prefix="/clients", tags=["clients"])


def _bu_name_map(db: Session, bu_ids) -> dict:
    ids = {i for i in bu_ids if i is not None}
    if not ids:
        return {}
    return {b.id: b.name for b in db.query(BusinessUnit).filter(BusinessUnit.id.in_(ids)).all()}


def _employee_name_map(db: Session, employee_ids) -> dict:
    ids = {i for i in employee_ids if i is not None}
    if not ids:
        return {}
    return {
        e.id: f"{e.first_name} {e.last_name}".strip()
        for e in db.query(Employee).filter(Employee.id.in_(ids)).all()
    }


@router.get("", response_model=ClientListResponse)
def list_clients(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    query = db.query(Client)
    if active_only:
        query = query.filter(Client.status != "INACTIVE")
    clients = query.order_by(Client.company_name).all()
    # 2026-08-12, Avinash: BU and Client Owner (account manager) weren't
    # visible anywhere in the UI -- resolved names here so the frontend
    # doesn't have to cross-reference raw IDs itself.
    bu_names = _bu_name_map(db, (c.business_unit_id for c in clients))
    am_names = _employee_name_map(db, (c.account_manager_employee_id for c in clients))
    return ClientListResponse(
        clients=[
            ClientListItem(
                id=c.id, company_name=c.company_name, status=c.status,
                business_unit_id=c.business_unit_id,
                business_unit_name=bu_names.get(c.business_unit_id),
                account_manager_employee_id=c.account_manager_employee_id,
                account_manager_name=am_names.get(c.account_manager_employee_id),
                line_type=c.line_type,
                website=c.website,
            )
            for c in clients
        ]
    )


@router.get("/business-units/{business_unit_id}/assignments")
def get_business_unit_assignments(
    business_unit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Resolves a BU's designated BU Head + HR Manager for Job-creation
    auto-assignment (agentic-first mandate -- the agent resolves what it
    already knows, no manual lookup step). Employee -> Users resolution
    is by email match (this codebase has no direct employees->users FK;
    Employee.email and Users.UserEmail are the only shared key) --
    user_id is None if no matching Users row exists for that email, so
    the caller can fall back to manual assignment rather than silently
    failing."""
    from app.models.employee import Employee
    from app.models.business_unit import BusinessUnit

    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
    if bu is None:
        raise HTTPException(status_code=404, detail=f"Business unit {business_unit_id} not found.")

    def _resolve(employee_id: Optional[str]):
        if employee_id is None:
            return None
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if employee is None:
            return None
        user = db.query(Users).filter(Users.UserEmail == employee.email).first()
        return {
            "employee_id": employee.id, "name": f"{employee.first_name} {employee.last_name}",
            "email": employee.email, "user_id": user.UserID if user else None,
        }

    return {
        "business_unit_id": business_unit_id,
        "bu_head": _resolve(bu.bu_head_employee_id),
        "hr_manager": _resolve(bu.hr_manager_employee_id),
    }


@router.post("", response_model=ClientCreateResponse, status_code=201)
def create_client_endpoint(
    body: ClientCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    try:
        client = create_client(
            db,
            company_name=body.company_name,
            created_by_user=current_user,
            line_type=body.line_type,
            country=body.country,
            website=body.website,
            billing_currency=body.billing_currency,
            hiring_manager=body.hiring_manager.dict() if body.hiring_manager else None,
            timesheet_approver=body.timesheet_approver.dict() if body.timesheet_approver else None,
        )
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return client


def _to_detail_response(db: Session, client: Client) -> ClientDetailResponse:
    bu_name = None
    if client.business_unit_id is not None:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == client.business_unit_id).first()
        bu_name = bu.name if bu else None
    am_name = None
    if client.account_manager_employee_id is not None:
        am = db.query(Employee).filter(Employee.id == client.account_manager_employee_id).first()
        am_name = f"{am.first_name} {am.last_name}".strip() if am else None
    return ClientDetailResponse(
        **{c: getattr(client, c) for c in ClientDetailResponse.__fields__ if hasattr(client, c)},
        business_unit_name=bu_name, account_manager_name=am_name,
    )


@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    return _to_detail_response(db, client)


@router.get("/{client_id}/contacts", response_model=ClientContactsListResponse)
def list_client_contacts_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    contacts = db.query(ClientContact).filter(ClientContact.client_id == client_id).all()
    return ClientContactsListResponse(contacts=contacts)


@router.post("/{client_id}/contacts", response_model=ClientContactResponse, status_code=201)
def add_client_contact_endpoint(
    client_id: str,
    body: ClientContactAddRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    try:
        contact = add_client_contact(
            db, client, name=body.name, email=body.email, role_type=body.role_type, phone=body.phone,
        )
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return contact


@router.patch("/{client_id}", response_model=ClientDetailResponse)
def update_client_endpoint(
    client_id: str,
    body: ClientUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    updates = body.dict(exclude_unset=True)
    # account_manager_employee_id ("Client Owner") has its own real
    # audit-history + notification path (assign_account_manager, HRMS-0709)
    # -- routed here separately rather than through the generic field-set
    # update_client_details() uses for everything else.
    account_manager_employee_id = updates.pop("account_manager_employee_id", None)
    try:
        if updates:
            client = update_client_details(db, client, updates)
        if account_manager_employee_id is not None:
            employee = db.query(Employee).filter(Employee.id == account_manager_employee_id).first()
            if not employee:
                raise HTTPException(status_code=404, detail=f"Employee {account_manager_employee_id!r} not found.")
            client = assign_account_manager(db, client, employee, changed_by=current_user.UserID)
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(client)
    return _to_detail_response(db, client)

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
from app.core.dependencies import get_current_internal_user, require_resource_permission
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
    assign_account_manager_user, create_client, resolve_account_manager_user,
    set_client_business_unit, update_client_details,
)

router = APIRouter(prefix="/clients", tags=["clients"])

def _bu_name_map(db: Session, bu_ids) -> dict:
    ids = {i for i in bu_ids if i is not None}
    if not ids:
        return {}
    return {b.id: b.name for b in db.query(BusinessUnit).filter(BusinessUnit.id.in_(ids)).all()}

def _contracting_company_name_map(db: Session, company_ids) -> dict:
    from app.models.location import Location
    ids = {i for i in company_ids if i}
    if not ids:
        return {}
    return {l.id: l.name for l in db.query(Location).filter(Location.id.in_(ids)).all()}


def _set_contracting_company(db: Session, client: Client, company_id: str, tenant_id: int) -> None:
    """company_id "" clears; an unknown company is a 400."""
    from app.models.location import Location
    if company_id and not db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first():
        raise HTTPException(status_code=400, detail="Unknown company")
    client.contracting_company_id = company_id or None
    db.commit()


def _user_name_map(db: Session, user_ids) -> dict:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {u.UserID: (u.UserName or u.UserEmail) for u in db.query(Users).filter(Users.UserID.in_(ids)).all()}

def _employee_name_map(db: Session, employee_ids) -> dict:
    ids = {i for i in employee_ids if i is not None}
    if not ids:
        return {}
    return {
        e.id: f"{e.first_name} {e.last_name}".strip()
        for e in db.query(Employee).filter(Employee.id.in_(ids)).all()
    }

@router.get(
    "",
    response_model=ClientListResponse,
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
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
    am_user_names = _user_name_map(db, (c.account_manager_user_id for c in clients))
    company_names = _contracting_company_name_map(db, (c.contracting_company_id for c in clients))
    return ClientListResponse(
        clients=[
            ClientListItem(
                id=c.id, company_name=c.company_name, status=c.status,
                business_unit_id=c.business_unit_id,
                business_unit_name=bu_names.get(c.business_unit_id),
                contracting_company_id=c.contracting_company_id,
                contracting_company_name=company_names.get(c.contracting_company_id),
                account_manager_employee_id=c.account_manager_employee_id,
                account_manager_user_id=c.account_manager_user_id,
                # The user-based account manager wins; the employee one is legacy
                account_manager_name=(
                    am_user_names.get(c.account_manager_user_id)
                    or am_names.get(c.account_manager_employee_id)
                ),
                line_type=c.line_type,
                website=c.website,
            )
            for c in clients
        ]
    )

@router.get(
    "/account-manager-options",
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
def list_account_manager_options(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Account manager choices: active users in the caller's tenant (the
    Users & Access Control list). Gated on clients.view, not
    users-access-control.view, so client editors can always load it."""
    users = (
        db.query(Users)
        .filter(Users.tenant_id == current_user.tenant_id, Users.terminated_at.is_(None))
        .order_by(Users.UserName)
        .all()
    )
    return {
        "users": [
            {"user_id": u.UserID, "user_name": u.UserName, "user_email": u.UserEmail}
            for u in users
        ]
    }

@router.get(
    "/business-units/{business_unit_id}/assignments",
    dependencies=[Depends(require_resource_permission("business-units", "view"))]
)
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

@router.post(
    "",
    response_model=ClientCreateResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("clients", "create"))]
)
def create_client_endpoint(
    body: ClientCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    try:
        # Validate the pick before creating, so a bad id can't leave a half-made client
        am_user = (
            resolve_account_manager_user(db, body.account_manager_user_id, current_user.tenant_id)
            if body.account_manager_user_id else None
        )
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
            business_unit_id=body.business_unit_id,
        )
        extra = {
            k: v for k, v in {
                "company_short_name": body.company_short_name,
                "tier": body.tier,
                "notes": body.notes,
            }.items() if v not in (None, "")
        }
        if extra:
            client = update_client_details(db, client, extra)
        if body.contracting_company_id:
            _set_contracting_company(db, client, body.contracting_company_id, current_user.tenant_id)
        if am_user is not None:
            client = assign_account_manager_user(
                db, client, am_user, changed_by=current_user.UserID, tenant_id=current_user.tenant_id,
            )
            db.commit()
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
    if client.account_manager_user_id is not None:
        am_user = db.query(Users).filter(Users.UserID == client.account_manager_user_id).first()
        am_name = (am_user.UserName or am_user.UserEmail) if am_user else None
    if am_name is None and client.account_manager_employee_id is not None:
        am = db.query(Employee).filter(Employee.id == client.account_manager_employee_id).first()
        am_name = f"{am.first_name} {am.last_name}".strip() if am else None
    return ClientDetailResponse(
        **{c: getattr(client, c) for c in ClientDetailResponse.__fields__ if hasattr(client, c)},
        business_unit_name=bu_name, account_manager_name=am_name,
        contracting_company_name=_contracting_company_name_map(db, [client.contracting_company_id]).get(client.contracting_company_id),
    )

@router.get(
    "/{client_id}",
    response_model=ClientDetailResponse,
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
def get_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    return _to_detail_response(db, client)

@router.get(
    "/{client_id}/contacts",
    response_model=ClientContactsListResponse,
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
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

@router.post(
    "/{client_id}/contacts",
    response_model=ClientContactResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("clients", "create"))]
)
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

@router.patch(
    "/{client_id}",
    response_model=ClientDetailResponse,
    dependencies=[Depends(require_resource_permission("clients", "edit"))]
)
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
    has_am_user = "account_manager_user_id" in updates
    account_manager_user_id = updates.pop("account_manager_user_id", None)
    business_unit_id = updates.pop("business_unit_id", None)
    has_company = "contracting_company_id" in updates
    company_id = updates.pop("contracting_company_id", None)
    try:
        if has_company:
            _set_contracting_company(db, client, company_id or "", current_user.tenant_id)
        if business_unit_id is not None:
            client = set_client_business_unit(db, client, business_unit_id, current_user.tenant_id)
        if updates:
            client = update_client_details(db, client, updates)
        if has_am_user:
            # User pick (Users & Access Control) wins over the legacy employee field
            am_user = (
                resolve_account_manager_user(db, account_manager_user_id, current_user.tenant_id)
                if account_manager_user_id else None
            )
            client = assign_account_manager_user(
                db, client, am_user, changed_by=current_user.UserID, tenant_id=current_user.tenant_id,
            )
        elif account_manager_employee_id is not None:
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

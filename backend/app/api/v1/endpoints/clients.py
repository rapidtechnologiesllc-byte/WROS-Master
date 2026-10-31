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
    assign_account_manager_user, assign_client_owner, create_client, resolve_client_team_user,
    set_client_business_unit, set_client_status, update_client_details,
)
from app.services.client_team_notification_service import notify_client_created, notify_client_owner_assigned

from app.core.data_scope import bu_filter, ensure_assignable, ensure_visible
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

def _get_client_or_404(db: Session, client_id: str, user) -> Client:
    """The client, if it is in the caller's tenant and business units (app.core.data_scope);
    404 otherwise -- the same answer as a client that does not exist."""
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    ensure_visible(db, user, client.business_unit_id, "Client")
    return client


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
    # the caller's tenant, and only the business units they may see (plus unassigned prospects)
    query = db.query(Client).filter(Client.tenant_id == current_user.tenant_id,
                                    bu_filter(db, current_user, Client.business_unit_id))
    if active_only:
        query = query.filter(Client.status != "INACTIVE")
    clients = query.order_by(Client.company_name).all()
    # 2026-08-12, Avinash: BU and Client Owner (account manager) weren't
    # visible anywhere in the UI -- resolved names here so the frontend
    # doesn't have to cross-reference raw IDs itself.
    bu_names = _bu_name_map(db, (c.business_unit_id for c in clients))
    am_names = _employee_name_map(db, (c.account_manager_employee_id for c in clients))
    user_names = _user_name_map(db, [u for c in clients for u in (c.account_manager_user_id, c.client_owner_user_id)])
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
                    user_names.get(c.account_manager_user_id)
                    or am_names.get(c.account_manager_employee_id)
                ),
                client_owner_user_id=c.client_owner_user_id,
                client_owner_name=user_names.get(c.client_owner_user_id),
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
    """Account manager and Client Owner choices: active users in the caller's tenant (the
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
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Who runs this business unit for a new job, so Job Create can pre-fill it: the BU head
    in the client's contracting company (BU heads are per company -- bu_leadership), or the
    only head when the BU operates in one company. hr_manager is None: no BU-level HR
    manager is recorded anywhere (it lived on a model nothing writes). The BU must be one
    the caller may see."""
    from app.services.bu_leadership import head_for_client

    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id,
                                       BusinessUnit.tenant_id == current_user.tenant_id).first()
    if bu is None:
        raise HTTPException(status_code=404, detail=f"Business unit {business_unit_id} not found.")
    ensure_visible(db, current_user, bu.id, "Business unit")
    head_id = head_for_client(db, bu.id, client_id)
    head = db.query(Users).filter(Users.UserID == head_id).first() if head_id else None
    return {
        "business_unit_id": business_unit_id,
        "bu_head": {"user_id": head.UserID, "name": head.UserName or head.UserEmail, "email": head.UserEmail}
        if head else None,
        "hr_manager": None,
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
            resolve_client_team_user(db, body.account_manager_user_id, current_user.tenant_id)
            if body.account_manager_user_id else None
        )
        # The Client Owner defaults to whoever adds the client
        owner = resolve_client_team_user(db, body.client_owner_user_id or current_user.UserID,
                                         current_user.tenant_id, "client owner")
        ensure_assignable(db, current_user, body.business_unit_id, "client")
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
        assign_client_owner(db, client, owner, changed_by=current_user.UserID)
        if am_user is not None:
            # notify=False: the new-client team email below tells the account manager
            client = assign_account_manager_user(
                db, client, am_user, changed_by=current_user.UserID, tenant_id=current_user.tenant_id,
                notify=False,
            )
        db.commit()
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    notify_client_created(db, client, actor=current_user)
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
        client_owner_name=_user_name_map(db, [client.client_owner_user_id]).get(client.client_owner_user_id),
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
    client = _get_client_or_404(db, client_id, current_user)
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
    _get_client_or_404(db, client_id, current_user)
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
    client = _get_client_or_404(db, client_id, current_user)
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
    client = _get_client_or_404(db, client_id, current_user)
    updates = body.dict(exclude_unset=True)
    # The account manager (assign_account_manager*, HRMS-0709) and the Client Owner
    # (assign_client_owner) have their own audit-history + notification paths -- routed here
    # separately rather than through the generic field-set update_client_details() uses.
    account_manager_employee_id = updates.pop("account_manager_employee_id", None)
    has_am_user = "account_manager_user_id" in updates
    account_manager_user_id = updates.pop("account_manager_user_id", None)
    has_owner = "client_owner_user_id" in updates
    client_owner_user_id = updates.pop("client_owner_user_id", None)
    owner_changed = False
    new_status = updates.pop("status", None)
    business_unit_id = updates.pop("business_unit_id", None)
    has_company = "contracting_company_id" in updates
    company_id = updates.pop("contracting_company_id", None)
    try:
        if has_company:
            _set_contracting_company(db, client, company_id or "", current_user.tenant_id)
        if business_unit_id is not None:
            ensure_assignable(db, current_user, business_unit_id, "client")
            client = set_client_business_unit(db, client, business_unit_id, current_user.tenant_id)
        if updates:
            client = update_client_details(db, client, updates)
        if new_status is not None and new_status != client.status:
            client = set_client_status(db, client, new_status, changed_by=current_user.UserID)
        if has_am_user:
            # User pick (Users & Access Control) wins over the legacy employee field
            am_user = (
                resolve_client_team_user(db, account_manager_user_id, current_user.tenant_id)
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
        if has_owner:
            owner = (
                resolve_client_team_user(db, client_owner_user_id, current_user.tenant_id, "client owner")
                if client_owner_user_id else None
            )
            owner_changed = assign_client_owner(db, client, owner, changed_by=current_user.UserID)
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(client)
    if owner_changed and client.client_owner_user_id:
        notify_client_owner_assigned(db, client, actor=current_user)
    return _to_detail_response(db, client)

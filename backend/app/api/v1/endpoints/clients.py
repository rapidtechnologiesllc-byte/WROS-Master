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
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.client import Client, ClientContact, ClientEmail, ClientHistory
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from app.schemas.client import (
    ClientContactAddRequest, ClientContactResponse, ClientContactsListResponse,
    ClientCreateRequest, ClientCreateResponse, ClientDetailResponse, ClientListItem,
    ClientHistoryEntry, ClientHistoryResponse, ClientListResponse, ClientUpdateCreateRequest,
    ClientUpdateCreateResponse, ClientUpdateRequest,
)
from app.services.client_service import (
    ClientValidationError, DuplicateClientError, add_client_contact, assign_account_manager,
    assign_account_manager_user, assign_client_owner, create_client, resolve_client_team_user,
    set_client_business_unit, set_client_contracting_company, set_client_status, update_client_details,
)
from app.services.client_team_notification_service import (
    notify_client_changes, notify_client_created,
)

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


def _set_contracting_company(db: Session, client: Client, company_id: str, tenant_id: int,
                             changed_by: Optional[str] = None) -> bool:
    """company_id "" clears; an unknown company is a 400. Returns whether it changed."""
    from app.models.location import Location
    if company_id and not db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first():
        raise HTTPException(status_code=400, detail="Unknown company")
    return set_client_contracting_company(db, client, company_id or None, changed_by=changed_by)


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
        db.add(ClientHistory(tenant_id=client.tenant_id, client_id=client.id, change_type="CREATED",
                             new_value=json.dumps({"company_name": client.company_name}),
                             changed_by=current_user.UserID))
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

def _email_client_changes(db: Session, client: Client, before: dict, actor: Users) -> None:
    """One email to the client's team for a save that moved responsibility; field edits (tier,
    terms, notes...) are History only. The newly assigned and the removed account manager /
    client owner are both told."""
    from app.services.bu_leadership import head_for_client
    from app.services.client_service import account_manager_workload

    users = _user_name_map(db, [before["account_manager_user_id"], client.account_manager_user_id,
                                before["client_owner_user_id"], client.client_owner_user_id])
    bus = _bu_name_map(db, [before["business_unit_id"], client.business_unit_id])
    companies = _contracting_company_name_map(db, [before["contracting_company_id"], client.contracting_company_id])
    changes, extra = [], {}

    def name(names, key):
        return names.get(key) or "none" if key else "none"

    if client.business_unit_id != before["business_unit_id"]:
        changes.append(f"Business unit: {name(bus, before['business_unit_id'])} -> {name(bus, client.business_unit_id)}")
        unit = db.query(BusinessUnit).filter(BusinessUnit.id == client.business_unit_id).first()
        if unit is not None and unit.partner_user_id:
            extra.setdefault(unit.partner_user_id, []).append("Partner of the new business unit")
        head = head_for_client(db, client.business_unit_id, client.id)
        if head:
            extra.setdefault(head, []).append("BU Head of the new business unit")
    if client.status != before["status"]:
        changes.append(f"Status: {before['status']} -> {client.status}")
    if client.account_manager_user_id != before["account_manager_user_id"]:
        changes.append(f"Account manager: {name(users, before['account_manager_user_id'])} -> "
                       f"{name(users, client.account_manager_user_id)}")
        if client.account_manager_user_id:
            changes.append(account_manager_workload(db, client))
        if before["account_manager_user_id"]:
            extra.setdefault(before["account_manager_user_id"], []).append("Former Account Manager")
    if client.client_owner_user_id != before["client_owner_user_id"]:
        changes.append(f"Client owner: {name(users, before['client_owner_user_id'])} -> "
                       f"{name(users, client.client_owner_user_id)}")
        if before["client_owner_user_id"]:
            extra.setdefault(before["client_owner_user_id"], []).append("Former Client Owner")
    if client.contracting_company_id != before["contracting_company_id"]:
        changes.append(f"Contracting company: {name(companies, before['contracting_company_id'])} -> "
                       f"{name(companies, client.contracting_company_id)}")
    if not changes:
        return
    last = db.query(ClientHistory.id).filter(ClientHistory.client_id == client.id)         .order_by(ClientHistory.id.desc()).first()
    notify_client_changes(db, client, actor=actor, key=f"client-change-{client.id}-{last[0] if last else 0}",
                          changes=changes, extra_team=extra)


# History tab: field labels and how to show stored ids
HISTORY_LABELS = {
    "CREATED": "Client created", "STATUS": "Status changed", "ACCOUNT_MANAGER": "Account manager changed",
    "CLIENT_OWNER": "Client owner changed", "TIER": "Tier changed", "CONTRACT_TERMS": "Contract terms changed",
    "BUSINESS_UNIT": "Business unit changed", "CONTRACTING_COMPANY": "Contracting company changed",
    "DETAILS": "Details edited",
}
EMAIL_TITLES = {"OUT": "Email sent to the client", "IN": "Email from the client", "TEAM": "Email to our team"}


def _history_value(key: str, value, names: dict):
    if value is None or value == "":
        return "blank"
    if key in names:
        return names[key].get(value) or str(value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _change_lines(old: dict, new: dict, names: dict) -> list:
    keys = list(dict.fromkeys([*old.keys(), *new.keys()]))
    label = lambda k: k.replace("_user_id", "").replace("_employee_id", " (employee)").replace("_id", "").replace("_", " ").capitalize()
    if not old:
        return [f"{label(k)}: {_history_value(k, new.get(k), names)}" for k in keys]
    return [f"{label(k)}: {_history_value(k, old.get(k), names)} -> {_history_value(k, new.get(k), names)}"
            for k in keys if old.get(k) != new.get(k)]


def _meeting_lines(meeting, tasks: dict, users: dict, opportunities: dict) -> list:
    lines = []
    if meeting.attendees:
        lines.append(f"Attendees: {meeting.attendees}")
    if meeting.opportunity_id in opportunities:
        lines.append(f"Opportunity: {opportunities[meeting.opportunity_id].stage}")
    lines.append(f"Discussed: {meeting.summary}")
    if meeting.decisions:
        lines.append(f"Agreed: {meeting.decisions}")
    for task_id in meeting.task_ids or []:
        task = tasks.get(task_id)
        if task is not None:
            owner = users.get(task.assigned_to_user_id) or "unassigned"
            due = f", due {task.due_date:%d %b %Y}" if task.due_date else ""
            lines.append(f"Next step: {task.title} ({owner}{due}, {task.status})")
    return lines


@router.post(
    "/{client_id}/updates",
    response_model=ClientUpdateCreateResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("clients", "edit"))]
)
def create_client_update_endpoint(
    client_id: str,
    body: ClientUpdateCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Record a meeting with the client; each next step becomes a task for its owner."""
    from app.services.client_update_service import ClientUpdateError, record_client_update

    client = _get_client_or_404(db, client_id, current_user)
    try:
        update = record_client_update(
            db, client, actor=current_user, meeting_date=body.meeting_date, summary=body.summary,
            attendees=body.attendees, decisions=body.decisions, opportunity_id=body.opportunity_id,
            next_steps=[step.model_dump() for step in body.next_steps],
        )
        db.commit()
    except ClientUpdateError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return ClientUpdateCreateResponse(id=update.id, task_ids=update.task_ids or [])


@router.get(
    "/{client_id}/history",
    response_model=ClientHistoryResponse,
    dependencies=[Depends(require_resource_permission("clients", "view"))]
)
def get_client_history_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Every change to the client (who, when, old -> new) and every email about it, newest first."""
    from app.core.config import settings

    client = _get_client_or_404(db, client_id, current_user)
    from app.models.client_update import ClientUpdate
    from app.models.opportunity import Opportunity
    from app.models.task import Task

    changes = db.query(ClientHistory).filter(ClientHistory.client_id == client.id).all()
    emails = db.query(ClientEmail).filter(ClientEmail.client_id == client.id).all()
    meetings = db.query(ClientUpdate).filter(ClientUpdate.client_id == client.id).all()
    tasks = {t.id: t for t in db.query(Task).filter(
        Task.id.in_([i for m in meetings for i in (m.task_ids or [])] or [-1]))}
    parsed = [(row, json.loads(row.old_value or "{}"), json.loads(row.new_value or "{}")) for row in changes]
    ids = lambda key: [d.get(key) for _, old, new in parsed for d in (old, new)]
    users = _user_name_map(db, [r.changed_by for r in changes] + [e.sent_by_user_id for e in emails]
                           + [m.created_by for m in meetings] + [t.assigned_to_user_id for t in tasks.values()]
                           + ids("account_manager_user_id") + ids("client_owner_user_id"))
    opportunities = {o.id: o for o in db.query(Opportunity).filter(
        Opportunity.id.in_([m.opportunity_id for m in meetings if m.opportunity_id] or ["-"]))}
    names = {
        "account_manager_user_id": users, "client_owner_user_id": users,
        "account_manager_employee_id": _employee_name_map(db, ids("account_manager_employee_id")),
        "business_unit_id": _bu_name_map(db, ids("business_unit_id")),
        "contracting_company_id": _contracting_company_name_map(db, ids("contracting_company_id")),
    }
    entries = [
        ClientHistoryEntry(kind="CHANGE", at=row.changed_at, by=users.get(row.changed_by) or row.changed_by,
                           title=HISTORY_LABELS.get(row.change_type, row.change_type),
                           lines=_change_lines(old, new, names))
        for row, old, new in parsed
    ] + [
        ClientHistoryEntry(kind="EMAIL", at=e.sent_at, by=users.get(e.sent_by_user_id) if e.sent_by_user_id else None,
                           title=f"{EMAIL_TITLES[e.direction]}: {e.subject or '(no subject)'}", direction=e.direction,
                           from_address=e.from_address, to_addresses=e.to_addresses, cc_addresses=e.cc_addresses,
                           snippet=e.snippet)
        for e in emails
    ] + [
        ClientHistoryEntry(kind="UPDATE", at=datetime.combine(m.meeting_date, datetime.min.time()),
                           by=users.get(m.created_by) or m.created_by, title="Meeting update",
                           lines=_meeting_lines(m, tasks, users, opportunities))
        for m in meetings
    ]
    entries.sort(key=lambda entry: entry.at, reverse=True)
    return ClientHistoryResponse(client_id=client.id, logging_mailbox=settings.THUNDER_MAILBOX, entries=entries)


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
    # (assign_client_owner) have their own audit-history paths -- routed here separately rather
    # than through the generic field-set update_client_details() uses. Every change writes
    # ClientHistory; changes that move responsibility (BU, status, account manager, client owner,
    # contracting company) are emailed to the client's team after the commit.
    account_manager_employee_id = updates.pop("account_manager_employee_id", None)
    has_am_user = "account_manager_user_id" in updates
    account_manager_user_id = updates.pop("account_manager_user_id", None)
    has_owner = "client_owner_user_id" in updates
    client_owner_user_id = updates.pop("client_owner_user_id", None)
    new_status = updates.pop("status", None)
    business_unit_id = updates.pop("business_unit_id", None)
    has_company = "contracting_company_id" in updates
    company_id = updates.pop("contracting_company_id", None)
    before = {
        "business_unit_id": client.business_unit_id, "status": client.status,
        "account_manager_user_id": client.account_manager_user_id,
        "client_owner_user_id": client.client_owner_user_id,
        "contracting_company_id": client.contracting_company_id,
    }
    actor = current_user.UserID
    try:
        if has_company:
            _set_contracting_company(db, client, company_id or "", current_user.tenant_id, changed_by=actor)
        if business_unit_id is not None:
            ensure_assignable(db, current_user, business_unit_id, "client")
            set_client_business_unit(db, client, business_unit_id, current_user.tenant_id, changed_by=actor)
        if updates:
            client = update_client_details(db, client, updates, changed_by=actor)
        if new_status is not None and new_status != client.status:
            client = set_client_status(db, client, new_status, changed_by=actor)
        if has_am_user:
            # User pick (Users & Access Control) wins over the legacy employee field
            am_user = (
                resolve_client_team_user(db, account_manager_user_id, current_user.tenant_id)
                if account_manager_user_id else None
            )
            # notify=False: the change email below tells the new and the former account manager
            client = assign_account_manager_user(
                db, client, am_user, changed_by=actor, tenant_id=current_user.tenant_id, notify=False,
            )
        elif account_manager_employee_id is not None:
            employee = db.query(Employee).filter(Employee.id == account_manager_employee_id).first()
            if not employee:
                raise HTTPException(status_code=404, detail=f"Employee {account_manager_employee_id!r} not found.")
            client = assign_account_manager(db, client, employee, changed_by=actor, notify=False)
        if has_owner:
            owner = (
                resolve_client_team_user(db, client_owner_user_id, current_user.tenant_id, "client owner")
                if client_owner_user_id else None
            )
            assign_client_owner(db, client, owner, changed_by=actor)
    except DuplicateClientError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(client)
    _email_client_changes(db, client, before, current_user)
    return _to_detail_response(db, client)

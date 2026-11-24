"""Asset ledger (CEO 2026-11-10). The IT Admin function owns every device; this service keeps one rule:
an item is always in exactly one place, and every move is recorded on the item.

What the system does by itself:
- a person placed on a project that needs kit they do not hold -> one task for IT Admin to issue it;
- a placement ends -> the client's devices and the project's kit are asked back (the employee's own
  company laptop stays with them for as long as they are employed);
- notice or exit -> every item is asked back and an asset clearance is opened: full and final
  settlement is on hold until IT Admin signs it off, refused while anything is still out;
- an overdue return climbs: the holder is reminded, then their reporting manager, then their BU head;
- a courier movement open too long, a defect open too long, a warranty about to end and a holder who
  has left are raised on the ledger (ledger_alerts) and by the daily sweep (run_asset_sweep).

Every function adds to the session and the caller commits, then calls send_notices(db): tasks and
emails are only announced once the change is saved.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import (
    ASSET_CATEGORIES, ASSET_CONDITIONS, CLOSED_STATUSES, HANDOVER_METHODS, HELD_STATUSES, ISSUE_SEVERITIES,
    OPEN_ISSUE_STATUSES, OWNER_TYPES, RETURN_REASONS, TASK_CLEARANCE, TASK_ESCALATION, TASK_ISSUE, TASK_KIT,
    TASK_RETURN, TASK_TRANSIT, Asset, AssetClearance, AssetEvent, AssetIssue, AssetReturn, AssetShipment,
    ProjectAssetRequirement,
)
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import HOLDING_STATUSES, EmployeeAllocation
from app.models.location import Location
from app.models.project import Project
from app.models.task import Task
from app.models.user import Users

logger = logging.getLogger(__name__)

OPEN_TASK_STATUSES = ("NEW", "IN_PROGRESS", "ON_HOLD")
LEAVING_STATUSES = ("NOTICE_PERIOD", "EXITED")
LEDGER_PATH = "/admin/assets"


class AssetRefused(ValueError):
    """The change is not allowed; the message says why in plain words."""


# --------------------------------------------------------------------------- who and where

def owner_function(db: Session, tenant_id: int):
    """The function that owns assets (settings.ASSET_OWNER_FUNCTION, seeded by db_contract)."""
    from app.models.org_structure import Department

    return db.query(Department).filter(Department.tenant_id == tenant_id, Department.active.is_(True),
                                       func.lower(Department.name) == settings.ASSET_OWNER_FUNCTION.lower()).first()


def it_admin_owner(db: Session, tenant_id: int) -> Optional[str]:
    """Who gets the asset tasks: the most senior person in the owning function; with nobody in it yet,
    the CEO (so the work is never left without an owner)."""
    function = owner_function(db, tenant_id)
    if function is not None:
        people = db.query(Users).filter(Users.department_id == function.id, Users.terminated_at.is_(None)).all()
        if people:
            from app.core import authority

            return max(people, key=lambda u: authority.level(db, u)).UserID
    from app.services.vendor_invoice_intake import vendor_payer

    return vendor_payer(db, tenant_id)


def employee_name(employee: Optional[Employee]) -> str:
    if employee is None:
        return "(unknown employee)"
    return f"{employee.first_name or ''} {employee.last_name or ''}".strip() or employee.id


def asset_label(asset: Asset) -> str:
    what = " ".join(filter(None, [asset.make, asset.model])) or asset.category.replace("_", " ").title()
    return f"{asset.asset_tag} {what}" + (f" (SN {asset.serial_number})" if asset.serial_number else "")


def employee_path(employee_id: str) -> str:
    return f"/employees/{employee_id}?tab=assets"


def asset_path(asset_id: str) -> str:
    return f"{LEDGER_PATH}?asset={asset_id}"


def owner_label(db: Session, asset: Asset) -> str:
    if asset.owner_type == "COMPANY":
        company = db.get(Location, asset.owner_company_id) if asset.owner_company_id else None
        return company.name if company else "Owner not recorded"
    if asset.owner_type == "CLIENT":
        client = db.get(Client, asset.owner_client_id) if asset.owner_client_id else None
        return f"Client: {client.company_name}" if client else "Owner not recorded"
    if asset.owner_type == "LEASED":
        return f"Leased: {asset.owner_name}" if asset.owner_name else "Owner not recorded"
    return "Employee's own device"


def _event(db: Session, asset: Asset, event_type: str, *, employee_id: Optional[str] = None,
           project_id: Optional[str] = None, note: Optional[str] = None, actor: Optional[str] = None) -> None:
    db.add(AssetEvent(tenant_id=asset.tenant_id, asset_id=asset.id, event_type=event_type, employee_id=employee_id,
                      project_id=project_id, note=(note or None), actor_user_id=actor))


# --------------------------------------------------------------------------- tasks and notices

def _notices(db: Session) -> list:
    return db.info.setdefault("asset_notices", [])


def send_notices(db: Session) -> int:
    """Call after commit: emails for the tasks opened and the reminders queued by this change. A failed
    email never undoes the change (the task is in My Tasks either way); it is logged."""
    pending, db.info["asset_notices"] = list(_notices(db)), []
    sent = 0
    for kind, payload in pending:
        try:
            if kind == "task":
                from app.services.task_notification_service import notify_task_assigned

                task = db.get(Task, payload)
                if task is not None and notify_task_assigned(db, task):
                    sent += 1
            else:
                from app.services.staff_mail_service import queue_staff_email

                user = db.get(Users, payload["user_id"])
                if user is not None and user.terminated_at is None and queue_staff_email(
                        user, key=payload["key"], subject=payload["subject"], paragraphs=payload["paragraphs"],
                        link_path=payload.get("link"), link_label="Open my assets"):
                    sent += 1
        except Exception as exc:
            logger.error(f"[Assets] notice {kind} not sent: {exc}", exc_info=True)
    return sent


def _tell(db: Session, user_id: Optional[str], *, key: str, subject: str, paragraphs: List[str],
          link: Optional[str] = None) -> None:
    if user_id:
        _notices(db).append(("email", {"user_id": user_id, "key": key, "subject": subject,
                                       "paragraphs": paragraphs, "link": link}))


def _open_task(db: Session, tenant_id: int, *, category: str, link: str, title: str, description: str,
               due: Optional[date], priority: str = "MEDIUM", assignee: Optional[str] = None,
               to_function: bool = True) -> Task:
    """One open task per (category, link, assignee): found and refreshed, else opened. Goes to the IT
    Admin owner unless an assignee is named (an escalation to a manager)."""
    owner = assignee or it_admin_owner(db, tenant_id)
    query = db.query(Task).filter(Task.category == category, Task.link == link, Task.status.in_(OPEN_TASK_STATUSES))
    if assignee:
        query = query.filter(Task.assigned_to_user_id == assignee)
    task = query.order_by(Task.id).first()
    due_at = datetime.combine(due, datetime.min.time()) if due else None
    if task is not None:
        task.title, task.description = title[:300], description
        if due_at is not None and (task.due_date is None or due_at < task.due_date):
            task.due_date = due_at
        if priority == "HIGH":
            task.priority = "HIGH"
        return task
    function = owner_function(db, tenant_id) if to_function else None
    task = Task(title=title[:300], description=description, priority=priority, tenant_id=tenant_id, category=category,
                link=link, due_date=due_at, assigned_to_user_id=owner,
                department_id=function.id if function is not None else None,
                visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if owner else "ORG_WIDE")
    db.add(task)
    db.flush()
    if owner is None:
        logger.error(f"[Assets] task #{task.id} ({category}) has no owner: nobody is in the "
                     f"{settings.ASSET_OWNER_FUNCTION} function and no CEO is designated")
    _notices(db).append(("task", task.id))
    return task


def _close_tasks(db: Session, category: str, link: str, *, done: bool = True) -> None:
    values = {Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()} if done else {Task.status: "CANCELLED"}
    db.query(Task).filter(Task.category == category, Task.link == link, Task.status.in_(OPEN_TASK_STATUSES)) \
        .update(values, synchronize_session=False)


# --------------------------------------------------------------------------- the ledger

def _clean(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


def _validate_owner(db: Session, tenant_id: int, owner_type: str, company_id: Optional[str],
                    client_id: Optional[str], owner_name: Optional[str]) -> Dict:
    """Every item names its owner: one of our companies, the client, or the leasing company."""
    if owner_type not in OWNER_TYPES:
        raise AssetRefused(f"Owner type must be one of {', '.join(OWNER_TYPES)}.")
    if owner_type == "COMPANY":
        company = db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first() \
            if company_id else None
        if company is None:
            raise AssetRefused("Choose which of our companies owns this item.")
        return {"owner_company_id": company.id, "owner_client_id": None, "owner_name": None}
    if owner_type == "CLIENT":
        client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant_id).first() \
            if client_id else None
        if client is None:
            raise AssetRefused("Choose the client that owns this item.")
        return {"owner_company_id": None, "owner_client_id": client.id, "owner_name": None}
    if owner_type == "LEASED":
        if not _clean(owner_name):
            raise AssetRefused("Enter the leasing company that owns this item.")
        return {"owner_company_id": None, "owner_client_id": None, "owner_name": _clean(owner_name)}
    return {"owner_company_id": None, "owner_client_id": None, "owner_name": None}


def _next_tag(db: Session, tenant_id: int) -> str:
    count = db.query(func.count(Asset.id)).filter(Asset.tenant_id == tenant_id).scalar() or 0
    while True:
        count += 1
        tag = f"AST-{count:05d}"
        if not db.query(Asset.id).filter(Asset.tenant_id == tenant_id, Asset.asset_tag == tag).first():
            return tag


def _assert_serial_free(db: Session, tenant_id: int, serial: Optional[str], *, except_id: Optional[str] = None) -> None:
    if not serial:
        return
    query = db.query(Asset).filter(Asset.tenant_id == tenant_id, func.lower(Asset.serial_number) == serial.lower())
    if except_id:
        query = query.filter(Asset.id != except_id)
    other = query.first()
    if other is not None:
        raise AssetRefused(f"Serial number {serial} is already on the ledger as {other.asset_tag}.")


def _employee_in(db: Session, tenant_id: int, employee_id: Optional[str]) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.tenant_id == tenant_id).first() \
        if employee_id else None
    if employee is None:
        raise AssetRefused("Employee not found.")
    return employee


def register_asset(db: Session, tenant_id: int, user: Users, *, category: str, owner_type: str,
                   owner_company_id: Optional[str] = None, owner_client_id: Optional[str] = None,
                   owner_name: Optional[str] = None, make: Optional[str] = None, model: Optional[str] = None,
                   serial_number: Optional[str] = None, asset_tag: Optional[str] = None, condition: str = "GOOD",
                   purchase_date: Optional[date] = None, purchase_cost_cents: Optional[int] = None,
                   currency: Optional[str] = None, warranty_until: Optional[date] = None,
                   notes: Optional[str] = None, employee_id: Optional[str] = None) -> Asset:
    """Put one item on the ledger, in stock. An employee's own device is recorded as with them."""
    if category not in ASSET_CATEGORIES:
        raise AssetRefused(f"Category must be one of {', '.join(ASSET_CATEGORIES)}.")
    if condition not in ASSET_CONDITIONS:
        raise AssetRefused(f"Condition must be one of {', '.join(ASSET_CONDITIONS)}.")
    if purchase_cost_cents is not None and purchase_cost_cents < 0:
        raise AssetRefused("The purchase cost cannot be negative.")
    owner = _validate_owner(db, tenant_id, owner_type, owner_company_id, owner_client_id, owner_name)
    serial = _clean(serial_number)
    _assert_serial_free(db, tenant_id, serial)
    tag = _clean(asset_tag)
    if tag and db.query(Asset.id).filter(Asset.tenant_id == tenant_id, Asset.asset_tag == tag).first():
        raise AssetRefused(f"Asset tag {tag} is already used.")
    holder = _employee_in(db, tenant_id, employee_id) if owner_type == "PERSONAL" else None
    if holder is not None and holder.status == "EXITED":
        raise AssetRefused(f"{employee_name(holder)} has left.")
    asset = Asset(tenant_id=tenant_id, asset_tag=tag or _next_tag(db, tenant_id), category=category,
                  make=_clean(make), model=_clean(model), serial_number=serial, owner_type=owner_type,
                  condition=condition, purchase_date=purchase_date, purchase_cost_cents=purchase_cost_cents,
                  currency=(_clean(currency) or "").upper()[:3] or None, warranty_until=warranty_until,
                  notes=_clean(notes), created_by=user.UserID,
                  status="ASSIGNED" if holder is not None else "IN_STOCK",
                  holder_employee_id=holder.id if holder is not None else None,
                  assigned_at=datetime.utcnow() if holder is not None else None, **owner)
    db.add(asset)
    db.flush()
    _event(db, asset, "REGISTERED", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=f"Owner: {owner_label(db, asset)}")
    return asset


EDITABLE = ("category", "make", "model", "serial_number", "condition", "purchase_date", "purchase_cost_cents",
            "currency", "warranty_until", "notes")


def update_asset(db: Session, asset: Asset, user: Users, changes: Dict) -> Asset:
    """Correct what the ledger says about an item (never who holds it: that only moves by an action)."""
    changed = []
    if any(key in changes for key in ("owner_type", "owner_company_id", "owner_client_id", "owner_name")):
        owner_type = changes.get("owner_type", asset.owner_type)
        if "PERSONAL" in (owner_type, asset.owner_type) and owner_type != asset.owner_type:
            raise AssetRefused("An employee's own device cannot become someone else's (or the reverse): "
                               "retire this record and register the item again.")
        owner = _validate_owner(db, asset.tenant_id, owner_type, changes.get("owner_company_id", asset.owner_company_id),
                                changes.get("owner_client_id", asset.owner_client_id),
                                changes.get("owner_name", asset.owner_name))
        before = owner_label(db, asset)
        asset.owner_type = owner_type
        for key, value in owner.items():
            setattr(asset, key, value)
        if owner_label(db, asset) != before:
            changed.append(f"owner: {before} -> {owner_label(db, asset)}")
    for key in EDITABLE:
        if key not in changes:
            continue
        value = changes[key]
        if key in ("make", "model", "serial_number", "notes"):
            value = _clean(value)
        if key == "currency":
            value = (_clean(value) or "").upper()[:3] or None
        if key == "category" and value not in ASSET_CATEGORIES:
            raise AssetRefused(f"Category must be one of {', '.join(ASSET_CATEGORIES)}.")
        if key == "condition" and value not in ASSET_CONDITIONS:
            raise AssetRefused(f"Condition must be one of {', '.join(ASSET_CONDITIONS)}.")
        if key == "purchase_cost_cents" and value is not None and value < 0:
            raise AssetRefused("The purchase cost cannot be negative.")
        if key == "serial_number":
            _assert_serial_free(db, asset.tenant_id, value, except_id=asset.id)
        if getattr(asset, key) != value:
            if key != "notes":
                changed.append(f"{key.replace('_', ' ')}: {getattr(asset, key) or '-'} -> {value or '-'}")
            setattr(asset, key, value)
    if changed:
        _event(db, asset, "UPDATED", note="; ".join(changed)[:2000], actor=user.UserID)
    return asset


def _need_tracking(method: str, carrier: Optional[str], tracking_number: Optional[str]) -> None:
    if method not in HANDOVER_METHODS:
        raise AssetRefused(f"Handover must be one of {', '.join(HANDOVER_METHODS)}.")
    if method == "COURIER" and not (_clean(carrier) and _clean(tracking_number)):
        raise AssetRefused("A courier movement needs the courier's name and the tracking number.")


def _ship(db: Session, asset: Asset, direction: str, *, employee_id: Optional[str], carrier: str,
          tracking_number: str, shipped_on: Optional[date], expected_on: Optional[date], actor: str) -> AssetShipment:
    shipped = shipped_on or date.today()
    if shipped > date.today():
        raise AssetRefused("The ship date cannot be in the future.")
    if expected_on is not None and expected_on < shipped:
        raise AssetRefused("The expected delivery date is before the ship date.")
    shipment = AssetShipment(tenant_id=asset.tenant_id, asset_id=asset.id, direction=direction, employee_id=employee_id,
                             carrier=_clean(carrier), tracking_number=_clean(tracking_number), shipped_on=shipped,
                             expected_on=expected_on, created_by=actor)
    db.add(shipment)
    db.flush()
    return shipment


def open_shipment(db: Session, asset: Asset, direction: Optional[str] = None) -> Optional[AssetShipment]:
    query = db.query(AssetShipment).filter(AssetShipment.asset_id == asset.id, AssetShipment.status == "IN_TRANSIT")
    if direction:
        query = query.filter(AssetShipment.direction == direction)
    return query.order_by(AssetShipment.created_at.desc()).first()


def issue_asset(db: Session, asset: Asset, employee: Employee, user: Users, *, method: str,
                carrier: Optional[str] = None, tracking_number: Optional[str] = None,
                shipped_on: Optional[date] = None, expected_on: Optional[date] = None,
                project_id: Optional[str] = None, return_at_project_end: Optional[bool] = None) -> Asset:
    """Stock -> an employee, by hand or by courier (tracked until they confirm it arrived)."""
    if asset.status != "IN_STOCK":
        raise AssetRefused(f"{asset.asset_tag} is not in stock (it is {asset.status.replace('_', ' ').lower()}).")
    if employee.tenant_id != asset.tenant_id:
        raise AssetRefused("Employee not found.")
    if employee.status in LEAVING_STATUSES:
        raise AssetRefused(f"{employee_name(employee)} is leaving: nothing new is issued to them.")
    _need_tracking(method, carrier, tracking_number)
    project = None
    if project_id:
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == asset.tenant_id).first()
        if project is None:
            raise AssetRefused("Project not found.")
    if asset.owner_type == "CLIENT" and project is not None and project.client_id != asset.owner_client_id:
        raise AssetRefused("This device belongs to a different client than the project's.")
    asset.holder_employee_id, asset.assigned_at = employee.id, datetime.utcnow()
    asset.project_id = project.id if project is not None else None
    # a project's own kit comes back when the project ends; the person's company laptop does not
    asset.return_at_project_end = bool(project is not None and (
        return_at_project_end if return_at_project_end is not None else asset.owner_type != "COMPANY"))
    _event(db, asset, "ISSUED", employee_id=employee.id, project_id=asset.project_id, actor=user.UserID,
           note=f"Issued to {employee_name(employee)}" + (f" for {project.name}" if project is not None else ""))
    if method == "COURIER":
        shipment = _ship(db, asset, "TO_EMPLOYEE", employee_id=employee.id, carrier=carrier,
                         tracking_number=tracking_number, shipped_on=shipped_on, expected_on=expected_on,
                         actor=user.UserID)
        asset.status = "IN_TRANSIT"
        _event(db, asset, "SHIPPED", employee_id=employee.id, actor=user.UserID,
               note=f"{shipment.carrier} {shipment.tracking_number}, shipped {shipment.shipped_on}")
        _tell(db, employee.wros_user_id, key=f"asset-shipped-{shipment.id}",
              subject=f"On its way to you: {asset_label(asset)}",
              paragraphs=[f"{asset_label(asset)} was shipped to you on {shipment.shipped_on} with {shipment.carrier}, "
                          f"tracking number {shipment.tracking_number}.",
                          "When it arrives, open My assets and confirm you received it."],
              link=employee_path(employee.id))
    else:
        asset.status = "ASSIGNED"
        _event(db, asset, "RECEIVED", employee_id=employee.id, actor=user.UserID, note="Handed over in person")
    db.flush()
    sync_kit_task(db, employee)
    return asset


def confirm_receipt(db: Session, asset: Asset, user: Users, *, received_on: Optional[date] = None,
                    note: Optional[str] = None) -> Asset:
    """The item shipped to an employee arrived (confirmed by them or by IT Admin)."""
    shipment = open_shipment(db, asset, "TO_EMPLOYEE")
    if asset.status != "IN_TRANSIT" or shipment is None:
        raise AssetRefused(f"{asset.asset_tag} is not on its way to anyone.")
    received = received_on or date.today()
    if received < shipment.shipped_on or received > date.today():
        raise AssetRefused("The received date must be between the ship date and today.")
    shipment.status, shipment.received_on, shipment.received_by = "DELIVERED", received, user.UserID
    asset.status = "ASSIGNED"
    if shipment.chase_task_id:
        db.query(Task).filter(Task.id == shipment.chase_task_id, Task.status.in_(OPEN_TASK_STATUSES)) \
            .update({Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()}, synchronize_session=False)
    _event(db, asset, "RECEIVED", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=_clean(note) or f"Received {received}")
    db.flush()
    holder = db.get(Employee, asset.holder_employee_id) if asset.holder_employee_id else None
    if holder is not None:
        sync_kit_task(db, holder)
    return asset


# --------------------------------------------------------------------------- returns

def open_returns(db: Session, employee_id: str) -> List[AssetReturn]:
    return db.query(AssetReturn).filter(AssetReturn.employee_id == employee_id, AssetReturn.status == "OPEN") \
        .order_by(AssetReturn.due_date).all()


def held_assets(db: Session, employee_id: str, *, include_personal: bool = True) -> List[Asset]:
    query = db.query(Asset).filter(Asset.holder_employee_id == employee_id, Asset.status.in_(HELD_STATUSES))
    if not include_personal:
        query = query.filter(Asset.owner_type != "PERSONAL")
    return query.order_by(Asset.asset_tag).all()


def sync_return_task(db: Session, employee: Employee) -> Optional[Task]:
    """One open IT Admin task per employee with items to hand back; closed when none are left."""
    link = employee_path(employee.id)
    returns = open_returns(db, employee.id)
    if not returns:
        _close_tasks(db, TASK_RETURN, link)
        _close_tasks(db, TASK_ESCALATION, link)
        return None
    lines = []
    for row in returns:
        asset = db.get(Asset, row.asset_id)
        lines.append(f"- {asset_label(asset)} ({owner_label(db, asset)}), due {row.due_date}, "
                     f"{row.reason.replace('_', ' ').lower()}")
    name = employee_name(employee)
    return _open_task(
        db, employee.tenant_id, category=TASK_RETURN, link=link,
        title=f"Collect {len(returns)} asset(s) from {name}", due=min(r.due_date for r in returns),
        description=(f"{name} has to hand back:\n" + "\n".join(lines) + "\n\nRecord the courier and tracking number when "
                     "it is sent, then sign each return off when it arrives. A client's device goes back to the client "
                     "after that. This task closes by itself once everything is signed off."))


def request_return(db: Session, asset: Asset, *, reason: str, due_date: date, project_id: Optional[str] = None,
                   actor: Optional[str] = None, note: Optional[str] = None) -> AssetReturn:
    """Ask an item back from the employee who holds it (once per item; an earlier date wins)."""
    if reason not in RETURN_REASONS:
        raise AssetRefused(f"Reason must be one of {', '.join(RETURN_REASONS)}.")
    if asset.status not in HELD_STATUSES or not asset.holder_employee_id:
        raise AssetRefused(f"{asset.asset_tag} is not with an employee.")
    if asset.owner_type == "PERSONAL":
        raise AssetRefused("An employee's own device is not handed back.")
    employee = db.get(Employee, asset.holder_employee_id)
    existing = db.query(AssetReturn).filter(AssetReturn.asset_id == asset.id, AssetReturn.status == "OPEN").first()
    if existing is not None:
        if due_date < existing.due_date:
            existing.due_date = due_date
        if reason == "EXIT":
            existing.reason = "EXIT"
        sync_return_task(db, employee)
        return existing
    row = AssetReturn(tenant_id=asset.tenant_id, asset_id=asset.id, employee_id=employee.id, reason=reason,
                      project_id=project_id, due_date=due_date, note=_clean(note))
    db.add(row)
    db.flush()
    _event(db, asset, "RETURN_REQUESTED", employee_id=employee.id, project_id=project_id, actor=actor,
           note=f"{reason.replace('_', ' ').title()}: due back {due_date}" + (f". {_clean(note)}" if _clean(note) else ""))
    sync_return_task(db, employee)
    _tell(db, employee.wros_user_id, key=f"asset-return-{row.id}",
          subject=f"Please return {asset_label(asset)} by {due_date}",
          paragraphs=[f"{asset_label(asset)} is due back by {due_date} ({reason.replace('_', ' ').lower()}).",
                      "Send it by courier and enter the courier and tracking number under My assets, or hand it "
                      "to IT Admin in person."],
          link=employee_path(employee.id))
    return row


def record_return_shipment(db: Session, asset: Asset, user: Users, *, carrier: str, tracking_number: str,
                           shipped_on: Optional[date] = None, expected_on: Optional[date] = None) -> AssetShipment:
    """The employee sent the item back by courier (entered by them or by IT Admin)."""
    if asset.status != "ASSIGNED" or not asset.holder_employee_id:
        raise AssetRefused(f"{asset.asset_tag} is not with an employee.")
    if asset.owner_type == "PERSONAL":
        raise AssetRefused("An employee's own device is not handed back.")
    _need_tracking("COURIER", carrier, tracking_number)
    shipment = _ship(db, asset, "FROM_EMPLOYEE", employee_id=asset.holder_employee_id, carrier=carrier,
                     tracking_number=tracking_number, shipped_on=shipped_on, expected_on=expected_on, actor=user.UserID)
    asset.status = "IN_TRANSIT"
    _event(db, asset, "RETURN_SHIPPED", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=f"{shipment.carrier} {shipment.tracking_number}, shipped {shipment.shipped_on}")
    db.flush()
    return shipment


def receive_return(db: Session, asset: Asset, user: Users, *, condition: str, received_on: Optional[date] = None,
                   note: Optional[str] = None) -> Asset:
    """IT Admin has the item back and signs the return off. A damaged item opens a defect on it."""
    if condition not in ASSET_CONDITIONS:
        raise AssetRefused(f"Condition must be one of {', '.join(ASSET_CONDITIONS)}.")
    if asset.status not in HELD_STATUSES or not asset.holder_employee_id:
        raise AssetRefused(f"{asset.asset_tag} is not with an employee.")
    if asset.owner_type == "PERSONAL":
        raise AssetRefused("An employee's own device is not handed back.")
    if open_shipment(db, asset, "TO_EMPLOYEE") is not None:
        raise AssetRefused(f"{asset.asset_tag} is still on its way to the employee: confirm it arrived, or mark it lost.")
    received = received_on or date.today()
    if received > date.today():
        raise AssetRefused("The received date cannot be in the future.")
    shipment = open_shipment(db, asset, "FROM_EMPLOYEE")
    if shipment is not None:
        if received < shipment.shipped_on:
            raise AssetRefused("The received date is before the ship date.")
        shipment.status, shipment.received_on, shipment.received_by = "DELIVERED", received, user.UserID
        if shipment.chase_task_id:
            db.query(Task).filter(Task.id == shipment.chase_task_id, Task.status.in_(OPEN_TASK_STATUSES)) \
                .update({Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()}, synchronize_session=False)
    employee = db.get(Employee, asset.holder_employee_id)
    now = datetime.utcnow()
    for row in db.query(AssetReturn).filter(AssetReturn.asset_id == asset.id, AssetReturn.status == "OPEN").all():
        row.status, row.signed_off_by, row.signed_off_at = "RETURNED", user.UserID, now
    _event(db, asset, "RETURNED", employee_id=employee.id, project_id=asset.project_id, actor=user.UserID,
           note=f"Back from {employee_name(employee)}, condition {condition.lower()}"
                + (f". {_clean(note)}" if _clean(note) else ""))
    asset.status, asset.condition = "IN_STOCK", condition
    asset.holder_employee_id, asset.project_id, asset.return_at_project_end, asset.assigned_at = None, None, False, None
    db.flush()
    if condition == "DAMAGED":
        report_issue(db, asset, user, description=f"Came back damaged from {employee_name(employee)}."
                     + (f" {_clean(note)}" if _clean(note) else ""), severity="HIGH")
    sync_return_task(db, employee)
    sync_kit_task(db, employee)
    return asset


def return_to_owner(db: Session, asset: Asset, user: Users, *, method: str, carrier: Optional[str] = None,
                    tracking_number: Optional[str] = None, shipped_on: Optional[date] = None,
                    note: Optional[str] = None) -> Asset:
    """A client's or a leased item in our stock goes back to its owner and leaves the ledger."""
    if asset.owner_type not in ("CLIENT", "LEASED"):
        raise AssetRefused("Only a client's or a leased item goes back to an owner.")
    if asset.status != "IN_STOCK":
        raise AssetRefused(f"{asset.asset_tag} must be back in stock first (it is {asset.status.replace('_', ' ').lower()}).")
    _need_tracking(method, carrier, tracking_number)
    detail = "handed over in person"
    if method == "COURIER":
        shipment = _ship(db, asset, "TO_OWNER", employee_id=None, carrier=carrier, tracking_number=tracking_number,
                         shipped_on=shipped_on, expected_on=None, actor=user.UserID)
        detail = f"{shipment.carrier} {shipment.tracking_number}, shipped {shipment.shipped_on}"
    asset.status = "RETURNED_TO_OWNER"
    _event(db, asset, "RETURNED_TO_OWNER", actor=user.UserID,
           note=f"To {owner_label(db, asset)}: {detail}" + (f". {_clean(note)}" if _clean(note) else ""))
    db.flush()
    return asset


def confirm_owner_received(db: Session, asset: Asset, user: Users, received_on: Optional[date] = None) -> AssetShipment:
    shipment = open_shipment(db, asset, "TO_OWNER")
    if shipment is None:
        raise AssetRefused(f"{asset.asset_tag} has no open shipment to its owner.")
    received = received_on or date.today()
    if received < shipment.shipped_on or received > date.today():
        raise AssetRefused("The received date must be between the ship date and today.")
    shipment.status, shipment.received_on, shipment.received_by = "DELIVERED", received, user.UserID
    if shipment.chase_task_id:
        db.query(Task).filter(Task.id == shipment.chase_task_id, Task.status.in_(OPEN_TASK_STATUSES)) \
            .update({Task.status: "COMPLETED", Task.completed_at: datetime.utcnow()}, synchronize_session=False)
    _event(db, asset, "RECEIVED", actor=user.UserID, note=f"{owner_label(db, asset)} confirmed receipt {received}")
    return shipment


# --------------------------------------------------------------------------- defects, loss, retirement

def report_issue(db: Session, asset: Asset, user: Users, *, description: str, severity: str = "MEDIUM") -> AssetIssue:
    if not _clean(description):
        raise AssetRefused("Describe the defect.")
    if severity not in ISSUE_SEVERITIES:
        raise AssetRefused(f"Severity must be one of {', '.join(ISSUE_SEVERITIES)}.")
    if asset.status in CLOSED_STATUSES:
        raise AssetRefused(f"{asset.asset_tag} is {asset.status.replace('_', ' ').lower()}: no defect can be raised on it.")
    issue = AssetIssue(tenant_id=asset.tenant_id, asset_id=asset.id, description=_clean(description), severity=severity,
                       reported_by=user.UserID)
    db.add(issue)
    db.flush()
    _event(db, asset, "DEFECT_REPORTED", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=f"{severity.title()}: {issue.description}"[:2000])
    holder = db.get(Employee, asset.holder_employee_id) if asset.holder_employee_id else None
    task = _open_task(
        db, asset.tenant_id, category=TASK_ISSUE, link=asset_path(asset.id),
        title=f"Defect on {asset_label(asset)}", priority="HIGH" if severity == "HIGH" else "MEDIUM",
        due=date.today() + timedelta(days=settings.ASSET_DEFECT_MAX_OPEN_DAYS),
        description=(f"{issue.description}\n\nHolder: {employee_name(holder) if holder else 'in stock'}. "
                     "Decide: repair it (record the vendor, then the fix and its cost), close it as no fault, or "
                     "retire the item."))
    issue.task_id = task.id
    return issue


def _open_issues(db: Session, asset_id: str) -> List[AssetIssue]:
    return db.query(AssetIssue).filter(AssetIssue.asset_id == asset_id,
                                       AssetIssue.status.in_(OPEN_ISSUE_STATUSES)).all()


def update_issue(db: Session, issue: AssetIssue, user: Users, *, action: str, resolution: Optional[str] = None,
                 repair_vendor: Optional[str] = None, fix_cost_cents: Optional[int] = None) -> AssetIssue:
    """START_REPAIR (with the vendor), FIXED / NO_FAULT (with what was found), or RETIRE the item."""
    if issue.status not in OPEN_ISSUE_STATUSES:
        raise AssetRefused("This defect is already closed.")
    asset = db.get(Asset, issue.asset_id)
    if fix_cost_cents is not None and fix_cost_cents < 0:
        raise AssetRefused("The repair cost cannot be negative.")
    if action == "START_REPAIR":
        if not _clean(repair_vendor):
            raise AssetRefused("Enter who is repairing it.")
        issue.status, issue.repair_vendor = "IN_REPAIR", _clean(repair_vendor)
        if asset.status == "IN_STOCK":
            asset.status = "IN_REPAIR"
        _event(db, asset, "REPAIR_STARTED", employee_id=asset.holder_employee_id, actor=user.UserID,
               note=f"With {issue.repair_vendor}")
        return issue
    if action not in ("FIXED", "NO_FAULT", "RETIRE"):
        raise AssetRefused("Action must be START_REPAIR, FIXED, NO_FAULT or RETIRE.")
    if not _clean(resolution):
        raise AssetRefused("Say what was found or done.")
    issue.resolution, issue.fix_cost_cents = _clean(resolution), fix_cost_cents
    issue.resolved_by, issue.resolved_at = user.UserID, datetime.utcnow()
    if action == "RETIRE":
        issue.status = "RETIRED"
        db.flush()
        retire_asset(db, asset, user, reason=f"Defect not worth repairing: {issue.resolution}")
        return issue
    issue.status = action
    cost = f", cost {fix_cost_cents / 100:,.2f}" if fix_cost_cents else ""
    _event(db, asset, "DEFECT_CLOSED", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=f"{action.replace('_', ' ').title()}: {issue.resolution}{cost}"[:2000])
    db.flush()
    if not _open_issues(db, asset.id):
        if asset.status == "IN_REPAIR":
            asset.status = "IN_STOCK"
        if action == "FIXED" and asset.condition == "DAMAGED":
            asset.condition = "GOOD"
        _close_tasks(db, TASK_ISSUE, asset_path(asset.id))
    return issue


def mark_lost(db: Session, asset: Asset, user: Users, *, note: str) -> Asset:
    """The item cannot be found (lost, stolen, never arrived). It stays on the ledger as lost, against
    the person who held it, and their return is closed as lost: IT Admin still signs their clearance."""
    if not _clean(note):
        raise AssetRefused("Say what happened (and the police report number for a theft).")
    if asset.status in CLOSED_STATUSES:
        raise AssetRefused(f"{asset.asset_tag} is already {asset.status.replace('_', ' ').lower()}.")
    employee = db.get(Employee, asset.holder_employee_id) if asset.holder_employee_id else None
    for shipment in db.query(AssetShipment).filter(AssetShipment.asset_id == asset.id,
                                                   AssetShipment.status == "IN_TRANSIT").all():
        shipment.status = "LOST"
    for row in db.query(AssetReturn).filter(AssetReturn.asset_id == asset.id, AssetReturn.status == "OPEN").all():
        row.status, row.note = "LOST", _clean(note)
    _event(db, asset, "LOST", employee_id=asset.holder_employee_id, actor=user.UserID,
           note=(f"While with {employee_name(employee)}: " if employee else "") + _clean(note))
    if employee is not None and db.query(AssetReturn.id).filter(
            AssetReturn.asset_id == asset.id, AssetReturn.employee_id == employee.id).first() is None:
        # no return was open: still keep on record that it was lost while with them
        db.add(AssetReturn(tenant_id=asset.tenant_id, asset_id=asset.id, employee_id=employee.id, reason="RECALL",
                           due_date=date.today(), status="LOST", note=_clean(note)))
    asset.status, asset.holder_employee_id = "LOST", None
    db.flush()
    if employee is not None:
        sync_return_task(db, employee)
        sync_kit_task(db, employee)
    return asset


def retire_asset(db: Session, asset: Asset, user: Users, *, reason: str) -> Asset:
    if not _clean(reason):
        raise AssetRefused("Say why it is retired (and how it was disposed of or wiped).")
    if asset.status in HELD_STATUSES:
        raise AssetRefused(f"{asset.asset_tag} is with an employee: it has to come back before it is retired.")
    if asset.status in ("RETIRED", "RETURNED_TO_OWNER"):
        raise AssetRefused(f"{asset.asset_tag} is already {asset.status.replace('_', ' ').lower()}.")
    now = datetime.utcnow()
    for issue in _open_issues(db, asset.id):
        issue.status, issue.resolved_by, issue.resolved_at = "RETIRED", user.UserID, now
        issue.resolution = issue.resolution or "Item retired"
    asset.status = "RETIRED"
    _event(db, asset, "RETIRED", actor=user.UserID, note=_clean(reason))
    _close_tasks(db, TASK_ISSUE, asset_path(asset.id))
    db.flush()
    return asset


# --------------------------------------------------------------------------- leaving: clearance

def clearance_for(db: Session, employee_id: str) -> Optional[AssetClearance]:
    return db.query(AssetClearance).filter(AssetClearance.employee_id == employee_id).first()


def open_clearance(db: Session, employee: Employee, *, due_date: Optional[date], actor: Optional[str] = None) -> AssetClearance:
    """Notice or exit: every item is asked back by the last working day and one clearance is opened for
    IT Admin. Idempotent; a later exit tightens the date."""
    due = due_date or date.today()
    clearance = clearance_for(db, employee.id)
    if clearance is None:
        clearance = AssetClearance(tenant_id=employee.tenant_id, employee_id=employee.id, due_date=due)
        db.add(clearance)
        db.flush()
    else:
        clearance.status, clearance.signed_off_by, clearance.signed_off_at = "PENDING", None, None
        clearance.due_date = due
    held = held_assets(db, employee.id, include_personal=False)
    for asset in held:
        request_return(db, asset, reason="EXIT", due_date=due, actor=actor)
    name = employee_name(employee)
    task = _open_task(
        db, employee.tenant_id, category=TASK_CLEARANCE, link=employee_path(employee.id), due=due, priority="HIGH",
        title=f"Asset clearance: {name} leaves on {due}",
        description=(f"{name}'s last working day is {due}. Full and final settlement is on hold until you sign off "
                     f"their asset clearance. The ledger shows {len(held)} item(s) with them"
                     + (": " + ", ".join(asset_label(a) for a in held) if held else "")
                     + ". Check that nothing else is out with them (anything not on the ledger yet), get every "
                       "item back and signed off, then sign the clearance on their Assets tab."))
    clearance.task_id = task.id
    return clearance


def clearance_blockers(db: Session, employee: Employee) -> List[str]:
    """What still stops IT Admin from signing the clearance off."""
    return [f"{asset_label(a)} is still {'in transit' if a.status == 'IN_TRANSIT' else 'with them'}"
            for a in held_assets(db, employee.id, include_personal=False)]


def lost_while_held(db: Session, employee_id: str) -> List[Asset]:
    ids = [aid for (aid,) in db.query(AssetReturn.asset_id).filter(AssetReturn.employee_id == employee_id,
                                                                  AssetReturn.status == "LOST")]
    return db.query(Asset).filter(Asset.id.in_(ids)).all() if ids else []


def sign_off_clearance(db: Session, employee: Employee, user: Users, *, note: Optional[str] = None) -> AssetClearance:
    """IT Admin confirms everything is back: this is what releases full and final settlement."""
    if employee.status not in LEAVING_STATUSES:
        raise AssetRefused(f"{employee_name(employee)} is not leaving: there is no clearance to sign.")
    blockers = clearance_blockers(db, employee)
    if blockers:
        raise AssetRefused("Not everything is back: " + "; ".join(blockers) + ".")
    lost = lost_while_held(db, employee.id)
    if lost and not _clean(note):
        raise AssetRefused("Lost while with them: " + ", ".join(asset_label(a) for a in lost)
                           + ". Add a note saying how this was settled before signing off.")
    clearance = clearance_for(db, employee.id)
    if clearance is None:
        clearance = AssetClearance(tenant_id=employee.tenant_id, employee_id=employee.id, due_date=employee.exit_date)
        db.add(clearance)
    now = datetime.utcnow()
    clearance.status, clearance.signed_off_by, clearance.signed_off_at, clearance.note = "CLEARED", user.UserID, now, _clean(note)
    for asset in held_assets(db, employee.id):  # only their own devices are left
        asset.status, asset.holder_employee_id = "RETURNED_TO_OWNER", None
        _event(db, asset, "RETURNED_TO_OWNER", employee_id=employee.id, actor=user.UserID,
               note="Employee's own device: off the ledger at exit (work access removed)")
    link = employee_path(employee.id)
    for category in (TASK_CLEARANCE, TASK_RETURN, TASK_ESCALATION, TASK_KIT):
        _close_tasks(db, category, link)
    db.flush()
    return clearance


def settlement_hold(db: Session, employee: Employee) -> Optional[str]:
    """Why full and final settlement may not be paid yet, or None when assets do not stop it. The same
    rule in every country: nothing is paid until IT Admin has signed the asset clearance."""
    if employee.status not in LEAVING_STATUSES:
        return None
    clearance = clearance_for(db, employee.id)
    if clearance is not None and clearance.status == "CLEARED":
        return None
    blockers = clearance_blockers(db, employee)
    if blockers:
        return "Assets not returned: " + "; ".join(blockers) + "."
    return "IT Admin has not signed off the asset clearance yet."


# --------------------------------------------------------------------------- projects: the kit

def project_requirements(db: Session, project_id: str) -> List[ProjectAssetRequirement]:
    return db.query(ProjectAssetRequirement).filter(ProjectAssetRequirement.project_id == project_id) \
        .order_by(ProjectAssetRequirement.category, ProjectAssetRequirement.provided_by).all()


def set_project_requirements(db: Session, project: Project, user: Users, items: List[Dict]) -> List[ProjectAssetRequirement]:
    """Replace the kit a project needs each person on it to hold; everyone on it is checked again."""
    seen, rows = set(), []
    for item in items:
        category, provided_by = item.get("category"), item.get("provided_by") or "COMPANY"
        quantity = item.get("quantity") or 1
        if category not in ASSET_CATEGORIES:
            raise AssetRefused(f"Category must be one of {', '.join(ASSET_CATEGORIES)}.")
        if provided_by not in ("COMPANY", "CLIENT"):
            raise AssetRefused("The kit comes from us (COMPANY) or from the client (CLIENT).")
        if not isinstance(quantity, int) or quantity < 1:
            raise AssetRefused("Quantity must be 1 or more.")
        if (category, provided_by) in seen:
            raise AssetRefused(f"{category.replace('_', ' ').title()} from {provided_by.lower()} is listed twice.")
        seen.add((category, provided_by))
        rows.append(ProjectAssetRequirement(tenant_id=project.tenant_id, project_id=project.id, category=category,
                                            provided_by=provided_by, quantity=quantity, note=_clean(item.get("note")),
                                            created_by=user.UserID))
    db.query(ProjectAssetRequirement).filter(ProjectAssetRequirement.project_id == project.id) \
        .delete(synchronize_session=False)
    db.add_all(rows)
    db.flush()
    for allocation in db.query(EmployeeAllocation).filter(EmployeeAllocation.project_id == project.id,
                                                          EmployeeAllocation.status == "ACTIVE").all():
        employee = db.get(Employee, allocation.employee_id)
        if employee is not None:
            sync_kit_task(db, employee)
    return rows


def kit_gaps(db: Session, employee: Employee) -> List[Dict]:
    """The kit this person's active project placements need and they do not hold (or have on its way)."""
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status == "ACTIVE",
        EmployeeAllocation.project_id.isnot(None)).all()
    if not allocations:
        return []
    held = held_assets(db, employee.id)
    gaps = []
    for allocation in allocations:
        project = db.get(Project, allocation.project_id)
        for need in project_requirements(db, allocation.project_id):
            if need.provided_by == "CLIENT":
                have = sum(1 for a in held if a.category == need.category and a.owner_type == "CLIENT"
                           and a.owner_client_id == project.client_id)
            else:
                have = sum(1 for a in held if a.category == need.category and a.owner_type in ("COMPANY", "LEASED"))
            if have < need.quantity:
                gaps.append({"project_id": project.id, "project_name": project.name, "category": need.category,
                             "provided_by": need.provided_by, "needed": need.quantity, "held": have,
                             "start_date": allocation.start_date, "note": need.note})
    return gaps


def sync_kit_task(db: Session, employee: Employee) -> Optional[Task]:
    """One open IT Admin task per person missing project kit; closed once they hold it all."""
    link = employee_path(employee.id)
    gaps = kit_gaps(db, employee) if employee.status not in LEAVING_STATUSES else []
    if not gaps:
        _close_tasks(db, TASK_KIT, link)
        return None
    name = employee_name(employee)
    lines = [f"- {g['needed'] - g['held']} x {g['category'].replace('_', ' ').lower()} for {g['project_name']} "
             f"({'the client sends its own' if g['provided_by'] == 'CLIENT' else 'from our stock'})"
             + (f": {g['note']}" if g["note"] else "") for g in gaps]
    return _open_task(
        db, employee.tenant_id, category=TASK_KIT, link=link, title=f"Issue project kit to {name}",
        due=max(min(g["start_date"] for g in gaps), date.today()), priority="HIGH",
        description=(f"{name} is placed on a project that needs kit they do not hold:\n" + "\n".join(lines)
                     + "\n\nIssue it from the asset ledger (register the client's device first when the client sends "
                       "one). This task closes by itself once they hold it."))


def returnable_at_project_end(db: Session, employee: Employee, allocation: EmployeeAllocation) -> List[Asset]:
    """What comes back when this placement ends: the client's devices and the kit issued for the project,
    unless another placement of theirs still needs it. Their company laptop stays (they keep it while
    employed, on the bench too)."""
    others = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.id != allocation.id,
        EmployeeAllocation.status.in_(HOLDING_STATUSES)).all()
    same_client = any(o.client_id == allocation.client_id for o in others)
    same_project = allocation.project_id is not None and any(o.project_id == allocation.project_id for o in others)
    result = []
    for asset in held_assets(db, employee.id, include_personal=False):
        client_device = asset.owner_type == "CLIENT" and asset.owner_client_id == allocation.client_id
        project_kit = (allocation.project_id is not None and asset.project_id == allocation.project_id
                       and asset.return_at_project_end)
        if (client_device and not same_client) or (project_kit and not same_project and not client_device):
            result.append(asset)
    return result


def on_allocation_ended(db: Session, allocation: EmployeeAllocation, employee: Employee,
                        actor: Optional[str] = None) -> List[AssetReturn]:
    due = allocation.end_date or date.today()
    rows = [request_return(db, asset, reason="PROJECT_END", due_date=due, project_id=allocation.project_id, actor=actor)
            for asset in returnable_at_project_end(db, employee, allocation)]
    sync_kit_task(db, employee)
    return rows


# --------------------------------------------------------------------------- what is wrong right now

def _days(count: int) -> str:
    return f"{count} day{'s' if count != 1 else ''}"


def ledger_alerts(db: Session, tenant_id: int, today: Optional[date] = None) -> List[Dict]:
    """Everything on the ledger that needs someone, most serious first."""
    today = today or date.today()
    alerts: List[Dict] = []

    def add(kind, severity, message, *, asset=None, employee_id=None):
        alerts.append({"kind": kind, "severity": severity, "message": message,
                       "asset_id": asset.id if asset is not None else None,
                       "asset_tag": asset.asset_tag if asset is not None else None, "employee_id": employee_id})

    assets = db.query(Asset).filter(Asset.tenant_id == tenant_id, Asset.status.notin_(("RETIRED", "RETURNED_TO_OWNER"))).all()
    by_id = {a.id: a for a in assets}
    holders = {e.id: e for e in db.query(Employee).filter(
        Employee.id.in_({a.holder_employee_id for a in assets if a.holder_employee_id} or {""})).all()}
    for asset in assets:
        holder = holders.get(asset.holder_employee_id) if asset.holder_employee_id else None
        if asset.status in HELD_STATUSES and holder is None:
            add("NO_HOLDER", "HIGH", f"{asset_label(asset)} is marked as out but nobody is recorded as holding it.", asset=asset)
        if asset.status in ("IN_STOCK", "IN_REPAIR") and asset.holder_employee_id:
            add("NO_HOLDER", "HIGH", f"{asset_label(asset)} is in stock but still shows a holder.", asset=asset)
        if holder is not None and holder.status == "EXITED" and asset.owner_type != "PERSONAL":
            add("HOLDER_LEFT", "HIGH", f"{asset_label(asset)} is still with {employee_name(holder)}, who has left"
                + (f" ({holder.exit_date})" if holder.exit_date else "") + ".", asset=asset, employee_id=holder.id)
        if owner_label(db, asset) == "Owner not recorded":
            add("OWNER_UNKNOWN", "MEDIUM", f"{asset_label(asset)} has no owner recorded.", asset=asset)
        if (asset.warranty_until and asset.status != "LOST"
                and today <= asset.warranty_until <= today + timedelta(days=settings.ASSET_WARRANTY_ALERT_DAYS)):
            add("WARRANTY", "LOW", f"Warranty on {asset_label(asset)} ends {asset.warranty_until}.", asset=asset)
    for row in db.query(AssetReturn).filter(AssetReturn.tenant_id == tenant_id, AssetReturn.status == "OPEN",
                                            AssetReturn.due_date < today).all():
        asset = by_id.get(row.asset_id)
        if asset is not None:
            add("RETURN_OVERDUE", "HIGH", f"{asset_label(asset)} was due back {row.due_date} "
                f"({_days((today - row.due_date).days)} overdue) from {employee_name(db.get(Employee, row.employee_id))}.",
                asset=asset, employee_id=row.employee_id)
    limit = settings.ASSET_TRANSIT_MAX_DAYS
    for shipment in db.query(AssetShipment).filter(AssetShipment.tenant_id == tenant_id,
                                                   AssetShipment.status == "IN_TRANSIT").all():
        late_from = shipment.expected_on or (shipment.shipped_on + timedelta(days=limit))
        asset = by_id.get(shipment.asset_id) or db.get(Asset, shipment.asset_id)
        if today > late_from and asset is not None:
            add("IN_TRANSIT_TOO_LONG", "HIGH", f"{asset_label(asset)} left on {shipment.shipped_on} with "
                f"{shipment.carrier} ({shipment.tracking_number}) and has not been confirmed as received.",
                asset=asset, employee_id=shipment.employee_id)
    stale = datetime.combine(today - timedelta(days=settings.ASSET_DEFECT_MAX_OPEN_DAYS), datetime.min.time())
    for issue in db.query(AssetIssue).filter(AssetIssue.tenant_id == tenant_id, AssetIssue.status.in_(OPEN_ISSUE_STATUSES),
                                             AssetIssue.reported_at < stale).all():
        asset = by_id.get(issue.asset_id)
        if asset is not None:
            add("DEFECT_OPEN", "MEDIUM", f"A defect on {asset_label(asset)} has been open since "
                f"{issue.reported_at:%Y-%m-%d}: {issue.description[:120]}", asset=asset)
    for employee in _people_on_projects_with_kit(db, tenant_id):
        for gap in kit_gaps(db, employee):
            add("KIT_MISSING", "HIGH", f"{employee_name(employee)} is on {gap['project_name']} without "
                f"{gap['needed'] - gap['held']} x {gap['category'].replace('_', ' ').lower()}.", employee_id=employee.id)
    leavers = db.query(Employee).filter(Employee.tenant_id == tenant_id, Employee.status == "EXITED").all()
    cleared = {eid for (eid,) in db.query(AssetClearance.employee_id).filter(AssetClearance.status == "CLEARED")}
    pending = {eid for (eid,) in db.query(AssetClearance.employee_id).filter(AssetClearance.status == "PENDING")}
    for employee in leavers:
        if employee.id in pending and employee.id not in cleared:
            add("CLEARANCE_PENDING", "HIGH", f"{employee_name(employee)} has left and their asset clearance is not "
                "signed off: full and final settlement is on hold.", employee_id=employee.id)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    alerts.sort(key=lambda a: order[a["severity"]])
    return alerts


def _people_on_projects_with_kit(db: Session, tenant_id: int) -> List[Employee]:
    project_ids = db.query(ProjectAssetRequirement.project_id).filter(ProjectAssetRequirement.tenant_id == tenant_id)
    employee_ids = db.query(EmployeeAllocation.employee_id).filter(
        EmployeeAllocation.status == "ACTIVE", EmployeeAllocation.project_id.in_(project_ids)).distinct()
    return db.query(Employee).filter(Employee.id.in_(employee_ids), Employee.status.notin_(LEAVING_STATUSES)).all()


# --------------------------------------------------------------------------- the daily sweep

def escalation_days() -> List[int]:
    raw = settings.ASSET_RETURN_ESCALATION_DAYS or ""
    try:
        days = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError(f"ASSET_RETURN_ESCALATION_DAYS must be three numbers of days (e.g. 1,3,7), got {raw!r}") from exc
    if len(days) != 3 or days != sorted(days) or days[0] < 0:
        raise ValueError(f"ASSET_RETURN_ESCALATION_DAYS must be three rising numbers of days (e.g. 1,3,7), got {raw!r}")
    return days


def escalate_return(db: Session, row: AssetReturn, today: date) -> int:
    """Move an overdue return up to the level its age calls for (each level once). Returns the new level."""
    overdue = (today - row.due_date).days
    level = sum(1 for threshold in escalation_days() if overdue >= threshold)
    if level <= row.escalation_level:
        return row.escalation_level
    asset, employee = db.get(Asset, row.asset_id), db.get(Employee, row.employee_id)
    name, link = employee_name(employee), employee_path(employee.id)
    what = f"{asset_label(asset)} was due back {row.due_date} ({_days(overdue)} overdue)"
    if row.escalation_level < 1:
        _tell(db, employee.wros_user_id, key=f"asset-overdue-{row.id}", subject=f"Overdue: return {asset_label(asset)}",
              paragraphs=[f"{what}. Please send it back today and enter the courier and tracking number under "
                          "My assets.", "If it is not returned your reporting manager is told next."], link=link)
        task = sync_return_task(db, employee)
        if task is not None:
            task.priority = "HIGH"
    if level >= 2 and row.escalation_level < 2:
        from app.services.org_structure_service import manager_user_for

        manager = manager_user_for(db, employee)
        if manager is not None:
            _open_task(db, row.tenant_id, category=TASK_ESCALATION, link=link, assignee=manager.UserID, to_function=False,
                       priority="HIGH", due=today, title=f"{name} has not returned company assets",
                       description=f"{what}. You are {name}'s reporting manager: get it sent back, or tell IT Admin "
                                   "what happened to it. This closes by itself when IT Admin signs the return off.")
        else:
            logger.warning(f"[Assets] return {row.id}: {name} has no reporting manager to escalate to")
    if level >= 3 and row.escalation_level < 3:
        from app.services.bu_leadership import head_user_id

        head = head_user_id(db, employee.bu_id, employee.company_id)
        if head:
            _open_task(db, row.tenant_id, category=TASK_ESCALATION, link=link, assignee=head, to_function=False,
                       priority="HIGH", due=today, title=f"Unreturned assets: {name}",
                       description=f"{what}. Reminders to {name} and their manager have not brought it back. Decide "
                                   "with IT Admin how it is recovered or written off (IT Admin then marks it lost).")
        else:
            logger.warning(f"[Assets] return {row.id}: no BU head for {name} to escalate to")
    row.escalation_level, row.last_escalated_at = level, datetime.utcnow()
    _event(db, asset, "ESCALATED", employee_id=employee.id,
           note=f"Return {_days(overdue)} overdue: " + {1: "holder reminded", 2: "reporting manager told",
                                                        3: "BU head told"}[level])
    return level


def run_asset_sweep(db: Session, today: Optional[date] = None) -> Dict:
    """Daily (scheduled job asset_sweep, internal only). Idempotent.
    1. Placements ending within ASSET_RETURN_LEAD_DAYS: the client's devices and project kit are asked back now.
    2. Anyone in notice or exited without a clearance gets one.
    3. Overdue returns climb: holder, reporting manager, BU head.
    4. A courier movement not confirmed within ASSET_TRANSIT_MAX_DAYS: one task to chase it.
    5. People on a project without the kit it needs: one task to issue it."""
    today = today or date.today()
    result = {"returns_requested": 0, "clearances_opened": 0, "escalated": 0, "chased": 0, "kit_tasks": 0, "failed": 0}

    def step(label, work):
        try:
            with db.begin_nested():  # a failure undoes this item only
                done = work()
            db.commit()
            send_notices(db)
            return done
        except Exception as exc:  # one bad row must not stop the others; logged and counted
            db.info["asset_notices"] = []
            logger.error(f"[Assets] sweep {label} failed: {exc}", exc_info=True)
            result["failed"] += 1
            return 0

    horizon = today + timedelta(days=settings.ASSET_RETURN_LEAD_DAYS)
    ending = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.status == "ACTIVE", EmployeeAllocation.end_date.isnot(None),
        EmployeeAllocation.end_date >= today, EmployeeAllocation.end_date <= horizon).all()
    for allocation in ending:
        employee = db.get(Employee, allocation.employee_id)
        if employee is None or not held_assets(db, employee.id, include_personal=False):
            continue
        before = {r.asset_id for r in open_returns(db, employee.id)}
        result["returns_requested"] += step(
            f"allocation {allocation.id}",
            lambda a=allocation, e=employee, b=before: len(
                [r for r in on_allocation_ended(db, a, e) if r.asset_id not in b]))

    with_clearance = db.query(AssetClearance.employee_id)
    for employee in db.query(Employee).filter(Employee.status.in_(LEAVING_STATUSES), Employee.tenant_id.isnot(None),
                                              ~Employee.id.in_(with_clearance)).all():
        # exited before the ledger existed with nothing on it: nothing to clear
        if employee.status == "EXITED" and not held_assets(db, employee.id):
            continue
        result["clearances_opened"] += step(
            f"clearance {employee.id}",
            lambda e=employee: 1 if open_clearance(db, e, due_date=e.exit_date or today) else 0)

    for row in db.query(AssetReturn).filter(AssetReturn.status == "OPEN", AssetReturn.due_date < today).all():
        level = row.escalation_level
        result["escalated"] += step(f"return {row.id}", lambda r=row, was=level: 1 if escalate_return(db, r, today) > was else 0)

    for shipment in db.query(AssetShipment).filter(AssetShipment.status == "IN_TRANSIT",
                                                   AssetShipment.chase_task_id.is_(None)).all():
        late_from = shipment.expected_on or (shipment.shipped_on + timedelta(days=settings.ASSET_TRANSIT_MAX_DAYS))
        if today <= late_from:
            continue
        result["chased"] += step(f"shipment {shipment.id}", lambda s=shipment: _chase(db, s, today))

    for tenant_id, in db.query(ProjectAssetRequirement.tenant_id).distinct():
        for employee in _people_on_projects_with_kit(db, tenant_id):
            had = db.query(Task.id).filter(Task.category == TASK_KIT, Task.link == employee_path(employee.id),
                                           Task.status.in_(OPEN_TASK_STATUSES)).first() is not None
            result["kit_tasks"] += step(
                f"kit {employee.id}", lambda e=employee, h=had: 1 if sync_kit_task(db, e) is not None and not h else 0)
    logger.info(f"[Assets] sweep {result}")
    return result


def _chase(db: Session, shipment: AssetShipment, today: date) -> int:
    asset = db.get(Asset, shipment.asset_id)
    who = employee_name(db.get(Employee, shipment.employee_id)) if shipment.employee_id else owner_label(db, asset)
    way = {"TO_EMPLOYEE": f"to {who}", "FROM_EMPLOYEE": f"back from {who}", "TO_OWNER": f"to {who}"}[shipment.direction]
    task = _open_task(
        db, shipment.tenant_id, category=TASK_TRANSIT, link=asset_path(asset.id), priority="HIGH", due=today,
        title=f"Chase the courier: {asset_label(asset)}",
        description=(f"{asset_label(asset)} left on {shipment.shipped_on} {way} with {shipment.carrier}, tracking "
                     f"{shipment.tracking_number}, and nobody has confirmed it arrived. Check the tracking; then "
                     "confirm receipt on the ledger, or mark the item lost."))
    shipment.chase_task_id = task.id
    return 1


# --------------------------------------------------------------------------- views

def asset_item(db: Session, asset: Asset, holders: Optional[Dict[str, Employee]] = None) -> Dict:
    holder = None
    if asset.holder_employee_id:
        holder = (holders or {}).get(asset.holder_employee_id) or db.get(Employee, asset.holder_employee_id)
    shipment = open_shipment(db, asset) if asset.status in ("IN_TRANSIT", "RETURNED_TO_OWNER") else None
    pending = db.query(AssetReturn).filter(AssetReturn.asset_id == asset.id, AssetReturn.status == "OPEN").first() \
        if asset.status in HELD_STATUSES else None
    return {
        "id": asset.id, "asset_tag": asset.asset_tag, "category": asset.category, "make": asset.make,
        "model": asset.model, "serial_number": asset.serial_number, "label": asset_label(asset),
        "owner_type": asset.owner_type, "owner_company_id": asset.owner_company_id,
        "owner_client_id": asset.owner_client_id, "owner_name": asset.owner_name, "owner_label": owner_label(db, asset),
        "status": asset.status, "condition": asset.condition, "holder_employee_id": asset.holder_employee_id,
        "holder_name": employee_name(holder) if holder is not None else None,
        "holder_status": holder.status if holder is not None else None,
        "project_id": asset.project_id, "return_at_project_end": asset.return_at_project_end,
        "assigned_at": asset.assigned_at, "purchase_date": asset.purchase_date,
        "purchase_cost_cents": asset.purchase_cost_cents, "currency": asset.currency,
        "warranty_until": asset.warranty_until, "notes": asset.notes,
        "open_issues": db.query(func.count(AssetIssue.id)).filter(
            AssetIssue.asset_id == asset.id, AssetIssue.status.in_(OPEN_ISSUE_STATUSES)).scalar() or 0,
        "shipment": shipment_item(shipment) if shipment is not None else None,
        "return_due": pending.due_date if pending is not None else None,
        "return_reason": pending.reason if pending is not None else None,
    }


def shipment_item(shipment: AssetShipment) -> Dict:
    return {"id": shipment.id, "direction": shipment.direction, "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number, "shipped_on": shipment.shipped_on,
            "expected_on": shipment.expected_on, "received_on": shipment.received_on, "status": shipment.status}


def list_assets(db: Session, tenant_id: int, *, status: Optional[str] = None, owner_type: Optional[str] = None,
                category: Optional[str] = None, search: Optional[str] = None,
                employee_id: Optional[str] = None) -> List[Dict]:
    query = db.query(Asset).filter(Asset.tenant_id == tenant_id)
    if status:
        query = query.filter(Asset.status == status)
    if owner_type:
        query = query.filter(Asset.owner_type == owner_type)
    if category:
        query = query.filter(Asset.category == category)
    if employee_id:
        query = query.filter(Asset.holder_employee_id == employee_id)
    if _clean(search):
        like = f"%{_clean(search).lower()}%"
        holder_ids = db.query(Employee.id).filter(
            Employee.tenant_id == tenant_id,
            func.lower(func.coalesce(Employee.first_name, "") + " " + func.coalesce(Employee.last_name, "")).like(like))
        query = query.filter(or_(func.lower(Asset.asset_tag).like(like), func.lower(Asset.serial_number).like(like),
                                 func.lower(Asset.make).like(like), func.lower(Asset.model).like(like),
                                 Asset.holder_employee_id.in_(holder_ids)))
    assets = query.order_by(Asset.asset_tag).all()
    holders = {e.id: e for e in db.query(Employee).filter(
        Employee.id.in_({a.holder_employee_id for a in assets if a.holder_employee_id} or {""})).all()}
    return [asset_item(db, asset, holders) for asset in assets]


def asset_detail(db: Session, asset: Asset) -> Dict:
    names = {}

    def who(user_id):
        if user_id and user_id not in names:
            user = db.get(Users, user_id)
            names[user_id] = (user.UserName or user.UserEmail) if user is not None else None
        return names.get(user_id)

    events = db.query(AssetEvent).filter(AssetEvent.asset_id == asset.id).order_by(AssetEvent.id.desc()).all()
    shipments = db.query(AssetShipment).filter(AssetShipment.asset_id == asset.id) \
        .order_by(AssetShipment.created_at.desc()).all()
    issues = db.query(AssetIssue).filter(AssetIssue.asset_id == asset.id).order_by(AssetIssue.reported_at.desc()).all()
    return {
        **asset_item(db, asset),
        "events": [{"id": e.id, "event_type": e.event_type, "note": e.note, "at": e.created_at,
                    "actor": who(e.actor_user_id) or "System",
                    "employee_name": employee_name(db.get(Employee, e.employee_id)) if e.employee_id else None}
                   for e in events],
        "shipments": [shipment_item(s) for s in shipments],
        "issues": [{"id": i.id, "description": i.description, "severity": i.severity, "status": i.status,
                    "repair_vendor": i.repair_vendor, "resolution": i.resolution, "fix_cost_cents": i.fix_cost_cents,
                    "reported_by": who(i.reported_by), "reported_at": i.reported_at, "resolved_at": i.resolved_at}
                   for i in issues],
    }


def employee_assets(db: Session, employee: Employee) -> Dict:
    """One person's assets: what they hold, what is due back, the kit they miss and (for a leaver)
    whether settlement is on hold."""
    clearance = clearance_for(db, employee.id)
    signer = db.get(Users, clearance.signed_off_by) if clearance is not None and clearance.signed_off_by else None
    past = db.query(AssetEvent).filter(AssetEvent.employee_id == employee.id).order_by(AssetEvent.id.desc()).limit(50).all()
    tags = {a.id: a for a in db.query(Asset).filter(Asset.id.in_({e.asset_id for e in past} or {""})).all()}
    return {
        "employee_id": employee.id, "employee_name": employee_name(employee), "employee_status": employee.status,
        "held": [asset_item(db, asset) for asset in held_assets(db, employee.id)],
        "kit_gaps": kit_gaps(db, employee) if employee.status not in LEAVING_STATUSES else [],
        "lost": [asset_label(a) for a in lost_while_held(db, employee.id)],
        "clearance": None if clearance is None else {
            "status": clearance.status, "due_date": clearance.due_date, "signed_off_at": clearance.signed_off_at,
            "signed_off_by": (signer.UserName or signer.UserEmail) if signer is not None else None,
            "note": clearance.note},
        "clearance_blockers": clearance_blockers(db, employee) if employee.status in LEAVING_STATUSES else [],
        "settlement_hold": settlement_hold(db, employee),
        "history": [{"id": e.id, "event_type": e.event_type, "note": e.note, "at": e.created_at,
                     "asset_label": asset_label(tags[e.asset_id]) if e.asset_id in tags else None} for e in past],
    }


def ledger_summary(db: Session, tenant_id: int) -> Dict:
    counts = dict(db.query(Asset.status, func.count(Asset.id)).filter(Asset.tenant_id == tenant_id)
                  .group_by(Asset.status).all())
    return {"total": sum(counts.values()), "by_status": counts,
            "open_returns": db.query(func.count(AssetReturn.id)).filter(
                AssetReturn.tenant_id == tenant_id, AssetReturn.status == "OPEN").scalar() or 0,
            "open_issues": db.query(func.count(AssetIssue.id)).filter(
                AssetIssue.tenant_id == tenant_id, AssetIssue.status.in_(OPEN_ISSUE_STATUSES)).scalar() or 0}

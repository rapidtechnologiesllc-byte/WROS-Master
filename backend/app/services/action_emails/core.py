"""The shared parts of the action emails: who is on a record, and one email per person (never the
actor) through staff_mail_service.queue_staff_email, queued after the caller's commit."""
import functools
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import Users

logger = logging.getLogger(__name__)

Team = Dict[str, List[str]]  # user_id -> the roles that person holds on the record, in a stable order


def add(team: Team, user_id: Optional[str], role: str) -> None:
    if user_id and role not in team.setdefault(user_id, []):
        team[user_id].append(role)


def merge(team: Team, other: Team) -> None:
    for user_id, roles in other.items():
        for role in roles:
            add(team, user_id, role)


def name_of(user: Optional[Users]) -> Optional[str]:
    return (user.UserName or user.UserEmail) if user is not None else None


def user_name(db: Session, user_id: Optional[str]) -> Optional[str]:
    return name_of(db.query(Users).filter(Users.UserID == user_id).first()) if user_id else None


def employee_login(db: Session, employee_id: Optional[str]) -> Optional[str]:
    """The WROS login of an employee (None for someone without one)."""
    from app.models.employee import Employee

    employee = db.query(Employee).filter(Employee.id == employee_id).first() if employee_id else None
    return employee.wros_user_id if employee is not None else None


def employee_team(db: Session, employee, *, as_role: str = "Employee") -> Team:
    """The employee (their login), their reporting manager in the org chart and their BU head."""
    from app.services.bu_leadership import head_user_id
    from app.services.org_structure_service import manager_user_for

    team: Team = {}
    add(team, employee.wros_user_id, as_role)
    manager = manager_user_for(db, employee)
    if manager is not None and manager.UserID != employee.wros_user_id:
        add(team, manager.UserID, "Reporting Manager")
    head = head_user_id(db, employee.bu_id, employee.company_id) if employee.bu_id else None
    if head != employee.wros_user_id:
        add(team, head, "BU Head")
    return team


def client_team(db: Session, client_id: Optional[str]) -> Team:
    """The client's Client Owner (once the client has that field), account manager and the head of
    its business unit in its contracting company."""
    from app.models.client import Client
    from app.services.bu_leadership import head_for_client

    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    team: Team = {}
    if client is None:
        return team
    add(team, getattr(client, "client_owner_user_id", None), "Client Owner")
    add(team, client.account_manager_user_id, "Account Manager")
    if client.business_unit_id is not None:
        add(team, head_for_client(db, client.business_unit_id, client.id), "BU Head")
    return team


def send(db: Session, team: Team, *, actor_id: Optional[str], key: str, subject: str, opening: str,
         details: Optional[List[str]] = None, link_path: Optional[str] = None,
         link_label: str = "Open in WROS") -> int:
    """Queue one email per team member except the actor; returns how many were queued. A member
    who is unknown or terminated is logged and skipped; a member whose email cannot be queued is
    logged with the stack and the rest still get theirs."""
    from app.services.staff_mail_service import queue_staff_email

    queued = 0
    for user_id, roles in team.items():
        if user_id == actor_id:
            continue
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user is None or user.terminated_at is not None:
            logger.warning(f"[ActionEmail] {key}: {user_id} is unknown or terminated; not emailed")
            continue
        try:
            if queue_staff_email(
                user, key=f"{key}-{user_id}", subject=subject[:250], link_path=link_path, link_label=link_label,
                paragraphs=[opening, f"You are on it as: {', '.join(roles)}.", *(details or [])],
            ):
                queued += 1
        except Exception as exc:
            logger.error(f"[ActionEmail] {key}: email to {user_id} not queued: {exc}", exc_info=True)
    logger.info(f"[ActionEmail] {key}: {queued} email(s) queued for {len(team)} person(s)")
    return queued


def before_delete(family: str, fn, *args):
    """Read who is on a record about to be deleted (fn returns its team, or a tuple starting with it).
    An error here is logged with the stack and gives an empty result: it never blocks the delete."""
    try:
        return fn(*args)
    except Exception as exc:
        logger.error(f"[ActionEmail] {family}.{fn.__name__} failed before a delete: {exc}", exc_info=True)
        return None


def after_commit(family: str):
    """Decorator for notify_*(): the action is committed, so an error here is logged with the stack
    and the call returns 0 -- it never undoes or fails the action."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs) -> int:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logger.error(f"[ActionEmail] {family}.{fn.__name__} not queued: {exc}", exc_info=True)
                return 0
        return inner
    return wrap

"""Record-level visibility by business unit -- the one rule every screen uses (CEO 2026-10-12).

The role template decides WHICH modules and actions a user has; this module decides WHICH
RECORDS inside them they see:

- org-level role template (org_level_access): everything, no filter;
- everyone else: the business units they partner, head (in any company) or belong to
  (app.core.visibility.get_user_bu_ids). Never by location.

Records not yet assigned to any business unit (a new prospect client, a candidate in the
org pool, an unassigned job) stay visible to everyone with the module -- the
Org-Pool-until-claimed rule (CEO 2026-08-05) -- unless a caller passes
unassigned_visible=False.

A record is attributed to a BU directly (its own business_unit_id / bu_id), through its
client (Client.business_unit_id) or through its job (Jobs.business_unit_id). Use:

- bu_filter / client_filter / job_filter / employee_filter: WHERE clauses for list queries;
- ensure_visible: 404 for a single record outside the scope (no leaking that it exists);
- ensure_assignable: 403 when a write would put a record into a BU outside the scope.
"""
import logging
from typing import Optional, Set

from fastapi import HTTPException
from sqlalchemy import or_, select, true

from app.core.visibility import get_user_bu_ids
from app.models.user import Users

logger = logging.getLogger(__name__)


def visible_bu_ids(db, user: Users) -> Optional[Set[int]]:
    """None = unrestricted (org-level); otherwise the set of visible business unit ids."""
    return get_user_bu_ids(db, user)


def bu_filter(db, user: Users, column, *, unassigned_visible: bool = True):
    """WHERE clause: the record's business unit column is visible to the user."""
    ids = visible_bu_ids(db, user)
    if ids is None:
        return true()
    in_scope = column.in_(ids) if ids else column.in_([-1])
    return or_(column.is_(None), in_scope) if unassigned_visible else in_scope


def visible_client_ids(db, user: Users, *, unassigned_visible: bool = True):
    """A subquery of the client ids the user may see (None = unrestricted)."""
    from app.models.client import Client

    if visible_bu_ids(db, user) is None:
        return None
    return select(Client.id).where(bu_filter(db, user, Client.business_unit_id, unassigned_visible=unassigned_visible))


def client_filter(db, user: Users, client_id_column, *, unassigned_visible: bool = True):
    """WHERE clause for records attributed to a BU through their client."""
    sub = visible_client_ids(db, user, unassigned_visible=unassigned_visible)
    if sub is None:
        return true()
    if unassigned_visible:
        return or_(client_id_column.is_(None), client_id_column.in_(sub))
    return client_id_column.in_(sub)


def job_filter(db, user: Users, job_id_column, *, unassigned_visible: bool = True):
    """WHERE clause for records attributed to a BU through their job (Jobs.business_unit_id)."""
    from app.models.user import Jobs

    if visible_bu_ids(db, user) is None:
        return true()
    sub = select(Jobs.jobID).where(bu_filter(db, user, Jobs.business_unit_id, unassigned_visible=unassigned_visible))
    return or_(job_id_column.is_(None), job_id_column.in_(sub)) if unassigned_visible else job_id_column.in_(sub)


def employee_filter(db, user: Users, employee_id_column, *, unassigned_visible: bool = True):
    """WHERE clause for records attributed to a BU through their employee (Employee.bu_id)."""
    from app.models.employee import Employee

    if visible_bu_ids(db, user) is None:
        return true()
    sub = select(Employee.id).where(bu_filter(db, user, Employee.bu_id, unassigned_visible=unassigned_visible))
    return employee_id_column.in_(sub)


def can_see_bu(db, user: Users, business_unit_id: Optional[int], *, unassigned_visible: bool = True) -> bool:
    ids = visible_bu_ids(db, user)
    if ids is None:
        return True
    if business_unit_id is None:
        return unassigned_visible
    return business_unit_id in ids


def client_bu_id(db, client_id: Optional[str]) -> Optional[int]:
    from app.models.client import Client

    if not client_id:
        return None
    row = db.query(Client.business_unit_id).filter(Client.id == client_id).first()
    return row[0] if row else None


def job_bu_id(db, job_id: Optional[str]) -> Optional[int]:
    from app.models.user import Jobs

    if not job_id:
        return None
    row = db.query(Jobs.business_unit_id).filter(Jobs.jobID == job_id).first()
    return row[0] if row else None


def ensure_visible(db, user: Users, business_unit_id: Optional[int], what: str = "Record", *,
                   unassigned_visible: bool = True) -> None:
    """404 when a single record belongs to a business unit outside the user's scope -- the
    same answer as a record that does not exist, so ids of other BUs cannot be probed."""
    if not can_see_bu(db, user, business_unit_id, unassigned_visible=unassigned_visible):
        raise HTTPException(status_code=404, detail=f"{what} not found")


def ensure_assignable(db, user: Users, business_unit_id: Optional[int], what: str = "record") -> None:
    """403 when a write would place a record in a business unit outside the user's scope
    (creating it there, or moving it there). Unassigned (None) is always allowed."""
    if business_unit_id is None:
        return
    ids = visible_bu_ids(db, user)
    if ids is not None and business_unit_id not in ids:
        raise HTTPException(status_code=403, detail=f"You cannot assign a {what} to a business unit outside your scope")

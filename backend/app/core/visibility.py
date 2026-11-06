"""
Data visibility rules for role-based access control.

Org-level users (via role_template.org_level_access flag) see organization-level data across all BUs.
Other roles should be scoped to their assigned BU.
"""

import logging
from app.models.user import Users

logger = logging.getLogger(__name__)


def is_org_level_user(user: Users) -> bool:
    """Sees organization-wide data (not BU-scoped): one of the user's enabled templates (Manage
    Role permission set or function add-on) is flagged org_level_access -- the same rule as
    app.core.authority.is_org_level. Never by role name, legacy UserRole or a super-user flag."""
    from sqlalchemy.orm import object_session

    from app.core import authority

    if user is None:
        return False
    db = object_session(user)
    if db is None:
        raise ValueError("is_org_level_user needs a user loaded from a database session")
    return authority.is_org_level(db, user)


def sees_every_business_unit(user: Users) -> bool:
    """Whose records are not narrowed to a business unit: org-level users, and people in a function
    that serves every BU (Department.sees_all_business_units, CEO 2026-11-06: HR, recruitment). Their
    role's permissions still decide what they may open or do; other org-level authority (acting on
    anyone's task, partner pay) stays with is_org_level_user."""
    from sqlalchemy.orm import object_session

    from app.models.org_structure import Department

    if is_org_level_user(user):
        return True
    if user is None or not user.department_id:
        return False
    department = object_session(user).get(Department, user.department_id)
    return bool(department and department.sees_all_business_units)


def should_bypass_bu_filter(user: Users) -> bool:
    """
    Determine if BU filtering should be skipped for this user.

    Returns True for org-level users (those with org_level_access=True on role_template)
    Returns False for BU-scoped users (regular recruiters, hiring managers, etc.)
    """
    return is_org_level_user(user)


def get_user_bu_id(user: Users) -> int | None:
    """
    Get the BU ID for filtering queries.

    For org-level users: returns None (no BU filter - see all BUs)
    For regular users: returns their assigned BU ID (see only their BU)

    Usage:
        bu_id = get_user_bu_id(user)
        if bu_id:
            candidates = db.query(Candidate).filter(Candidate.business_unit_id == bu_id).all()
        else:
            candidates = db.query(Candidate).all()
    """
    if sees_every_business_unit(user):
        return None

    return user.business_unit_id


def scope_bu_ids(db, user: Users) -> set[int] | None:
    """
    The business units a BU-scoped user may see (CEO 2026-10-12): the BUs they partner, the
    BUs they head in any company, and their own BU. None = org-level (role template
    org_level_access) -- no filter. The top-bar selector never widens this.
    """
    from app.services.bu_leadership import led_business_units

    if sees_every_business_unit(user):
        return None
    ids = led_business_units(db, user)
    if user.business_unit_id is not None:
        ids.add(user.business_unit_id)
    return ids


def get_user_bu_ids(db, user: Users) -> set[int] | None:
    """What the user sees on this request: their scope (scope_bu_ids), narrowed to the business
    unit chosen in the top-bar selector when it is inside that scope (app.core.bu_view)."""
    from app.core.bu_view import active_bu

    ids = scope_bu_ids(db, user)
    chosen = active_bu()
    if chosen is not None and (ids is None or chosen in ids):
        return {chosen}
    return ids


def resolve_dashboard_partner(db, user: Users, requested_partner_id: str | None) -> str | None:
    """
    Whose Partner dashboard to show. A partner (owner of at least one BU)
    always sees their own; org-level users may choose any partner via
    ?partner_user_id=; with none chosen this returns None and the endpoint
    asks for a choice. Anyone else gets 403.
    """
    from fastapi import HTTPException
    from app.models.business_unit import BusinessUnit

    owns = db.query(BusinessUnit.id).filter(BusinessUnit.partner_user_id == user.UserID).first() is not None
    if should_bypass_bu_filter(user):
        return requested_partner_id or (user.UserID if owns else None)
    if owns:
        if requested_partner_id and requested_partner_id != user.UserID:
            raise HTTPException(status_code=403, detail="You can only view your own partner dashboard")
        return user.UserID
    raise HTTPException(status_code=403, detail="You are not the partner of any business unit. "
                                                "An admin sets the Partner on each business unit.")


def partner_choices(db) -> list:
    """Users who own at least one BU, for the Partner dashboard picker."""
    from app.models.business_unit import BusinessUnit

    rows = (db.query(Users).join(BusinessUnit, BusinessUnit.partner_user_id == Users.UserID)
            .distinct().order_by(Users.UserName).all())
    return [{"id": u.UserID, "name": u.UserName or u.UserEmail} for u in rows]


def resolve_dashboard_head_bu(db, user: Users, requested_bu_id: int | None) -> tuple[int | None, list]:
    """
    Which BU the BU Head dashboard shows, and the BUs the viewer may pick
    from. A BU head sees the BU(s) they run; a partner the BUs they own;
    org-level users any BU. Others fall back to their own BU.
    """
    from fastapi import HTTPException
    from app.models.business_unit import BusinessUnit

    if sees_every_business_unit(user):
        allowed = business_unit_choices(db)
    else:
        rows = db.query(BusinessUnit).filter(
            BusinessUnit.active == True,  # noqa: E712
            BusinessUnit.id.in_(get_user_bu_ids(db, user) or set()),
        ).order_by(BusinessUnit.name).all()
        allowed = [{"id": bu.id, "name": bu.display_name or bu.name} for bu in rows]
    allowed_ids = {b["id"] for b in allowed}
    if requested_bu_id is not None:
        if requested_bu_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="You can only view business units you head or own")
        return requested_bu_id, allowed
    if len(allowed) == 1 or (allowed and not sees_every_business_unit(user)):
        return allowed[0]["id"], allowed
    return None, allowed


def business_unit_choices(db) -> list:
    """Active business units, for a dashboard's BU picker."""
    from app.models.business_unit import BusinessUnit

    rows = db.query(BusinessUnit).filter(BusinessUnit.active == True).order_by(BusinessUnit.name).all()  # noqa: E712
    return [{"id": bu.id, "name": bu.display_name or bu.name} for bu in rows]

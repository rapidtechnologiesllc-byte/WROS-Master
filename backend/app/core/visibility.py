"""
Data visibility rules for role-based access control.

Org-level users (via role_template.org_level_access flag) see organization-level data across all BUs.
Other roles should be scoped to their assigned BU.
"""

import logging
from app.models.user import Users

logger = logging.getLogger(__name__)


def is_org_level_user(user: Users) -> bool:
    """
    Check if user should see organization-level data (not BU-scoped).

    Queries role_template.org_level_access flag instead of hardcoded role names.
    Supports both new RBAC (role_template) and legacy UserRole systems.
    """
    if not user:
        return False

    # New RBAC: Check role_template.org_level_access flag
    if user.role_template_id and user.role_template:
        try:
            org_level = getattr(user.role_template, 'org_level_access', False)
            if org_level:
                logger.debug(f"User {user.UserEmail} is org-level via role_template {user.role_template.name}")
                return True
        except Exception as e:
            logger.warning(f"Failed to check role_template org_level_access: {e}")

    # Legacy RBAC: Check hardcoded role set (for backward compatibility)
    # These roles will be migrated to set org_level_access=True on their role_template
    legacy_org_level_roles = {"super user", "admin", "ceo", "cfo"}

    if user.UserRole and user.UserRole.lower() in legacy_org_level_roles:
        logger.debug(f"User {user.UserEmail} is org-level via legacy UserRole: {user.UserRole}")
        return True

    # Check role_template (new RBAC system) for org_level_access flag
    if user.role_template and hasattr(user.role_template, 'org_level_access') and user.role_template.org_level_access:
        logger.debug(f"User {user.UserEmail} is org-level via role_template: {user.role_template.name}")
        return True

    return False


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
    if should_bypass_bu_filter(user):
        return None

    return user.business_unit_id


def get_user_bu_ids(db, user: Users) -> set[int] | None:
    """
    Every BU a BU-scoped user may see: their own BU, the BUs they own as
    Partner, and the BUs they run as BU Head. None = org-level (no filter).
    """
    from app.models.business_unit import BusinessUnit

    if should_bypass_bu_filter(user):
        return None
    ids = {
        bu_id for (bu_id,) in db.query(BusinessUnit.id).filter(
            (BusinessUnit.partner_user_id == user.UserID) | (BusinessUnit.manager_id == user.UserID)
        )
    }
    if user.business_unit_id is not None:
        ids.add(user.business_unit_id)
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

    if should_bypass_bu_filter(user):
        allowed = business_unit_choices(db)
    else:
        rows = db.query(BusinessUnit).filter(
            BusinessUnit.active == True,  # noqa: E712
            (BusinessUnit.manager_id == user.UserID) | (BusinessUnit.partner_user_id == user.UserID)
            | (BusinessUnit.id == user.business_unit_id),
        ).order_by(BusinessUnit.name).all()
        allowed = [{"id": bu.id, "name": bu.display_name or bu.name} for bu in rows]
    allowed_ids = {b["id"] for b in allowed}
    if requested_bu_id is not None:
        if requested_bu_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="You can only view business units you head or own")
        return requested_bu_id, allowed
    if len(allowed) == 1 or (allowed and not should_bypass_bu_filter(user)):
        return allowed[0]["id"], allowed
    return None, allowed


def business_unit_choices(db) -> list:
    """Active business units, for a dashboard's BU picker."""
    from app.models.business_unit import BusinessUnit

    rows = db.query(BusinessUnit).filter(BusinessUnit.active == True).order_by(BusinessUnit.name).all()  # noqa: E712
    return [{"id": bu.id, "name": bu.display_name or bu.name} for bu in rows]

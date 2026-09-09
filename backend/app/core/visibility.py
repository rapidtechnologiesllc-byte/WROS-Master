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

    if user.role and user.role.name and user.role.name.lower() in legacy_org_level_roles:
        logger.debug(f"User {user.UserEmail} is org-level via legacy role: {user.role.name}")
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

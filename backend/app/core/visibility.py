"""
import logging
Data visibility rules for role-based access control.

CEO/SuperUser/CFO should see organization-level data across all BUs.
Other roles should be scoped to their assigned BU.
"""

from app.models.user import Users

def is_org_level_user(user: Users) -> bool:
    """
    Check if user should see organization-level data (not BU-scoped).

    CEO, Super User, Admin, and CFO roles see org-level data.
    """
    if not user:
        return False

    org_level_roles = {"super user", "admin", "ceo", "cfo"}

    # Check legacy UserRole field
    if user.UserRole and user.UserRole.lower() in org_level_roles:
        return True

    # Check RBAC role relationship
    if user.role and user.role.name and user.role.name.lower() in org_level_roles:
        return True

    return False

def should_bypass_bu_filter(user: Users) -> bool:
    """
    Determine if BU filtering should be skipped for this user.

    Returns True for org-level users (CEO, Super User, etc.)
    """
    return is_org_level_user(user)

def get_user_bu_id(user: Users) -> int | None:
    """
    Get the BU ID for filtering queries.

    For org-level users: returns None (no BU filter)
    For regular users: returns their assigned BU ID
    """
    if should_bypass_bu_filter(user):
        return None

    return user.business_unit_id

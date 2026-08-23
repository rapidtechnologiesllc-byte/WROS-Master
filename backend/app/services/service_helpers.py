"""Service Helper Functions - Shared utilities for service layer.

Provides database-driven helper for getting users by permission.
Used by all service layer files to replace hardcoded role filters.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.user import Users, UserRole
from app.models.role_template import RoleTemplate, RoleTemplateModuleAccess, Module


def get_users_with_permission(permission: str, db: Session, tenant_id: int = 1) -> List[Users]:
    """Get all users who have a specific permission via role templates.

    Args:
        permission: Permission string (e.g., 'revenue.view', 'finance.manage')
        db: Database session
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        List of Users who have the permission
    """
    if not permission or '.' not in permission:
        return []

    resource, action = permission.lower().split('.', 1)

    return db.query(Users).join(
        UserRole, Users.UserID == UserRole.user_id
    ).join(
        RoleTemplate, UserRole.role_template_id == RoleTemplate.id
    ).join(
        RoleTemplateModuleAccess, RoleTemplate.id == RoleTemplateModuleAccess.role_template_id
    ).join(
        Module, RoleTemplateModuleAccess.module_id == Module.id
    ).filter(
        Module.name == resource,
        RoleTemplateModuleAccess.access_level == action,
        Users.tenant_id == tenant_id
    ).distinct().all()


def get_users_with_any_permission(permissions: List[str], db: Session, tenant_id: int = 1) -> List[Users]:
    """Get all users who have ANY of the given permissions.

    Args:
        permissions: List of permission strings
        db: Database session
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        List of Users who have at least one of the permissions
    """
    all_users = set()

    for permission in permissions:
        users = get_users_with_permission(permission, db, tenant_id)
        all_users.update(users)

    return list(all_users)

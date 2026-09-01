"""
DEPRECATED: RBAC service stub for backwards compatibility.

The RBAC Permission system has been deprecated in favor of RoleTemplate-based permissions.
This stub file prevents import errors during the transition period.

Use RoleTemplate and RoleTemplatePermission models instead for new code.
"""
from typing import Optional
from sqlalchemy.orm import Session


class RBACService:
    """Deprecated RBAC service - stub for backwards compatibility."""

    @staticmethod
    def has_attribute(db: Session, user_id: str, attribute: str, expected: bool = True) -> bool:
        """Stub: Always return False (no attributes in deprecated system)."""
        return False

    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str) -> bool:
        """Stub: Always return False (no permissions in deprecated system)."""
        return False

    @staticmethod
    def get_user_roles(db: Session, user_id: str):
        """Stub: Always return empty list."""
        return []

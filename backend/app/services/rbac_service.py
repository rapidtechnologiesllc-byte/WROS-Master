"""
import logging
DEPRECATED: RBAC service stub for backwards compatibility.

The RBAC Permission system has been deprecated in favor of RoleTemplate-based permissions.
This stub file prevents import errors during the transition period.

Use RoleTemplate and RoleTemplatePermission models instead for new code.
"""
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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
    def has_any_permission(db: Session, user_id: str, permissions: list) -> bool:
        """Stub: Always return False (no permissions in deprecated system)."""
        return False

    @staticmethod
    def get_user_roles(db: Session, user_id: str):
        """Stub: Always return empty list."""
        return []

    @staticmethod
    def is_super_user(db: Session, user_id: str, tenant_id: str = None) -> bool:
        """Check if user has Super User role template."""
        from app.models.user import Users
        from app.models.role_template import RoleTemplate

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return False

        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.id == user.role_template_id,
            RoleTemplate.name == "Super User"
        ).first()

        return role_template is not None

    @staticmethod
    def is_super_admin(user_id: str, db: Session, tenant_id: str = None) -> bool:
        """Check if user has Super User or Admin role template."""
        from app.models.user import Users
        from app.models.role_template import RoleTemplate

        user = db.query(Users).filter(Users.UserID == user_id).first()
        if not user or not user.role_template_id:
            return False

        role_template = db.query(RoleTemplate).filter(
            RoleTemplate.id == user.role_template_id,
            RoleTemplate.name.in_(["Super User", "Admin"])
        ).first()

        return role_template is not None

    @staticmethod
    def get_user_role(db: Session, user_id: str):
        """Stub: Always return None (no role in deprecated system)."""
        return None

    @staticmethod
    def seed_roles_and_permissions(db: Session):
        """Stub: Do nothing (RBAC deprecated)."""
        pass

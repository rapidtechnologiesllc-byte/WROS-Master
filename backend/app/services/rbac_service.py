"""RBAC Service — Database-driven permission checking and role management.

ZERO-HARDCODING: All roles, permissions, and attributes come from database role_templates.
No hardcoded seed data. No hardcoded permission strings.

This is the CLEAN implementation. The old hardcoded version has been moved to
rbac_service_deprecated.py for reference only.
"""

from typing import List, Optional, Set
from sqlalchemy.orm import Session

from app.models.user import Users
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Module, Resource
from app.services.permission_helper import PermissionHelper


class RBACService:
    """Database-driven RBAC - all data comes from role_templates."""

    @staticmethod
    def list_roles(db: Session, tenant_id: int = 1) -> List[RoleTemplate]:
        """Get all available role templates for the given tenant."""
        return db.query(RoleTemplate).filter(
            RoleTemplate.tenant_id == tenant_id
        ).all()

    @staticmethod
    def get_user_roles(user_id: str, db: Session, tenant_id: int = 1) -> List[RoleTemplate]:
        """Get role template assigned to a user.

        Returns list of single RoleTemplate object user has via role_template_id.
        """
        user = db.query(Users).filter(Users.UserID == user_id).first()

        roles = []
        if user and user.role_template_id:
            role = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id
            ).first()
            if role:
                roles.append(role)

        return roles

    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str, tenant_id: int = 1) -> bool:
        """Check if user has specific permission (database-driven).

        Permission format: 'resource.action' (e.g., 'recruitment.manage', 'project.view')

        Returns True if user has permission via any of their assigned role templates.
        """
        return PermissionHelper.has_permission(user_id, permission, db, tenant_id)

    @staticmethod
    def has_any_permission(db: Session, user_id: str, permissions: List[str], tenant_id: int = 1) -> bool:
        """Check if user has ANY of the given permissions."""
        return PermissionHelper.has_any_permission(user_id, permissions, db, tenant_id)

    @staticmethod
    def has_all_permissions(db: Session, user_id: str, permissions: List[str], tenant_id: int = 1) -> bool:
        """Check if user has ALL of the given permissions."""
        return PermissionHelper.has_all_permissions(user_id, permissions, db, tenant_id)

    @staticmethod
    def is_super_user(db: Session, user_id: str, tenant_id: int = 1) -> bool:
        """Check if user is super user (has admin.manage permission)."""
        return PermissionHelper.is_super_admin(user_id, db, tenant_id)

    @staticmethod
    def get_user_permissions(db: Session, user_id: str, tenant_id: int = 1) -> Set[str]:
        """Get all permissions for user as a set of permission strings.

        Returns: {'recruitment.manage', 'project.view', ...}
        """
        return PermissionHelper.get_user_permissions(user_id, db, tenant_id)

    @staticmethod
    def get_accessible_modules(db: Session, user_id: str, tenant_id: int = 1) -> List[Module]:
        """Get all modules (functional areas) user can access."""
        return PermissionHelper.get_accessible_modules(user_id, db, tenant_id)

    @staticmethod
    def get_data_access_scope(db: Session, user_id: str, tenant_id: int = 1):
        """Get user's complete data access scope (locations, BUs, subordinates, global access)."""
        return PermissionHelper.get_data_access_scope(user_id, db, tenant_id)

    @staticmethod
    def has_attribute(db: Session, user_id: str, attribute: str, expected: bool = True) -> bool:
        """Check if user's role has a specific attribute set to expected value.

        Attributes are defined on RoleTemplate model. Examples:
        - 'bu_restricted': User can only see own BU
        - 'global_access': User can see all BUs
        - 'pipeline_control': User can manage hiring pipeline

        For now, this queries role_template attributes. In future, could be database table.
        """
        user_roles = RBACService.get_user_roles(user_id, db, tenant_id=1)

        for role in user_roles:
            # Check role attributes (if they exist on the model)
            if hasattr(role, attribute):
                if getattr(role, attribute) == expected:
                    return True

        return False

    @staticmethod
    def get_role_by_name(db: Session, role_name: str, tenant_id: int = 1) -> Optional[RoleTemplate]:
        """Get a role template by name."""
        return db.query(RoleTemplate).filter(
            RoleTemplate.name == role_name,
            RoleTemplate.tenant_id == tenant_id
        ).first()

    @staticmethod
    def assign_role_to_user(db: Session, user_id: str, role_id: int, business_unit_id: Optional[str] = None, tenant_id: int = 1):
        """Assign a role template to a user.

        Args:
            user_id: User ID
            role_id: RoleTemplate ID
            business_unit_id: Optional BU context for the role
            tenant_id: Tenant ID
        """
        user_role = UserRole(
            user_id=user_id,
            role_template_id=role_id,
            business_unit_id=business_unit_id,
            tenant_id=tenant_id
        )
        db.add(user_role)
        db.commit()
        db.refresh(user_role)
        return user_role

    @staticmethod
    def remove_role_from_user(db: Session, user_id: str, role_id: int, tenant_id: int = 1):
        """Remove role template assignment from a user."""
        user = db.query(Users).filter(Users.UserID == user_id).first()
        if user:
            user.role_template_id = None
            db.commit()

    @staticmethod
    def get_users_with_permission(db: Session, permission: str, tenant_id: int = 1) -> List[Users]:
        """Get all users who have a specific permission.

        Useful for service layer to find users to notify, assign tasks, etc.
        """
        from app.services.service_helpers import get_users_with_permission
        return get_users_with_permission(permission, db, tenant_id)

    @staticmethod
    def get_users_with_any_permission(db: Session, permissions: List[str], tenant_id: int = 1) -> List[Users]:
        """Get all users who have ANY of the given permissions."""
        from app.services.service_helpers import get_users_with_any_permission
        return get_users_with_any_permission(permissions, db, tenant_id)

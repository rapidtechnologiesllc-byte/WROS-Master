import logging
"""Permission Helper Service - Centralized permission and data scope management.

Core functions for:
- Getting user permissions from role templates
- Checking specific permissions
- Getting accessible modules
- Calculating data access scope (BU, Location, Hierarchy)
- Getting user's subordinates

All permission checks should use these functions instead of hardcoded checks.
ZERO-HARDCODING principle: All permission checks go through these helpers.
"""

from typing import List, Set
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.user import Users
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Module, Resource
from app.services.organization_service import OrganizationService
from app.core.logging import logger

@dataclass
class DataScope:
    """User's data access scope - what data they can see."""
    tenant_id: int
    user_id: str
    accessible_locations: List[str]  # Geographic boundary
    accessible_bus: List[str]  # Business units
    subordinates: List[str]  # Reporting chain
    can_see_global_data: bool  # Cross-BU visibility

logger = logging.getLogger(__name__)

class PermissionHelper:
    """Centralized permission and scope checking."""

    @staticmethod
    def get_user_permissions(user_id: str, db: Session, tenant_id: int = 1) -> Set[str]:
        """Get all permissions for user via role templates.

        Returns set of permission strings: {'recruitment.manage', 'project.view', ...}
        """
        user = db.query(Users).filter(
            Users.UserID == user_id,
            Users.tenant_id == tenant_id
        ).first()

        if not user or not user.role_template_id:
            return set()

        permissions = set()

        # Get all permissions for user's role template
        perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == user.role_template_id
        ).all()

        for perm in perms:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource:
                # Format: resource_name.action (e.g., 'candidates.view', 'candidates.create')
                if perm.can_view:
                    permissions.add(f"{resource.name}.view")
                if perm.can_create:
                    permissions.add(f"{resource.name}.create")
                if perm.can_edit:
                    permissions.add(f"{resource.name}.edit")
                if perm.can_delete:
                    permissions.add(f"{resource.name}.delete")

        return permissions

    @staticmethod
    def has_permission(user_id: str, permission: str, db: Session, tenant_id: int = 1) -> bool:
        """Check if user has specific permission.

        permission format: 'resource.action' (e.g., 'recruitment.manage', 'project.view')
        """
        permissions = PermissionHelper.get_user_permissions(user_id, db, tenant_id)
        return permission.lower() in permissions

    @staticmethod
    def has_any_permission(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        """Check if user has any of the given permissions."""
        user_permissions = PermissionHelper.get_user_permissions(user_id, db, tenant_id)
        for perm in permissions:
            if perm.lower() in user_permissions:
                return True
        return False

    @staticmethod
    def has_all_permissions(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        """Check if user has all of the given permissions."""
        user_permissions = PermissionHelper.get_user_permissions(user_id, db, tenant_id)
        for perm in permissions:
            if perm.lower() not in user_permissions:
                return False
        return True

    @staticmethod
    def is_super_admin(user_id: str, db: Session, tenant_id: int = 1) -> bool:
        """Check if user is super admin (has admin.manage permission)."""
        return PermissionHelper.has_permission(user_id, "admin.manage", db, tenant_id)

    @staticmethod
    def get_accessible_modules(user_id: str, db: Session, tenant_id: int = 1) -> List[Module]:
        """Get list of modules user can access."""
        user = db.query(Users).filter(
            Users.UserID == user_id,
            Users.tenant_id == tenant_id
        ).first()

        if not user or not user.role_template_id:
            # CRITICAL FIX: Raise error instead of returning empty list
            raise Exception(f"Cannot determine user modules: user not found or missing role template for user_id={user_id}")

        modules = set()

        perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == user.role_template_id
        ).all()

        for perm in perms:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource and resource.module_id:
                module = db.query(Module).filter(Module.id == resource.module_id).first()
                if module:
                    modules.add(module)

        return list(modules)

    @staticmethod
    def get_data_access_scope(user_id: str, db: Session, tenant_id: int = 1) -> DataScope:
        """Calculate user's data access scope.

        Returns DataScope object with accessible locations, BUs, subordinates, and global visibility.
        """
        user = db.query(Users).filter(
            Users.UserID == user_id,
            Users.tenant_id == tenant_id
        ).first()

        if not user:
            return DataScope(
                tenant_id=tenant_id,
                user_id=user_id,
                accessible_locations=[],
                accessible_bus=[],
                subordinates=[],
                can_see_global_data=False
            )

        # Get accessible locations
        accessible_locations = OrganizationService.get_user_accessible_locations(user_id, db, tenant_id)

        # Get accessible business units
        accessible_bus = OrganizationService.get_user_accessible_business_units(user_id, db, tenant_id)

        # Get subordinates in reporting chain
        subordinates = OrganizationService.get_all_subordinates(user_id, db, tenant_id)

        # Check if user can see global data
        can_see_global = PermissionHelper.has_any_permission(
            user_id,
            ["admin.manage", "finance.view_global", "revenue.view_pnl"],
            db,
            tenant_id
        )

        return DataScope(
            tenant_id=tenant_id,
            user_id=user_id,
            accessible_locations=accessible_locations or ["*"],
            accessible_bus=accessible_bus or ["*"],
            subordinates=subordinates,
            can_see_global_data=can_see_global
        )

    @staticmethod
    def get_user_subordinates(user_id: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get all subordinates in reporting chain (recursive)."""
        return OrganizationService.get_all_subordinates(user_id, db, tenant_id)

    @staticmethod
    def is_manager_of(manager_id: str, employee_id: str, db: Session, tenant_id: int = 1) -> bool:
        """Check if manager_id manages employee_id."""
        return OrganizationService.is_manager_of(manager_id, employee_id, db, tenant_id)

    @staticmethod
    def get_permissions_by_module(user_id: str, module_name: str, db: Session, tenant_id: int = 1) -> List[str]:
        """Get all permissions user has for a specific module."""
        all_permissions = PermissionHelper.get_user_permissions(user_id, db, tenant_id)
        return [p for p in all_permissions if p.startswith(f"{module_name.lower()}.")]

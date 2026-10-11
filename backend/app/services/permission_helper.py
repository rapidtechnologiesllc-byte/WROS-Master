"""Permission checks by user id: a thin adapter over app.core.authority, where every
authority rule lives (role template flags, hierarchy level, permission matrix)."""

from typing import List, Set
from sqlalchemy.orm import Session

from app.models.user import Users
from app.models.role_template import RoleTemplatePermission, Resource
import logging

logger = logging.getLogger(__name__)

class PermissionHelper:
    """Permission checks by user id (see app.core.authority)."""

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
    def _user(user_id: str, db: Session, tenant_id: int):
        return db.query(Users).filter(Users.UserID == user_id, Users.tenant_id == tenant_id).first()

    @staticmethod
    def has_permission(user_id: str, permission: str, db: Session, tenant_id: int = 1) -> bool:
        """permission: '<resource>.<view|create|edit|delete>' on a seeded resource (e.g.
        'candidates.view'). Super users (role template flag) pass. A malformed string raises."""
        from app.core import authority

        return authority.has_permission(db, PermissionHelper._user(user_id, db, tenant_id), permission)

    @staticmethod
    def has_any_permission(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        from app.core import authority

        return authority.has_any_permission(db, PermissionHelper._user(user_id, db, tenant_id), permissions)

    @staticmethod
    def has_all_permissions(user_id: str, permissions: List[str], db: Session, tenant_id: int = 1) -> bool:
        from app.core import authority

        user = PermissionHelper._user(user_id, db, tenant_id)
        return all(authority.has_permission(db, user, p) for p in permissions)

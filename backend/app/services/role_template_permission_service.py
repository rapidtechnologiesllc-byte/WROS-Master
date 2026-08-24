"""
Role Template Permission Service - Dynamic permission checking based on role templates.

Replaces hardcoded "Super User" checks with actual role template permissions (V/C/E/D).
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource
from app.models.user import Users, UserRole
from app.core.logging import logger


class RoleTemplatePermissionService:
    """
    Check user permissions against their assigned role templates.
    Each user can have multiple roles; permissions are the UNION of all assigned roles.
    """

    @staticmethod
    def get_user_roles(db: Session, user_id: str, tenant_id: int = 1) -> list[RoleTemplate]:
        """Get all role templates assigned to a user via the UserRole junction table."""
        user_roles = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.tenant_id == tenant_id
        ).all()

        return [ur.role_template for ur in user_roles if ur.role_template]

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: int = 1) -> Resource:
        """Get a resource by name (e.g., 'candidates', 'jobs', 'users')."""
        return db.query(Resource).filter(
            Resource.name == resource_name,
            Resource.tenant_id == tenant_id
        ).first()

    @staticmethod
    def is_super_user(db: Session, user_id: str, tenant_id: int = 1) -> bool:
        """
        Check if user is a Super User by verifying they have permissions for ALL resources.

        A Super User is one whose assigned roles grant access to every resource in the system.
        This is dynamic - determined by database permissions, not role names.

        Args:
            db: Database session
            user_id: User ID
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            True if user's roles cover all resources, False otherwise
        """
        try:
            # Get user's role templates
            user_roles = RoleTemplatePermissionService.get_user_roles(db, user_id, tenant_id)
            if not user_roles:
                return False

            role_ids = [role.id for role in user_roles]

            # Get total resource count
            total_resources = db.query(Resource).filter(
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).count()

            if total_resources == 0:
                return False

            # Get resources this user's roles can access (UNION of all roles)
            accessible_resources = db.query(RoleTemplatePermission.resource_id).filter(
                RoleTemplatePermission.role_template_id.in_(role_ids),
                RoleTemplatePermission.can_view == True
            ).distinct().count()

            # User is super user if they have access to ALL resources
            return accessible_resources >= total_resources

        except Exception as e:
            logger.error(f"Error checking super user status: {e}")
            return False

    @staticmethod
    def has_permission(
        db: Session,
        user_id: str,
        resource_name: str,
        action: str,  # 'view', 'create', 'edit', 'delete'
        tenant_id: int = 1
    ) -> bool:
        """
        Check if user has permission to perform an action on a resource.

        Args:
            db: Database session
            user_id: User ID
            resource_name: Resource name (e.g., 'candidates')
            action: Action type ('view', 'create', 'edit', 'delete')
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            True if user has permission, False otherwise
        """
        try:
            # SUPER USER BYPASS: Super Users have all permissions
            if RoleTemplatePermissionService.is_super_user(db, user_id, tenant_id):
                logger.info(f"Super User {user_id} granted all permissions (bypass)")
                return True

            # Get user's role templates
            user_roles = RoleTemplatePermissionService.get_user_roles(db, user_id, tenant_id)
            if not user_roles:
                return False

            # Get the resource
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if not resource:
                # If resource doesn't exist, no permission
                return False

            # Map action to permission field
            action_map = {
                'view': 'can_view',
                'create': 'can_create',
                'edit': 'can_edit',
                'delete': 'can_delete'
            }

            if action not in action_map:
                return False

            permission_field = action_map[action]

            # Check if ANY of the user's roles has this permission
            # (permissions are ORed together for multi-role users)
            for role in user_roles:
                perm = db.query(RoleTemplatePermission).filter(
                    RoleTemplatePermission.role_template_id == role.id,
                    RoleTemplatePermission.resource_id == resource.id
                ).first()

                if perm and getattr(perm, permission_field):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking role template permission: {e}")
            return False

    @staticmethod
    def can_view(db: Session, user_id: str, resource_name: str, tenant_id: int = 1) -> bool:
        """Check if user can VIEW a resource."""
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, 'view', tenant_id)

    @staticmethod
    def can_create(db: Session, user_id: str, resource_name: str, tenant_id: int = 1) -> bool:
        """Check if user can CREATE in a resource."""
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, 'create', tenant_id)

    @staticmethod
    def can_edit(db: Session, user_id: str, resource_name: str, tenant_id: int = 1) -> bool:
        """Check if user can EDIT a resource."""
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, 'edit', tenant_id)

    @staticmethod
    def can_delete(db: Session, user_id: str, resource_name: str, tenant_id: int = 1) -> bool:
        """Check if user can DELETE from a resource."""
        return RoleTemplatePermissionService.has_permission(db, user_id, resource_name, 'delete', tenant_id)

    @staticmethod
    def get_user_permissions(db: Session, user_id: str, tenant_id: int = 1) -> dict:
        """
        Get all permissions for a user as a dictionary.

        Returns: {
            "resource_name": {
                "can_view": True/False,
                "can_create": True/False,
                "can_edit": True/False,
                "can_delete": True/False
            },
            ...
        }
        """
        try:
            permissions = {}

            # Get all resources for this tenant
            resources = db.query(Resource).filter(
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).all()

            # Get user's roles
            user_roles = RoleTemplatePermissionService.get_user_roles(db, user_id, tenant_id)
            role_ids = [role.id for role in user_roles]

            # For each resource, check all permissions
            for resource in resources:
                # Check if ANY role has this permission (OR logic for multi-role users)
                can_view = False
                can_create = False
                can_edit = False
                can_delete = False

                if role_ids:
                    perms = db.query(RoleTemplatePermission).filter(
                        RoleTemplatePermission.resource_id == resource.id,
                        RoleTemplatePermission.role_template_id.in_(role_ids)
                    ).all()

                    for perm in perms:
                        if perm.can_view:
                            can_view = True
                        if perm.can_create:
                            can_create = True
                        if perm.can_edit:
                            can_edit = True
                        if perm.can_delete:
                            can_delete = True

                permissions[resource.name] = {
                    "can_view": can_view,
                    "can_create": can_create,
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "display_name": resource.display_name
                }

            return permissions

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return {}

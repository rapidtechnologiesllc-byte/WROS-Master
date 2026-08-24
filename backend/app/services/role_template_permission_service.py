"""
Role Template Permission Service - Dynamic permission checking based on role templates.

Replaces hardcoded "Super User" checks with actual role template permissions (V/C/E/D).
Uses efficient database queries to avoid N+1 problems.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource
from app.models.user import UserRole
from app.core.logging import logger


class RoleTemplatePermissionService:
    """
    Check user permissions against their assigned role templates.
    Each user can have multiple roles; permissions are the UNION of all assigned roles.
    """

    @staticmethod
    def get_user_roles(db: Session, user_id: str, tenant_id: int = 1) -> list[RoleTemplate]:
        """
        Get all role templates assigned to a user via the UserRole junction table.

        Logs warning if user has UserRole without role_template (data integrity issue).
        """
        user_roles = db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.tenant_id == tenant_id
        ).all()

        roles = []
        for ur in user_roles:
            if ur.role_template is None:
                logger.warning(f"Data integrity issue: user_id={user_id} has UserRole without role_template")
                continue
            roles.append(ur.role_template)

        return roles

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: int = 1) -> Resource | None:
        """Get a resource by name (e.g., 'candidates', 'jobs', 'users')."""
        if not resource_name:
            return None

        try:
            return db.query(Resource).filter(
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).first()
        except (AttributeError, ValueError) as e:
            logger.error(f"get_resource_by_name({resource_name}, tenant={tenant_id}): {e}")
            return None

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
            if not role_ids:
                return False

            # Get total resource count
            total_resources = db.query(func.count(Resource.id)).filter(
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).scalar() or 0

            if total_resources == 0:
                return False

            # Get resources this user's roles can access (UNION of all roles)
            # Single efficient query using COUNT(DISTINCT) instead of distinct().count()
            accessible_resources = db.query(func.count(func.distinct(RoleTemplatePermission.resource_id))).filter(
                RoleTemplatePermission.role_template_id.in_(role_ids),
                RoleTemplatePermission.can_view == True
            ).scalar() or 0

            # User is super user if they have access to ALL resources
            result = accessible_resources >= total_resources
            if result:
                logger.info(f"is_super_user({user_id}): True (accessible={accessible_resources}, total={total_resources})")
            return result

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"is_super_user({user_id}, tenant={tenant_id}): {e}", exc_info=True)
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
            # Validate inputs
            if not user_id or not resource_name or not action:
                return False

            # SUPER USER BYPASS: Super Users have all permissions
            if RoleTemplatePermissionService.is_super_user(db, user_id, tenant_id):
                logger.info(f"Super User {user_id} granted all permissions (bypass)")
                return True

            # Get user's role templates
            user_roles = RoleTemplatePermissionService.get_user_roles(db, user_id, tenant_id)
            if not user_roles:
                return False

            role_ids = [role.id for role in user_roles]
            if not role_ids:
                return False

            # Get the resource
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if not resource:
                return False

            # Map action to permission field
            action_map = {
                'view': 'can_view',
                'create': 'can_create',
                'edit': 'can_edit',
                'delete': 'can_delete'
            }

            if action not in action_map:
                logger.warning(f"has_permission: invalid action '{action}'")
                return False

            permission_field = action_map[action]

            # OPTIMIZED: Single query with IN clause instead of N+1 loop
            # Get permission for this user's roles on this resource
            perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id.in_(role_ids),
                RoleTemplatePermission.resource_id == resource.id,
                getattr(RoleTemplatePermission, permission_field) == True
            ).first()

            return perm is not None

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"has_permission({user_id}, {resource_name}, {action}, tenant={tenant_id}): {e}", exc_info=True)
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
                "can_delete": True/False,
                "display_name": "Display Name"
            },
            ...
        }
        """
        try:
            # Validate input
            if not user_id:
                return {}

            # Get all resources for this tenant
            resources = db.query(Resource).filter(
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).all()

            if not resources:
                return {}

            # Get user's roles
            user_roles = RoleTemplatePermissionService.get_user_roles(db, user_id, tenant_id)
            role_ids = [role.id for role in user_roles]

            permissions = {}

            # OPTIMIZED: Single query instead of N+1 loop per resource
            # Get ALL permissions for this user's roles in one query
            if role_ids:
                all_perms = db.query(RoleTemplatePermission).filter(
                    RoleTemplatePermission.role_template_id.in_(role_ids)
                ).all()

                # Build lookup dict: {resource_id: [perm1, perm2, ...]}
                perm_lookup = {}
                for perm in all_perms:
                    if perm.resource_id not in perm_lookup:
                        perm_lookup[perm.resource_id] = []
                    perm_lookup[perm.resource_id].append(perm)
            else:
                perm_lookup = {}

            # For each resource, aggregate permissions from all roles (OR logic)
            for resource in resources:
                perms = perm_lookup.get(resource.id, [])

                # Use any() for cleaner boolean aggregation
                can_view = any(p.can_view for p in perms)
                can_create = any(p.can_create for p in perms)
                can_edit = any(p.can_edit for p in perms)
                can_delete = any(p.can_delete for p in perms)

                permissions[resource.name] = {
                    "can_view": can_view,
                    "can_create": can_create,
                    "can_edit": can_edit,
                    "can_delete": can_delete,
                    "display_name": resource.display_name
                }

            logger.info(f"get_user_permissions({user_id}): {len(permissions)} resources")
            return permissions

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"get_user_permissions({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            return {}

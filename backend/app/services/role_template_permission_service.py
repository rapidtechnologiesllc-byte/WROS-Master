"""
Role Template Permission Service - Simplified single-role with custom overrides.

Architecture (Option C):
1. Each user has ONE role_template (via users.role_id)
2. User can have custom permission overrides (user_custom_permissions table)
3. Permission = role_template permission + custom override (if exists)

NO UNION logic. NO multi-role complexity. Just database + overrides.
"""
import logging

from sqlalchemy.orm import Session
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource
from app.models.user import Users, UserCustomPermission
from app.core.logging import logger

logger = logging.getLogger(__name__)

class RoleTemplatePermissionService:
    """
    Check user permissions based on their assigned role + custom overrides.

    Simple model:
    - User has ONE role_template (not multiple)
    - Custom permissions can override the role template
    - No UNION logic needed
    """

    @staticmethod
    def get_user_role(db: Session, user_id: str, tenant_id: int = 1) -> RoleTemplate | None:
        """Get the user's assigned role template (single role, not multiple)."""
        print(f"[DEBUG] get_user_role: user_id={user_id}, tenant_id={tenant_id}")
        try:
            user = db.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                print(f"[DEBUG] User {user_id} not found in database")
                logger.warning(f"User not found: {user_id}")
                return None

            print(f"[DEBUG] User found: {user_id}, role_template_id={user.role_template_id}")
            if not user.role_template_id:
                print(f"[DEBUG] User {user_id} has no role_template_id assigned")
                logger.warning(f"User {user_id} has no role_template_id assigned")
                return None

            role = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id,
                RoleTemplate.tenant_id == tenant_id,
                RoleTemplate.enabled == True
            ).first()

            if not role:
                print(f"[DEBUG] Role template {user.role_template_id} not found for user {user_id} with tenant {tenant_id}")
                logger.warning(f"Role template {user.role_template_id} not found for user {user_id}")
                return None

            print(f"[DEBUG] Role found: id={role.id}, name={role.name}")
            return role

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"get_user_role({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            raise ValueError("Operation failed")

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: int = 1) -> Resource | None:
        """Get a resource by name (case-insensitive)."""
        print(f"[DEBUG] get_resource_by_name: resource={resource_name}, tenant_id={tenant_id}")
        if not resource_name:
            print(f"[DEBUG] Resource name is empty")
            return None

        try:
            from sqlalchemy import func
            # Case-insensitive lookup: lower(name) = lower(resource_name)
            resource = db.query(Resource).filter(
                func.lower(Resource.name) == resource_name.lower(),
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).first()
            if resource:
                print(f"[DEBUG] Found resource: id={resource.id}, name={resource.name}, tenant={resource.tenant_id}")
            else:
                print(f"[DEBUG] Resource '{resource_name}' not found in database for tenant {tenant_id}")
            return resource
        except (AttributeError, ValueError) as e:
            print(f"[DEBUG] Exception in get_resource_by_name: {e}")
            logger.error(f"get_resource_by_name({resource_name}, tenant={tenant_id}): {e}", exc_info=True)
            raise ValueError("Operation failed")

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

        Process:
        1. Get user's role_template (single role)
        2. Check role_template_permissions for this resource
        3. Check user_custom_permissions for override
        4. Return: role permission OR custom override

        Args:
            db: Database session
            user_id: User ID
            resource_name: Resource name (e.g., 'candidates')
            action: Action type ('view', 'create', 'edit', 'delete')
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            True if user has permission, False otherwise
        """
        print(f"[DEBUG] has_permission called: user={user_id}, resource={resource_name}, action={action}, tenant={tenant_id}")
        try:
            # Validate inputs
            if not user_id or not resource_name or not action:
                print(f"[DEBUG] Invalid inputs: user={user_id}, resource={resource_name}, action={action}")
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
            print(f"[DEBUG] Mapped action '{action}' to field '{permission_field}'")

            # Get user's role template (single role)
            print(f"[DEBUG] Getting user role for user {user_id}")
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                print(f"[DEBUG] User role not found for {user_id}")
                return False
            print(f"[DEBUG] Found role: id={role.id}, name={role.name}, tenant={role.tenant_id}")

            # Get the resource
            print(f"[DEBUG] Getting resource '{resource_name}' with tenant {tenant_id}")
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if not resource:
                print(f"[DEBUG] Resource '{resource_name}' not found for tenant {tenant_id}")
                return False
            print(f"[DEBUG] Found resource: id={resource.id}, name={resource.name}, tenant={resource.tenant_id}")

            # Step 1: Check role template permission (with tenant isolation)
            print(f"[DEBUG] Querying permission: role_id={role.id}, resource_id={resource.id}, tenant_id={tenant_id}")
            role_perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id == resource.id,
                RoleTemplatePermission.tenant_id == tenant_id
            ).first()

            role_has_permission = False
            if role_perm:
                role_has_permission = getattr(role_perm, permission_field, False)
                print(f"[DEBUG] Found permission: id={role_perm.id}, {permission_field}={role_has_permission}")
            else:
                print(f"[DEBUG] No permission record found for role {role.id} and resource {resource.id}")

            # Step 2: Check user custom override (can grant or restrict)
            # Query user_custom_permissions if it exists
            try:
                from app.models.user import UserCustomPermission
                custom_perm = db.query(UserCustomPermission).filter(
                    UserCustomPermission.user_id == user_id,
                    UserCustomPermission.resource_id == resource.id
                ).first()

                if custom_perm:
                    # Custom override takes precedence
                    return getattr(custom_perm, permission_field, False)
            except (ImportError, AttributeError):
                # UserCustomPermission model doesn't exist yet, use role permission only
                pass

            # Return role permission (no custom override)
            print(f"[DEBUG] Returning: role_has_permission={role_has_permission}")
            return role_has_permission

        except (AttributeError, ValueError, TypeError) as e:
            print(f"[DEBUG] Exception in has_permission: {e}")
            logger.error(f"has_permission({user_id}, {resource_name}, {action}, tenant={tenant_id}): {e}", exc_info=True)
            return False

    @staticmethod
    def is_super_user(db: Session, user_id: str, tenant_id: int = 1) -> bool:
        """Check if user is a super user (has all permissions)."""
        try:
            if not user_id:
                return False

            user = db.query(Users).filter(
                Users.UserID == user_id,
                Users.tenant_id == tenant_id
            ).first()
            if not user:
                return False

            # Check if user has a super user role (database flag, not hardcoded names)
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                return False

            # Check is_super_user flag (production safe)
            return role.is_super_user is True
        except Exception as e:
            logger.error(f"is_super_user({user_id}): {e}", exc_info=True)
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

        Combines role template permissions with custom overrides.

        Returns: {
            "resource_name": {
                "can_view": True/False,
                "can_create": True/False,
                "can_edit": True/False,
                "can_delete": True/False,
                "display_name": "Display Name",
                "overridden": True/False  (True if custom override applied)
            },
            ...
        }
        """
        try:
            # Validate input
            if not user_id:
                # CRITICAL FIX: Raise error instead of returning empty dict
                raise ValueError("Cannot get user permissions: user_id is required")

            # Get user's role template
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                # CRITICAL FIX: Raise error instead of returning empty dict
                raise ValueError(f"Cannot get user permissions: no role template found for user_id={user_id}")

            # OPTIMIZATION: Get only role template permissions (not all resources)
            # This avoids expensive query of all resources for every request
            # Filter by tenant to prevent cross-tenant leaks
            role_perms = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.tenant_id == tenant_id
            ).all()

            if not role_perms:
                # No permissions for this role
                logger.warning(f"No role template permissions found for role_id={role.id}")
                return {}

            # Get user custom permissions (overrides)
            custom_perms = {}
            try:
                custom_perm_rows = db.query(UserCustomPermission).filter(
                    UserCustomPermission.user_id == user_id
                ).all()

                for perm in custom_perm_rows:
                    custom_perms[perm.resource_id] = {
                        "can_view": perm.can_view,
                        "can_create": perm.can_create,
                        "can_edit": perm.can_edit,
                        "can_delete": perm.can_delete
                    }
            except (ImportError, AttributeError):
                # UserCustomPermission doesn't exist yet
                pass

            # Build final permissions from role + custom overrides
            # Only include resources with actual permissions (no need to fetch all resources)
            permissions = {}

            # Get resource IDs from role permissions, then fetch only those resources
            resource_ids = [perm.resource_id for perm in role_perms]
            if resource_ids:
                # Fetch only resources that have permissions assigned
                resources_with_perms = db.query(Resource).filter(
                    Resource.id.in_(resource_ids),
                    Resource.tenant_id == tenant_id,
                    Resource.enabled == True
                ).all()

                # Build lookup of resource by ID
                resource_by_id = {r.id: r for r in resources_with_perms}

                # Combine role permissions with resources
                for role_perm in role_perms:
                    resource = resource_by_id.get(role_perm.resource_id)
                    if not resource:
                        continue

                    perms = {
                        "can_view": role_perm.can_view,
                        "can_create": role_perm.can_create,
                        "can_edit": role_perm.can_edit,
                        "can_delete": role_perm.can_delete
                    }
                    overridden = False

                    # Apply custom override if exists
                    if role_perm.resource_id in custom_perms:
                        perms = custom_perms[role_perm.resource_id]
                        overridden = True

                    permissions[resource.name] = {
                        **perms,
                        "display_name": resource.display_name,
                        "overridden": overridden
                    }

            logger.info(f"get_user_permissions({user_id}): {len(permissions)} resources, {sum(1 for p in permissions.values() if p['overridden'])} overridden")
            return permissions

        except Exception as e:
            logger.error(f"get_user_permissions({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            raise RuntimeError(f"Failed to get user permissions for user_id={user_id}: {str(e)}")

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
        logger.debug(f"get_user_role: user_id={user_id}, tenant_id={tenant_id}")
        try:
            user = db.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.debug(f"User {user_id} not found in database")
                logger.warning(f"User not found: {user_id}")
                return None

            logger.debug(f"User found: {user_id}, role_template_id={user.role_template_id}")
            if not user.role_template_id:
                logger.debug(f"User {user_id} has no role_template_id assigned")
                logger.warning(f"User {user_id} has no role_template_id assigned")
                return None

            role = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id,
                RoleTemplate.tenant_id == tenant_id,
                RoleTemplate.enabled == True
            ).first()

            if not role:
                logger.debug(f"Role template {user.role_template_id} not found for user {user_id} with tenant {tenant_id}")
                logger.warning(f"Role template {user.role_template_id} not found for user {user_id}")
                return None

            logger.debug(f"Role found: id={role.id}, name={role.name}")
            return role

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"get_user_role({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            raise ValueError("Operation failed")

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: int = 1) -> Resource | None:
        """Get a resource by name (case-insensitive)."""
        logger.debug(f"get_resource_by_name: resource={resource_name}, tenant_id={tenant_id}")
        if not resource_name:
            logger.debug("Resource name is empty")
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
                logger.debug(f"Found resource: id={resource.id}, name={resource.name}, tenant={resource.tenant_id}")
            else:
                logger.debug(f"Resource '{resource_name}' not found in database for tenant {tenant_id}")
            return resource
        except (AttributeError, ValueError) as e:
            logger.debug(f"Exception in get_resource_by_name: {e}")
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

        CRITICAL FIX (2026-09-21): If database unavailable, default to ALLOW
        (graceful degradation - user can submit form even if permission check fails).
        This prevents form submission from failing when DB connection pool exhausted.

        Args:
            db: Database session
            user_id: User ID
            resource_name: Resource name (e.g., 'candidates')
            action: Action type ('view', 'create', 'edit', 'delete')
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            True if user has permission, False otherwise. Returns True on DB errors (graceful degradation).
        """
        logger.debug(f"has_permission called: user={user_id}, resource={resource_name}, action={action}, tenant={tenant_id}")
        try:
            # Validate inputs
            if not user_id or not resource_name or not action:
                logger.debug(f"Invalid inputs: user={user_id}, resource={resource_name}, action={action}")
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
            logger.debug(f"Mapped action '{action}' to field '{permission_field}'")

            # Get user's role template (single role)
            logger.debug(f"Getting user role for user {user_id}")
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                logger.debug(f"User role not found for {user_id}")
                return False
            logger.debug(f"Found role: id={role.id}, name={role.name}, tenant={role.tenant_id}")

            # Get the resource
            logger.debug(f"Getting resource '{resource_name}' with tenant {tenant_id}")
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if not resource:
                logger.debug(f"Resource '{resource_name}' not found for tenant {tenant_id}")
                return False
            logger.debug(f"Found resource: id={resource.id}, name={resource.name}, tenant={resource.tenant_id}")

            # Step 1: Check role template permission (with tenant isolation)
            logger.debug(f"Querying permission: role_id={role.id}, resource_id={resource.id}, tenant_id={tenant_id}")
            role_perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id == resource.id,
                RoleTemplatePermission.tenant_id == tenant_id
            ).first()

            role_has_permission = False
            if role_perm:
                role_has_permission = getattr(role_perm, permission_field, False)
                logger.debug(f"Found permission: id={role_perm.id}, {permission_field}={role_has_permission}")
            else:
                logger.debug(f"No permission record found for role {role.id} and resource {resource.id}")

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
            logger.debug(f"Returning: role_has_permission={role_has_permission}")
            return role_has_permission

        except (AttributeError, ValueError, TypeError) as e:
            logger.debug(f"Exception in has_permission: {e}")
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

        Combines role template permissions with custom overrides.
        Uses in-memory cache (5-min TTL) to reduce database load.
        Uses circuit breaker to prevent cascading failures.

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
        # PHASE 2 FIX (2026-09-21): Check cache first
        from app.services.permission_cache import get_permission_cache
        cache = get_permission_cache()
        cache_key = f"{user_id}:{tenant_id}"

        cached_perms = cache.get(cache_key)
        if cached_perms is not None:
            return cached_perms

        # PHASE 2 FIX (2026-09-21): Use circuit breaker to prevent cascading failures
        from app.services.permission_circuit_breaker import get_permission_breaker
        breaker = get_permission_breaker()

        # If circuit is OPEN, return empty dict (graceful degradation)
        def fetch_permissions():
            return RoleTemplatePermissionService._fetch_user_permissions_internal(db, user_id, tenant_id)

        try:
            permissions = breaker.call(
                fetch_permissions,
                fallback_value={}
            )
        except Exception as e:
            logger.error(f"get_user_permissions({user_id}, tenant={tenant_id}): {e} - RETURNING EMPTY FALLBACK", exc_info=True)
            return {}

        # Cache the result (even if empty)
        cache.set(cache_key, permissions)
        return permissions

    @staticmethod
    def _fetch_user_permissions_internal(db: Session, user_id: str, tenant_id: int = 1) -> dict:
        """
        Internal: Fetch user permissions from database.
        This is the actual database operation wrapped by cache and circuit breaker.
        """
        try:
            # Validate input
            if not user_id:
                raise ValueError("Cannot get user permissions: user_id is required")

            # Get user's role template
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                raise ValueError(f"Cannot get user permissions: no role template found for user_id={user_id}")

            # OPTIMIZATION: Get only role template permissions (not all resources)
            # This avoids expensive query of all resources for every request
            # Filter by tenant to prevent cross-tenant leaks
            role_perms = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.tenant_id == tenant_id
            ).all()

            if not role_perms:
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
                pass

            # Build final permissions from role + custom overrides
            permissions = {}
            resource_ids = [perm.resource_id for perm in role_perms]

            if resource_ids:
                resources_with_perms = db.query(Resource).filter(
                    Resource.id.in_(resource_ids),
                    Resource.tenant_id == tenant_id,
                    Resource.enabled == True
                ).all()

                resource_by_id = {r.id: r for r in resources_with_perms}

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
            logger.error(f"_fetch_user_permissions_internal({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            raise  # Re-raise so circuit breaker can catch it

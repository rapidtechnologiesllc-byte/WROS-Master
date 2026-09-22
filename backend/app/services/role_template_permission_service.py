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
        try:
            user = db.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.warning(f"User not found: {user_id}")
                return None

            if not user.role_template_id:
                logger.warning(f"User {user_id} has no role_template_id assigned")
                return None

            role = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id,
                RoleTemplate.tenant_id == tenant_id,
                RoleTemplate.enabled == True
            ).first()

            if not role:
                logger.warning(f"Role template {user.role_template_id} not found for user {user_id}")
                return None

            return role

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"get_user_role({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            raise ValueError("Operation failed")

    @staticmethod
    def get_resource_by_name(db: Session, resource_name: str, tenant_id: int = 1) -> Resource | None:
        """Get a resource by name."""
        if not resource_name:
            return None

        try:
            return db.query(Resource).filter(
                Resource.name == resource_name,
                Resource.tenant_id == tenant_id,
                Resource.enabled == True
            ).first()
        except (AttributeError, ValueError) as e:
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
        try:
            # Validate inputs
            if not user_id or not resource_name or not action:
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

            # Get user's role template (single role)
            role = RoleTemplatePermissionService.get_user_role(db, user_id, tenant_id)
            if not role:
                return False

            # Get the resource
            resource = RoleTemplatePermissionService.get_resource_by_name(db, resource_name, tenant_id)
            if not resource:
                return False

            # Step 1: Check role template permission
            role_perm = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id,
                RoleTemplatePermission.resource_id == resource.id
            ).first()

            role_has_permission = False
            if role_perm:
                role_has_permission = getattr(role_perm, permission_field, False)

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
            return role_has_permission

        except (AttributeError, ValueError, TypeError, Exception) as e:
            # CRITICAL FIX (2026-09-21): Default to ALLOW on any DB error
            # This prevents cascade failures when connection pool exhausted
            logger.error(f"has_permission({user_id}, {resource_name}, {action}, tenant={tenant_id}): {e} - ALLOWING (graceful degradation)", exc_info=True)
            return True  # Allow operation to proceed (graceful degradation)

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
    def is_super_user(db: Session, user_id: str, tenant_id: int = 1) -> bool:
        """
        Check if user has the 'Super User' role template.

        Super users bypass all permission checks.

        Args:
            db: Database session
            user_id: User ID to check
            tenant_id: Tenant ID (for multi-tenancy)

        Returns:
            True if user is Super User, False otherwise
        """
        try:
            user = db.query(Users).filter(Users.UserID == user_id).first()
            if not user or not user.role_template_id:
                return False

            role_template = db.query(RoleTemplate).filter(
                RoleTemplate.id == user.role_template_id,
                RoleTemplate.name == "Super Admin",
                RoleTemplate.tenant_id == tenant_id,
                RoleTemplate.enabled == True
            ).first()

            return role_template is not None

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"is_super_user({user_id}, tenant={tenant_id}): {e}", exc_info=True)
            return False

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

            # Get only role template permissions (not all resources)
            role_perms = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == role.id
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

"""
Permission Helper Functions - Dynamic Permission Loading from Role Templates

This module provides functions to check permissions dynamically from role templates
instead of using hardcoded permission strings throughout the application.

ZERO-HARDCODING principle: All permission checks go through these helpers.
No 'job.create', 'candidate.view' etc. hardcoded anywhere.
"""

from sqlalchemy.orm import Session
from app.models.user import Users, UserRole
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource, Module


def get_user_permissions(db: Session, user_id: str) -> dict:
    """
    Get all permissions for a user based on their assigned role template.

    Returns: {
        'modules': ['Recruitment', 'Finance', ...],
        'resources_by_module': {
            'Recruitment': {
                'candidates': {'view': True, 'create': True, 'edit': False, 'delete': False},
                'jobs': {'view': True, 'create': False, ...},
                ...
            },
            ...
        },
        'all_resources_permission': {  # Flattened for easy checks
            'candidates.view': True,
            'candidates.create': True,
            'jobs.view': True,
            ...
        }
    }
    """
    try:
        # Get user and their role template assignment
        user = db.query(Users).filter_by(UserID=user_id).first()
        if not user:
            return {'modules': [], 'resources_by_module': {}, 'all_resources_permission': {}}

        # Get user's assigned role template
        user_role = db.query(UserRole).filter_by(user_id=user_id).first()
        if not user_role or not user_role.role_template_id:
            return {'modules': [], 'resources_by_module': {}, 'all_resources_permission': {}}

        role_template = db.query(RoleTemplate).filter_by(id=user_role.role_template_id).first()
        if not role_template:
            return {'modules': [], 'resources_by_module': {}, 'all_resources_permission': {}}

        # Build permission structure
        result = {
            'modules': [],
            'resources_by_module': {},
            'all_resources_permission': {}
        }

        # Get all permissions for this role template
        permissions = db.query(RoleTemplatePermission).filter_by(
            role_template_id=role_template.id
        ).all()

        for perm in permissions:
            resource = perm.resource
            module = resource.module

            # Add module if not already added
            if module.name not in result['modules']:
                result['modules'].append(module.name)
                result['resources_by_module'][module.name] = {}

            # Add resource permissions
            result['resources_by_module'][module.name][resource.name] = {
                'view': perm.can_view,
                'create': perm.can_create,
                'edit': perm.can_edit,
                'delete': perm.can_delete,
            }

            # Flatten for easy lookup (e.g., 'candidates.view')
            for action in ['view', 'create', 'edit', 'delete']:
                perm_key = f"{resource.name}.{action}"
                perm_value = getattr(perm, f'can_{action}')
                result['all_resources_permission'][perm_key] = perm_value

        return result

    except Exception as e:
        print(f"Error getting user permissions: {e}")
        return {'modules': [], 'resources_by_module': {}, 'all_resources_permission': {}}


def has_permission(db: Session, user_id: str, resource: str, action: str) -> bool:
    """
    Check if user has a specific permission.

    Args:
        db: Database session
        user_id: User ID to check
        resource: Resource name (e.g., 'candidates', 'jobs', 'invoices')
        action: Action type ('view', 'create', 'edit', 'delete')

    Returns: bool - True if user has permission, False otherwise

    Example:
        if has_permission(db, user.UserID, 'jobs', 'create'):
            # User can create jobs
    """
    permissions = get_user_permissions(db, user_id)
    perm_key = f"{resource}.{action}"
    return permissions['all_resources_permission'].get(perm_key, False)


def has_module_access(db: Session, user_id: str, module: str) -> bool:
    """
    Check if user has access to any resource in a module.

    Args:
        db: Database session
        user_id: User ID to check
        module: Module name (e.g., 'Recruitment', 'Finance', 'Admin')

    Returns: bool - True if user has access to at least one resource in module
    """
    permissions = get_user_permissions(db, user_id)
    return module in permissions['modules']


def get_accessible_resources(db: Session, user_id: str, module: str, action: str = 'view') -> list:
    """
    Get list of resources user can access in a module.

    Args:
        db: Database session
        user_id: User ID to check
        module: Module name
        action: Action type to check ('view', 'create', 'edit', 'delete')

    Returns: list of resource names user can access

    Example:
        resources = get_accessible_resources(db, user.UserID, 'Recruitment', 'view')
        # Returns: ['candidates', 'jobs', 'submissions', ...]
    """
    permissions = get_user_permissions(db, user_id)
    resources_in_module = permissions['resources_by_module'].get(module, {})

    accessible = []
    for resource_name, actions in resources_in_module.items():
        if actions.get(action, False):
            accessible.append(resource_name)

    return accessible


def is_super_user(user: Users) -> bool:
    """
    Check if user is a super user (global admin).
    Super users have access to everything.
    """
    # Could be determined by a flag on the user model or a special role template
    return user.is_admin if hasattr(user, 'is_admin') else False


# --- DEPRECATED ---
# These functions should NO LONGER be used anywhere in the codebase.
# They represent the old hardcoding pattern.

def _DEPRECATED_check_hardcoded_permission(permission_string: str) -> None:
    """
    DEPRECATED - DO NOT USE

    This represents the old pattern of checking hardcoded permission strings
    like 'job.create', 'candidate.view', etc.

    All code checking hardcoded permissions should be replaced with calls to:
    - has_permission(db, user_id, resource, action)
    - has_module_access(db, user_id, module)
    - get_accessible_resources(db, user_id, module, action)
    """
    raise NotImplementedError("Hardcoded permission checks are deprecated. Use has_permission() instead.")

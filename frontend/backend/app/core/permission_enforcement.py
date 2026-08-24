"""
Permission Enforcement Layer - Middleware and decorators for V, C, E, D permissions.

This module provides:
1. Decorators to enforce permission checks on endpoints
2. Middleware to log permission checks for audit trail
3. Helper functions for frontend permission validation

All endpoints must use @require_permission or @require_action_permission decorators.
Permission format: 'resource.action' (e.g., 'administration.view', 'candidates.create')
"""

from functools import wraps
from typing import Callable, List, Optional
from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.services.permission_helper import PermissionHelper
from app.core.logging import logger


# ============================================================================
# PERMISSION CHECK DECORATORS
# ============================================================================

def require_permission(permission: str):
    """
    Decorator to enforce a specific permission on an endpoint.

    Usage:
        @router.get("/candidates")
        @require_permission("candidates.view")
        async def get_candidates(db: Session = Depends(get_db),
                                current_user: Users = Depends(get_current_internal_user)):
            ...

    Args:
        permission: Permission string in format 'resource.action' (e.g., 'candidates.view')
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            # Check permission
            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_permission(
                current_user.UserID, permission, db, tenant_id
            )

            # Log permission check for audit trail
            _log_permission_check(
                current_user.UserID, permission, has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: {permission} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )

            # Call the original function
            return await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            # Check permission
            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_permission(
                current_user.UserID, permission, db, tenant_id
            )

            # Log permission check for audit trail
            _log_permission_check(
                current_user.UserID, permission, has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: {permission} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}"
                )

            # Call the original function
            return func(*args, **kwargs)

        # Use async wrapper if the function is async, otherwise sync wrapper
        if hasattr(func, '__await__'):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def require_any_permission(permissions: List[str]):
    """
    Decorator to enforce that user has ANY of the given permissions.

    Usage:
        @router.get("/reports")
        @require_any_permission(["reports.view", "analytics.view"])
        async def get_reports(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_any_permission(
                current_user.UserID, permissions, db, tenant_id
            )

            _log_permission_check(
                current_user.UserID, f"any({permissions})", has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: any{permissions} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: requires one of {permissions}"
                )

            return await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_any_permission(
                current_user.UserID, permissions, db, tenant_id
            )

            _log_permission_check(
                current_user.UserID, f"any({permissions})", has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: any{permissions} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: requires one of {permissions}"
                )

            return func(*args, **kwargs)

        if hasattr(func, '__await__'):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def require_all_permissions(permissions: List[str]):
    """
    Decorator to enforce that user has ALL of the given permissions.

    Usage:
        @router.post("/approve-offer")
        @require_all_permissions(["offers.view", "offers.approve"])
        async def approve_offer(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_all_permissions(
                current_user.UserID, permissions, db, tenant_id
            )

            _log_permission_check(
                current_user.UserID, f"all({permissions})", has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: all{permissions} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: requires all of {permissions}"
                )

            return await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database or user session not available"
                )

            tenant_id = getattr(current_user, 'tenant_id', 1)
            has_perm = PermissionHelper.has_all_permissions(
                current_user.UserID, permissions, db, tenant_id
            )

            _log_permission_check(
                current_user.UserID, f"all({permissions})", has_perm, "endpoint", func.__name__, db, tenant_id
            )

            if not has_perm:
                logger.warning(f"Permission denied for user {current_user.UserID}: all{permissions} on {func.__name__}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: requires all of {permissions}"
                )

            return func(*args, **kwargs)

        if hasattr(func, '__await__'):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def require_action_permission(resource: str, action: str):
    """
    Decorator for V, C, E, D (View, Create, Edit, Delete) permission enforcement.

    Usage:
        @router.get("/candidates")
        @require_action_permission("administration", "view")
        async def get_users(...):
            ...

        @router.post("/users")
        @require_action_permission("administration", "create")
        async def create_user(...):
            ...

        @router.put("/users/{id}")
        @require_action_permission("administration", "edit")
        async def update_user(...):
            ...

        @router.delete("/users/{id}")
        @require_action_permission("administration", "delete")
        async def delete_user(...):
            ...

    Args:
        resource: Resource name (e.g., 'administration', 'recruitment', 'projects')
        action: Action name - 'view', 'create', 'edit', or 'delete'
    """
    permission = f"{resource}.{action}"
    return require_permission(permission)


# ============================================================================
# AUDIT LOGGING
# ============================================================================

def _log_permission_check(
    user_id: str,
    permission: str,
    granted: bool,
    check_type: str,
    context: str,
    db: Session,
    tenant_id: int = 1
):
    """
    Log permission check for audit trail.

    Args:
        user_id: User ID performing the action
        permission: Permission being checked
        granted: Whether permission was granted
        check_type: Type of check ('endpoint', 'component', 'api')
        context: Context (function name, component name, etc.)
        db: Database session
        tenant_id: Tenant ID
    """
    try:
        # Import here to avoid circular imports
        from app.models.audit_log import AuditLog

        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action_type="PERMISSION_CHECK",
            resource_type="PERMISSION",
            resource_id=permission,
            action_status="GRANTED" if granted else "DENIED",
            details={
                "permission": permission,
                "check_type": check_type,
                "context": context,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(audit_log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log permission check: {str(e)}")
        # Don't raise - audit logging failure shouldn't break the app


# ============================================================================
# FRONTEND HELPER - GET PERMISSIONS FOR A USER
# ============================================================================

async def get_user_permissions_response(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Return user's permissions in response format for frontend.

    Used by frontend to cache user permissions and make local permission checks.
    Endpoint: GET /api/v1/auth/me/permissions

    Returns:
        {
            "user_id": "...",
            "permissions": ["administration.view", "administration.create", ...],
            "modules": ["administration", "recruitment", ...],
            "is_super_admin": false
        }
    """
    tenant_id = getattr(current_user, 'tenant_id', 1)

    permissions = PermissionHelper.get_user_permissions(current_user.UserID, db, tenant_id)
    modules = PermissionHelper.get_accessible_modules(current_user.UserID, db, tenant_id)
    is_super_admin = PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)

    return {
        "user_id": current_user.UserID,
        "permissions": sorted(list(permissions)),
        "modules": [{"id": m.id, "name": m.name} for m in modules],
        "is_super_admin": is_super_admin
    }


# ============================================================================
# INLINE PERMISSION CHECKS FOR ENDPOINTS
# ============================================================================

def check_permission(
    user_id: str,
    permission: str,
    db: Session,
    tenant_id: int = 1
) -> bool:
    """
    Inline permission check for complex authorization logic.

    Usage in endpoint:
        if not check_permission(current_user.UserID, "candidates.approve", db):
            raise HTTPException(status_code=403, detail="Permission denied")
    """
    has_perm = PermissionHelper.has_permission(user_id, permission, db, tenant_id)
    _log_permission_check(user_id, permission, has_perm, "inline", "check_permission", db, tenant_id)
    return has_perm


def check_any_permission(
    user_id: str,
    permissions: List[str],
    db: Session,
    tenant_id: int = 1
) -> bool:
    """
    Inline permission check for ANY permission.
    """
    has_perm = PermissionHelper.has_any_permission(user_id, permissions, db, tenant_id)
    _log_permission_check(user_id, f"any({permissions})", has_perm, "inline", "check_any_permission", db, tenant_id)
    return has_perm


def check_all_permissions(
    user_id: str,
    permissions: List[str],
    db: Session,
    tenant_id: int = 1
) -> bool:
    """
    Inline permission check for ALL permissions.
    """
    has_perm = PermissionHelper.has_all_permissions(user_id, permissions, db, tenant_id)
    _log_permission_check(user_id, f"all({permissions})", has_perm, "inline", "check_all_permissions", db, tenant_id)
    return has_perm

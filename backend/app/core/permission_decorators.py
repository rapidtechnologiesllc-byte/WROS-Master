"""Permission checking decorators for FastAPI endpoints"""
from functools import wraps
from typing import Optional, Callable
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_internal_user
from app.models.user import Users
import logging
from app.services.permission_service import PermissionService

def require_permission(permission: str):
    """Decorator to require specific permission before endpoint execution.

    Usage:
    @router.get("/candidates")
    @require_permission("candidate.view")
        async def get_candidates(db: Session = Depends(get_db),
                                current_user: Users = Depends(get_current_internal_user)):
            ...
    """
    def decorator(func: Callable):
        pass
    @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db and current_user from kwargs if present, else via dependency injection
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db:
                # If not passed, try to get from dependencies
                db = kwargs.get("db") or Depends(get_db)
            if not current_user:
                current_user = kwargs.get("current_user") or Depends(get_current_internal_user)

            # Verify both are present
            if isinstance(db, type) or db is None:
                raise HTTPException(status_code=500, detail="Database session not available")
            if isinstance(current_user, type) or current_user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")

            # Check permission
            has_perm = PermissionService.has_permission(
                db, current_user.UserID, permission, current_user.tenant_id
            )

            if not has_perm:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission}"
                )

            return await func(*args, **kwargs) if hasattr(func, '__call__') and hasattr(func(*[]), '__await__') else func(*args, **kwargs)

        return wrapper

    return decorator

def apply_data_scope(module: str):
    """Decorator to apply data scope filter to endpoint.

    Adds 'data_scope' dict to kwargs with scope type and filtering info.

    Usage:
    @router.get("/candidates")
    @apply_data_scope("candidates")
        async def get_candidates(db: Session = Depends(get_db),
                                current_user: Users = Depends(get_current_internal_user),
                                data_scope: dict = None):
            # Use data_scope to filter query
            ...
    """
    def decorator(func: Callable):
    @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get("db")
            current_user = kwargs.get("current_user")

            if not db or not current_user:
                raise HTTPException(status_code=500, detail="Missing dependencies")

            # Get data scope for this user and module
            scope = PermissionService.get_data_scope(db, current_user.UserID, module)
            kwargs["data_scope"] = scope

            return await func(*args, **kwargs) if hasattr(func, '__call__') and hasattr(func(*[]), '__await__') else func(*args, **kwargs)

        return wrapper

    return decorator

def mask_field(db: Session, user_id: str, table: str, field: str, value: any, tenant_id: int) -> any:
    """Mask a field value based on field-level permissions.

    Usage in a serializer:
        def serialize_employee(emp, db, user_id, tenant_id):
            return {
                "id": emp.id,
                "name": emp.name,
                "salary": mask_field(db, user_id, "employees", "salary", emp.salary, tenant_id)
            }
    """
    access_level = PermissionService.get_field_access_level(db, user_id, table, field)

    if access_level == "hidden":
        return None
    elif access_level == "masked":
        # Return masked version (e.g., last 4 digits for SSN)
        if isinstance(value, str) and len(value) > 4:
            return "*" * (len(value) - 4) + value[-4:]
        return "****"
    elif access_level == "readonly" or access_level == "editable":
        return value
    else:
        return None

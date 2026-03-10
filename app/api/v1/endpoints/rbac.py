"""
RBAC Admin Endpoints — manage roles, permissions, and user role assignments.
All routes require Super User or Admin access.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.schemas.rbac import (
    RoleCreate, RoleResponse, RoleListItem,
    PermissionCreate, PermissionResponse,
    AssignRoleRequest, AssignPermissionRequest,
    UserPermissionSummary,
)
from app.services.rbac_service import RBACService
from app.core.logging import logger

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ===========================================================================
# Roles
# ===========================================================================

@router.get(
    "/roles",
    response_model=List[RoleListItem],
    summary="List all roles",
)
def list_roles(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined RBAC roles (lightweight list)."""
    return RBACService.list_roles(db)


@router.post(
    "/roles",
    response_model=RoleListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role",
)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create a new RBAC role. Returns 409 if the role name already exists."""
    try:
        return RBACService.create_role(db, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating role: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create role")


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get a role with its attributes and permissions",
)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Retrieve a single role with its full attribute list and assigned permissions.
    """
    role = RBACService.get_role_or_404(db, role_id)
    # Build permissions list from role_permissions relationship
    permissions = [rp.permission for rp in role.role_permissions if rp.permission]
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        attributes=[
            {"id": a.id, "role_id": a.role_id, "attribute_name": a.attribute_name, "attribute_value": a.attribute_value}
            for a in role.attributes
        ],
        permissions=[
            {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at}
            for p in permissions
        ],
    )


# ===========================================================================
# Permissions
# ===========================================================================

@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    summary="List all permissions",
)
def list_permissions(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Return all defined RBAC permissions."""
    return RBACService.list_permissions(db)


@router.post(
    "/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new permission",
)
def create_permission(
    data: PermissionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Create a new named permission string. Returns 409 if it already exists."""
    try:
        return RBACService.create_permission(db, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error creating permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to create permission")


# ===========================================================================
# Role ↔ Permission Management
# ===========================================================================

@router.post(
    "/roles/{role_id}/permissions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a permission to a role",
)
def assign_permission_to_role(
    role_id: int,
    data: AssignPermissionRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Add a permission to a role. Idempotent — no error if already assigned."""
    try:
        RBACService.assign_permission_to_role(db, role_id, data.permission_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error assigning permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to assign permission")


@router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a permission from a role",
)
def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Remove a permission from a role. Returns 404 if the mapping doesn't exist."""
    try:
        RBACService.remove_permission_from_role(db, role_id, permission_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error removing permission: {exc}")
        raise HTTPException(status_code=500, detail="Failed to remove permission")


# ===========================================================================
# User Role Assignment
# ===========================================================================

@router.post(
    "/users/{user_id}/assign-role",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign a role to a user",
)
def assign_role_to_user(
    user_id: str,
    data: AssignRoleRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Assign an RBAC role to a user by their UserID.
    Returns 404 if the user or role does not exist.
    """
    try:
        RBACService.assign_role_to_user(db, user_id, data.role_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error assigning role to user: {exc}")
        raise HTTPException(status_code=500, detail="Failed to assign role")


@router.get(
    "/users/{user_id}/permissions",
    response_model=UserPermissionSummary,
    summary="Get a user's effective permissions and attributes",
)
def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Inspect the full permission and attribute set for a user based on their assigned RBAC role.
    Returns an empty summary if no role is assigned.
    """
    return RBACService.get_user_permission_summary(db, user_id)

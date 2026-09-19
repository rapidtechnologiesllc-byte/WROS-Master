"""
HR Permissions Endpoint - Returns current user's permissions
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.role_template_permission_service import RoleTemplatePermissionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get("/permissions", response_model=dict)
async def get_user_permissions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get current user's permissions.
    Returns list of permission strings that the user has.
    """
    try:
        if not current_user:
            logger.warning("Permissions request: current_user is None")
            raise HTTPException(status_code=401, detail="User not authenticated")

        user_id = current_user.UserID if hasattr(current_user, 'UserID') else None
        if not user_id:
            logger.warning("Permissions request: user_id not found in current_user")
            raise HTTPException(status_code=401, detail="User ID not found")

        tenant_id = current_user.tenant_id if hasattr(current_user, 'tenant_id') else None

        user_permissions = RoleTemplatePermissionService.get_user_permissions(
            db, user_id, tenant_id
        )

        logger.info(f"Permissions fetched for user {user_id}: {len(user_permissions) if user_permissions else 0} permissions")
        return {
            "status": "success",
            "permissions": user_permissions if user_permissions else [],
            "user_id": user_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user permissions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch permissions")

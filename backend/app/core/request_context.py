"""
Request Context - Mandatory tenant and role context extraction from authenticated user
CRITICAL: NO FALLBACK TO DEFAULTS. If tenant_id or role_template_id missing, operation FAILS.
"""
import logging
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)


class RequestContext(BaseModel):
    """Extracted request context from authenticated user - MANDATORY fields"""
    tenant_id: int
    role_template_id: int
    user_id: str


def get_request_context(
    current_user = Depends(get_current_user)
) -> RequestContext:
    """Extract mandatory tenant and role context from authenticated user.

    CRITICAL: tenant_id and role_template_id are REQUIRED MANDATORY fields.
    Login validation must ensure both are present before token creation.
    This dependency extracts them and raises 403 if either is missing.
    Add to any endpoint accessing tenant-scoped data or checking permissions.
    """
    if not current_user:
        logger.error("RequestContext: current_user is None")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )
    
    # Extract tenant_id - NO FALLBACK
    tenant_id = getattr(current_user, 'tenant_id', None)
    if tenant_id is None:
        logger.error(
            f"RequestContext: User {getattr(current_user, 'UserID', 'UNKNOWN')} "
            f"has no tenant_id - login should have validated this"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context not found. Please contact support."
        )
    
    # Extract role_template_id - NO FALLBACK
    role_template_id = getattr(current_user, 'role_template_id', None)
    if role_template_id is None:
        logger.error(
            f"RequestContext: User {getattr(current_user, 'UserID', 'UNKNOWN')} "
            f"has no role_template_id - login should have validated this"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role template context not found. Please contact support."
        )
    
    # Extract user_id
    user_id = getattr(current_user, 'UserID', None)
    if not user_id:
        logger.error("RequestContext: User has no UserID")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID not found in context"
        )
    
    return RequestContext(
        tenant_id=int(tenant_id),
        role_template_id=int(role_template_id),
        user_id=user_id
    )

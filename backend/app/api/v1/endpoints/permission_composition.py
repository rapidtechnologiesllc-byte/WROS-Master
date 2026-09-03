import logging
"""Advanced Permission Composition Endpoints.

Provides APIs for:
- Expanding permissions with hierarchy and conditional rules
- Validating permission sets
- Viewing permission trees and hierarchies
- Analyzing permission conflicts
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.models.role_template import RoleTemplate
from app.services.permission_composition_service import PermissionCompositionService


router = APIRouter(prefix="/admin/permissions", tags=["Permission Composition"])

logger = logging.getLogger(__name__)

class PermissionCheckRequest(BaseModel):
    role_template_id: int
    required_permission: str
    user_attributes: Optional[Dict] = None


class PermissionValidationRequest(BaseModel):
    permissions: List[str]


@router.post(
    "/expand",
    dependencies=[Depends(require_resource_permission("expand", "create"))]
)
def expand_permissions(
    request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Expand permissions for a role template with hierarchy and conditional rules."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == request.role_template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    expanded = PermissionCompositionService.expand_permissions(
        db=db,
        role_template_id=request.role_template_id,
        user_attributes=request.user_attributes
    )

    return {
        "role_template_id": request.role_template_id,
        "role_name": template.name,
        "permissions": sorted(list(expanded)),
        "total_permissions": len(expanded)
    }


@router.post(
    "/check",
    dependencies=[Depends(require_resource_permission("check", "create"))]
)
def check_permission(
    request: PermissionCheckRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Check if role template has a specific permission (with hierarchy)."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == request.role_template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    has_perm = PermissionCompositionService.has_permission(
        db=db,
        role_template_id=request.role_template_id,
        required_permission=request.required_permission,
        user_attributes=request.user_attributes
    )

    return {
        "role_template_id": request.role_template_id,
        "role_name": template.name,
        "required_permission": request.required_permission,
        "has_permission": has_perm
    }


@router.post(
    "/validate",
    dependencies=[Depends(require_resource_permission("validate", "create"))]
)
def validate_permissions(
    request: PermissionValidationRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Validate a permission set for conflicts and redundancies."""
    validation = PermissionCompositionService.validate_permission_hierarchy(
        request.permissions
    )

    return {
        "valid": validation["valid"],
        "redundant_permissions": validation["redundant_permissions"],
        "conflicts": validation["conflicts"],
        "warnings": validation["warnings"],
        "recommendation": "Review warnings and remove redundant permissions"
    }


@router.get(
    "/{template_id}/tree",
    dependencies=[Depends(require_resource_permission("permission_composition", "view"))]
)
def get_permission_tree(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get hierarchical view of all permissions for a role template."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    tree = PermissionCompositionService.get_permission_tree(
        db=db,
        role_template_id=template_id
    )

    return {
        "role_template_id": template_id,
        "role_name": template.name,
        **tree
    }


@router.get(
    "/hierarchy/rules",
    dependencies=[Depends(require_resource_permission("hierarchy", "view"))]
)
def get_permission_hierarchy(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get the complete permission hierarchy rules."""
    return {
        "hierarchy": PermissionCompositionService.PERMISSION_HIERARCHY,
        "conditional_rules": PermissionCompositionService.CONDITIONAL_RULES,
        "description": "This hierarchy defines which permissions imply other permissions"
    }

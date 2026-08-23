"""Role Template management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.business_unit import BusinessUnit
from app.services.rbac_audit_service import RBACauditService
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/admin/role-templates", tags=["Role Templates"])
rbac_router = APIRouter(prefix="/rbac", tags=["RBAC"])


class PermissionInput(BaseModel):
    resource_id: int
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False


class RoleTemplateCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[PermissionInput]


class GrantRevokePermissionInput(BaseModel):
    resource_name: str
    action: str  # view, create, edit, delete


class RoleTemplateUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: List[PermissionInput]


class RoleTemplateResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    is_system: bool
    permissions: List[dict]

    class Config:
        from_attributes = True


@router.get("")
def list_role_templates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """List all role templates."""
    templates = db.query(RoleTemplate).filter(
        RoleTemplate.tenant_id == current_user.tenant_id
    ).all()

    result = []
    for template in templates:
        permissions = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == template.id
        ).all()

        perm_list = []
        for perm in permissions:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            if resource:
                perm_list.append({
                    "resource_id": perm.resource_id,
                    "resource_name": resource.name,
                    "resource_display": resource.display_name,
                    "can_view": perm.can_view,
                    "can_create": perm.can_create,
                    "can_edit": perm.can_edit,
                    "can_delete": perm.can_delete,
                })

        result.append({
            "id": template.id,
            "name": template.name,
            "display_name": template.display_name,
            "description": template.description,
            "is_system": template.is_system,
            "enabled": template.enabled,
            "permissions": perm_list,
        })

    return {"role_templates": result}


@router.get("/{template_id}")
def get_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get single role template with all permissions."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    permissions = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id
    ).all()

    perm_list = []
    for perm in permissions:
        resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
        if resource:
            perm_list.append({
                "resource_id": perm.resource_id,
                "resource_name": resource.name,
                "resource_display": resource.display_name,
                "can_view": perm.can_view,
                "can_create": perm.can_create,
                "can_edit": perm.can_edit,
                "can_delete": perm.can_delete,
            })

    return {
        "id": template.id,
        "name": template.name,
        "display_name": template.display_name,
        "description": template.description,
        "is_system": template.is_system,
        "enabled": template.enabled,
        "permissions": perm_list,
    }


@router.post("")
def create_role_template(
    data: RoleTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create new role template."""
    # Check if template name already exists
    existing = db.query(RoleTemplate).filter(
        RoleTemplate.name == data.name,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Role template name already exists")

    # Create template
    template = RoleTemplate(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        is_system=False,
        tenant_id=current_user.tenant_id,
        created_by=current_user.UserEmail
    )
    db.add(template)
    db.flush()

    # Add permissions
    for perm_input in data.permissions:
        perm = RoleTemplatePermission(
            role_template_id=template.id,
            resource_id=perm_input.resource_id,
            can_view=perm_input.can_view,
            can_create=perm_input.can_create,
            can_edit=perm_input.can_edit,
            can_delete=perm_input.can_delete
        )
        db.add(perm)

    db.commit()
    db.refresh(template)

    # Audit log
    RBACauditService.log_role_template_created(
        db=db,
        template_id=template.id,
        template_name=template.name,
        template_data={
            "name": template.name,
            "display_name": template.display_name,
            "description": template.description,
            "permissions_count": len(data.permissions)
        },
        user_id=current_user.UserID,
        tenant_id=current_user.tenant_id,
        ip_address=request.client.host if request.client else None
    )

    return {
        "id": template.id,
        "name": template.name,
        "display_name": template.display_name,
        "description": template.description,
        "message": "Role template created successfully"
    }


@router.put("/{template_id}")
def update_role_template(
    template_id: int,
    data: RoleTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update role template permissions."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    if template.is_system:
        raise HTTPException(status_code=400, detail="Cannot modify system role templates")

    # Update basic fields
    if data.display_name:
        template.display_name = data.display_name
    if data.description is not None:
        template.description = data.description

    # Delete existing permissions
    db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id
    ).delete()

    # Add new permissions
    for perm_input in data.permissions:
        perm = RoleTemplatePermission(
            role_template_id=template.id,
            resource_id=perm_input.resource_id,
            can_view=perm_input.can_view,
            can_create=perm_input.can_create,
            can_edit=perm_input.can_edit,
            can_delete=perm_input.can_delete
        )
        db.add(perm)

    db.commit()

    return {"message": "Role template updated successfully"}


@router.post("/{template_id}/grant-permission")
def grant_permission(
    template_id: int,
    data: GrantRevokePermissionInput,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Grant a permission to a role template."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    resource_name = data.resource_name
    action = data.action  # view, create, edit, delete

    if not resource_name or not action:
        raise HTTPException(status_code=400, detail="resource_name and action are required")

    # Find resource by name
    resource = db.query(Resource).filter(Resource.name == resource_name).first()
    if not resource:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_name}' not found")

    # Get or create permission
    perm = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id,
        RoleTemplatePermission.resource_id == resource.id
    ).first()

    if not perm:
        perm = RoleTemplatePermission(
            role_template_id=template.id,
            resource_id=resource.id,
            can_view=False,
            can_create=False,
            can_edit=False,
            can_delete=False
        )
        db.add(perm)

    # Grant the action
    if action == "view":
        perm.can_view = True
    elif action == "create":
        perm.can_create = True
    elif action == "edit":
        perm.can_edit = True
    elif action == "delete":
        perm.can_delete = True

    db.commit()

    # Audit log
    RBACauditService.log_permission_granted(
        db=db,
        template_id=template.id,
        resource_name=resource_name,
        action=action,
        user_id=current_user.UserID,
        tenant_id=current_user.tenant_id,
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Permission granted: {resource_name} - {action}"}


@router.post("/{template_id}/revoke-permission")
def revoke_permission(
    template_id: int,
    data: GrantRevokePermissionInput,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Revoke a permission from a role template."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    resource_name = data.resource_name
    action = data.action  # view, create, edit, delete

    if not resource_name or not action:
        raise HTTPException(status_code=400, detail="resource_name and action are required")

    # Find resource by name
    resource = db.query(Resource).filter(Resource.name == resource_name).first()
    if not resource:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_name}' not found")

    # Get permission
    perm = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id,
        RoleTemplatePermission.resource_id == resource.id
    ).first()

    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    # Revoke the action
    if action == "view":
        perm.can_view = False
    elif action == "create":
        perm.can_create = False
    elif action == "edit":
        perm.can_edit = False
    elif action == "delete":
        perm.can_delete = False

    db.commit()

    # Audit log
    RBACauditService.log_permission_revoked(
        db=db,
        template_id=template.id,
        resource_name=resource_name,
        action=action,
        user_id=current_user.UserID,
        tenant_id=current_user.tenant_id,
        ip_address=request.client.host if request.client else None
    )

    return {"message": f"Permission revoked: {resource_name} - {action}"}


@router.delete("/{template_id}")
def delete_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete role template."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    if template.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system role templates")

    # Check if any users are using this template
    users_count = db.query(Users).filter(
        Users.role_template_id == template.id
    ).count()

    if users_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete template: {users_count} users are using it"
        )

    # Delete permissions and template
    db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id
    ).delete()

    db.delete(template)
    db.commit()

    return {"message": "Role template deleted successfully"}


@router.post("/{template_id}/toggle-status")
def toggle_template_status(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Toggle role template enabled/disabled status."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    # Toggle the enabled status
    template.enabled = not template.enabled
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "enabled": template.enabled,
        "message": f"Role template {'enabled' if template.enabled else 'disabled'} successfully"
    }


@rbac_router.get("/business-units")
def list_business_units(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get all active business units for the current tenant.
    Used by user creation/edit forms to populate BU dropdown.
    """
    bus = db.query(BusinessUnit).filter(
        BusinessUnit.tenant_id == current_user.tenant_id
    ).all()

    result = []
    for bu in bus:
        result.append({
            "id": bu.id,
            "name": bu.name if hasattr(bu, "name") else bu.bu_name,
            "bu_name": bu.bu_name if hasattr(bu, "bu_name") else bu.name,
        })

    return {"business_units": result}


@router.get("/{template_id}/audit-trail")
def get_template_audit_trail(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get complete audit trail for a specific role template."""
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    audit_logs = RBACauditService.get_audit_trail_for_template(
        db=db,
        template_id=template_id,
        tenant_id=current_user.tenant_id
    )

    return {
        "template_id": template_id,
        "template_name": template.name,
        "audit_trail": audit_logs
    }


@router.get("/audit/logs")
def get_rbac_audit_logs(
    entity_type: str = None,
    action: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get RBAC audit logs for the current tenant."""
    logs = RBACauditService.get_audit_logs(
        db=db,
        entity_type=entity_type,
        action=action,
        tenant_id=current_user.tenant_id,
        limit=min(limit, 500)
    )

    return {
        "total": len(logs),
        "logs": logs
    }

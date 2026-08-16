"""Role Template management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.business_unit import BusinessUnit
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


def check_rbac_permission(current_user: Users) -> None:
    """Check if user can manage RBAC templates (must have rbac.manage permission)."""
    # Only CEO, Admin, Super User can manage role templates
    allowed_roles = {"CEO", "ADMIN", "SUPER USER"}
    user_role_upper = (current_user.UserRole or "").upper()
    if user_role_upper not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CEOs, Admins, and Super Users can manage role templates"
        )


@router.get("")
def list_role_templates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """List all role templates."""
    check_rbac_permission(current_user)

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
    check_rbac_permission(current_user)

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
        "permissions": perm_list,
    }


@router.post("")
def create_role_template(
    data: RoleTemplateCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create new role template."""
    check_rbac_permission(current_user)

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
    check_rbac_permission(current_user)

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
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Grant a permission to a role template."""
    check_rbac_permission(current_user)

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
    return {"message": f"Permission granted: {resource_name} - {action}"}


@router.post("/{template_id}/revoke-permission")
def revoke_permission(
    template_id: int,
    data: GrantRevokePermissionInput,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Revoke a permission from a role template."""
    check_rbac_permission(current_user)

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
    return {"message": f"Permission revoked: {resource_name} - {action}"}


@router.delete("/{template_id}")
def delete_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete role template."""
    check_rbac_permission(current_user)

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

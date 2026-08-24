"""RBAC Role Template management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from app.services.rbac_service import RBACService
from app.models.rbac_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/admin/role-templates", tags=["RBAC Templates"])


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


class RoleTemplateUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: List[PermissionInput] = []


class RoleTemplateResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    is_system: bool
    permissions: List[dict]

    class Config:
        from_attributes = True


def check_rbac_permission(current_user: Users, db: Session) -> None:
    """Check if user can manage RBAC templates (must have rbac.manage permission)."""
    if not RBACService.has_any_permission(db, current_user.UserID, ["admin.manage", "rbac.manage"]):
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
    check_rbac_permission(current_user, db)

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
    check_rbac_permission(current_user, db)

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
    check_rbac_permission(current_user, db)

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
    try:
        check_rbac_permission(current_user, db)

        template = db.query(RoleTemplate).filter(
            RoleTemplate.id == template_id,
            RoleTemplate.tenant_id == current_user.tenant_id
        ).first()

        if not template:
            raise HTTPException(status_code=404, detail="Role template not found")

        # Update basic fields
        if data.display_name:
            template.display_name = data.display_name
        if data.description is not None:
            template.description = data.description

        # Delete existing permissions
        db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == template.id
        ).delete()
        db.flush()

        # Add new permissions
        if data.permissions:
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

        db.flush()
        db.commit()

        return {"message": "Role template updated successfully"}
    except Exception as e:
        db.rollback()
        import traceback
        print(f"Error updating role template: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating role template: {str(e)}")


@router.delete("/{template_id}")
def delete_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete role template."""
    check_rbac_permission(current_user, db)

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

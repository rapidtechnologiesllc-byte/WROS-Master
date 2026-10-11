"""Role Template management endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.core.config import settings
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.business_unit import BusinessUnit
from pydantic import BaseModel
from typing import List, Optional
import json

from app.core.audit import write_audit_log
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/admin/role-templates", tags=["Role Templates"])


def _audit_rows(db: Session, tenant_id, *, entity_type=None, entity_id=None, action=None, limit=100):
    """Audit-log rows for the tenant, newest first, as plain dicts."""
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return [
        {
            "id": row.id, "entity_type": row.entity_type, "entity_id": row.entity_id,
            "action": row.action, "user_id": row.user_id, "old_value": row.old_value,
            "new_value": row.new_value, "ip_address": row.ip_address,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }
        for row in query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    ]
rbac_router = APIRouter(prefix="/rbac", tags=["RBAC"])

logger = logging.getLogger(__name__)

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

class ToggleStatusRequest(BaseModel):
    is_active: bool

class GrantRevokePermissionInput(BaseModel):
    resource_name: str
    action: str  # view, create, edit, delete

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

@router.get(
    "",
    dependencies=[Depends(require_resource_permission("role-templates", "view"))]
)
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
            "hierarchy_level": template.hierarchy_level,
            "specialization": template.specialization,
            "permissions": perm_list,
        })

    return {"role_templates": result}

@router.get(
    "/{template_id}",
    dependencies=[Depends(require_resource_permission("role-templates", "view"))]
)
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
        "hierarchy_level": template.hierarchy_level,
        "specialization": template.specialization,
        "permissions": perm_list,
    }

@router.post(
    "",
    dependencies=[Depends(require_resource_permission("role-templates", "edit"))]
)
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

    write_audit_log(
        db, entity_type="role_template", entity_id=str(template.id), action="create",
        tenant_id=current_user.tenant_id, user_id=current_user.UserID,
        new_value=json.dumps({
            "name": template.name,
            "display_name": template.display_name,
            "description": template.description,
            "permissions_count": len(data.permissions),
        }),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "display_name": template.display_name,
        "description": template.description,
        "message": "Role template created successfully"
    }

@router.put(
    "/{template_id}",
    dependencies=[Depends(require_resource_permission("role-templates", "edit"))]
)
def update_role_template(
    template_id: int,
    data: RoleTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update role template permissions."""
    from app.core.logging import logger
    try:
        logger.info(f"[PUT] Updating role template {template_id} for user {current_user.UserID}")

        template = db.query(RoleTemplate).filter(
            RoleTemplate.id == template_id,
            RoleTemplate.tenant_id == current_user.tenant_id
        ).first()

        if not template:
            logger.warning(f"[PUT] Template {template_id} not found for tenant {current_user.tenant_id}")
            raise HTTPException(status_code=404, detail="Role template not found")

        logger.info(f"[PUT] Found template: {template.name}")

        # Update basic fields
        if data.display_name:
            template.display_name = data.display_name
            logger.info(f"[PUT] Updated display_name to: {data.display_name}")
        if data.description is not None:
            template.description = data.description
            logger.info("[PUT] Updated description")

        # Delete existing permissions
        logger.info(f"[PUT] Deleting existing permissions for template {template_id}")
        db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == template.id
        ).delete()
        db.flush()
        logger.info("[PUT] Permissions deleted and flushed")

        # Add new permissions
        if data.permissions:
            logger.info(f"[PUT] Adding {len(data.permissions)} new permissions")
            for idx, perm_input in enumerate(data.permissions):
                perm = RoleTemplatePermission(
                    role_template_id=template.id,
                    resource_id=perm_input.resource_id,
                    can_view=perm_input.can_view,
                    can_create=perm_input.can_create,
                    can_edit=perm_input.can_edit,
                    can_delete=perm_input.can_delete
                )
                db.add(perm)
                logger.info(f"[PUT] Added permission {idx+1}: resource_id={perm_input.resource_id}")

        logger.info("[PUT] Flushing permissions")
        db.flush()
        logger.info("[PUT] Committing transaction")
        db.commit()
        logger.info(f"[PUT] Role template {template_id} updated successfully")

        return {"message": "Role template updated successfully"}
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[PUT] Error updating role template {template_id}: {str(e)}", exc_info=True)
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating role template: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating role template: {str(e)}")

@router.post(
    "/{template_id}/grant-permission",
    dependencies=[Depends(require_resource_permission("role-templates", "edit"))]
)
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
        db.flush()  # Flush to ensure perm has an ID

    # Grant the action - only update if it's currently false
    action_updated = False
    if action == "view" and not perm.can_view:
        perm.can_view = True
        action_updated = True
    elif action == "create" and not perm.can_create:
        perm.can_create = True
        action_updated = True
    elif action == "edit" and not perm.can_edit:
        perm.can_edit = True
        action_updated = True
    elif action == "delete" and not perm.can_delete:
        perm.can_delete = True
        action_updated = True

    # Only commit if something changed
    if action_updated or not perm.id:
        db.commit()

    return {"message": f"Permission granted: {resource_name} - {action}"}

@router.post(
    "/{template_id}/revoke-permission",
    dependencies=[Depends(require_resource_permission("role-templates", "edit"))]
)
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
        # If permission doesn't exist, it's already revoked - return success
        return {"message": f"Permission already revoked: {resource_name} - {action}"}

    # Revoke the action - only update if it's currently true
    action_updated = False
    if action == "view" and perm.can_view:
        perm.can_view = False
        action_updated = True
    elif action == "create" and perm.can_create:
        perm.can_create = False
        action_updated = True
    elif action == "edit" and perm.can_edit:
        perm.can_edit = False
        action_updated = True
    elif action == "delete" and perm.can_delete:
        perm.can_delete = False
        action_updated = True

    # Only commit if something changed
    if action_updated:
        db.commit()

    return {"message": f"Permission revoked: {resource_name} - {action}"}

@router.delete(
    "/{template_id}",
    dependencies=[Depends(require_resource_permission("role-templates", "edit"))]
)
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

@router.post(
    "/{template_id}/toggle-status",
    dependencies=[Depends(require_resource_permission("role-templates", "create"))]
)
def toggle_template_status(
    template_id: int,
    request: ToggleStatusRequest,
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

    # Set enabled status from request
    template.enabled = request.is_active
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "enabled": template.enabled,
        "is_active": template.enabled,
        "message": f"Role template {'enabled' if template.enabled else 'disabled'} successfully"
    }

@rbac_router.get("/business-units")
def list_business_units(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    All business units for the current tenant with their companies, partner
    and BU head. Used by the BU list and every BU dropdown.
    """
    bus = db.query(BusinessUnit).filter(
        BusinessUnit.tenant_id == _bu_tenant(current_user)
    ).order_by(BusinessUnit.name).all()
    return {"business_units": [_bu_dict(db, bu) for bu in bus]}

class BusinessUnitCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    region: Optional[str] = None
    continent: Optional[str] = None
    # Companies (legal entities, e.g. BX-US, BX-IN) the BU operates in.
    # None leaves unchanged; [] clears.
    company_ids: Optional[List[str]] = None
    # Users; "" clears, None leaves unchanged
    partner_user_id: Optional[str] = None
    head_user_id: Optional[str] = None


# Who may be named on a BU: by role template hierarchy level (app.core.authority), not role name
def _leader_requirement(min_level: int) -> str:
    from app.services.org_hierarchy_validator import HIERARCHY_LEVELS

    return f"{HIERARCHY_LEVELS.get(min_level, f'level {min_level}')} or above (role level {min_level}+)"


def _bu_tenant(user: Users) -> int:
    return user.tenant_id if getattr(user, "tenant_id", None) else 1


def _leader(db: Session, tenant_id: int, user_id: str, min_level: int, label: str) -> Users:
    from app.core import authority

    user = db.query(Users).filter(Users.UserID == user_id, Users.tenant_id == tenant_id).first()
    if not user:
        raise HTTPException(status_code=422, detail=f"Unknown {label}")
    if authority.level(db, user) < min_level:
        raise HTTPException(
            status_code=422,
            detail=f"{label} must be {_leader_requirement(min_level)}; {user.UserName or user.UserEmail}'s role is "
                   f"level {authority.level(db, user)} (set it on the Users tab)",
        )
    return user


def _set_bu_structure(db: Session, bu: BusinessUnit, tenant_id: int, req: BusinessUnitCreateRequest) -> None:
    """Validate and apply companies, partner and BU head."""
    from app.models.business_unit import BusinessUnitCompany
    from app.models.location import Location

    if req.company_ids is not None:
        wanted = set(req.company_ids)
        known = {l.id for l in db.query(Location).filter(Location.tenant_id == tenant_id, Location.id.in_(wanted))}
        if wanted - known:
            raise HTTPException(status_code=422, detail="Unknown company")
        db.flush()
        current = {c.company_id: c for c in db.query(BusinessUnitCompany).filter(BusinessUnitCompany.business_unit_id == bu.id)}
        for company_id, row in current.items():
            if company_id not in wanted:
                db.delete(row)
        for company_id in wanted - set(current):
            db.add(BusinessUnitCompany(tenant_id=tenant_id, business_unit_id=bu.id, company_id=company_id))

    if req.partner_user_id is not None:
        bu.partner_user_id = _leader(db, tenant_id, req.partner_user_id, settings.PARTNER_MIN_LEVEL, "Partner").UserID if req.partner_user_id else None
    if req.head_user_id is not None:
        bu.manager_id = _leader(db, tenant_id, req.head_user_id, settings.BU_LEADER_MIN_LEVEL, "BU Head").UserID if req.head_user_id else None


def _bu_dict(db: Session, bu: BusinessUnit) -> dict:
    from app.models.business_unit import BusinessUnitCompany
    from app.models.location import Location

    companies = (
        db.query(Location).join(BusinessUnitCompany, BusinessUnitCompany.company_id == Location.id)
        .filter(BusinessUnitCompany.business_unit_id == bu.id).order_by(Location.name).all()
    )
    person = lambda u: {"user_id": u.UserID, "name": u.UserName or u.UserEmail} if u else None
    return {
        "id": bu.id,
        "name": bu.name,
        "display_name": bu.display_name,
        "description": bu.description,
        "active": bu.active,
        "companies": [{"id": c.id, "name": c.name} for c in companies],
        "partner": person(bu.partner),
        "head": person(bu.manager),
    }

@rbac_router.get("/business-units/leader-options", dependencies=[Depends(require_resource_permission("business-units", "view"))])
def business_unit_leader_options(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Users who can be named Partner / BU Head on a business unit (by role)."""
    from app.models.role_template import RoleTemplate

    def users_at(min_level):
        rows = (db.query(Users).join(RoleTemplate, RoleTemplate.id == Users.role_template_id)
                .filter(Users.tenant_id == _bu_tenant(current_user), RoleTemplate.enabled.is_(True),
                        RoleTemplate.hierarchy_level >= min_level)
                .order_by(Users.UserName).all())
        return [{"user_id": u.UserID, "name": u.UserName or u.UserEmail} for u in rows]

    return {"partners": users_at(settings.PARTNER_MIN_LEVEL), "heads": users_at(settings.BU_LEADER_MIN_LEVEL),
            "partner_requirement": _leader_requirement(settings.PARTNER_MIN_LEVEL),
            "head_requirement": _leader_requirement(settings.BU_LEADER_MIN_LEVEL)}

@rbac_router.get("/business-units/{bu_id}", dependencies=[Depends(require_resource_permission("business-units", "view"))])
def get_business_unit_rbac(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get a single business unit by id. Used by the edit form to prefill fields."""
    bu = db.query(BusinessUnit).filter(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == _bu_tenant(current_user),
    ).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")
    return _bu_dict(db, bu)

@rbac_router.post("/business-units", dependencies=[Depends(require_resource_permission("business-units", "create"))])
def create_business_unit_rbac(
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Create a new business unit.
    Accessible from RBAC endpoints.
    """
    # Validate input
    if not req.name:
        raise HTTPException(status_code=400, detail="Business Unit name is required")

    # Determine tenant_id (default to 1 if None)
    tenant_id = current_user.tenant_id if hasattr(current_user, 'tenant_id') and current_user.tenant_id else 1

    new_bu = BusinessUnit(
        name=req.name,
        display_name=req.display_name or req.name,
        description=req.description,
        bu_code=req.name.upper().replace(" ", ""),
        tenant_id=tenant_id,
        active=True
    )

    db.add(new_bu)
    db.flush()
    _set_bu_structure(db, new_bu, tenant_id, req)
    db.commit()
    db.refresh(new_bu)

    return {
        "id": new_bu.id,
        "name": new_bu.name,
        "display_name": new_bu.display_name,
        "status": "created"
    }

@rbac_router.put("/business-units/{bu_id}", dependencies=[Depends(require_resource_permission("business-units", "edit"))])
def update_business_unit_rbac(
    bu_id: int,
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update a business unit. Accessible from RBAC endpoints (matches create_business_unit_rbac's field set - region/continent are accepted but BusinessUnit has no such columns, same as create)."""
    bu = db.query(BusinessUnit).filter(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == (current_user.tenant_id if hasattr(current_user, 'tenant_id') and current_user.tenant_id else 1),
    ).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")

    if req.name:
        bu.name = req.name
    if req.display_name:
        bu.display_name = req.display_name
    if req.description is not None:
        bu.description = req.description
    _set_bu_structure(db, bu, bu.tenant_id, req)

    db.commit()
    db.refresh(bu)

    return {
        "id": bu.id,
        "name": bu.name,
        "display_name": bu.display_name,
        "status": "updated"
    }

@rbac_router.delete("/business-units/{bu_id}", dependencies=[Depends(require_resource_permission("business-units", "delete"))])
def delete_business_unit_rbac(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete a business unit. Accessible from RBAC endpoints."""
    bu = db.query(BusinessUnit).filter(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == (current_user.tenant_id if hasattr(current_user, 'tenant_id') and current_user.tenant_id else 1),
    ).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")

    db.delete(bu)
    db.commit()

    return {"status": "deleted"}


@router.get(
    "/{template_id}/users",
    dependencies=[Depends(require_resource_permission("role-templates", "view"))]
)
def get_users_for_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get all users assigned to a specific role template."""
    # Verify template exists and belongs to current tenant
    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role template not found"
        )

    # Get users assigned to this role template
    users = db.query(Users).filter(
        Users.role_template_id == template_id,
        Users.tenant_id == current_user.tenant_id
    ).all()

    return {
        "template_id": template_id,
        "template_name": template.name,
        "user_count": len(users),
        "users": [
            {
                "user_id": u.UserID,
                "email": u.UserEmail,
                "name": u.UserName,
                "role": template.name,
                "business_unit": u.business_unit_name if hasattr(u, 'business_unit_name') else None,
                "active": u.is_active()
            }
            for u in users
        ]
    }


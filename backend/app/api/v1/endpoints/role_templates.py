"""Role Template management endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.core.config import settings
from app.services.role_template_permission_service import invalidate_permissions
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.business_unit import BusinessUnit
from pydantic import BaseModel
from typing import Dict, List, Optional
import json

from app.core.audit import write_audit_log
from app.models.audit_log import AuditLog
from app.core.tenant_context import tenant_id_of

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
    # The function this add-on is for (Recruitment, HR, Finance ...); "General" = any function
    specialization: str = "General"
    permissions: List[PermissionInput]

class ToggleStatusRequest(BaseModel):
    is_active: bool

class GrantRevokePermissionInput(BaseModel):
    resource_name: str
    action: str  # view, create, edit, delete

class RoleTemplateUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    specialization: Optional[str] = None
    permissions: List[PermissionInput] = []


def _function(value: Optional[str]) -> str:
    """A template's function: General or one the org knows (org_hierarchy_validator.FUNCTION_WORDS)."""
    from app.services.org_hierarchy_validator import FUNCTION_WORDS

    value = (value or "General").strip()
    if value != "General" and value not in FUNCTION_WORDS:
        raise HTTPException(status_code=422,
                            detail=f"Function must be General or one of {sorted(FUNCTION_WORDS)}")
    return value

class RoleTemplateResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    is_system: bool
    permissions: List[dict]

    class Config:
        from_attributes = True

def _owner_role(db: Session, template_id: int):
    """{id, name, hierarchy_level} of the Manage Role whose permission set this is, else None."""
    from app.services.org_roles_service import owning_role

    role = owning_role(db, template_id)
    return {"id": role.id, "name": role.name, "hierarchy_level": role.hierarchy_level} if role else None


def _guard_role_set(db: Session, template: RoleTemplate, current_user: Users) -> None:
    """A Manage Role's permission set decides what everyone holding that role may do, so
    changing it takes the same right as managing the roles themselves (org-roles edit)."""
    from app.core import authority

    if _owner_role(db, template.id) and not authority.has_permission(db, current_user, "org-roles.edit"):
        raise HTTPException(status_code=403,
                            detail="Changing a role's permissions needs the Manage Roles (org-roles) edit permission")


def _canonical_resource(db: Session, name: str, tenant_id: int) -> Resource:
    from app.services.role_template_permission_service import RoleTemplatePermissionService

    resource = RoleTemplatePermissionService.get_resource_by_name(db, name, tenant_id)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Resource '{name}' not found")
    return resource


@router.get(
    "/functions",
    dependencies=[Depends(require_resource_permission("role-templates", "view"))]
)
def list_functions():
    """Functions an add-on can be for. A person's department names their function, and the
    user form suggests the add-on whose function matches it."""
    from app.services.org_hierarchy_validator import FUNCTION_WORDS

    return {"functions": ["General", *FUNCTION_WORDS.keys()]}


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
            "owner_role": _owner_role(db, template.id),
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
        "owner_role": _owner_role(db, template.id),
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
        specialization=_function(data.specialization),
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
            tenant_id=template.tenant_id,
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
        _guard_role_set(db, template, current_user)

        # Update basic fields
        if data.display_name:
            template.display_name = data.display_name
            logger.info(f"[PUT] Updated display_name to: {data.display_name}")
        if data.description is not None:
            template.description = data.description
            logger.info("[PUT] Updated description")
        if data.specialization is not None:
            function = _function(data.specialization)
            if function != "General" and _owner_role(db, template.id):
                raise HTTPException(status_code=400, detail="A role's permissions apply to everyone holding the role; "
                                                            "a function belongs on a function add-on")
            template.specialization = function

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
                    tenant_id=template.tenant_id,
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
        invalidate_permissions()
        logger.info(f"[PUT] Role template {template_id} updated successfully")

        return {"message": "Role template updated successfully"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[PUT] Error updating role template {template_id}: {str(e)}", exc_info=True)
        db.rollback()
        import traceback
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

    _guard_role_set(db, template, current_user)
    resource = _canonical_resource(db, resource_name, template.tenant_id)

    # Get or create permission
    perm = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id,
        RoleTemplatePermission.resource_id == resource.id,
        RoleTemplatePermission.tenant_id == template.tenant_id,
    ).first()

    if not perm:
        perm = RoleTemplatePermission(
            role_template_id=template.id,
            resource_id=resource.id,
            tenant_id=template.tenant_id,
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
        invalidate_permissions()

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

    _guard_role_set(db, template, current_user)
    resource = _canonical_resource(db, resource_name, template.tenant_id)

    # Get permission
    perm = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id,
        RoleTemplatePermission.resource_id == resource.id,
        RoleTemplatePermission.tenant_id == template.tenant_id,
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
        invalidate_permissions()

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
    owner = _owner_role(db, template.id)
    if owner:
        raise HTTPException(status_code=400,
                            detail=f"This is the {owner['name']} role's permission set; it goes with the role")

    # Its own permission rows go with it; anything else still using it (people holding it as
    # their add-on, ...) blocks the delete -- the session is never committed on a 409
    from app.core.references import ensure_deletable

    db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == template.id
    ).delete()
    db.flush()
    ensure_deletable(db, template, f"Role template '{template.display_name or template.name}'")

    db.delete(template)
    db.commit()
    invalidate_permissions()

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

    owner = _owner_role(db, template.id)
    if owner and not request.is_active:
        raise HTTPException(status_code=400,
                            detail=f"This is the {owner['name']} role's permission set; disabling it would "
                                   "silently strip everyone holding the role. Revoke permissions instead.")

    # Set enabled status from request
    template.enabled = request.is_active
    db.add(template)
    db.commit()
    invalidate_permissions()
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
    # Users; "" clears, None leaves unchanged. One partner for the whole BU.
    partner_user_id: Optional[str] = None
    # BU head per company the BU operates in: {company_id: user_id, "" clears that company}.
    # None leaves all heads unchanged; companies not listed are left as they are.
    location_heads: Optional[Dict[str, str]] = None


# Who may be named on a BU: by role template hierarchy level (app.core.authority), not role name
def _leader_requirement(min_level: int) -> str:
    from app.services.org_hierarchy_validator import HIERARCHY_LEVELS

    return f"{HIERARCHY_LEVELS.get(min_level, f'level {min_level}')} or above (role level {min_level}+)"


def _bu_tenant(user: Users) -> int:
    return tenant_id_of(user)


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
    """Validate and apply companies, partner and the BU head in each company."""
    from app.models.business_unit import BusinessUnitCompany
    from app.models.location import Location
    from app.services import bu_leadership

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
        db.flush()
        bu_leadership.drop_heads_outside(db, bu.id, wanted)

    if req.partner_user_id is not None:
        bu.partner_user_id = _leader(db, tenant_id, req.partner_user_id, settings.PARTNER_MIN_LEVEL, "Partner").UserID if req.partner_user_id else None
    if req.location_heads is not None:
        try:
            bu_leadership.set_location_heads(
                db, bu, tenant_id, req.location_heads,
                lambda user_id: _leader(db, tenant_id, user_id, settings.BU_LEADER_MIN_LEVEL, "BU Head"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


def _bu_dict(db: Session, bu: BusinessUnit) -> dict:
    from app.models.business_unit import BusinessUnitCompany
    from app.models.location import Location
    from app.services.bu_leadership import location_heads

    companies = (
        db.query(Location).join(BusinessUnitCompany, BusinessUnitCompany.company_id == Location.id)
        .filter(BusinessUnitCompany.business_unit_id == bu.id).order_by(Location.name).all()
    )
    person = lambda u: {"user_id": u.UserID, "name": u.UserName or u.UserEmail} if u else None
    heads = location_heads(db, bu.id)
    return {
        "id": bu.id,
        "name": bu.name,
        "display_name": bu.display_name,
        "description": bu.description,
        "active": bu.active,
        # each company the BU operates in, with the BU head there
        "companies": [{"id": c.id, "name": c.name, "head": person(heads[c.id].head) if c.id in heads else None}
                      for c in companies],
        "partner": person(bu.partner),
    }

@rbac_router.get("/business-units/leader-options", dependencies=[Depends(require_resource_permission("business-units", "view"))])
def business_unit_leader_options(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Users who can be named Partner / BU Head on a business unit (by role level -- the same
    authority.level that _leader checks, so the picker and the save can't disagree)."""
    from app.core import authority

    people = db.query(Users).filter(Users.tenant_id == _bu_tenant(current_user)).order_by(Users.UserName).all()
    levels = {u.UserID: authority.level(db, u) for u in people}

    def users_at(min_level):
        return [{"user_id": u.UserID, "name": u.UserName or u.UserEmail} for u in people
                if levels[u.UserID] >= min_level]

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
    tenant_id = tenant_id_of(current_user)

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
        BusinessUnit.tenant_id == tenant_id_of(current_user),
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
        BusinessUnit.tenant_id == tenant_id_of(current_user),
    ).first()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")

    from app.core.references import ensure_deletable

    ensure_deletable(db, bu, f"Business unit '{bu.display_name or bu.name}'")
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

    # Who gets this template: as their function add-on, or -- for a role's permission set --
    # everyone whose Job Title is that role
    from sqlalchemy import func, or_

    from app.services.org_roles_service import owning_role

    holds = Users.role_template_id == template_id
    role = owning_role(db, template_id)
    if role is not None:
        holds = or_(holds, func.lower(func.trim(Users.job_title)) == role.name.strip().lower())
    users = db.query(Users).filter(holds, Users.tenant_id == current_user.tenant_id).all()

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


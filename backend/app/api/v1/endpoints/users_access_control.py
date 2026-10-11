"""
Users Access Control Management Endpoints
Handles management of:
- Users (CRUD operations)
- Business Units (CRUD operations)
- Delivery Centers (CRUD operations)
- Organizational Hierarchy (Get/Update)
- Role Templates (CRUD operations)

All endpoints require appropriate role-based permissions.
Super User can access everything; other roles require specific permissions.

Permission Model:
- GET /users → administration.view
- POST /users → administration.create
- PUT /users/{id} → administration.edit
- DELETE /users/{id} → administration.delete

Same pattern applied to all other resources (business_units, role_templates, etc.).
"""
import uuid

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import (
    require_resource_permission,
    get_current_internal_user,
    require_role_template_permission,
    require_resource_permission,
)
from app.core.permission_registry import Permissions
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.org_structure import OrgNode
from app.models.role_template import RoleTemplate
from app.schemas.user import AllUsersResponse, UserResponse
from app.services.role_template_permission_service import RoleTemplatePermissionService
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/users-access-control", tags=["Users Access Control"])

# ============================================================================
# USERS ENDPOINTS
# ============================================================================
logger = logging.getLogger(__name__)

class UserCreateRequest(BaseModel):
    user_name: str
    user_email: str
    user_password: str
    job_title: Optional[str] = None
    business_unit_id: Optional[int] = None
    department_id: Optional[str] = None
    role_template_id: int

class UserUpdateRequest(BaseModel):
    user_name: Optional[str] = None
    job_title: Optional[str] = None
    business_unit_id: Optional[int] = None
    department_id: Optional[str] = None


# ============================================================================
# BUSINESS UNITS ENDPOINTS
# ============================================================================

class BusinessUnitCreateRequest(BaseModel):
    name: str
    display_name: str
    bu_code: Optional[str] = None
    description: Optional[str] = None


# ============================================================================
# DELIVERY CENTERS ENDPOINTS (Locations)
# ============================================================================

class DeliveryCenterCreateRequest(BaseModel):
    name: str
    # Country / State / City names, from the same cascading picker as candidates
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    center_type: Optional[str] = "Delivery"  # HQ = parent company, Delivery = subsidiary
    headcount: Optional[int] = 0
    # Required for a subsidiary: the parent company it belongs to
    parent_company_id: Optional[str] = None


PARENT_COMPANY_TYPE = "HQ"


def _validate_company_structure(db: Session, tenant_id, center_type, parent_company_id, company_id=None):
    """A subsidiary must name an existing parent company; a parent company has none."""
    if center_type == PARENT_COMPANY_TYPE:
        if parent_company_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A parent company cannot itself have a parent company")
        return None
    if not parent_company_id:
        has_parent = db.query(Location).filter(Location.tenant_id == tenant_id, Location.location_type == PARENT_COMPANY_TYPE).first()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pick the parent company this subsidiary belongs to" if has_parent
            else "Add the parent company first: a subsidiary has to belong to one",
        )
    parent = db.query(Location).filter(Location.id == parent_company_id, Location.tenant_id == tenant_id).first()
    if parent is None or parent.location_type != PARENT_COMPANY_TYPE or parent.id == company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The parent must be an existing parent company")
    return parent.id

@router.get(
    "/delivery-centers",
    dependencies=[Depends(require_resource_permission("delivery-centers", "view"))]
)
def list_delivery_centers(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """List the companies (legal entities, e.g. BX-US, BX-IN). Headcount is
    counted from employees whose employer is the company, not typed in."""
    from sqlalchemy import func
    from app.models.business_unit import BusinessUnitCompany
    from app.models.employee import Employee
    from app.services.ceo_fy_progress_service import WORKING_STATUSES_EXCLUDED

    query = db.query(Location)

    if hasattr(current_user, 'tenant_id'):
        query = query.filter(Location.tenant_id == current_user.tenant_id)

    total = query.count()
    locations = query.order_by(Location.name).offset(skip).limit(limit).all()
    ids = [l.id for l in locations]
    names = {l.id: l.name for l in db.query(Location).filter(Location.tenant_id == current_user.tenant_id)}
    headcount = dict(
        db.query(Employee.company_id, func.count(Employee.id))
        .filter(Employee.company_id.in_(ids), Employee.status.notin_(WORKING_STATUSES_EXCLUDED))
        .group_by(Employee.company_id).all()
    ) if ids else {}
    bu_count = dict(
        db.query(BusinessUnitCompany.company_id, func.count(BusinessUnitCompany.id))
        .filter(BusinessUnitCompany.company_id.in_(ids)).group_by(BusinessUnitCompany.company_id).all()
    ) if ids else {}

    return {
        "delivery_centers": [
            {
                "id": l.id,
                "name": l.name,
                "city": getattr(l, 'city', None),
                "state": getattr(l, 'state', None),
                "parent_company_id": l.parent_company_id,
                "parent_company_name": names.get(l.parent_company_id),
                "country": getattr(l, 'country', None),
                "center_type": getattr(l, 'location_type', 'Delivery'),
                "headcount": headcount.get(l.id, 0),
                "business_unit_count": bu_count.get(l.id, 0),
                "created_at": getattr(l, 'created_at', None),
            }
            for l in locations
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post(
    "/delivery-centers",
    dependencies=[Depends(require_resource_permission("delivery-centers", "create"))]
)
def create_delivery_center(
    req: DeliveryCenterCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create a new delivery center (Admin and Super User only)."""
    # Validate input
    if not req.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required")
    tenant_id = current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1
    parent_id = _validate_company_structure(db, tenant_id, req.center_type, req.parent_company_id)

    new_dc = Location(
        parent_company_id=parent_id,
        name=req.name,
        city=req.city,
        state=req.state,
        country=req.country,
        location_type=req.center_type,
        headcount=req.headcount,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1
    )

    db.add(new_dc)
    db.commit()
    db.refresh(new_dc)

    return {
        "id": new_dc.id,
        "name": new_dc.name,
        "status": "created"
    }

@router.put(
    "/delivery-centers/{dc_id}",
    dependencies=[Depends(require_resource_permission("delivery-centers", "edit"))]
)
def update_delivery_center(
    dc_id: str,
    req: DeliveryCenterCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update delivery center (Admin and Super User only)."""
    dc = db.query(Location).filter(Location.id == dc_id).first()
    if not dc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery Center not found")

    # Update fields
    if req.name:
        dc.name = req.name
    if req.center_type or req.parent_company_id is not None:
        new_type = req.center_type or dc.location_type
        new_parent = req.parent_company_id if req.parent_company_id is not None else dc.parent_company_id
        if new_type != PARENT_COMPANY_TYPE and dc.location_type == PARENT_COMPANY_TYPE and \
                db.query(Location).filter(Location.parent_company_id == dc.id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="This parent company has subsidiaries; move them first")
        dc.parent_company_id = _validate_company_structure(db, dc.tenant_id, new_type, new_parent or None, dc.id)
    # None leaves a field unchanged; "" clears it
    if req.city is not None:
        dc.city = req.city or None
    if req.state is not None:
        dc.state = req.state or None
    if req.country is not None:
        dc.country = req.country or None
    if req.center_type:
        dc.location_type = req.center_type
    if req.headcount is not None:
        dc.headcount = req.headcount

    db.commit()
    db.refresh(dc)

    return {
        "id": dc.id,
        "name": dc.name,
        "status": "updated"
    }

@router.delete(
    "/delivery-centers/{dc_id}",
    dependencies=[Depends(require_resource_permission("delivery-centers", "delete"))]
)
def delete_delivery_center(
    dc_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete delivery center (Super User only)."""
    dc = db.query(Location).filter(Location.id == dc_id).first()
    if not dc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery Center not found")
    if db.query(Location).filter(Location.parent_company_id == dc.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This parent company has subsidiaries; delete or move them first")

    db.delete(dc)
    db.commit()

    return {"status": "deleted"}

# ============================================================================
# ORGANIZATIONAL HIERARCHY ENDPOINTS
# ============================================================================

class OrgNodeCreateRequest(BaseModel):
    employee_name: str
    position_id: int
    reports_to: Optional[str] = None  # parent org node id
    department_id: Optional[str] = None
    specialization: Optional[str] = None

class OrgNodeUpdateRequest(BaseModel):
    employee_name: Optional[str] = None
    position_id: Optional[int] = None
    reports_to: Optional[str] = None  # parent org node id
    department_id: Optional[str] = None
    specialization: Optional[str] = None


# ============================================================================
# ROLE TEMPLATES ENDPOINTS
# ============================================================================

class RoleTemplateCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list] = []

@router.get(
    "/role-templates",
    dependencies=[Depends(require_resource_permission("role-templates", "view"))]
)
def list_role_templates(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """List all role templates."""
    query = db.query(RoleTemplate)

    if hasattr(current_user, 'tenant_id'):
        query = query.filter(RoleTemplate.tenant_id == current_user.tenant_id)

    total = query.count()
    templates = query.offset(skip).limit(limit).all()

    return {
        "role_templates": [
            {
                "id": t.id,
                "name": t.name,
                "display_name": t.display_name or t.name,
                "description": t.description,
                "is_active": getattr(t, 'is_active', True),
                "created_at": getattr(t, 'created_at', None),
            }
            for t in templates
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post(
    "/role-templates",
    dependencies=[Depends(require_resource_permission("role-templates", "create"))]
)
def create_role_template(
    req: RoleTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create a new role template (Admin and Super User only)."""
    # Validate input
    if not req.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role template name is required")

    new_template = RoleTemplate(
        name=req.name,
        display_name=req.display_name or req.name,
        description=req.description,
        is_active=True,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1
    )

    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    return {
        "id": new_template.id,
        "name": new_template.name,
        "display_name": new_template.display_name,
        "status": "created"
    }


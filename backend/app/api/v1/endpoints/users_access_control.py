"""
Users Access Control Management Endpoints
Handles management of:
- Users (CRUD operations)
- Business Units (CRUD operations)
- Delivery Centers (CRUD operations)
- Organizational Hierarchy (Get/Update)
import logging
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
    city: Optional[str] = None
    country: Optional[str] = None
    center_type: Optional[str] = "Delivery"  # HQ, Delivery, etc.
    headcount: Optional[int] = 0

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery Center name is required")

    new_dc = Location(
        name=req.name,
        city=req.city,
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
    if req.city:
        dc.city = req.city
    if req.country:
        dc.country = req.country
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


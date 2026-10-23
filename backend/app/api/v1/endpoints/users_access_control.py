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
from app.core.tenant_context import tenant_id_of
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.models.location import Location
from app.models.role_template import RoleTemplate
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
    """Every company is a registered entity that reports to the holding company (the tenant,
    e.g. BlitzenX), which owns the org-wide P&L. A parent company inside the tenant is optional
    (legal nesting only); when given it must be another company of the same tenant."""
    if not parent_company_id:
        return None
    parent = db.query(Location).filter(Location.id == parent_company_id, Location.tenant_id == tenant_id).first()
    if parent is None or parent.id == company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="The parent must be another company of the same holding company")
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

    from app.models.tenant import Tenant

    tenant_id = tenant_id_of(current_user)
    query = db.query(Location).filter(Location.tenant_id == tenant_id)
    total = query.count()
    locations = query.order_by(Location.company_seq, Location.name).offset(skip).limit(limit).all()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
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
                # "<tenant>-<n>": this company inside its parent company (the tenant)
                "company_code": l.company_code,
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
        # The parent company is the tenant: it owns the org-wide P&L of all its companies
        "parent_company": {"tenant_id": tenant_id, "name": tenant.name if tenant else None,
                           "company_code": str(tenant_id)},
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
    tenant_id = tenant_id_of(current_user)
    parent_id = _validate_company_structure(db, tenant_id, req.center_type, req.parent_company_id)

    # Next number inside the tenant (code "<tenant>-<n>"); the unique index makes a race fail loudly
    from sqlalchemy import func as sql_func
    next_seq = (db.query(sql_func.max(Location.company_seq)).filter(Location.tenant_id == tenant_id).scalar() or 0) + 1
    new_dc = Location(
        parent_company_id=parent_id,
        name=req.name,
        city=req.city,
        state=req.state,
        country=req.country,
        location_type=req.center_type,
        headcount=req.headcount,
        tenant_id=tenant_id,
        company_seq=next_seq,
    )

    db.add(new_dc)
    db.commit()
    db.refresh(new_dc)

    return {
        "id": new_dc.id,
        "name": new_dc.name,
        "company_code": new_dc.company_code,
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
    from app.core.references import ensure_deletable

    dc = db.query(Location).filter(Location.id == dc_id, Location.tenant_id == current_user.tenant_id).first()
    if not dc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    ensure_deletable(db, dc, f"Company '{dc.name}'")  # subsidiaries, users, seats, BU links ...

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



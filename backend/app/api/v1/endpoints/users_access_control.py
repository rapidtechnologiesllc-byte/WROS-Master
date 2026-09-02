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

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.permission_enforcement import (
    require_action_permission, check_permission, check_any_permission
)
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.models.location import Location
from app.models.org_structure import OrgNode
from app.models.role_template import RoleTemplate
from app.schemas.user import AllUsersResponse, UserResponse
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
    role_template_id: int

class UserUpdateRequest(BaseModel):
    user_name: Optional[str] = None
    job_title: Optional[str] = None
    business_unit_id: Optional[int] = None

@router.get("/users")
    dependencies=[Depends(get_current_user)]
@require_action_permission("administration", "view")
def list_users(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None
):
    """
    List all users with pagination and search.

    Permission: administration.view

    Query Parameters:
    - skip: Number of users to skip (default 0)
    - limit: Maximum users to return (default 100, max 500)
    - search: Search by name or email
    """

    query = db.query(Users)

    # Filter by search term if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Users.UserName.ilike(search_term),
                Users.UserEmail.ilike(search_term)
            )
        )

    # Get total count
    total = query.count()

    # Paginate
    users = query.offset(skip).limit(limit).all()

    return {
        "users": [
            {
                "user_id": u.UserID,
                "user_name": u.UserName,
                "user_email": u.UserEmail,
                "user_role": u.UserRole,
                "job_title": getattr(u, 'job_title', None),
                "business_unit_id": getattr(u, 'business_unit_id', None),
                "created_at": getattr(u, 'created_at', None),
                "is_active": getattr(u, 'is_active', True),
            }
            for u in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post("/users")
    dependencies=[Depends(get_current_user)]
@require_action_permission("administration", "create")
def create_user(
    req: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Create a new user.

    Permission: administration.create

    Request Body:
    - user_name: User's full name (required)
    - user_email: User's email address (required)
    - user_password: User's password (required)
    - job_title: User's job title (optional)
    - business_unit_id: Business unit to assign user to (optional)
    - role_template_id: Role template ID to assign to user (required)
    """

    # Validate input
    if not req.user_name or not req.user_email or not req.user_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name, email, and password are required")

    if not req.role_template_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role template is required")

    # Check if user already exists
    existing = db.query(Users).filter(Users.UserEmail == req.user_email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists with this email")

    # Create user (use the create_access_token function from users.py for password hashing)
    from app.core.security import get_password_hash
    from app.utils.uniq_id_generator import user_id_generator

    new_user = Users(
        UserID=user_id_generator(),
        UserName=req.user_name,
        UserEmail=req.user_email,
        UserPassword=get_password_hash(req.user_password),
        UserRole="User",  # Default legacy role
        job_title=req.job_title,
        business_unit_id=req.business_unit_id,
        role_template_id=req.role_template_id,  # Assign role template
        is_active=True,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "user_id": new_user.UserID,
        "user_name": new_user.UserName,
        "user_email": new_user.UserEmail,
        "user_role": new_user.UserRole,
        "job_title": new_user.job_title,
        "business_unit_id": new_user.business_unit_id,
        "status": "created"
    }

@router.put("/users/{user_id}")
    dependencies=[Depends(get_current_user)]
@require_action_permission("administration", "edit")
def update_user(
    user_id: str,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Update user details.

    Permission: administration.edit

    Path Parameters:
    - user_id: ID of the user to update

    Request Body:
    - user_name: Updated user name (optional)
    - job_title: Updated job title (optional)
    - business_unit_id: Updated business unit (optional)
    """

    user = db.query(Users).filter(Users.UserID == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update fields
    if req.user_name:
        user.UserName = req.user_name
    if req.job_title:
        user.job_title = req.job_title
    if req.business_unit_id:
        user.business_unit_id = req.business_unit_id

    db.commit()
    db.refresh(user)

    return {
        "user_id": user.UserID,
        "user_name": user.UserName,
        "user_email": user.UserEmail,
        "status": "updated"
    }

@router.delete("/users/{user_id}")
    dependencies=[Depends(get_current_user)]
@require_action_permission("administration", "delete")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Delete a user.

    Permission: administration.delete

    Path Parameters:
    - user_id: ID of the user to delete

    Note: Users cannot delete themselves. Deletion is permanent.
    """

    user = db.query(Users).filter(Users.UserID == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deleting the current user
    if user.UserID == current_user.UserID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")

    db.delete(user)
    db.commit()

    return {"status": "deleted"}

# ============================================================================
# BUSINESS UNITS ENDPOINTS
# ============================================================================

class BusinessUnitCreateRequest(BaseModel):
    name: str
    display_name: str
    bu_code: Optional[str] = None
    description: Optional[str] = None

@router.get("/business-units")
    dependencies=[Depends(require_resource_permission("business-unit", "view"))]
def list_business_units(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """List all business units."""
    try:
        query = db.query(BusinessUnit)

        if hasattr(current_user, 'tenant_id'):
            query = query.filter(BusinessUnit.tenant_id == current_user.tenant_id)

        total = query.count()
        bus = query.offset(skip).limit(limit).all()

        return {
            "business_units": [
                {
                    "id": b.id,
                    "name": b.name,
                    "display_name": b.display_name,
                    "bu_code": b.bu_code,
                    "description": b.description,
                    "created_at": b.created_at,
                }
                for b in bus
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"[ERROR] list_business_units failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/business-units")
    dependencies=[Depends(require_resource_permission("business-unit", "create"))]
def create_business_unit(
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create a new business unit (Admin and Super User only)."""
    # Check permissions (RBAC-aware)
    is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or \
                    (hasattr(current_user, 'roles') and any(r.name.lower() == "super user" for r in current_user.roles))

    if not is_super_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions - Super User access required")

    # Validate input
    if not req.name or not req.display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business Unit name and display name are required")

    # Determine tenant_id (default to 1 if None)
    tenant_id = current_user.tenant_id if hasattr(current_user, 'tenant_id') and current_user.tenant_id else 1

    new_bu = BusinessUnit(
        name=req.name,
        display_name=req.display_name,
        bu_code=req.bu_code or req.name.upper().replace(" ", ""),
        description=req.description,
        tenant_id=tenant_id
    )

    db.add(new_bu)
    db.commit()
    db.refresh(new_bu)

    return {
        "id": new_bu.id,
        "name": new_bu.name,
        "display_name": new_bu.display_name,
        "bu_code": new_bu.bu_code,
        "status": "created"
    }

@router.put("/business-units/{bu_id}")
    dependencies=[Depends(require_resource_permission("business-unit", "update"))]
def update_business_unit(
    bu_id: int,
    req: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update business unit (Admin and Super User only)."""
    # Check permissions (RBAC-aware)
    is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or \
                    (hasattr(current_user, 'roles') and any(r.name.lower() == "super user" for r in current_user.roles))

    if not is_super_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions - Super User access required")

    bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
    if not bu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business Unit not found")

    # Update fields
    if req.name:
        bu.name = req.name
    if req.display_name:
        bu.display_name = req.display_name
    if req.bu_code:
        bu.bu_code = req.bu_code
    if req.description is not None:
        bu.description = req.description

    db.commit()
    db.refresh(bu)

    return {
        "id": bu.id,
        "name": bu.name,
        "display_name": bu.display_name,
        "bu_code": bu.bu_code,
        "status": "updated"
    }

@router.delete("/business-units/{bu_id}")
    dependencies=[Depends(require_resource_permission("business-unit", "delete"))]
def delete_business_unit(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete business unit (Super User only)."""
    # Check permissions - Super User only (RBAC-aware)
    is_super_user = (current_user.UserRole and current_user.UserRole.lower() == "super user") or \
                    (hasattr(current_user, 'roles') and any(r.name.lower() == "super user" for r in current_user.roles))

    if not is_super_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super User access required")

    bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
    if not bu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business Unit not found")

    db.delete(bu)
    db.commit()

    return {"status": "deleted"}

# ============================================================================
# DELIVERY CENTERS ENDPOINTS (Locations)
# ============================================================================

class DeliveryCenterCreateRequest(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    center_type: Optional[str] = "Delivery"  # HQ, Delivery, etc.
    headcount: Optional[int] = 0

@router.get("/delivery-centers")
    dependencies=[Depends(require_resource_permission("delivery-center", "view"))]
def list_delivery_centers(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """List all delivery centers (locations)."""
    query = db.query(Location)

    if hasattr(current_user, 'tenant_id'):
        query = query.filter(Location.tenant_id == current_user.tenant_id)

    total = query.count()
    locations = query.offset(skip).limit(limit).all()

    return {
        "delivery_centers": [
            {
                "id": l.id,
                "name": l.name,
                "city": getattr(l, 'city', None),
                "country": getattr(l, 'country', None),
                "center_type": getattr(l, 'location_type', 'Delivery'),
                "headcount": getattr(l, 'headcount', 0),
                "created_at": getattr(l, 'created_at', None),
            }
            for l in locations
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post("/delivery-centers")
    dependencies=[Depends(require_resource_permission("delivery-center", "create"))]
def create_delivery_center(
    req: DeliveryCenterCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create a new delivery center (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

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

@router.put("/delivery-centers/{dc_id}")
    dependencies=[Depends(require_resource_permission("delivery-center", "update"))]
def update_delivery_center(
    dc_id: int,
    req: DeliveryCenterCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update delivery center (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

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

@router.delete("/delivery-centers/{dc_id}")
    dependencies=[Depends(require_resource_permission("delivery-center", "delete"))]
def delete_delivery_center(
    dc_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete delivery center (Super User only)."""
    # Check permissions - Super User only
    if not (current_user.UserRole and current_user.UserRole.lower() == "super user"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super User access required")

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
    reports_to: Optional[int] = None
    business_unit_id: Optional[int] = None
    location: Optional[str] = None

class OrgNodeUpdateRequest(BaseModel):
    employee_name: Optional[str] = None
    position_id: Optional[int] = None
    reports_to: Optional[int] = None
    business_unit_id: Optional[int] = None
    location: Optional[str] = None

@router.get("/organizational-hierarchy")
    dependencies=[Depends(require_resource_permission("organizational-hierarchy", "view"))]
def get_organizational_hierarchy(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """Get organizational hierarchy (all org nodes)."""
    query = db.query(OrgNode)

    if hasattr(current_user, 'tenant_id'):
        query = query.filter(OrgNode.tenant_id == current_user.tenant_id)

    total = query.count()
    nodes = query.offset(skip).limit(limit).all()

    return {
        "organizational_hierarchy": [
            {
                "id": n.id,
                "employee_name": n.employee_name,
                "position_id": n.position_id,
                "reports_to": n.reports_to,
                "business_unit_id": n.business_unit_id,
                "location": getattr(n, 'location', None),
                "created_at": getattr(n, 'created_at', None),
            }
            for n in nodes
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post("/organizational-hierarchy")
    dependencies=[Depends(require_resource_permission("organizational-hierarchy", "create"))]
def create_org_node(
    req: OrgNodeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create organizational hierarchy node (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    # Validate input
    if not req.employee_name or not req.position_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee name and position are required")

    new_node = OrgNode(
        employee_name=req.employee_name,
        position_id=req.position_id,
        reports_to=req.reports_to,
        business_unit_id=req.business_unit_id,
        location=req.location,
        tenant_id=current_user.tenant_id if hasattr(current_user, 'tenant_id') else 1
    )

    db.add(new_node)
    db.commit()
    db.refresh(new_node)

    return {
        "id": new_node.id,
        "employee_name": new_node.employee_name,
        "status": "created"
    }

@router.put("/organizational-hierarchy/{node_id}")
    dependencies=[Depends(require_resource_permission("organizational-hierarchy", "update"))]
def update_org_node(
    node_id: int,
    req: OrgNodeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update organizational hierarchy node (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational node not found")

    # Update fields
    if req.employee_name:
        node.employee_name = req.employee_name
    if req.position_id:
        node.position_id = req.position_id
    if req.reports_to is not None:
        node.reports_to = req.reports_to
    if req.business_unit_id:
        node.business_unit_id = req.business_unit_id
    if req.location:
        node.location = req.location

    db.commit()
    db.refresh(node)

    return {
        "id": node.id,
        "employee_name": node.employee_name,
        "status": "updated"
    }

@router.delete("/organizational-hierarchy/{node_id}")
    dependencies=[Depends(require_resource_permission("organizational-hierarchy", "delete"))]
def delete_org_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete organizational hierarchy node (Super User only)."""
    # Check permissions - Super User only
    if not (current_user.UserRole and current_user.UserRole.lower() == "super user"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super User access required")

    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizational node not found")

    db.delete(node)
    db.commit()

    return {"status": "deleted"}

# ============================================================================
# ROLE TEMPLATES ENDPOINTS
# ============================================================================

class RoleTemplateCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[list] = []

@router.get("/role-templates")
    dependencies=[Depends(require_resource_permission("role-template", "view"))]
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

@router.get("/role-templates/{template_id}")
    dependencies=[Depends(require_resource_permission("role-template", "view"))]
def get_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get a single role template with all permissions."""
    from app.models.role_template import RoleTemplatePermission, Resource

    template = db.query(RoleTemplate).filter(
        RoleTemplate.id == template_id,
        RoleTemplate.tenant_id == current_user.tenant_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Role template not found")

    # Load all permissions for this template
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
        "is_system": getattr(template, 'is_system', False),
        "is_active": getattr(template, 'is_active', True),
        "permissions": perm_list,
    }


@router.post("/role-templates")
    dependencies=[Depends(require_resource_permission("role-template", "create"))]
def create_role_template(
    req: RoleTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Create a new role template (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

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

@router.put("/role-templates/{template_id}")
    dependencies=[Depends(require_resource_permission("role-template", "update"))]
def update_role_template(
    template_id: int,
    req: RoleTemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Update role template (Admin and Super User only)."""
    # Check permissions
    if not (current_user.UserRole and current_user.UserRole.lower() in ["super user", "admin"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    template = db.query(RoleTemplate).filter(RoleTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role template not found")

    # Update fields
    if req.name:
        template.name = req.name
    if req.display_name:
        template.display_name = req.display_name
    if req.description is not None:
        template.description = req.description

    db.commit()
    db.refresh(template)

    return {
        "id": template.id,
        "name": template.name,
        "status": "updated"
    }

@router.delete("/role-templates/{template_id}")
    dependencies=[Depends(require_resource_permission("role-template", "delete"))]
def delete_role_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Delete role template (Super User only)."""
    # Check permissions - Super User only
    if not (current_user.UserRole and current_user.UserRole.lower() == "super user"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super User access required")

    template = db.query(RoleTemplate).filter(RoleTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role template not found")

    # Check if template is in use
    in_use = db.query(Users).filter(Users.role_template_id == template_id).first()
    if in_use:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete role template in use")

    db.delete(template)
    db.commit()

    return {"status": "deleted"}

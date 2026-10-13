"""
Organizational Structure API â€” Initialize and manage org hierarchy.

Endpoints for:
- Initializing org positions and approval chains for a tenant
- Creating/managing org nodes (CEO, Partners, Departments, etc.)
- Linking employees to org nodes
- Retrieving approval chains for employees
"""
import uuid
from app.services.org_hierarchy_validator import LEVEL_POSITION_CODES
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.schemas.org_structure import (
    OrgPositionResponse,
    OrgNodeResponse,
    DepartmentResponse,
)
from app.services.org_structure_service import create_org_node
from app.services.org_hierarchy_validator import (
    HIERARCHY_LEVELS,
    SPECIALIZATIONS,
    OrgHierarchyValidator,
    function_of_department_name,
)
from app.models.org_structure import OrgPosition, OrgNode, Department
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users

router = APIRouter(prefix="/org", tags=["Organization Structure"])


@router.get(
    "/positions",
    dependencies=[
        Depends(require_resource_permission("admin-settings", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=List[OrgPositionResponse],
    summary="List all org positions",
    description="Returns all organizational positions (CEO, Partner, BU Head, etc.)",
)
def list_org_positions(
    db: Session = Depends(get_db),
) -> List[OrgPositionResponse]:
    """Get all organizational positions, ordered by rank."""
    positions = db.query(OrgPosition).order_by(OrgPosition.rank).all()
    return [OrgPositionResponse.from_orm(p) for p in positions]

@router.get(
    "/valid-supervisors",
    response_model=List[OrgNodeResponse],
    summary="List valid supervisors for a new hire's hierarchy level/specialization",
    description=(
        "Wraps OrgHierarchyValidator.get_valid_supervisors() - returns the org "
        "nodes a person at the given hierarchy_level/specialization could "
        "report to, so a parent_node_id can be picked before creating them."
    ),
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def list_valid_supervisors(
    hierarchy_level: int,
    specialization: Optional[str] = None,  # accepted from older screens; function no longer limits reporting
    business_unit_id: Optional[int] = None,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[OrgNodeResponse]:
    """Get the org nodes eligible to be this hierarchy_level/specialization's parent_node_id."""
    if hierarchy_level >= 17:
        # CEO reports to nobody - nothing to pick.
        return []

    supervisors = OrgHierarchyValidator.get_valid_supervisors(
        db,
        employee_hierarchy_level=hierarchy_level,
        employee_specialization=specialization,
        business_unit_id=str(business_unit_id) if business_unit_id else None,
        tenant_id=current_user.tenant_id,
    )
    return [OrgNodeResponse.from_orm(s) for s in supervisors]

@router.get(
    "/hierarchy-reference",
    summary="Hierarchy levels and specializations accepted by the org validator",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def get_hierarchy_reference(current_user = Depends(get_current_internal_user)):
    return {
        # position_code: the org position (job title) a seat at this level holds
        "levels": [{"level": level, "name": name, "position_code": LEVEL_POSITION_CODES.get(level)}
                   for level, name in sorted(HIERARCHY_LEVELS.items(), reverse=True)],
        "specializations": SPECIALIZATIONS,
    }

@router.get(
    "/nodes",
    response_model=List[OrgNodeResponse],
    summary="List org nodes for a tenant",
    description="Returns all organizational nodes (instances of positions)",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def list_org_nodes(
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[OrgNodeResponse]:
    """Get all organizational nodes for the current tenant."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    # Join with Tenant to include tenant name
    nodes = db.query(OrgNode).filter(OrgNode.tenant_id == tenant_id).all()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    result = []
    company_names = _company_names(db, tenant_id)
    for node in nodes:
        node_dict = OrgNodeResponse.from_orm(node).dict()
        node_dict['tenant_name'] = tenant.name if tenant else f"Tenant {tenant_id}"
        node_dict['company_name'] = company_names.get(node.company_id)
        result.append(OrgNodeResponse(**node_dict))

    return result

@router.get(
    "/nodes/{org_node_id}",
    response_model=OrgNodeResponse,
    summary="Get a specific org node",
    description="Returns details of a specific organizational node",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def get_org_node(
    org_node_id: str,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> OrgNodeResponse:
    """Get a specific organizational node by ID."""

    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    node = db.query(OrgNode).filter(OrgNode.id == org_node_id, OrgNode.tenant_id == tenant_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org node not found")

    # Include tenant name
    node_dict = OrgNodeResponse.from_orm(node).dict()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    node_dict['tenant_name'] = tenant.name if tenant else f"Tenant {tenant_id}"

    return OrgNodeResponse(**node_dict)


@router.get(
    "/departments",
    response_model=List[DepartmentResponse],
    summary="List departments for a tenant",
    description="Returns all departments organized by business unit",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def list_departments(
    business_unit_id: Optional[int] = None,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[DepartmentResponse]:
    """Get all departments for the current tenant, optionally for one business unit."""

    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    query = db.query(Department).filter(Department.tenant_id == tenant_id)
    if business_unit_id is not None:
        query = query.filter(Department.business_unit_id == business_unit_id)
    departments = query.order_by(Department.name).all()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_name = tenant.name if tenant else f"Tenant {tenant_id}"

    result = []
    for dept in departments:
        dept_dict = DepartmentResponse.from_orm(dept).dict()
        dept_dict['tenant_name'] = tenant_name
        dept_dict['business_unit_name'] = dept.business_unit.name if dept.business_unit else None
        dept_dict['function'] = function_of_department_name(dept.name)
        result.append(DepartmentResponse(**dept_dict))

    return result


class CreateOrgNodeRequest(BaseModel):
    name: str
    hierarchy_level: int
    specialization: Optional[str] = None  # derived from the department; kept for older clients
    parent_id: Optional[str] = None
    department_id: Optional[str] = None
    company_id: Optional[str] = None


class UpdateOrgNodeRequest(BaseModel):
    name: Optional[str] = None
    company_id: Optional[str] = None  # "" clears


def _company_names(db: Session, tenant_id: int) -> dict:
    from app.models.location import Location
    return {l.id: l.name for l in db.query(Location).filter(Location.tenant_id == tenant_id)}

@router.post(
    "/nodes",
    response_model=OrgNodeResponse,
    summary="Create an organizational node",
    description="Create a seat in the org chart. Position is derived from hierarchy_level; placement is validated against the reporting rules.",
    dependencies=[Depends(require_resource_permission("admin-settings", "create"))],
)
def create_org_node_endpoint(
    request: CreateOrgNodeRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> OrgNodeResponse:
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    try:
        node = create_org_node(
            db,
            tenant_id=tenant_id,
            name=request.name,
            hierarchy_level=request.hierarchy_level,
            specialization=request.specialization,
            parent_id=request.parent_id,
            department_id=request.department_id,
            company_id=request.company_id,
        )
        db.commit()
        db.refresh(node)
        data = OrgNodeResponse.from_orm(node).dict()
        data["company_name"] = _company_names(db, tenant_id).get(node.company_id)
        return OrgNodeResponse(**data)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"[OrgNode] Tenant {tenant_id}: Failed to create node: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create org node")

@router.patch(
    "/nodes/{org_node_id}",
    response_model=OrgNodeResponse,
    summary="Rename an org node or change its company",
    dependencies=[Depends(require_resource_permission("admin-settings", "edit"))],
)
def update_org_node_endpoint(
    org_node_id: str,
    request: UpdateOrgNodeRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> OrgNodeResponse:
    from app.services.org_structure_service import update_org_node

    tenant_id = current_user.tenant_id
    try:
        node = update_org_node(db, tenant_id, org_node_id, name=request.name, company_id=request.company_id)
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    db.commit()
    db.refresh(node)
    data = OrgNodeResponse.from_orm(node).dict()
    data["company_name"] = _company_names(db, tenant_id).get(node.company_id)
    return OrgNodeResponse(**data)

@router.delete(
    "/nodes/{org_node_id}",
    summary="Delete an org node",
    description="Only a node with no reports and no people assigned to it can be deleted.",
    dependencies=[Depends(require_resource_permission("admin-settings", "delete"))],
)
def delete_org_node_endpoint(
    org_node_id: str,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id
    node = db.query(OrgNode).filter(OrgNode.id == org_node_id, OrgNode.tenant_id == tenant_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org node not found")

    # Direct reports, people seated here, partner/BU assignments, department hiring manager ...
    from app.core.references import ensure_deletable

    ensure_deletable(db, node, f"Seat '{node.name}'")
    db.delete(node)
    db.commit()
    return {"status": "deleted", "id": org_node_id}

class DepartmentRequest(BaseModel):
    name: str
    # Departments are org-wide routing groups; a BU only for a BU-specific team
    business_unit_id: Optional[int] = None
    description: Optional[str] = None
    cost_center_code: Optional[str] = None

def _department_response(dept: Department, tenant_id: int, db: Session) -> DepartmentResponse:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    data = DepartmentResponse.from_orm(dept).dict()
    data["tenant_name"] = tenant.name if tenant else None
    data["business_unit_name"] = dept.business_unit.name if dept.business_unit else None
    return DepartmentResponse(**data)

def _tenant_business_unit(db: Session, business_unit_id: int, tenant_id: int) -> BusinessUnit:
    bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id, BusinessUnit.tenant_id == tenant_id).first()
    if not bu:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Business unit not found")
    return bu

@router.post(
    "/departments",
    response_model=DepartmentResponse,
    summary="Create a department (org-wide, or within one business unit)",
    dependencies=[Depends(require_resource_permission("admin-settings", "create"))],
)
def create_department_endpoint(
    request: DepartmentRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    tenant_id = current_user.tenant_id
    if not request.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department name is required")
    if request.business_unit_id is not None:
        _tenant_business_unit(db, request.business_unit_id, tenant_id)

    duplicate = db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.business_unit_id == request.business_unit_id,
        Department.name == request.name.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A department with this name already exists")

    dept = Department(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        business_unit_id=request.business_unit_id,
        name=request.name.strip(),
        description=request.description,
        cost_center_code=request.cost_center_code,
        active=True,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return _department_response(dept, tenant_id, db)

@router.put(
    "/departments/{department_id}",
    response_model=DepartmentResponse,
    summary="Update a department",
    dependencies=[Depends(require_resource_permission("admin-settings", "edit"))],
)
def update_department_endpoint(
    department_id: str,
    request: DepartmentRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    tenant_id = current_user.tenant_id
    dept = db.query(Department).filter(Department.id == department_id, Department.tenant_id == tenant_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    if not request.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department name is required")

    if request.business_unit_id != dept.business_unit_id:
        # Moving a department would silently move every node/user in it to another BU.
        in_use = (
            db.query(OrgNode).filter(OrgNode.department_id == department_id).count()
            or db.query(Users).filter(Users.department_id == department_id).count()
        )
        if in_use:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department has people or org nodes - it can't be moved to another business unit")
        if request.business_unit_id is not None:
            _tenant_business_unit(db, request.business_unit_id, tenant_id)
        dept.business_unit_id = request.business_unit_id

    dept.name = request.name.strip()
    dept.description = request.description
    dept.cost_center_code = request.cost_center_code
    db.commit()
    db.refresh(dept)
    return _department_response(dept, tenant_id, db)

@router.delete(
    "/departments/{department_id}",
    summary="Delete an unused department",
    dependencies=[Depends(require_resource_permission("admin-settings", "delete"))],
)
def delete_department_endpoint(
    department_id: str,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
):
    tenant_id = current_user.tenant_id
    dept = db.query(Department).filter(Department.id == department_id, Department.tenant_id == tenant_id).first()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    from app.core.references import ensure_deletable

    ensure_deletable(db, dept, f"Department '{dept.name}'")  # seats, users, tasks routed to it ...
    db.delete(dept)
    db.commit()
    return {"status": "deleted", "id": department_id}


# ── Roles (job titles and their org level), managed next to departments ─────────────────
# The 17-level scale, the level -> position mapping and the reporting rules stay in code
# (org_hierarchy_validator); the roles a firm uses are data. Guardrails: a held role can't
# be retired or re-levelled, CEO is level 17 and unique, CFO is level 16, and the CEO role
# and the last level-17 role can't be retired.

class OrgRoleRequest(BaseModel):
    name: str
    hierarchy_level: int
    designation: Optional[str] = None
    description: Optional[str] = None


class OrgRoleUpdateRequest(BaseModel):
    name: Optional[str] = None
    hierarchy_level: Optional[int] = None
    designation: Optional[str] = None  # "" clears
    description: Optional[str] = None
    active: Optional[bool] = None


def _role_dict(db: Session, role) -> dict:
    from app.services.org_hierarchy_validator import HIERARCHY_LEVELS
    from app.services.org_roles_service import holders_count

    return {"id": role.id, "name": role.name, "hierarchy_level": role.hierarchy_level,
            "level_name": HIERARCHY_LEVELS.get(role.hierarchy_level), "designation": role.designation,
            "description": role.description, "active": role.active, "users": holders_count(db, role),
            # the role's permission set, edited in the Role Templates editor
            "role_template_id": role.role_template_id}


def _audit_role(action: str, role, user) -> None:
    logger.info(f"[AUDIT] org_role {action}: id={role.id} name={role.name!r} level={role.hierarchy_level} "
                f"designation={role.designation} active={role.active} by={user.UserID} tenant={role.tenant_id}")


# Reading the list is part of editing users (the Job Title picker); changing it is org-roles
@router.get("/roles", summary="Roles (job titles) and their org level",
            dependencies=[Depends(require_resource_permission("users-access-control", "view"))])
def list_org_roles(include_inactive: bool = False, current_user=Depends(get_current_internal_user),
                   db: Session = Depends(get_db)) -> List[dict]:
    from app.models.org_structure import OrgRole

    query = db.query(OrgRole).filter(OrgRole.tenant_id == current_user.tenant_id)
    if not include_inactive:
        query = query.filter(OrgRole.active.is_(True))
    return [_role_dict(db, r) for r in query.order_by(OrgRole.hierarchy_level.desc(), OrgRole.name)]


@router.post("/roles", status_code=201, summary="Add a role",
             dependencies=[Depends(require_resource_permission("org-roles", "create"))])
def create_org_role(request: OrgRoleRequest, current_user=Depends(get_current_internal_user),
                    db: Session = Depends(get_db)) -> dict:
    from app.models.org_structure import OrgRole
    from app.services.org_roles_service import ensure_permission_set, validate_role

    designation = request.designation or None
    try:
        name = validate_role(db, current_user.tenant_id, request.name, request.hierarchy_level,
                             designation=designation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    role = OrgRole(tenant_id=current_user.tenant_id, name=name, hierarchy_level=request.hierarchy_level,
                   designation=designation, description=request.description)
    db.add(role)
    db.flush()
    ensure_permission_set(db, role)
    db.commit()
    db.refresh(role)
    _audit_role("created", role, current_user)
    return _role_dict(db, role)


@router.put("/roles/{role_id}", summary="Rename, re-level, designate, describe or retire a role",
            dependencies=[Depends(require_resource_permission("org-roles", "edit"))])
def update_org_role(role_id: int, request: OrgRoleUpdateRequest, current_user=Depends(get_current_internal_user),
                    db: Session = Depends(get_db)) -> dict:
    """A rename carries the people holding the role with it. A held role can't change level
    or be retired: reassign its people first."""
    from app.models.org_structure import OrgRole
    from app.models.user import Users
    from app.services.org_roles_service import ensure_permission_set, holders_count, validate_role
    from app.services.role_template_permission_service import invalidate_permissions

    role = db.query(OrgRole).filter(OrgRole.id == role_id, OrgRole.tenant_id == current_user.tenant_id).first()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    held = holders_count(db, role)
    level = request.hierarchy_level if request.hierarchy_level is not None else role.hierarchy_level
    designation = (request.designation or None) if request.designation is not None else role.designation
    if level != role.hierarchy_level and held:
        raise HTTPException(status_code=409, detail=f"{held} people hold this role - give them another role first, then change its level")
    if request.active is False and role.active:
        if held:
            raise HTTPException(status_code=409, detail=f"{held} people hold this role - give them another role first, then retire it")
        if designation == "ceo":
            raise HTTPException(status_code=409, detail="The CEO role can't be retired")
        if role.hierarchy_level == 17 and not db.query(OrgRole).filter(
                OrgRole.tenant_id == role.tenant_id, OrgRole.hierarchy_level == 17,
                OrgRole.active.is_(True), OrgRole.id != role.id).first():
            raise HTTPException(status_code=409, detail="The last level-17 role can't be retired")
    try:
        name = validate_role(db, role.tenant_id, request.name if request.name is not None else role.name, level,
                             role.id, designation=designation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if name != role.name:
        # exact (case/space-insensitive) match: ilike would treat % and _ in a name as wildcards
        db.query(Users).filter(Users.tenant_id == role.tenant_id,
                               func.lower(func.trim(Users.job_title)) == role.name.strip().lower()) \
            .update({Users.job_title: name}, synchronize_session=False)
    role.name, role.hierarchy_level, role.designation = name, level, designation
    if request.description is not None:
        role.description = request.description or None
    if request.active is not None:
        role.active = request.active
    ensure_permission_set(db, role)  # template name/level follow the role
    db.commit()
    invalidate_permissions()
    db.refresh(role)
    _audit_role("updated", role, current_user)
    return _role_dict(db, role)

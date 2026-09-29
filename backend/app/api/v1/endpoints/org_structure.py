"""
import logging
Organizational Structure API â€” Initialize and manage org hierarchy.

Endpoints for:
- Initializing org positions and approval chains for a tenant
- Creating/managing org nodes (CEO, Partners, Departments, etc.)
- Linking employees to org nodes
- Retrieving approval chains for employees
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.schemas.org_structure import (
    OrgPositionResponse,
    OrgNodeResponse,
    DepartmentResponse,
    ApprovalChainResponse,
    OrgInitializeRequest,
    OrgInitializeResponse,
)
from app.services.org_structure_service import (
    init_default_positions,
    get_position_by_rank,
    get_position_by_name,
    create_root_ceo_node,
    create_partner_node,
    create_bu_head_node,
    create_department,
    create_org_node,
    assign_partner_to_bu,
    setup_approval_chains,
    get_employee_approvers,
)
from app.services.org_hierarchy_validator import (
    HIERARCHY_LEVELS,
    SPECIALIZATIONS,
    OrgHierarchyValidator,
)
from app.models.org_structure import OrgPosition, OrgNode, Department, ApprovalChain
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users

router = APIRouter(prefix="/org", tags=["Organization Structure"])

@router.post(
    "/initialize",
    response_model=OrgInitializeResponse,
    summary="Initialize org hierarchy for a tenant",
    description="Creates default org positions and approval chains for a new tenant",
    dependencies=[Depends(require_resource_permission("admin-settings", "create"))],
)
def initialize_org_structure(
    request: OrgInitializeRequest,
    db: Session = Depends(get_db),
) -> OrgInitializeResponse:
    """
    Initialize organizational hierarchy for a tenant.
    Creates: org positions (10 levels), root CEO node, approval chains.

    **Permission required:** ADMIN or SUPER_USER
    """
    tenant_id = request.tenant_id if hasattr(request, 'tenant_id') else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant_id provided")

    try:
        # Step 1: Initialize default positions
        pos_result = init_default_positions(db)
        logger.info(f"[OrgInit] Tenant {tenant_id}: Created {pos_result['created']} positions, updated {pos_result['updated']}")

        # Step 2: Create root CEO node
        ceo_node = create_root_ceo_node(db, tenant_id, name=request.ceo_name or "CEO")
        logger.info(f"[OrgInit] Tenant {tenant_id}: Created CEO node {ceo_node.id}")

        # Step 3: Set up approval chains
        chain_result = setup_approval_chains(db, tenant_id)
        logger.info(f"[OrgInit] Tenant {tenant_id}: Created {chain_result['approval_chains_created']} approval chains")

        return OrgInitializeResponse(
            success=True,
            message="Organizational hierarchy initialized successfully",
            tenant_id=tenant_id,
            ceo_node_id=ceo_node.id,
            positions_created=pos_result["created"],
            positions_updated=pos_result["updated"],
            approval_chains_created=chain_result["approval_chains_created"],
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[OrgInit] Tenant {tenant_id}: Failed to initialize: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize org structure: {str(e)}"
        )

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
    specialization: str,
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
        "levels": [{"level": level, "name": name} for level, name in sorted(HIERARCHY_LEVELS.items(), reverse=True)],
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
    for node in nodes:
        node_dict = OrgNodeResponse.from_orm(node).dict()
        node_dict['tenant_name'] = tenant.name if tenant else f"Tenant {tenant_id}"
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
    "/nodes/{org_node_id}/approvers",
    response_model=List[OrgNodeResponse],
    summary="Get approval chain for an org node",
    description="Returns the chain of approvers up to CEO for a given org node",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def get_approvers_for_node(
    org_node_id: str,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[OrgNodeResponse]:
    """Get the approval chain (all approvers up to CEO) for a given org node."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    approvers_list = get_employee_approvers(db, org_node_id)
    nodes = []
    for approver_info in approvers_list:
        node = db.query(OrgNode).filter(OrgNode.id == approver_info["org_node_id"], OrgNode.tenant_id == tenant_id).first()
        if node:
            nodes.append(OrgNodeResponse.from_orm(node))
    return nodes

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
        dept_dict['business_unit_name'] = dept.business_unit.name if dept.business_unit else f"BU {dept.business_unit_id}"
        result.append(DepartmentResponse(**dept_dict))

    return result

@router.get(
    "/approval-chains",
    response_model=List[ApprovalChainResponse],
    summary="List approval chain workflows",
    description="Returns all approval workflows for the tenant",
    dependencies=[Depends(require_resource_permission("admin-settings", "view"))],
)
def list_approval_chains(
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[ApprovalChainResponse]:
    """Get all approval chain configurations for the current tenant."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    chains = db.query(ApprovalChain).filter(
        ApprovalChain.tenant_id == tenant_id,
        ApprovalChain.active == True
    ).all()
    return [ApprovalChainResponse.from_orm(c) for c in chains]

class CreateOrgNodeRequest(BaseModel):
    name: str
    hierarchy_level: int
    specialization: str
    parent_id: Optional[str] = None
    department_id: Optional[str] = None

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
        )
        db.commit()
        db.refresh(node)
        return OrgNodeResponse.from_orm(node)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"[OrgNode] Tenant {tenant_id}: Failed to create node: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create org node")

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
    from app.models.employee import Employee

    tenant_id = current_user.tenant_id
    node = db.query(OrgNode).filter(OrgNode.id == org_node_id, OrgNode.tenant_id == tenant_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org node not found")

    if db.query(OrgNode).filter(OrgNode.parent_id == org_node_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reassign this node's direct reports before deleting it")
    if db.query(Users).filter(Users.org_node_id == org_node_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user is placed on this node - reassign them before deleting it")
    if db.query(Employee).filter(Employee.org_node_id == org_node_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An employee is placed on this node - reassign them before deleting it")
    if db.query(Department).filter(Department.hiring_manager_id == org_node_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This node is a department's hiring manager - change that first")

    db.delete(node)
    db.commit()
    return {"status": "deleted", "id": org_node_id}

class DepartmentRequest(BaseModel):
    name: str
    business_unit_id: int
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
    summary="Create a department within a business unit",
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
    _tenant_business_unit(db, request.business_unit_id, tenant_id)

    duplicate = db.query(Department).filter(
        Department.tenant_id == tenant_id,
        Department.business_unit_id == request.business_unit_id,
        Department.name == request.name.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A department with this name already exists in that business unit")

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
    if db.query(OrgNode).filter(OrgNode.department_id == department_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Org nodes belong to this department - move them first")
    if db.query(Users).filter(Users.department_id == department_id).count():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Users belong to this department - move them first")

    db.delete(dept)
    db.commit()
    return {"status": "deleted", "id": department_id}

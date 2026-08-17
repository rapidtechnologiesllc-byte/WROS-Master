"""
Organizational Structure API — Initialize and manage org hierarchy.

Endpoints for:
- Initializing org positions and approval chains for a tenant
- Creating/managing org nodes (CEO, Partners, Departments, etc.)
- Linking employees to org nodes
- Retrieving approval chains for employees
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import require_permission, get_current_internal_user
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
from app.models.org_structure import OrgPosition, OrgNode, Department, ApprovalChain
from app.models.business_unit import BusinessUnit


router = APIRouter(prefix="/org", tags=["Organization Structure"])


@router.post(
    "/initialize",
    response_model=OrgInitializeResponse,
    summary="Initialize org hierarchy for a tenant",
    description="Creates default org positions and approval chains for a new tenant",
    dependencies=[Depends(require_permission("admin.create"))],
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
        logger.error(f"[OrgInit] Tenant {tenant_id}: Failed to initialize: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize org structure: {str(e)}"
        )


@router.get(
    "/positions",
    response_model=List[OrgPositionResponse],
    summary="List all org positions",
    description="Returns all organizational positions (CEO, Partner, BU Head, etc.)",
    dependencies=[Depends(require_permission("admin.view"))],
)
def list_org_positions(
    db: Session = Depends(get_db),
) -> List[OrgPositionResponse]:
    """Get all organizational positions, ordered by rank."""
    positions = db.query(OrgPosition).order_by(OrgPosition.rank).all()
    return [OrgPositionResponse.from_orm(p) for p in positions]


@router.get(
    "/nodes",
    response_model=List[OrgNodeResponse],
    summary="List org nodes for a tenant",
    description="Returns all organizational nodes (instances of positions)",
    dependencies=[Depends(require_permission("admin.view"))],
)
def list_org_nodes(
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[OrgNodeResponse]:
    """Get all organizational nodes for the current tenant."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    nodes = db.query(OrgNode).filter(OrgNode.tenant_id == tenant_id).all()
    return [OrgNodeResponse.from_orm(n) for n in nodes]


@router.get(
    "/nodes/{org_node_id}",
    response_model=OrgNodeResponse,
    summary="Get a specific org node",
    description="Returns details of a specific organizational node",
    dependencies=[Depends(require_permission("admin.view"))],
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
    return OrgNodeResponse.from_orm(node)


@router.get(
    "/nodes/{org_node_id}/approvers",
    response_model=List[OrgNodeResponse],
    summary="Get approval chain for an org node",
    description="Returns the chain of approvers up to CEO for a given org node",
    dependencies=[Depends(require_permission("admin.view"))],
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
    dependencies=[Depends(require_permission("admin.view"))],
)
def list_departments(
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> List[DepartmentResponse]:
    """Get all departments for the current tenant."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    departments = db.query(Department).filter(Department.tenant_id == tenant_id).all()
    return [DepartmentResponse.from_orm(d) for d in departments]


@router.get(
    "/approval-chains",
    response_model=List[ApprovalChainResponse],
    summary="List approval chain workflows",
    description="Returns all approval workflows for the tenant",
    dependencies=[Depends(require_permission("admin.view"))],
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
    employee_name: str
    position_id: int
    reports_to_id: Optional[str] = None
    business_unit_id: Optional[int] = None
    location: Optional[str] = None


@router.post(
    "/nodes",
    response_model=OrgNodeResponse,
    summary="Create an organizational node",
    description="Create a new organizational node (position instance)",
    dependencies=[Depends(require_permission("admin.create"))],
)
def create_org_node_endpoint(
    request: CreateOrgNodeRequest,
    current_user = Depends(get_current_internal_user),
    db: Session = Depends(get_db),
) -> OrgNodeResponse:
    """Create a new organizational node for the current tenant."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to a tenant")

    try:
        node = create_org_node(
            db=db,
            tenant_id=tenant_id,
            employee_name=request.employee_name,
            position_id=request.position_id,
            reports_to_id=request.reports_to_id,
            business_unit_id=request.business_unit_id,
            location=request.location,
        )
        db.commit()
        return OrgNodeResponse.from_orm(node)
    except Exception as e:
        db.rollback()
        logger.error(f"[OrgNode] Tenant {tenant_id}: Failed to create node: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create org node: {str(e)}"
        )

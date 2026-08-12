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
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
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
from app.models.rbac import BusinessUnit


router = APIRouter(prefix="/org", tags=["Organization Structure"])


@router.post(
    "/initialize",
    response_model=OrgInitializeResponse,
    summary="Initialize org hierarchy for a tenant",
    description="Creates default org positions and approval chains for a new tenant",
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
    description="Returns all organizational positions (CEO, Partner, BU Head, etc.)"
)
def list_org_positions(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> List[OrgPositionResponse]:
    """Get all organizational positions, ordered by rank."""
    positions = db.query(OrgPosition).order_by(OrgPosition.rank).all()
    return [OrgPositionResponse.from_orm(p) for p in positions]


@router.get(
    "/nodes",
    response_model=List[OrgNodeResponse],
    summary="List org nodes for a tenant",
    description="Returns all organizational nodes (instances of positions)"
)
def list_org_nodes(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> List[OrgNodeResponse]:
    """Get all organizational nodes for the current tenant."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No tenant context")

    nodes = db.query(OrgNode).filter(OrgNode.tenant_id == tenant_id).all()
    return [OrgNodeResponse.from_orm(n) for n in nodes]


@router.get(
    "/nodes/{org_node_id}",
    response_model=OrgNodeResponse,
    summary="Get a specific org node",
    description="Returns details of a specific organizational node"
)
def get_org_node(
    org_node_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> OrgNodeResponse:
    """Get a specific organizational node by ID."""
    node = db.query(OrgNode).filter(OrgNode.id == org_node_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org node not found")
    return OrgNodeResponse.from_orm(node)


@router.get(
    "/nodes/{org_node_id}/approvers",
    response_model=List[OrgNodeResponse],
    summary="Get approval chain for an org node",
    description="Returns the chain of approvers up to CEO for a given org node"
)
def get_approvers_for_node(
    org_node_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> List[OrgNodeResponse]:
    """Get the approval chain (all approvers up to CEO) for a given org node."""
    approvers_list = get_employee_approvers(db, org_node_id)
    nodes = []
    for approver_info in approvers_list:
        node = db.query(OrgNode).filter(OrgNode.id == approver_info["org_node_id"]).first()
        if node:
            nodes.append(OrgNodeResponse.from_orm(node))
    return nodes


@router.get(
    "/departments",
    response_model=List[DepartmentResponse],
    summary="List departments for a tenant",
    description="Returns all departments organized by business unit"
)
def list_departments(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> List[DepartmentResponse]:
    """Get all departments for the current tenant."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No tenant context")

    departments = db.query(Department).filter(Department.tenant_id == tenant_id).all()
    return [DepartmentResponse.from_orm(d) for d in departments]


@router.get(
    "/approval-chains",
    response_model=List[ApprovalChainResponse],
    summary="List approval chain workflows",
    description="Returns all approval workflows for the tenant"
)
def list_approval_chains(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_or_none),
) -> List[ApprovalChainResponse]:
    """Get all approval chain configurations for the current tenant."""
    tenant_id = current_user.get("tenant_id") if current_user else None
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No tenant context")

    chains = db.query(ApprovalChain).filter(
        ApprovalChain.tenant_id == tenant_id,
        ApprovalChain.active == True
    ).all()
    return [ApprovalChainResponse.from_orm(c) for c in chains]

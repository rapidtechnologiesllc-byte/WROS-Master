"""
Organizational Structure Service — initialize and manage org hierarchy.

Responsibilities:
- Create/populate default OrgPositions (the 10 named titles)
- Create/manage OrgNodes (instances of positions in the tree)
- Link employees to org nodes for approval chains and role-based access
- Manage approval chain workflows based on position hierarchy
"""
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.org_structure import OrgPosition, OrgNode, Department, ApprovalChain, PartnerBUAssignment
from app.models.business_units import BusinessUnit


# The 10 organizational positions (CEO down to Senior Consultant)
DEFAULT_POSITIONS = [
    {
        "rank": 0,
        "name": "CEO",
        "description": "Chief Executive Officer — runs entire organization",
        "approves_to_rank": None,  # CEO is top, nobody above
        "approves_workflows": "TIMESHEET,OFFER_LETTER,BUDGET_APPROVAL,PO_APPROVAL",
        "rbac_role_name": "ceo"
    },
    {
        "rank": 1,
        "name": "Partner",
        "description": "Partner — responsible for one or more business units",
        "approves_to_rank": 0,  # Approves to CEO
        "approves_workflows": "TIMESHEET,OFFER_LETTER,BUDGET_APPROVAL,PO_APPROVAL",
        "rbac_role_name": "partner"
    },
    {
        "rank": 2,
        "name": "BU Head",
        "description": "Business Unit Head — runs a business unit",
        "approves_to_rank": 1,  # Approves to Partner
        "approves_workflows": "TIMESHEET,OFFER_LETTER,BUDGET_APPROVAL,PO_APPROVAL",
        "rbac_role_name": "bu_head"
    },
    {
        "rank": 3,
        "name": "Senior Director",
        "description": "Senior Director — leads major initiatives within BU",
        "approves_to_rank": 2,  # Approves to BU Head
        "approves_workflows": "TIMESHEET,OFFER_LETTER,BUDGET_APPROVAL,PO_APPROVAL",
        "rbac_role_name": "senior_director"
    },
    {
        "rank": 4,
        "name": "Director",
        "description": "Director — leads teams, approves hires and timesheets",
        "approves_to_rank": 3,  # Approves to Senior Director
        "approves_workflows": "TIMESHEET,OFFER_LETTER,PO_APPROVAL",
        "rbac_role_name": "director"
    },
    {
        "rank": 5,
        "name": "Technical Manager",
        "description": "Technical Manager — manages technical resources and projects",
        "approves_to_rank": 4,  # Approves to Director
        "approves_workflows": "TIMESHEET,PO_APPROVAL",
        "rbac_role_name": "technical_manager"
    },
    {
        "rank": 6,
        "name": "Senior Manager",
        "description": "Senior Manager — senior individual contributor role",
        "approves_to_rank": 4,  # Approves to Director (not Technical Manager)
        "approves_workflows": "TIMESHEET",
        "rbac_role_name": "senior_manager"
    },
    {
        "rank": 7,
        "name": "Manager",
        "description": "Manager — manages team members and client relationships",
        "approves_to_rank": 4,  # Approves to Director (can also be under Technical/Senior Manager)
        "approves_workflows": None,  # Managers don't approve workflows
        "rbac_role_name": "manager"
    },
    {
        "rank": 8,
        "name": "Team Lead",
        "description": "Team Lead — leads small teams or projects",
        "approves_to_rank": 7,  # Approves to Manager
        "approves_workflows": None,
        "rbac_role_name": "team_lead"
    },
    {
        "rank": 9,
        "name": "Senior Consultant",
        "description": "Senior Consultant — senior individual contributor",
        "approves_to_rank": 7,  # Approves to Manager (or Team Lead)
        "approves_workflows": None,
        "rbac_role_name": "senior_consultant"
    },
]


def init_default_positions(db: Session) -> dict:
    """
    Initialize or update the default organizational positions in the database.
    Returns dict with created/updated counts.
    """
    created = 0
    updated = 0

    for pos_data in DEFAULT_POSITIONS:
        existing = db.query(OrgPosition).filter(
            OrgPosition.name == pos_data["name"]
        ).first()

        if existing:
            # Update existing position
            for key, value in pos_data.items():
                setattr(existing, key, value)
            db.add(existing)
            updated += 1
        else:
            # Create new position
            position = OrgPosition(**pos_data)
            db.add(position)
            created += 1

    db.commit()
    return {"created": created, "updated": updated}


def get_position_by_rank(db: Session, rank: int) -> Optional[OrgPosition]:
    """Fetch a position by its rank (0=CEO, 1=Partner, etc.)"""
    return db.query(OrgPosition).filter(OrgPosition.rank == rank).first()


def get_position_by_name(db: Session, name: str) -> Optional[OrgPosition]:
    """Fetch a position by its name"""
    return db.query(OrgPosition).filter(OrgPosition.name == name).first()


def create_root_ceo_node(db: Session, tenant_id: int, name: str = "CEO") -> OrgNode:
    """
    Create the root CEO node for a tenant (if it doesn't already exist).
    The CEO node is corporate-level (no department).
    """
    existing = db.query(OrgNode).filter(
        OrgNode.tenant_id == tenant_id,
        OrgNode.position_id == get_position_by_rank(db, 0).id
    ).first()
    if existing:
        return existing

    ceo_position = get_position_by_rank(db, 0)
    if not ceo_position:
        raise ValueError("CEO position not found; call init_default_positions() first")

    ceo_node = OrgNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        position_id=ceo_position.id,
        name=name,
        parent_id=None,  # CEO has no parent
        department_id=None,  # CEO is corporate-level
        active=True
    )
    db.add(ceo_node)
    db.commit()
    return ceo_node


def create_partner_node(
    db: Session,
    tenant_id: int,
    name: str,
    parent_id: Optional[str] = None
) -> OrgNode:
    """
    Create a Partner node (rank 1) at corporate level.
    Typically has CEO as parent.
    """
    partner_position = get_position_by_rank(db, 1)
    if not partner_position:
        raise ValueError("Partner position not found; call init_default_positions() first")

    # If no parent provided, use the root CEO
    if not parent_id:
        ceo = db.query(OrgNode).filter(
            OrgNode.tenant_id == tenant_id,
            OrgNode.position_id == get_position_by_rank(db, 0).id
        ).first()
        parent_id = ceo.id if ceo else None

    partner_node = OrgNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        position_id=partner_position.id,
        name=name,
        parent_id=parent_id,
        department_id=None,  # Partner is corporate-level
        active=True
    )
    db.add(partner_node)
    db.commit()
    return partner_node


def create_bu_head_node(
    db: Session,
    tenant_id: int,
    name: str,
    parent_id: str  # typically a Partner node
) -> OrgNode:
    """
    Create a BU Head node (rank 2) within a department.
    Must have a Partner or higher as parent.
    """
    bu_head_position = get_position_by_rank(db, 2)
    if not bu_head_position:
        raise ValueError("BU Head position not found; call init_default_positions() first")

    bu_head_node = OrgNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        position_id=bu_head_position.id,
        name=name,
        parent_id=parent_id,
        department_id=None,  # BU Head can be corporate-level or dept-level
        active=True
    )
    db.add(bu_head_node)
    db.commit()
    return bu_head_node


def create_department(
    db: Session,
    tenant_id: int,
    business_unit_id: str,
    name: str,
    description: str = None,
    hiring_manager_id: Optional[str] = None,
    cost_center_code: Optional[str] = None
) -> Department:
    """
    Create a department under a business unit.
    """
    department = Department(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        business_unit_id=business_unit_id,
        name=name,
        description=description,
        hiring_manager_id=hiring_manager_id,
        cost_center_code=cost_center_code,
        active=True
    )
    db.add(department)
    db.commit()
    return department


def create_org_node(
    db: Session,
    tenant_id: int,
    position_name: str,  # e.g., "Manager", "Team Lead"
    node_name: str,  # e.g., "John Smith", "East Coast Team"
    parent_id: str,
    department_id: Optional[str] = None
) -> OrgNode:
    """
    Create an org node for a specific position.
    """
    position = get_position_by_name(db, position_name)
    if not position:
        raise ValueError(f"Position '{position_name}' not found")

    node = OrgNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        position_id=position.id,
        name=node_name,
        parent_id=parent_id,
        department_id=department_id,
        active=True
    )
    db.add(node)
    db.commit()
    return node


def assign_partner_to_bu(
    db: Session,
    tenant_id: int,
    partner_org_node_id: str,
    business_unit_id: str
) -> PartnerBUAssignment:
    """
    Link a Partner OrgNode to a Business Unit they oversee.
    """
    assignment = PartnerBUAssignment(
        tenant_id=tenant_id,
        partner_org_node_id=partner_org_node_id,
        business_unit_id=business_unit_id,
        active=True
    )
    db.add(assignment)
    db.commit()
    return assignment


def setup_approval_chains(db: Session, tenant_id: int) -> dict:
    """
    Create standard approval chain workflows:
    - Manager → Director (for TIMESHEET, OFFER_LETTER, PO_APPROVAL)
    - Director → Senior Director (for TIMESHEET, OFFER_LETTER, PO_APPROVAL)
    - Senior Director → Partner (for TIMESHEET, OFFER_LETTER, PO_APPROVAL)
    - Partner → CEO (for BUDGET_APPROVAL)
    - etc.
    """
    chains_created = 0

    workflows = ["TIMESHEET", "OFFER_LETTER", "PO_APPROVAL"]

    # Define approval routing: (from_rank, to_rank, workflows)
    approvals = [
        (7, 4, workflows),  # Manager → Director
        (4, 3, workflows),  # Director → Senior Director
        (3, 1, workflows),  # Senior Director → Partner
        (1, 0, ["BUDGET_APPROVAL"]),  # Partner → CEO (budget approval)
        (5, 4, workflows),  # Technical Manager → Director
        (6, 4, workflows),  # Senior Manager → Director
        (8, 7, workflows),  # Team Lead → Manager
        (9, 7, workflows),  # Senior Consultant → Manager
    ]

    for from_rank, to_rank, wfs in approvals:
        from_pos = get_position_by_rank(db, from_rank)
        to_pos = get_position_by_rank(db, to_rank)

        if not from_pos or not to_pos:
            continue

        for workflow in wfs:
            existing = db.query(ApprovalChain).filter(
                ApprovalChain.tenant_id == tenant_id,
                ApprovalChain.from_position_id == from_pos.id,
                ApprovalChain.to_position_id == to_pos.id,
                ApprovalChain.workflow == workflow
            ).first()

            if not existing:
                chain = ApprovalChain(
                    tenant_id=tenant_id,
                    from_position_id=from_pos.id,
                    to_position_id=to_pos.id,
                    workflow=workflow,
                    auto_escalate=True,
                    escalate_after_days=3,
                    active=True
                )
                db.add(chain)
                chains_created += 1

    db.commit()
    return {"approval_chains_created": chains_created}


def get_employee_approvers(db: Session, org_node_id: str) -> List[dict]:
    """
    Get the approval chain for an employee at a specific OrgNode.
    Returns list of approver nodes in hierarchy order (up to CEO).
    """
    node = db.query(OrgNode).filter(OrgNode.id == org_node_id).first()
    if not node:
        return []

    approvers = []
    current = node

    # Walk up the tree until we reach root (parent_id is None)
    while current.parent_id:
        parent = db.query(OrgNode).filter(OrgNode.id == current.parent_id).first()
        if parent:
            approvers.append({
                "org_node_id": parent.id,
                "name": parent.name,
                "position_name": parent.position.name,
                "position_rank": parent.position.rank
            })
            current = parent
        else:
            break

    return approvers

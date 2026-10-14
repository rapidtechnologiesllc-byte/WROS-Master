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
    {
        "rank": 10,
        # Levels 1-4 (Intern, Associate, Senior Associate, Consultant) sit here
        # (org_hierarchy_validator.LEVEL_POSITION_CODES); without it no one at those
        # levels could be placed in the org chart
        "name": "Consultant",
        "description": "Consultant - individual contributor (Intern to Consultant)",
        "approves_to_rank": 7,  # Same approver as a Senior Consultant
        "approves_workflows": None,
        "rbac_role_name": "consultant"
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
    name: str,
    hierarchy_level: int,
    specialization: Optional[str] = None,
    parent_id: Optional[str] = None,
    department_id: Optional[str] = None,
    company_id: Optional[str] = None,
) -> OrgNode:
    """
    Validate and add (without committing) an org node. position_id is derived
    from hierarchy_level so the two scales can't disagree. Raises ValueError
    with a caller-safe message when the placement breaks the reporting rules.
    """
    from app.services.org_hierarchy_validator import OrgHierarchyValidator, position_id_for_level

    from app.services.org_hierarchy_validator import specialization_for_department

    if not name or not name.strip():
        raise ValueError("Name is required")
    _validate_company(db, tenant_id, company_id)
    if department_id:
        specialization = specialization_for_department(db, department_id)
    specialization = specialization or "General"

    business_unit_id = None
    if department_id:
        department = db.query(Department).filter(
            Department.id == department_id, Department.tenant_id == tenant_id
        ).first()
        if department is None:
            raise ValueError("Department not found")
        business_unit_id = department.business_unit_id

    is_valid, error = OrgHierarchyValidator.validate_reporting_relationship(
        db, hierarchy_level, specialization, parent_id or None, business_unit_id, tenant_id
    )
    if not is_valid:
        raise ValueError(error)

    node = OrgNode(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        position_id=position_id_for_level(db, hierarchy_level),
        name=name.strip(),
        parent_id=parent_id or None,
        department_id=department_id or None,
        company_id=company_id or None,
        hierarchy_level=hierarchy_level,
        specialization=specialization,
        active=True,
    )
    db.add(node)
    db.flush()
    return node

def place_user_in_org(
    db: Session,
    user,
    *,
    hierarchy_level: int,
    specialization: Optional[str],
    parent_id: Optional[str],
    company_id: Optional[str] = None,
    department_id: Optional[str] = None,
) -> OrgNode:
    """Give a user their seat in the org chart, or move the seat they have.

    One rule set for create and edit: the reporting rules of OrgHierarchyValidator
    (level gap, specialization, business unit), and for an existing seat, no reporting
    to itself or to anyone below it. Reporting across companies is allowed -- a BX-IN
    BU head may report to a partner in BX-US; the seat keeps its own company. Adds
    without committing; raises ValueError with a caller-safe message."""
    from app.services.org_hierarchy_validator import (
        OrgHierarchyValidator, position_id_for_level, specialization_for_department,
    )

    tenant_id = user.tenant_id
    node = db.query(OrgNode).filter(OrgNode.id == user.org_node_id, OrgNode.tenant_id == tenant_id).first() \
        if user.org_node_id else None
    if node is None:
        node = create_org_node(db, tenant_id=tenant_id, name=user.UserName or user.UserEmail,
                               hierarchy_level=hierarchy_level, specialization=specialization,
                               parent_id=parent_id, department_id=department_id, company_id=company_id)
        user.org_node_id = node.id
    else:
        _validate_company(db, tenant_id, company_id)
        business_unit_id = None
        if department_id:
            department = db.query(Department).filter(
                Department.id == department_id, Department.tenant_id == tenant_id).first()
            if department is None:
                raise ValueError("Department not found")
            business_unit_id = department.business_unit_id
        ancestor = parent_id
        while ancestor:
            if ancestor == node.id:
                raise ValueError("A person cannot report to themselves or to someone who reports to them")
            row = db.query(OrgNode.parent_id).filter(OrgNode.id == ancestor).first()
            ancestor = row[0] if row else None
        is_valid, error = OrgHierarchyValidator.validate_reporting_relationship(
            db, hierarchy_level, specialization, parent_id or None, business_unit_id, tenant_id)
        if not is_valid:
            raise ValueError(error)
        node.hierarchy_level = hierarchy_level
        node.specialization = specialization_for_department(db, department_id) if department_id \
            else (specialization or "General")
        node.position_id = position_id_for_level(db, hierarchy_level)
        node.parent_id = parent_id or None
        node.company_id = company_id or None
        node.department_id = department_id or None
        node.name = user.UserName or node.name
    user.location_id = company_id or None
    _sync_employee_reporting(db, user, node)
    db.flush()
    return node


def _sync_employee_reporting(db: Session, user, node: OrgNode) -> None:
    """One reporting line: the person's employee record takes their org seat, and its manager
    is the employee record of whoever sits in the parent seat (timesheet approval and the
    expense manager both follow the org chart)."""
    from app.models.employee import Employee
    from app.models.user import Users

    employee = db.query(Employee).filter(Employee.wros_user_id == user.UserID).first()
    if employee is None:
        return
    employee.org_node_id = node.id
    # An empty boss seat (or a boss with no employee record) leaves a hand-set manager in
    # place: only a person actually sitting in the parent seat replaces it.
    if not node.parent_id:
        return
    boss = db.query(Users).filter(Users.org_node_id == node.parent_id, Users.tenant_id == user.tenant_id).first()
    if boss is None:
        return
    employee.reporting_manager_user_id = boss.UserID
    manager = db.query(Employee).filter(Employee.wros_user_id == boss.UserID).first()
    if manager is not None:
        employee.manager_id = manager.id


def _validate_company(db: Session, tenant_id: int, company_id: Optional[str]) -> None:
    from app.models.location import Location
    if company_id and not db.query(Location).filter(Location.id == company_id, Location.tenant_id == tenant_id).first():
        raise ValueError("Company not found")


def update_org_node(db: Session, tenant_id: int, node_id: str, *, name: Optional[str] = None,
                    company_id: Optional[str] = None) -> OrgNode:
    """Rename a seat or change its company ("" clears). Level, reporting line
    and department go through the validator, so they are not editable here."""
    node = db.query(OrgNode).filter(OrgNode.id == node_id, OrgNode.tenant_id == tenant_id).first()
    if node is None:
        raise LookupError("Org node not found")
    if name is not None:
        if not name.strip():
            raise ValueError("Name is required")
        node.name = name.strip()
    if company_id is not None:
        _validate_company(db, tenant_id, company_id)
        node.company_id = company_id or None
    db.flush()
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

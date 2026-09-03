"""
Organizational Hierarchy Models — Corporate → Business Unit → Department → Org Hierarchy

Full structure: Corporate (Tenant) → Business Unit → Department → OrgNode hierarchy
- OrgPosition: named titles in the org (10 levels: CEO, Partner, BU Head, Senior Director, Director,
  Technical Manager, Senior Manager, Manager, Team Lead, Senior Consultant)
- Department: teams/divisions under a business unit (e.g., "Guidewire Staffing", "Guidewire Billing")
- OrgNode: instances of positions within departments (e.g., "BU Head - Guidewire", "Manager - East Coast Team").
  Each node has one parent, zero or more children.
- Employee links to one OrgNode; that node's position determines role, access, and approval rights.
- Approval rules (e.g., "a Manager approves their team's timesheets") live in a separate
  ApprovalChain table that references position transitions (e.g., Manager → Director).
"""
import logging
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index
)
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)

class Department(Base):
    """
    A department/team within a business unit.
    Example: "Guidewire Staffing", "Salesforce Development", "Microsoft Operations"

    Hierarchy: Tenant (Corporate) → BusinessUnit → Department → OrgNode
    Every department has a hiring manager (an OrgNode at Manager level or above).
    """
    __tablename__ = "departments"

    id = Column(String(512), primary_key=True, index=True)  # UUID
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False, index=True)

    # Department name (e.g., "Staffing", "Billing", "Operations")
    name = Column(String(512), nullable=False)

    # Optional description of what this department does
    description = Column(Text, nullable=True)

    # Hiring manager for this department (OrgNode ID, typically Manager or Senior Manager position)
    hiring_manager_id = Column(String(512), ForeignKey("org_nodes.id"), nullable=True, index=True)

    # Cost center or profit center for finance reporting
    cost_center_code = Column(String(512), nullable=True)

    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id])
    org_nodes = relationship("OrgNode", back_populates="department", foreign_keys="OrgNode.department_id")
    hiring_manager = relationship("OrgNode", foreign_keys=[hiring_manager_id])

    __table_args__ = (
        Index("ix_departments_tenant_id_bu_id", "tenant_id", "business_unit_id"),
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name!r} bu_id={self.business_unit_id}>"

class OrgPosition(Base):
    """
    Named organizational titles: CEO, Partner, BU Head, Senior Director, Director, etc.
    These are templates; instances are OrgNodes (a specific "Senior Director of Guidewire Practice").
    Tied to RBAC roles and approval responsibilities.
    """
    __tablename__ = "org_positions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(512), unique=True, nullable=False, index=True)  # "CEO", "Partner", "BU Head", etc.
    rank = Column(Integer, nullable=False, index=True)  # 0=CEO, 1=Partner, ..., 9=Senior Consultant; used for hierarchy traversal
    description = Column(Text, nullable=True)

    # Approval authority — which position this one reports to for approval authority
    # (e.g., Manager's decisions go to Director; Director's go to Senior Director)
    approves_to_rank = Column(Integer, nullable=True)  # null for CEO (nobody above)

    # This position approves what workflows
    # (stored as comma-separated strings for flexibility; examples: "TIMESHEET", "PO_APPROVAL", "OFFER_LETTER")
    approves_workflows = Column(String(512), nullable=True)

    # RBAC role associated with this position (e.g., "Manager" position → "manager" role)
    rbac_role_name = Column(String(512), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    nodes = relationship("OrgNode", back_populates="position", foreign_keys="OrgNode.position_id")

    def __repr__(self) -> str:
        return f"<OrgPosition id={self.id} name={self.name!r} rank={self.rank}>"

class OrgNode(Base):
    """
    An instance of a position in the organizational tree within a department.
    Examples: "CEO", "Partner - BlitzenX", "BU Head - Guidewire", "Manager - East Coast Team".

    Each node has one parent (except the root CEO node, which has parent_id=null).
    This creates the tree structure within a department. Cross-department reporting
    (e.g., CEO over all departments, Partner over all BU Heads) is defined by position rank.

    HIERARCHY ENFORCEMENT (2026-08-27):
    - hierarchy_level: 1-17 (Intern → CEO) defines authority and valid parents
    - specialization: domain (Recruitment, Development, HR, Finance, etc.) for same-domain reporting
    """
    __tablename__ = "org_nodes"

    id = Column(String(512), primary_key=True, index=True)  # UUID
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    position_id = Column(Integer, ForeignKey("org_positions.id"), nullable=False, index=True)

    # Descriptive name for this specific node (e.g., "Guidewire Practice", "East Coast AE Team")
    name = Column(String(512), nullable=False)

    # Parent node in the hierarchy (null for root-level nodes only: CEO, Partner)
    parent_id = Column(String(512), ForeignKey("org_nodes.id"), nullable=True, index=True)

    # Department this node belongs to (null for corporate-level: CEO, Partner)
    department_id = Column(String(512), ForeignKey("departments.id"), nullable=True, index=True)

    # MANDATORY: Hierarchy level (1-17) for enforcement of reporting structure
    hierarchy_level = Column(Integer, nullable=False, default=5, comment="1-17: Intern→CEO, defines authority")

    # MANDATORY: Specialization domain (Recruitment, Development, HR, Finance, etc.)
    specialization = Column(String(512), nullable=False, default="General", comment="Specialization: Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis")

    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    position = relationship("OrgPosition", back_populates="nodes", foreign_keys=[position_id])
    parent = relationship("OrgNode", remote_side=[id], foreign_keys=[parent_id], backref="children")
    employees = relationship("Employee", back_populates="org_node", foreign_keys="Employee.org_node_id")
    department = relationship("Department", back_populates="org_nodes", foreign_keys=[department_id])

    __table_args__ = (
        Index("ix_org_nodes_tenant_id_position_id", "tenant_id", "position_id"),
        Index("ix_org_nodes_tenant_id_parent_id", "tenant_id", "parent_id"),
        Index("ix_org_nodes_tenant_id_department_id", "tenant_id", "department_id"),
    )

    def __repr__(self) -> str:
        return f"<OrgNode id={self.id} name={self.name!r} position_id={self.position_id} dept_id={self.department_id}>"

class PartnerBUAssignment(Base):
    """
    Links a Partner (OrgNode) to the Business Units they oversee.
    A Partner can oversee multiple Business Units, but each BU has only one Partner.
    """
    __tablename__ = "partner_bu_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # The Partner OrgNode (position_id must be "Partner")
    partner_org_node_id = Column(String(512), ForeignKey("org_nodes.id"), nullable=False, index=True)

    # The Business Unit this Partner oversees
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False, index=True)

    # Whether this assignment is active
    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    partner_org_node = relationship("OrgNode", foreign_keys=[partner_org_node_id])
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id])

    __table_args__ = (
        Index("ix_partner_bu_tenant_bu", "tenant_id", "business_unit_id"),
        Index("ix_partner_bu_partner_node", "tenant_id", "partner_org_node_id"),
    )

    def __repr__(self) -> str:
        return f"<PartnerBUAssignment partner={self.partner_org_node_id} bu={self.business_unit_id}>"

class ApprovalChain(Base):
    """
    Defines approval workflows within the org hierarchy.
    Examples:
    - "A Manager's timesheet approvals go to their Director" (Manager → Director, TIMESHEET)
    - "A Director's hiring decisions go to their Senior Director" (Director → Senior Director, OFFER_LETTER)
    - "A Senior Director's budgets go to their Partner" (Senior Director → Partner, BUDGET_APPROVAL)

    This separates approval routing from position definitions, so org structure can change
    without rewriting approval logic.
    """
    __tablename__ = "approval_chains"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Position that needs approval (e.g., "Manager" needs timesheet approval from above)
    from_position_id = Column(Integer, ForeignKey("org_positions.id"), nullable=False, index=True)

    # Position that approves (e.g., "Director" approves Manager's timesheets)
    to_position_id = Column(Integer, ForeignKey("org_positions.id"), nullable=False, index=True)

    # Workflow this chain handles (e.g., "TIMESHEET", "OFFER_LETTER", "BUDGET_APPROVAL")
    workflow = Column(String(512), nullable=False, index=True)

    # Whether automatic escalation is enabled (if to_position is unavailable, escalate to their approver)
    auto_escalate = Column(Boolean, default=True, nullable=False)

    # Number of days before auto-escalation if no action taken (null = no auto-escalate)
    escalate_after_days = Column(Integer, nullable=True)

    active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_approval_chains_tenant_workflow", "tenant_id", "workflow"),
    )

    def __repr__(self) -> str:
        return f"<ApprovalChain from_pos={self.from_position_id} to_pos={self.to_position_id} workflow={self.workflow!r}>"

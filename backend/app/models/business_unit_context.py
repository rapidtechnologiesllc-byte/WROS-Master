"""
import logging
BusinessUnitContext Model - Unified Business Unit Reference Pattern

ARCHITECTURAL DECISION (2026-08-14):
Instead of scattering business_unit_id, partner_id, bu_head_id across 20+ tables,
centralize all BU context into a single BusinessUnitContext entity.

Benefits:
- Single FK to BusinessUnitContext instead of 3+ scattered FKs
- Consistent partner/head assignments across all tables
- Queryable BU relationships in one place
- Auditability: full BU assignment history
- Type-safe: Integer PK instead of VARCHAR mismatches

Usage:
  class Department(Base):
      bu_context_id = Column(Integer, FK("business_unit_context.id"))
      bu_context = relationship("BusinessUnitContext")

      @property
      def business_unit(self):
          return self.bu_context.business_unit

      @property
      def partner(self):
          return self.bu_context.partner_org_node
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from app.models.base import Base

logger = logging.getLogger(__name__)

class BusinessUnitContext(Base):
    """
    Unified context for all business unit relationships.

    One BusinessUnitContext maps to:
    - A specific business unit (primary reference)
    - The partner responsible for that BU
    - The BU head (executive owner)
    - The HR manager for that BU
    - Audit/compliance fields

    This eliminates scattered business_unit_id across 20+ tables.
    Tables that need BU context now have ONE FK: bu_context_id.
    """
    __tablename__ = "business_unit_context"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Core reference: which business unit
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False, index=True)

    # BU leadership: who is responsible
    # Partner (OrgNode at Partner position level)
    partner_org_node_id = Column(String(512), ForeignKey("org_nodes.id"), nullable=True, index=True)

    # BU Head (typically an Employee)
    bu_head_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)

    # HR Manager for this BU
    hr_manager_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)

    # Sourcing lead (Recruiter responsible for this BU)
    sourcing_lead_employee_id = Column(String(512), ForeignKey("employees.id"), nullable=True, index=True)

    # Finance: cost center or profit center code
    cost_center_code = Column(String(512), nullable=True)

    # Status: is this context active
    active = Column(Boolean, nullable=False, default=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(512), nullable=True)
    updated_by = Column(String(512), nullable=True)

    # Relationships
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id], lazy="select")
    partner_org_node = relationship("OrgNode", foreign_keys=[partner_org_node_id], lazy="select")
    bu_head = relationship("Employee", foreign_keys=[bu_head_employee_id], lazy="select")
    hr_manager = relationship("Employee", foreign_keys=[hr_manager_employee_id], lazy="select")
    sourcing_lead = relationship("Employee", foreign_keys=[sourcing_lead_employee_id], lazy="select")

    __table_args__ = (
        # Ensure one active context per tenant+BU combination
        Index("ix_bu_context_tenant_bu", "tenant_id", "business_unit_id"),
        # Fast lookup by tenant
        Index("ix_bu_context_tenant_active", "tenant_id", "active"),
    )

    def __repr__(self) -> str:
        return f"<BusinessUnitContext id={self.id} tenant_id={self.tenant_id} bu_id={self.business_unit_id}>"

"""
Business Rules Configuration Engine - WROS Orchestration Rules

Stores configurable business rules that gate all major decisions:
- Profit margin acceptance (minimum % to accept deals)
- Utilization targets (min/max billable hours per person)
- Certification requirements (what certs needed per role)
- Experience minimums (years required per certification)
- Timeline feasibility (sourcing, interview, onboarding SLAs)
- Bench pool rules (how long before action)
- KPI requirements (buddy program completion, etc.)

All rules are configuration-driven (stored in database tables),
not hardcoded, so admins can adjust without engineering.
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import relationship
import logging

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)


class BusinessRuleConfig(Base):
    """Master business rules - configurable by admin."""
    __tablename__ = "business_rules_config"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Rule key: MIN_PROFIT_MARGIN, MAX_UTILIZATION_PCT, SOURCING_DAYS, etc.
    rule_key = Column(String(100), nullable=False, index=True)
    rule_value = Column(String(255), nullable=False)  # Stored as string, parsed by service
    rule_category = Column(String(50), nullable=False)  # PROFIT, UTILIZATION, CERTIFICATION, TIMELINE, BENCH, KPI

    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    effective_date = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    updated_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<BusinessRuleConfig {self.rule_key}={self.rule_value}>"


class CertificationRequirement(Base):
    """What certifications are required for each role."""
    __tablename__ = "certification_requirements"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Role name: "Guidewire Architect", "Salesforce Developer", etc.
    role_name = Column(String(100), nullable=False, index=True)

    # Links to Certification table
    certification_id = Column(String(512), ForeignKey("certifications.id"), nullable=False)

    # Minimum years of experience required
    min_experience_years = Column(Integer, nullable=False, default=0)

    # Must have completed buddy program?
    buddy_program_required = Column(Boolean, default=False)

    # Market rates for this role
    market_hourly_rate_min = Column(Numeric(10, 2), nullable=False)
    market_hourly_rate_max = Column(Numeric(10, 2), nullable=False)

    is_active = Column(Boolean, default=True)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    certification = relationship("Certification", foreign_keys=[certification_id])

    def __repr__(self) -> str:
        return f"<CertificationRequirement {self.role_name}>"


class BUSpecialtyConfig(Base):
    """What specialties each BU offers (and their profit targets)."""
    __tablename__ = "bu_specialty_configs"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=False, index=True)

    # Specialty name: "Guidewire", "Salesforce", "AWS", etc.
    specialty_name = Column(String(100), nullable=False)

    # Link to certification
    certification_id = Column(String(512), ForeignKey("certifications.id"), nullable=False)

    # Target margin for deals in this specialty
    target_margin_pct = Column(Numeric(5, 2), nullable=False, default=30.0)

    # Target utilization for people in this specialty
    target_utilization_pct = Column(Integer, nullable=False, default=85)

    # Max people available in this specialty
    max_capacity = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    created_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id])
    certification = relationship("Certification", foreign_keys=[certification_id])

    def __repr__(self) -> str:
        return f"<BUSpecialtyConfig {self.specialty_name}>"


class OpportunityEvaluation(Base):
    """Track every opportunity evaluated against business rules."""
    __tablename__ = "opportunity_evaluations"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Opportunity details
    client_name = Column(String(255), nullable=False)
    opportunity_description = Column(Text, nullable=False)
    required_role = Column(String(100), nullable=False)  # "Guidewire Architect", etc.
    required_timeline_days = Column(Integer, nullable=False)
    contract_value = Column(Numeric(15, 2), nullable=False)

    # Rule evaluation results
    profit_margin_pct = Column(Numeric(5, 2), nullable=True)
    profit_gate_pass = Column(Boolean, nullable=True)  # True if margin > minimum
    capability_gate_pass = Column(Boolean, nullable=True)  # True if we offer this role
    timeline_gate_pass = Column(Boolean, nullable=True)  # True if feasible in timeline
    certification_gate_pass = Column(Boolean, nullable=True)  # True if we have certified people

    # Decision
    recommendation = Column(String(20), nullable=False)  # ACCEPT, REJECT, ESCALATE
    reason = Column(Text, nullable=True)
    required_action = Column(Text, nullable=True)  # "Source Guidewire architect (14 days)" or similar

    evaluated_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    evaluated_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<OpportunityEvaluation {self.client_name} {self.recommendation}>"

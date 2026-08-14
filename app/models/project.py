"""
HRMS-0801 (Project Lifecycle Management) + HRMS-0804 (Milestone
Creation & Completion Tracking), Phase 2 Domain 4.

A project is auto-created when an Opportunity transitions to WON (see
app.services.opportunity_service.transition_stage()'s BR-0801-01 hook),
inheriting client_id/currency/continent -- or created manually for
non-opportunity-originated work (opportunity_id stays nullable either
way, per the doc's own note).

HRMS-1107 (Project Health Monitoring Agent, Phase 3 EPIC-11) doesn't
exist in this codebase -- HRMS-0807 (Project Risk Flagging), which is
specified to only ever *display* HRMS-1107's score rather than
recompute it, is NOT built here: there is no score to display yet, and
building a second, competing health-scoring formula would be exactly
the kind of drift HRMS-0807's own BR-0807-01 warns against.
"""
import uuid
from datetime import date as date_type, datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    String, Text, func,
)

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES
from app.models.employee import DELIVERY_ENGINES


def _new_uuid() -> str:
    return str(uuid.uuid4())


PROJECT_STATUSES = ("PLANNING", "ACTIVE", "ON_HOLD", "COMPLETED", "CLOSED")
BILLING_TYPES = ("TIME_AND_MATERIALS", "FIXED_BID")
# S-358/HRMS-0519: Speciality Engine work is executed through these SI
# partners. delivery_engine reuses Employee.DELIVERY_ENGINES (same "one
# enum" discipline app.models.demand already follows) rather than a
# third copy -- the source doc's own validation rule ("if delivery_
# engine=SPECIALITY AND si_partner IS NULL") assumes Project carries
# this field directly, and nothing in this codebase derives it any
# other way (Project has no Demand link of its own; Demand points to
# Project, not the reverse).
SI_PARTNERS = ("PWC", "EY", "CASTLEBAY", "ZENSAR", "LTI_MINDTREE", "OTHER")
# Backlog item, 2026-08-05: Avinash -- "If Speciality then always =
# Staff Augmentation so you don't need another field, but when it is
# core we need to break down the subtype of revenue." Speciality has no
# stored business-type value at all (it's implicitly Staff Aug, never
# persisted); this enum only ever applies when delivery_engine=CORE,
# service-layer enforced (same posture as si_partner above, not a DB
# CHECK constraint -- create_project() is reused by many unrelated
# tests' fixtures with no opinion on business type).
PROJECT_BUSINESS_TYPES = ("T_AND_M", "MANAGED_SERVICES", "PROJECT", "POD", "PILOT")
# Speciality: INR or USD. Core: USD only. Same ask, same source quote.
SPECIALITY_CURRENCIES = ("INR", "USD")
CORE_CURRENCIES = ("USD",)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    # Nullable: not every project traces back to a tracked opportunity
    # (e.g. an existing client's direct follow-on request) -- HRMS-0801's
    # own data mapping calls this out explicitly.
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=True, index=True)
    client_owner_id = Column(String(36), ForeignKey("users.UserID"), nullable=True, index=True)

    name = Column(String(300), nullable=False)
    status = Column(
        Enum(*PROJECT_STATUSES, name="project_status", native_enum=False, create_constraint=True),
        nullable=False, default="ACTIVE",
    )
    billing_type = Column(
        Enum(*BILLING_TYPES, name="project_billing_type", native_enum=False, create_constraint=True),
        nullable=False, default="TIME_AND_MATERIALS",
    )
    currency = Column(
        Enum(*BILLING_CURRENCIES, name="project_currency", native_enum=False, create_constraint=True),
        nullable=False, default="USD",
    )
    continent = Column(String(50), nullable=True)
    # HRMS-0910 BR-0910-02: weekend timesheet entries are only flagged as
    # an anomaly when the project does NOT opt in to weekend billing.
    allow_weekend_billing = Column(Boolean, nullable=False, default=False)

    # S-358/HRMS-0519 -- delivery_engine defaults SPECIALITY (same
    # discipline as Employee: no exceptions without explicit action).
    # si_partner is DB-nullable (CORE-engine projects legitimately have
    # none) but service-layer-required whenever delivery_engine=
    # SPECIALITY, per BR "SI Partner Mandatory for SPECIALITY Projects".
    delivery_engine = Column(
        Enum(*DELIVERY_ENGINES, name="project_delivery_engine", native_enum=False, create_constraint=True),
        nullable=False, default="SPECIALITY", server_default="SPECIALITY",
    )
    si_partner = Column(
        Enum(*SI_PARTNERS, name="project_si_partner", native_enum=False, create_constraint=True),
        nullable=True,
    )
    # Backlog item, 2026-08-05 -- conditional-by-delivery_engine fields.
    # end_client: Speciality/Staff-Aug concept, optional even for
    # Speciality (per Avinash: "end client where end client is not a
    # mandatory field"). client_partner: Core concept ("Direct client
    # project, managed service"). business_type: CORE-only revenue
    # subtype breakdown, see PROJECT_BUSINESS_TYPES above.
    end_client = Column(String(300), nullable=True)
    client_partner = Column(String(300), nullable=True)
    business_type = Column(
        Enum(*PROJECT_BUSINESS_TYPES, name="project_business_type", native_enum=False, create_constraint=True),
        nullable=True,
    )

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    owner_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True)

    is_complete = Column(
        Enum("PENDING", "COMPLETE", name="project_milestone_completion", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    completion_date = Column(Date, nullable=True)
    # HRMS-0804 BR-0804-01: always computed at completion time
    # (completion_date - due_date), never a manually-entered field --
    # HRMS-1107's health score depends on this being trustworthy.
    delay_days = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

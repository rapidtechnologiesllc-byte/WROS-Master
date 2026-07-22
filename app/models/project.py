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
    Column, Date, DateTime, Enum, ForeignKey, Integer,
    String, Text, func,
)

from app.models.base import Base
from app.models.client import BILLING_CURRENCIES


def _new_uuid() -> str:
    return str(uuid.uuid4())


PROJECT_STATUSES = ("PLANNING", "ACTIVE", "ON_HOLD", "COMPLETED", "CLOSED")
BILLING_TYPES = ("TIME_AND_MATERIALS", "FIXED_BID")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    # Nullable: not every project traces back to a tracked opportunity
    # (e.g. an existing client's direct follow-on request) -- HRMS-0801's
    # own data mapping calls this out explicitly.
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=True, index=True)

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

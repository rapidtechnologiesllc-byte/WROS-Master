"""
Help Desk / IT-HR Ticketing -- a Task type, not a parallel object (per
import logging
task.py's own module docstring). Internal-employees-only.

Best-of-breed synthesis, researched 2026-08-04 (ServiceNow + Salesforce
Service Cloud + Zendesk + Freshdesk):
- ServiceNow: Impact x Urgency -> Priority derivation (not a direct
  Priority pick -- structurally prevents inflation, more precise than
  Task's own Thunder-challenge gate for tickets specifically); real
  Category/Subcategory two-level taxonomy; a real state lifecycle;
  separate Response vs Resolution SLA targets.
- Freshdesk (Omniroute) / Zendesk (skills-based routing): workload-
  based routing -- already satisfied by Task's own capacity-aware
  round-robin, no new mechanism needed here.
- Freshdesk/Zendesk parent-child tickets: already satisfied by Task's
  own parent_task_id, no new mechanism needed here.

Categories route through the real, dynamic, admin-configurable
Department table (TicketCategoryRoute), not a hardcoded HR/IT/
Facilities/Other list -- covers every department/function per
Avinash's explicit direction, including ones that don't exist yet.
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.task import TASK_PRIORITIES

def _new_uuid() -> str:
    return str(uuid.uuid4())

# ServiceNow's own real value sets for Impact/Urgency -- Priority is
# DERIVED from these two (see ticket_service.derive_priority_from_impact_urgency()),
# never picked directly, which is what actually prevents inflation for
# a ticket (Task's own Thunder-challenge gate is the fallback for
# GENERAL tasks, where there's no Impact/Urgency pair to derive from).
TICKET_IMPACTS = ("INDIVIDUAL", "DEPARTMENT", "MULTIPLE_DEPARTMENTS", "ORG_WIDE")
TICKET_URGENCIES = ("LOW", "MODERATE", "CRITICAL")

# Impact x Urgency -> Priority lookup, adapted from the real ServiceNow
# matrix pattern researched this session. A real admin-editable lookup
# table would be the eventual richer version of this (ServiceNow calls
# it a "Priority Data Lookup") -- this is a code-constant v1, same
# posture this codebase already takes for other unconfigured defaults
# (e.g. S-041's WHATSAPP_FOLLOWUP_HOURS), flagged not hidden.
IMPACT_URGENCY_PRIORITY_MATRIX = {
    ("ORG_WIDE", "CRITICAL"): "URGENT",
    ("ORG_WIDE", "MODERATE"): "HIGH",
    ("ORG_WIDE", "LOW"): "HIGH",
    ("MULTIPLE_DEPARTMENTS", "CRITICAL"): "URGENT",
    ("MULTIPLE_DEPARTMENTS", "MODERATE"): "HIGH",
    ("MULTIPLE_DEPARTMENTS", "LOW"): "MEDIUM",
    ("DEPARTMENT", "CRITICAL"): "HIGH",
    ("DEPARTMENT", "MODERATE"): "MEDIUM",
    ("DEPARTMENT", "LOW"): "MEDIUM",
    ("INDIVIDUAL", "CRITICAL"): "HIGH",
    ("INDIVIDUAL", "MODERATE"): "MEDIUM",
    ("INDIVIDUAL", "LOW"): "LOW",
}

logger = logging.getLogger(__name__)

class TicketCategoryRoute(Base):
    """Admin-configurable category -> department routing rule. No
    hardcoded category list -- an admin adds one row per real category
    their org needs, for ANY department, not just HR/IT/Facilities."""
    __tablename__ = "ticket_category_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(512), nullable=False)
    subcategory = Column(String(512), nullable=True)
    department_id = Column(String(512), ForeignKey("departments.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

    department = relationship("Department", foreign_keys=[department_id])

    __table_args__ = (
        UniqueConstraint("category", "subcategory", name="uq_ticket_category_route"),
    )

class TicketSLAPolicy(Base):
    """Response vs Resolution SLA targets per Priority tier -- code-
    constant defaults seeded by a migration, admin-editable via
    PATCH /tickets/admin/sla-policies/{priority}."""
    __tablename__ = "ticket_sla_policies"

    priority = Column(String(10), primary_key=True)
    response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class TicketDetail(Base):
    """1:1 extension of a Task with task_type='TICKET' -- SLA/Impact/
    Urgency fields that don't apply to a GENERAL task, kept off the
    shared Task table rather than bloating it (same posture as
    task_capacity_alerts being its own table instead of a Task column)."""
    __tablename__ = "ticket_details"

    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)

    impact = Column(String(30), nullable=False)
    urgency = Column(String(15), nullable=False)

    response_due_at = Column(DateTime, nullable=False)
    resolution_due_at = Column(DateTime, nullable=False)
    first_response_at = Column(DateTime, nullable=True)
    response_breached = Column(Boolean, nullable=False, default=False)
    resolution_breached = Column(Boolean, nullable=False, default=False)

    task = relationship("Task")

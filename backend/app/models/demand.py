"""
HRMS-0103 — Demand / Job Requisition Management, Phase 2 Domain 2/4.

Same translation conventions as
app.models.employee/client.

Note: this is a genuinely new entity, distinct from the existing `Jobs`
table (app.models.user.Jobs) -- Jobs was built for the onboarding
module's own recruiting flow and doesn't have a client_id FK, a demand
state machine, or the bench-first/sourcing gating fields this spec
calls for. Per this session's confirmed direction, `demands` is built
as its own table rather than retrofitting Jobs -- reconciling the two
(or migrating Jobs data into demands) is a separate decision, flagged
in the developer handoff, not resolved by silently picking one here.
"""
import logging
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.employee import DELIVERY_ENGINES

def _new_uuid() -> str:
    return str(uuid.uuid4())

WORK_LOCATIONS = ("REMOTE", "ONSITE", "HYBRID")
EMPLOYMENT_TYPES = ("FULLTIME", "CONTRACT")  # what a job hires as; C2C/1099 never (CEO 2026-10-15)
INTERVIEW_TYPES = ("L1_ONLY", "L1_AND_L2")
URGENCY_LEVELS = ("IMMEDIATE", "HIGH", "NORMAL", "FLEXIBLE")
DEMAND_STATUSES = ("DRAFT", "OPEN", "IN_PROGRESS", "FILLED", "CANCELLED", "ON_HOLD")
# HRMS-0210 BR-0210-01: a tag, not a schema branch -- opportunity-
# originated demands get identical sourcing/bench-first/allocation
# treatment to any other demand.
DEMAND_SOURCE_TYPES = ("DIRECT", "OPPORTUNITY")

# HRMS-0103 step 3 -- allowed status transitions.
ALLOWED_DEMAND_TRANSITIONS = {
    "DRAFT": {"OPEN"},
    "OPEN": {"IN_PROGRESS", "ON_HOLD", "CANCELLED"},
    "IN_PROGRESS": {"FILLED", "ON_HOLD", "CANCELLED"},
    "ON_HOLD": {"OPEN", "IN_PROGRESS", "CANCELLED"},
    "FILLED": set(),      # terminal
    "CANCELLED": set(),   # terminal
}

logger = logging.getLogger(__name__)

# A client demand and a recruiting job are one record: the Jobs row (see
# app.models.user.Jobs, which carries the demand columns and Demand
# attribute names as synonyms). `Demand` is kept as the name the delivery
# code uses for it.
from app.models.user import Jobs as Demand  # noqa: E402


class DemandHistory(Base):
    """Insert-only, same immutable pattern as employee/client history."""
    __tablename__ = "demand_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=False, index=True)
    change_type = Column(
        Enum("STATUS", "RECRUITER", "URGENCY", "HEADCOUNT", name="demand_change_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(512), nullable=True)
    changed_at = Column(DateTime, server_default=func.now())

"""
import logging
S-372/HRMS-0528 -- Confirmed vs Potential Demand Workflow.

Built from `Requirements/S-372_HRMS-0528.docx` directly.

`Demand.confirmation_status` unifies both paths the doc describes: a
CONFIRMED-type deal (SOW already in hand) and a POTENTIAL-type deal
(interview-first, SOW arrives later) both converge on the same terminal
state -- CONFIRMED -- once a real SOW reference is recorded. There's no
separate "workflow type" field distinct from this status; the doc's own
Step 1 schema only adds the one status column plus the SOW fields.

DemandAlignmentCall: per-candidate tracking (a demand can have more than
one candidate considered over time), not folded into Demand itself --
the 3-way call, both fit confirmations, and the release trigger are all
scoped to a specific employee being proposed for a specific demand.
"""
import logging
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


DEMAND_CONFIRMATION_STATUSES = ("POTENTIAL", "CONFIRMED", "CANCELLED")

logger = logging.getLogger(__name__)

class DemandAlignmentCall(Base):
    __tablename__ = "demand_alignment_calls"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)

    curtis_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    bu_head_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # SchedulerService.book3WayAlignment() result

    # NULL = not yet responded. True/False = an actual response, never
    # overwritten by anyone but that participant -- see BR: employee
    # confirmation cannot be overridden.
    employee_fit_confirmed = Column(Boolean, nullable=True)
    employee_fit_confirmed_at = Column(DateTime, nullable=True)
    employee_fit_notes = Column(Text, nullable=True)

    bu_head_fit_confirmed = Column(Boolean, nullable=True)
    bu_head_fit_confirmed_at = Column(DateTime, nullable=True)
    bu_head_fit_notes = Column(Text, nullable=True)

    specialty_client_release_triggered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

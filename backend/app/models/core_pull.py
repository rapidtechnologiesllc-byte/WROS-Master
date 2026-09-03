"""
S-353/HRMS-0514 -- Core-Pull Conflict Rule Engine ("Core Wins Policy") and
import logging
S-373/HRMS-0529 -- Specialty Pool Minimum 40 Core-Certified Guard.

Both stories per docs/build-package/04-RESOURCE-MANAGEMENT.md Part A, built
against `Requirements/S-353_HRMS-0514.docx` and `Requirements/S-373_HRMS-0529.docx`
directly -- not the phase doc's own summary, which (like HRMS-1105's story
doc) mislabels this engine "HRMS-0312". HRMS-0312 in the real 357-doc corpus
is an unrelated story (Workforce Scenario Planning); the real, canonical
Core-Pull ID is HRMS-0514/S-353, confirmed against
`WROS_Canonical_Backlog_S001-401.xlsx`. See CLAUDE.md's correction note.
"""
import logging
import uuid

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Integer, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


CORE_PULL_EVENT_STATUSES = ("PENDING", "EXECUTED", "OVERRIDDEN")

logger = logging.getLogger(__name__)

class CorePullEvent(Base):
    """One row per detected Core-vs-Speciality conflict for a single
    Core-Certified employee. PENDING until execute_core_pull() runs (or
    override_core_pull() cancels it)."""

    __tablename__ = "core_pull_events"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    core_demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    speciality_allocation_id = Column(String(512), ForeignKey("employee_allocations.id"), nullable=False, index=True)

    status = Column(
        String(20), nullable=False, default="PENDING",
        # CHECK constraint added at the DB level in the migration -- see
        # app.models.employee's ck_core_requires_certification for the
        # same "constant tuple + CheckConstraint" convention.
    )
    detected_at = Column(DateTime, server_default=func.now())
    executed_at = Column(DateTime, nullable=True)

    # BU Head override path -- BR: min 100 chars, Director-visible.
    override_justification = Column(Text, nullable=True)
    overridden_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    overridden_at = Column(DateTime, nullable=True)


class SpecialtyPoolReplacementPlan(Base):
    """S-373/HRMS-0529 -- logged by a BU Head before a Core move that
    would drop the Specialty Core-Certified pool below 40 is allowed to
    proceed. 'We will hire someone' is not a plan -- expected_date is
    required, per that story's own BR."""

    __tablename__ = "specialty_pool_replacement_plans"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id_moving = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    replacement_strategy = Column(Text, nullable=False)  # min 100 chars, enforced in the service layer
    expected_replacement_date = Column(Date, nullable=False)

    logged_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    logged_at = Column(DateTime, server_default=func.now())

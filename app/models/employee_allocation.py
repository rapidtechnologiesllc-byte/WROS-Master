"""
HRMS-0507 -- Employee Allocation Records.

This is deliberately the minimal "allocate employee to project" data
primitive, not Phase 4's full Resource Management build
(docs/build-package/04-RESOURCE-MANAGEMENT.md is explicit that HRMS-1105's
agent, the Core-Pull engine HRMS-0312, and the 40-person Specialty floor
guard are Phase 4, "unlocked in parallel with Phase 3"). What IS built
here -- the table itself, and the single human-driven allocate/end
action -- is exactly what that same Phase 4 doc calls out as the
foundational piece Phase 4's agent depends on ("Part B", item 3:
"Allocate Employee to Project ... always a distinct human (RM) decision,
never automatic"). Built now because HRMS-0901 Timesheet Submission
genuinely can't exist without it (timesheets are always tied to an
active allocation).

FK note: 02-DATA-MODEL.md's Domain 3 sketch names the column
`project_id`, but this codebase has no `projects` table yet (Domain 4,
EPIC-08, not built). Linked to `demands.id` instead -- the closest
already-built anchor for "what this person is now staffed against" --
same flagged-not-resolved posture as the pre-existing Demand vs. Jobs
note in app.models.demand.
"""
import uuid
from datetime import date as date_type

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


ALLOCATION_STATUSES = ("ACTIVE", "ENDED")


class EmployeeAllocation(Base):
    __tablename__ = "employee_allocations"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    demand_id = Column(String(36), ForeignKey("demands.id"), nullable=False, index=True)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)

    status = Column(
        Enum(*ALLOCATION_STATUSES, name="employee_allocation_status", native_enum=False, create_constraint=True),
        nullable=False, default="ACTIVE",
    )
    utilization_pct = Column(Numeric(5, 2), nullable=True)
    start_date = Column(Date, nullable=False, default=date_type.today)
    end_date = Column(Date, nullable=True)

    client_reporting_manager_contact_id = Column(String(36), ForeignKey("client_contacts.id"), nullable=True)
    # HRMS-0902 -- the RM/Admin who approves this allocation's timesheets.
    timesheet_approver_email = Column(String(300), nullable=True)
    billing_rate_usd_cents = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

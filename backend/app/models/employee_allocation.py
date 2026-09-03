"""
import logging
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
`project_id`, but this codebase had no `projects` table when this model
was first built (Domain 4, EPIC-08). Linked to `demands.id` at the time
-- kept, since it's still meaningful history (what sourcing decision
led here) -- and now ALSO linked to `projects.id` (nullable, since an
allocation predating HRMS-0801 or made outside a tracked project has
none) once HRMS-0801 landed. `role`/`utilization_pct` double as HRMS-
0803's "role"/"allocation_pct" fields -- same concept, no new column
needed for the latter.
"""
import logging
import uuid
from datetime import date as date_type

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, func,
)

from app.models.base import Base
from app.models.project import SI_PARTNERS

def _new_uuid() -> str:
    return str(uuid.uuid4())

# CORE_PULLED (S-353/HRMS-0514): distinct from a normal ENDED -- a Specialty
# allocation that was cut short by a same-day Core-Pull transfer, not a
# regular project end. Kept separate so reporting can tell the two apart
# without inferring intent from end_date proximity to another allocation's
# start_date.
ALLOCATION_STATUSES = ("ACTIVE", "ENDED", "CORE_PULLED")

logger = logging.getLogger(__name__)

class EmployeeAllocation(Base):
    __tablename__ = "employee_allocations"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    client_id = Column(String(512), ForeignKey("clients.id"), nullable=False, index=True)
    # HRMS-0803 -- nullable: not every allocation is tied to a tracked project.
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)
    role = Column(String(512), nullable=True)

    status = Column(
        Enum(*ALLOCATION_STATUSES, name="employee_allocation_status", native_enum=False, create_constraint=True),
        nullable=False, default="ACTIVE",
    )
    utilization_pct = Column(Numeric(5, 2), nullable=True)
    start_date = Column(Date, nullable=False, default=date_type.today)
    end_date = Column(Date, nullable=True)

    client_reporting_manager_contact_id = Column(String(512), ForeignKey("client_contacts.id"), nullable=True)
    # HRMS-0902 -- the RM/Admin who approves this allocation's timesheets.
    timesheet_approver_email = Column(String(300), nullable=True)
    billing_rate_usd_cents = Column(Integer, nullable=True)
    # S-358/HRMS-0519 -- denormalized copy of Project.si_partner at
    # allocation-creation time (per the doc's own "enables fast 'who is
    # at PwC right now' queries without project table joins" rationale).
    # Nullable: allocations with no project, or a CORE-engine project
    # with no si_partner, legitimately have none.
    si_partner = Column(
        Enum(*SI_PARTNERS, name="employee_allocation_si_partner", native_enum=False, create_constraint=True),
        nullable=True,
    )

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

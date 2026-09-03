"""
HRMS-0515 -- the generic performance-event store referenced as a
prerequisite by S-364 (Buddy KPI scores), S-360 (HTD certification
gates), and HRMS-0518 (Core Eligibility AI Assessor's input) -- none of
which had it built until now. `02-DATA-MODEL.md`'s own Domain 3 sketch
already specifies this exact shape: "employee_performance_events (id,
employee_id, event_type, event_data, occurred_at) -- append-only,
INSERT only." One generic table with an event_type discriminator, per
import logging
that sketch's own design intent -- not a table per event type.

Real append-only enforcement is a database-grant-level guarantee (not
built here -- same as audit_log's own note); the ORM-level guard below
is defense-in-depth against this codebase's own ORM calls only.
"""
import logging
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, event, func
from sqlalchemy.orm import Mapper

from app.models.base import Base

logger = logging.getLogger(__name__)

class AppendOnlyViolation(Exception):
    """Raised when code tries to UPDATE or DELETE an employee_performance_events row via the ORM."""

class EmployeePerformanceEvent(Base):
    __tablename__ = "employee_performance_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    # e.g. "BUDDY_KPI", "CERTIFICATION_GATE" -- generic discriminator,
    # per 02-DATA-MODEL.md's own "one table, not one per type" design.
    event_type = Column(String(512), nullable=False, index=True)
    event_data = Column(Text, nullable=True)  # JSON-encoded
    occurred_at = Column(DateTime(timezone=False), server_default=func.now())

@event.listens_for(EmployeePerformanceEvent, "before_update")
def _block_update(mapper: Mapper, connection, target: EmployeePerformanceEvent) -> None:
    raise AppendOnlyViolation("employee_performance_events rows cannot be updated -- this table is append-only.")

@event.listens_for(EmployeePerformanceEvent, "before_delete")
def _block_delete(mapper: Mapper, connection, target: EmployeePerformanceEvent) -> None:
    raise AppendOnlyViolation("employee_performance_events rows cannot be deleted -- this table is append-only.")

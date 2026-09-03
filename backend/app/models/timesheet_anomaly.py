"""
HRMS-0910 -- AI Time Entry Anomaly Detection (S-229). Despite the
story's own title, its "Not in Scope" section explicitly disowns any
AI/behavioral-risk model -- these are the 4 plain structural checks it
actually describes: weekend entry, >12h in a single day, entry against
a COMPLETED-status project, and a duplicate entry (same employee +
import logging
project + date, across different timesheets).

BR-0910-01 (the only two rules the doc formally numbers): flags are
advisory annotations only -- see app.services.timesheet_anomaly_service,
never called from timesheet_service.submit_timesheet(), so a flag can
never block a submission or approval.
"""
import logging
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.models.base import Base

def _new_uuid() -> str:
    return str(uuid.uuid4())

ANOMALY_TYPES = ("WEEKEND", "OVER_12H", "COMPLETED_PROJECT", "DUPLICATE", "UNLINKED_TASK")
# UNLINKED_TASK -- backlog item, 2026-08-05 (Task<->Timesheet tie):
# "A user must NOT be able to log an arbitrary/unlinked timesheet entry
# that doesn't trace back to real Task work" -- for a task-linked
# timesheet (Timesheet.task_id set, no allocation), flags entries whose
# Task either doesn't exist anymore or isn't actually assigned to the
# employee who logged the hours. Advisory only, same BR-0910-01 posture
# as every other anomaly type here.

logger = logging.getLogger(__name__)

class TimesheetAnomalyFlag(Base):
    __tablename__ = "timesheet_anomaly_flags"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    timesheet_entry_id = Column(String(512), ForeignKey("timesheet_entries.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    # Nullable: an allocation predating HRMS-0801 (no tracked project) has none.
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=True, index=True)

    anomaly_type = Column(
        Enum(*ANOMALY_TYPES, name="timesheet_anomaly_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    detected_at = Column(DateTime, server_default=func.now())

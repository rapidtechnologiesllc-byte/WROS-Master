"""
HRMS-0904 -- Timesheet Dispute Resolution, Phase 2 Domain 4.

Builds directly on the existing Timesheet/TimesheetEntry tables
(HRMS-0901/0902). BR-01's "approved timesheet is never edited directly"
is honored literally here: resolving a dispute (even ADJUSTED) never
mutates the original Timesheet/TimesheetEntry rows -- the adjustment
lives entirely on this dispute record. The doc's fuller adjustment path
("creates a correction via revenue_adjustments if invoiced, or updates
revenue_record.billable_hours if not") is NOT built -- `revenue_records`/
`revenue_adjustments`/`invoices` don't exist in this codebase yet. This
dispute record is a complete, real audit trail on its own (what was
disputed, by whom, how it was resolved, what the adjusted hours were)
that a future revenue layer can read once it exists -- not a stub.
"""
import uuid

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


DISPUTE_RAISED_BY = ("RM", "EMPLOYEE", "CLIENT")
DISPUTE_STATUSES = ("OPEN", "UNDER_REVIEW", "RESOLVED_ADJUSTED", "RESOLVED_CONFIRMED", "CANCELLED")
OPEN_DISPUTE_STATUSES = ("OPEN", "UNDER_REVIEW")


class TimesheetDispute(Base):
    __tablename__ = "timesheet_disputes"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    timesheet_id = Column(String(36), ForeignKey("timesheets.id"), nullable=False, index=True)

    raised_by = Column(
        Enum(*DISPUTE_RAISED_BY, name="timesheet_dispute_raised_by", native_enum=False, create_constraint=True),
        nullable=False,
    )
    raised_by_user_id = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    disputed_date = Column(DateTime, nullable=True)  # specific day being disputed, or null for whole week
    disputed_hours = Column(Numeric(4, 2), nullable=True)  # hours claimed by disputing party
    original_hours = Column(Numeric(6, 2), nullable=False)  # snapshot of timesheet.total_hours at dispute-raise time

    reason = Column(Text, nullable=False)  # BR: min 50 chars, enforced in service layer

    status = Column(
        Enum(*DISPUTE_STATUSES, name="timesheet_dispute_status", native_enum=False, create_constraint=True),
        nullable=False, default="OPEN",
    )
    resolved_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    adjusted_hours = Column(Numeric(6, 2), nullable=True)  # final agreed hours if resolution=ADJUSTED

    created_at = Column(DateTime, server_default=func.now())

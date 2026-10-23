"""One submission of a timesheet and its review (CEO 2026-10-22). Every submit opens a review
routed to the employee's approver with an approval task; the entries are snapshotted at submit,
so a resubmission shows the approver exactly what changed since the rejected version. revision
counts submissions of the same timesheet (1 = first)."""
from sqlalchemy import (JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text,
                        UniqueConstraint, func)

from app.models.base import Base

REVIEW_DECISIONS = ("PENDING", "APPROVED", "REJECTED")


class TimesheetReview(Base):
    __tablename__ = "timesheet_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    timesheet_id = Column(String(512), ForeignKey("timesheets.id", ondelete="CASCADE"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    approver_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    approval_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    submitted_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    submitted_at = Column(DateTime, server_default=func.now(), nullable=False)
    # [{entry_date, hours, entry_type, notes}] as submitted
    entries_snapshot = Column(JSON, nullable=False)
    # the employee's answer to the previous rejection (required when nothing changed)
    employee_response = Column(Text, nullable=True)
    decision = Column(Enum(*REVIEW_DECISIONS, name="timesheet_review_decision", native_enum=False,
                           create_constraint=True), nullable=False, default="PENDING")
    decided_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)
    flagged_dates = Column(JSON, nullable=True)  # ["YYYY-MM-DD", ...] the approver marked as the problem
    # on a resubmission: the approver confirmed the earlier rejection is addressed
    addressed_confirmed = Column(Boolean, nullable=False, default=False)
    resubmit_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

    __table_args__ = (UniqueConstraint("timesheet_id", "revision", name="uq_timesheet_review_revision"),)

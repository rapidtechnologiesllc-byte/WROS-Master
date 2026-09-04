"""
EPIC-16 -- Timesheet Nag Cascade. One row per employee+week that's
missing a submitted timesheet. Mechanical pattern reused from the
already-scoped S-355 design (scheduled dispatch -> one reminder ->
escalation-on-repeated-non-response, tracked against the non-
responder) -- same shape, applied here to timesheet submission instead
of manager weekly input.
"""
import logging
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class TimesheetNagLog(Base):
    __tablename__ = "timesheet_nag_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    week_starting_date = Column(Date, nullable=False)

    # 1 = employee nagged directly, 2 = escalated to reporting manager.
    escalation_level = Column(Integer, nullable=False, default = True)
    last_nagged_at = Column(DateTime, server_default=func.now())
    resolved = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint('employee_id', 'week_starting_date', name='uq_timesheet_nag_employee_week'),
    )

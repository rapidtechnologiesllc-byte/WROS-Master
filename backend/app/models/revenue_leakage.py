"""
HRMS-0906 (Revenue Realization & Leakage Detection -- time-tracking
layer) + HRMS-0903 (Timesheet-to-Revenue Bridge Validation).

Both are monitor-and-flag layers over the real Timesheet/Invoice
schema now that Invoice (HRMS-0907) exists. HRMS-0903's own doc
describes a fuller TimesheetRevenueProcessor re-processing step this
build doesn't have (that's HRMS-0605, not built) -- reconciliation
here goes straight to flagging a gap rather than attempting an
automatic re-process first, since there's no processor to re-run.
"""
import uuid

from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class RevenueLeakageFlag(Base):
    __tablename__ = "revenue_leakage_time_layer"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    project_id = Column(String(512), ForeignKey("projects.id"), nullable=False, index=True)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    approved_hours = Column(Numeric(8, 2), nullable=False)
    invoiced_hours = Column(Numeric(8, 2), nullable=False)
    unbilled_hours = Column(Numeric(8, 2), nullable=False)

    # HRMS-0906 BR-0906-02: a populated reason suppresses this as a
    # false leakage flag (e.g. a client-negotiated cap) -- the row
    # stays for audit, but reporting queries filter it out.
    partial_billing_reason = Column(Text, nullable=True)

    detected_at = Column(DateTime, server_default=func.now())


class ReconciliationAlert(Base):
    """HRMS-0903 -- an approved timesheet with no corresponding invoice
    line item past the grace period."""
    __tablename__ = "reconciliation_alerts"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    timesheet_id = Column(String(512), ForeignKey("timesheets.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False)
    billable_hours = Column(Numeric(6, 2), nullable=False)

    gap_detected_at = Column(DateTime, server_default=func.now())
    status = Column(
        Enum("UNRESOLVED", "RESOLVED", name="reconciliation_alert_status", native_enum=False, create_constraint=True),
        nullable=False, default="UNRESOLVED",
    )

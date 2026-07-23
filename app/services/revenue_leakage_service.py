"""
HRMS-0906 (Revenue Realization & Leakage Detection) + HRMS-0903
(Timesheet-to-Revenue Bridge Validation).

Per BR-0906-01, this is the shared detection source a broader Revenue
Visibility leakage list (HRMS-0214, Domain 4 Opportunities cluster)
is specified to read from rather than reimplementing -- this module IS
that shared source.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.revenue_leakage import ReconciliationAlert, RevenueLeakageFlag
from app.models.timesheet import Timesheet

DEFAULT_LEAKAGE_GRACE_DAYS = 7   # HRMS-0906: configurable via HRMS-0115, hardcoded default here
DEFAULT_RECONCILIATION_GRACE_DAYS = 1  # HRMS-0903


def scan_project_revenue_leakage(
    db: Session, project: Project, *, period_start, period_end,
    grace_days: int = DEFAULT_LEAKAGE_GRACE_DAYS, now: Optional[datetime] = None,
) -> Optional[RevenueLeakageFlag]:
    """
    HRMS-0906: compares approved billable hours against actually-
    invoiced hours for this project+period. Only flags once the grace
    period has elapsed (never mid-period, when hours simply haven't
    been invoiced yet because the period isn't over). partial_billing_
    reason is never set here -- only via log_partial_billing_reason(),
    a separate explicit action.
    """
    now = now or datetime.utcnow()
    if now < datetime.combine(period_end, datetime.min.time()) + timedelta(days=grace_days):
        return None  # too early to flag -- not yet past the grace period

    approved_timesheets = db.query(Timesheet).join(
        EmployeeAllocation, Timesheet.allocation_id == EmployeeAllocation.id
    ).filter(
        EmployeeAllocation.project_id == project.id,
        Timesheet.week_starting_date >= period_start,
        Timesheet.week_starting_date <= period_end,
        Timesheet.status == "APPROVED",
    ).all()
    approved_hours = sum(float(ts.billable_hours) for ts in approved_timesheets)

    invoiced_hours = db.query(InvoiceLineItem).join(
        Invoice, InvoiceLineItem.invoice_id == Invoice.id
    ).filter(
        Invoice.project_id == project.id,
        Invoice.billing_period_start >= period_start,
        Invoice.billing_period_end <= period_end,
    ).with_entities(InvoiceLineItem.hours).all()
    invoiced_total = sum(float(h[0]) for h in invoiced_hours)

    unbilled = approved_hours - invoiced_total
    if unbilled <= 0:
        return None

    flag = db.query(RevenueLeakageFlag).filter(
        RevenueLeakageFlag.project_id == project.id,
        RevenueLeakageFlag.period_start == period_start,
        RevenueLeakageFlag.period_end == period_end,
    ).first()
    if flag is None:
        flag = RevenueLeakageFlag(
            tenant_id=project.tenant_id, project_id=project.id,
            period_start=period_start, period_end=period_end,
            approved_hours=approved_hours, invoiced_hours=invoiced_total, unbilled_hours=unbilled,
        )
    else:
        flag.approved_hours = approved_hours
        flag.invoiced_hours = invoiced_total
        flag.unbilled_hours = unbilled
    db.add(flag)
    return flag


def log_partial_billing_reason(db: Session, flag: RevenueLeakageFlag, *, reason: str) -> RevenueLeakageFlag:
    """HRMS-0906 BR-0906-02: a logged reason (e.g. a client-negotiated
    cap) suppresses this from being counted as real leakage."""
    flag.partial_billing_reason = reason
    db.add(flag)
    return flag


def get_active_leakage_flags(db: Session, *, tenant_id: Optional[int] = None) -> List[RevenueLeakageFlag]:
    """Only flags with no logged reason count as genuine, unresolved leakage."""
    return db.query(RevenueLeakageFlag).filter(
        RevenueLeakageFlag.tenant_id == tenant_id,
        RevenueLeakageFlag.partial_billing_reason.is_(None),
    ).all()


def find_reconciliation_gaps(
    db: Session, *, tenant_id: Optional[int] = None,
    grace_days: int = DEFAULT_RECONCILIATION_GRACE_DAYS, now: Optional[datetime] = None,
) -> List[Timesheet]:
    """
    HRMS-0903: every APPROVED timesheet past the grace period must have
    at least one InvoiceLineItem referencing it -- otherwise it's a
    reconciliation gap. No automatic re-processing attempt (HRMS-0605's
    TimesheetRevenueProcessor doesn't exist) -- goes straight to
    detection.

    tenant_id is optional (None = scan every tenant) so any pre-existing
    caller that scanned globally keeps working -- the REST endpoint
    always passes the caller's own tenant_id, since attributing another
    tenant's timesheet to a ReconciliationAlert row scoped to the
    caller's tenant would otherwise leak cross-tenant data.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=grace_days)

    query = db.query(Timesheet).filter(
        Timesheet.status == "APPROVED",
        Timesheet.approved_at.isnot(None),
        Timesheet.approved_at <= cutoff,
    )
    if tenant_id is not None:
        query = query.filter(Timesheet.tenant_id == tenant_id)
    approved = query.all()

    gaps = []
    for ts in approved:
        has_line_item = db.query(InvoiceLineItem).filter(InvoiceLineItem.timesheet_id == ts.id).first()
        if not has_line_item:
            gaps.append(ts)
    return gaps


def create_reconciliation_alert(db: Session, timesheet: Timesheet, *, tenant_id: Optional[int] = None) -> ReconciliationAlert:
    existing = db.query(ReconciliationAlert).filter(
        ReconciliationAlert.timesheet_id == timesheet.id, ReconciliationAlert.status == "UNRESOLVED",
    ).first()
    if existing:
        return existing

    alert = ReconciliationAlert(
        tenant_id=tenant_id or timesheet.tenant_id, timesheet_id=timesheet.id,
        employee_id=timesheet.employee_id, billable_hours=timesheet.billable_hours,
    )
    db.add(alert)
    return alert


def resolve_reconciliation_alert(db: Session, alert: ReconciliationAlert) -> ReconciliationAlert:
    alert.status = "RESOLVED"
    db.add(alert)
    return alert

"""
Proves HRMS-0907 (Invoice Generation/Status Tracking -- R-10 gate,
HRMS-0904 open-dispute gate, DRAFT->APPROVED->SENT->PAID lifecycle),
HRMS-0906 (Revenue Leakage detection over approved-vs-invoiced hours,
BR-0906-02 partial-billing-reason suppression), and HRMS-0903
import logging
(Timesheet-to-Revenue Reconciliation gap detection).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.employee import Employee, EmployeeEmploymentHistory
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import AllocationConflictLogEntry, BenchPeriod, BenchPoolEntry, EmployeeUtilizationMetric
from app.models.project import Project, ProjectMilestone
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.timesheet_dispute import TimesheetDispute
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.revenue_leakage import RevenueLeakageFlag, ReconciliationAlert
from app.models.user import Users

from app.services.employee_allocation_service import allocate_employee_to_project
from app.services.project_service import create_project
from app.services.timesheet_service import create_weekly_draft, upsert_entries, submit_timesheet, approve_timesheet
from app.services.timesheet_dispute_service import raise_dispute
from app.services.invoice_service import (
    generate_invoice, approve_invoice, send_invoice, mark_invoice_paid,
    UnapprovedTimesheetBlocksInvoice, OpenDisputeBlocksInvoice, InvalidInvoiceTransition,
)
from app.services.revenue_leakage_service import (
    scan_project_revenue_leakage, log_partial_billing_reason, get_active_leakage_flags,
    find_reconciliation_gaps, create_reconciliation_alert, resolve_reconciliation_alert,
    DEFAULT_LEAKAGE_GRACE_DAYS,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Employee.__table__, EmployeeEmploymentHistory.__table__, Users.__table__,
        EmployeeAllocation.__table__, Project.__table__, ProjectMilestone.__table__,
        Timesheet.__table__, TimesheetEntry.__table__, TimesheetDispute.__table__,
        Invoice.__table__, InvoiceLineItem.__table__,
        RevenueLeakageFlag.__table__, ReconciliationAlert.__table__,
        BenchPoolEntry.__table__, BenchPeriod.__table__, EmployeeUtilizationMetric.__table__, AllocationConflictLogEntry.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


@pytest.fixture()
def project_with_approved_timesheet(db_session):
    """One project, one employee, one APPROVED 40h/week timesheet at
    $100/hr ($10000 cents), the week before this one -- no invoice
    generated yet."""
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()
    project = create_project(db_session, tenant_id=tenant.id, client_id=client.id, name="Acme Rollout")
    db_session.commit()
    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, project_id=project.id,
        job_title="Sr. Guidewire Developer", required_skills='["Guidewire"]',
        min_experience_years=5.0, work_location="REMOTE", status="OPEN",
        billing_rate_usd_cents=10000,
    )
    db_session.add(demand)
    db_session.commit()
    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="BENCH",
    )
    db_session.add(employee)
    db_session.commit()
    allocation = allocate_employee_to_project(
        db_session, tenant_id=tenant.id, employee=employee, demand=demand, project=project,
    )
    db_session.commit()

    monday = _monday_of(date.today()) - timedelta(days=7)
    ts = create_weekly_draft(db_session, allocation, monday, tenant_id=tenant.id)
    db_session.commit()
    upsert_entries(db_session, ts, [
        {"entry_date": monday + timedelta(days=i), "hours": 8, "entry_type": "BILLABLE"} for i in range(5)
    ])
    submit_timesheet(db_session, ts)
    approve_timesheet(db_session, ts, approved_by="U-RM")
    db_session.commit()

    period_start = monday
    period_end = monday + timedelta(days=6)
    return tenant, client, project, employee, allocation, ts, period_start, period_end


# ---------------------------------------------------------------------------
# HRMS-0907: generate_invoice -- R-10 gate + HRMS-0904 dispute gate
# ---------------------------------------------------------------------------

def test_generate_invoice_blocked_by_unapproved_timesheet(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    ts.status = "SUBMITTED"
    db_session.commit()

    with pytest.raises(UnapprovedTimesheetBlocksInvoice):
        generate_invoice(db_session, project, period_start=period_start, period_end=period_end)


def test_generate_invoice_blocked_by_open_dispute(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    raise_dispute(db_session, ts, raised_by="CLIENT", reason="x" * 60)
    db_session.commit()

    with pytest.raises(OpenDisputeBlocksInvoice):
        generate_invoice(db_session, project, period_start=period_start, period_end=period_end)


def test_generate_invoice_creates_line_items_and_total(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet

    invoice = generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()

    assert invoice.status == "DRAFT"
    assert invoice.project_id == project.id
    assert invoice.client_id == client.id
    # 40 billable hours * $100.00/hr (10000 cents) = 400000 cents
    assert invoice.total_usd_cents == 400000

    line_items = db_session.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    assert len(line_items) == 1
    assert line_items[0].timesheet_id == ts.id
    assert float(line_items[0].hours) == 40.0


# ---------------------------------------------------------------------------
# HRMS-0907: lifecycle transitions
# ---------------------------------------------------------------------------

def test_invoice_lifecycle_draft_to_paid(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    invoice = generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()

    approve_invoice(db_session, invoice, approved_by="U-FIN")
    db_session.commit()
    assert invoice.status == "APPROVED"
    assert invoice.approved_by == "U-FIN"

    send_invoice(db_session, invoice)
    db_session.commit()
    assert invoice.status == "SENT"
    assert invoice.sent_at is not None

    mark_invoice_paid(db_session, invoice)
    db_session.commit()
    assert invoice.status == "PAID"
    assert invoice.paid_at is not None


def test_cannot_send_a_draft_invoice(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    invoice = generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()

    with pytest.raises(InvalidInvoiceTransition):
        send_invoice(db_session, invoice)


def test_cannot_approve_a_non_draft_invoice(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    invoice = generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()
    approve_invoice(db_session, invoice, approved_by="U-FIN")
    db_session.commit()

    with pytest.raises(InvalidInvoiceTransition):
        approve_invoice(db_session, invoice, approved_by="U-FIN")


def test_cannot_mark_paid_before_sent(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    invoice = generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()
    approve_invoice(db_session, invoice, approved_by="U-FIN")
    db_session.commit()

    with pytest.raises(InvalidInvoiceTransition):
        mark_invoice_paid(db_session, invoice)


# ---------------------------------------------------------------------------
# HRMS-0906: revenue leakage detection
# ---------------------------------------------------------------------------

def test_leakage_not_flagged_before_grace_period_elapses(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet

    flag = scan_project_revenue_leakage(
        db_session, project, period_start=period_start, period_end=period_end,
        now=datetime.combine(period_end, datetime.min.time()) + timedelta(days=1),
    )
    assert flag is None


def test_leakage_flagged_after_grace_period_when_unbilled(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet

    now = datetime.combine(period_end, datetime.min.time()) + timedelta(days=DEFAULT_LEAKAGE_GRACE_DAYS + 1)
    flag = scan_project_revenue_leakage(db_session, project, period_start=period_start, period_end=period_end, now=now)
    db_session.commit()

    assert flag is not None
    assert float(flag.approved_hours) == 40.0
    assert float(flag.invoiced_hours) == 0.0
    assert float(flag.unbilled_hours) == 40.0
    assert flag.partial_billing_reason is None


def test_leakage_not_flagged_once_fully_invoiced(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()

    now = datetime.combine(period_end, datetime.min.time()) + timedelta(days=DEFAULT_LEAKAGE_GRACE_DAYS + 1)
    flag = scan_project_revenue_leakage(db_session, project, period_start=period_start, period_end=period_end, now=now)
    assert flag is None


def test_partial_billing_reason_suppresses_from_active_flags(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    now = datetime.combine(period_end, datetime.min.time()) + timedelta(days=DEFAULT_LEAKAGE_GRACE_DAYS + 1)
    flag = scan_project_revenue_leakage(db_session, project, period_start=period_start, period_end=period_end, now=now)
    db_session.commit()

    assert len(get_active_leakage_flags(db_session, tenant_id=tenant.id)) == 1

    log_partial_billing_reason(db_session, flag, reason="Client-negotiated cap for this sprint.")
    db_session.commit()

    assert get_active_leakage_flags(db_session, tenant_id=tenant.id) == []
    # BR-0906-02: row persists for audit even though it's suppressed.
    assert db_session.query(RevenueLeakageFlag).count() == 1


# ---------------------------------------------------------------------------
# HRMS-0903: reconciliation gap detection
# ---------------------------------------------------------------------------

def test_reconciliation_gap_found_for_approved_uninvoiced_timesheet(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    ts.approved_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()

    gaps = find_reconciliation_gaps(db_session)
    assert ts.id in [g.id for g in gaps]


def test_no_reconciliation_gap_once_invoiced(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    ts.approved_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()
    generate_invoice(db_session, project, period_start=period_start, period_end=period_end)
    db_session.commit()

    gaps = find_reconciliation_gaps(db_session)
    assert ts.id not in [g.id for g in gaps]


def test_no_reconciliation_gap_before_grace_period(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet
    ts.approved_at = datetime.utcnow()
    db_session.commit()

    gaps = find_reconciliation_gaps(db_session, grace_days=1)
    assert ts.id not in [g.id for g in gaps]


def test_create_and_resolve_reconciliation_alert(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet

    alert = create_reconciliation_alert(db_session, ts, tenant_id=tenant.id)
    db_session.commit()
    assert alert.status == "UNRESOLVED"
    assert alert.timesheet_id == ts.id

    resolve_reconciliation_alert(db_session, alert)
    db_session.commit()
    assert alert.status == "RESOLVED"


def test_create_reconciliation_alert_is_idempotent_while_unresolved(db_session, project_with_approved_timesheet):
    tenant, client, project, employee, allocation, ts, period_start, period_end = project_with_approved_timesheet

    first = create_reconciliation_alert(db_session, ts, tenant_id=tenant.id)
    db_session.commit()
    second = create_reconciliation_alert(db_session, ts, tenant_id=tenant.id)
    db_session.commit()

    assert first.id == second.id
    assert db_session.query(ReconciliationAlert).filter(ReconciliationAlert.timesheet_id == ts.id).count() == 1

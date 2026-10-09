"""Auto-invoicing bills last month's approved timesheets with no person in the loop, and
holds anything odd for finance: unapproved weeks wait, an outsized week or total holds the
draft, a missing accounts contact holds it, and a period is never billed or emailed twice."""
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client, ClientContact
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice
from app.models.invoice_automation import InvoiceAutomationDecision
from app.models.project import Project
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs
from app.services.invoice_automation_service import run_auto_invoicing

RATE = 9000
TODAY = date(2026, 10, 3)  # bills September 2026


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def queued():
    calls = []
    with patch("app.services.thunder_mail.cadence_service.enqueue_once",
               side_effect=lambda name, tid, data, tenant, delay_seconds=0: calls.append((name, tid)) or True):
        yield calls


def _project(db, *, weeks, contact=True):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    unit = BusinessUnit(name=f"bu-{_uid()}", display_name="BU")
    db.add(unit)
    db.flush()
    client = Client(tenant_id=1, company_name=f"Client {_uid()}", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    if contact:
        db.add(ClientContact(tenant_id=1, client_id=client.id, name="AP", email=f"ap{_uid()}@client.example",
                             role_type="ACCOUNTS", is_primary=True))
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Dev", jobDescription="d", jobSkills="x", jobExperience="5",
               jobLocation="Remote")
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {_uid()}", delivery_engine="CORE")
    db.add_all([job, project])
    db.flush()
    worker = Employee(tenant_id=1, first_name="Sam", last_name="Lee", email=f"s{_uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id)
    db.add(worker)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=worker.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=RATE, status="ACTIVE",
                                    start_date=date(2025, 1, 1))
    db.add(allocation)
    db.flush()
    for week, hours, status in weeks:
        db.add(Timesheet(tenant_id=1, employee_id=worker.id, allocation_id=allocation.id, week_starting_date=week,
                         total_hours=hours, billable_hours=hours, non_billable_hours=0, status=status))
    db.commit()
    return project


def _decision(db, project):
    return db.query(InvoiceAutomationDecision).filter_by(project_id=project.id).one_or_none()


def test_clean_month_is_invoiced_approved_and_emailed_once(db, queued):
    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED"), (date(2026, 9, 14), 40, "APPROVED")])
    assert run_auto_invoicing(db, today=TODAY)["sent"] >= 1
    decision = _decision(db, project)
    invoice = db.get(Invoice, decision.invoice_id)
    assert decision.decision == "SENT" and invoice.status == "APPROVED" and invoice.total_usd_cents == 80 * RATE
    assert [q for q in queued if q[0] == "send_invoice_email"] == [("send_invoice_email", f"invoice-email-{invoice.id}-1")]
    run_auto_invoicing(db, today=TODAY)  # the next day: nothing billed or sent again
    assert db.query(Invoice).filter_by(project_id=project.id).count() == 1
    assert len([q for q in queued if q[0] == "send_invoice_email"]) == 1


def test_unapproved_week_waits_without_a_decision(db, queued):
    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED"), (date(2026, 9, 14), 40, "SUBMITTED")])
    run_auto_invoicing(db, today=TODAY)
    assert _decision(db, project) is None and db.query(Invoice).filter_by(project_id=project.id).count() == 0


@pytest.mark.parametrize("weeks, contact, reason", [
    ([(date(2026, 9, 7), 72, "APPROVED")], True, "billed 72h in one week"),
    ([(date(2026, 9, 7), 40, "APPROVED")], False, "no active ACCOUNTS contact"),
])
def test_anomalies_hold_the_draft_for_finance(db, queued, weeks, contact, reason):
    project = _project(db, weeks=weeks, contact=contact)
    run_auto_invoicing(db, today=TODAY)
    decision = _decision(db, project)
    assert decision.decision == "HELD" and reason in " ".join(decision.reasons)
    assert db.get(Invoice, decision.invoice_id).status == "DRAFT"
    assert not [q for q in queued if q[0] == "send_invoice_email"]
    assert db.query(Task).filter(Task.category == "FINANCE", Task.title.like(f"%{project.name}%")).count() == 1


def test_a_total_far_from_last_month_is_held(db, queued):
    project = _project(db, weeks=[(date(2026, 8, 3), 40, "APPROVED"), (date(2026, 9, 7), 40, "APPROVED"),
                                  (date(2026, 9, 14), 40, "APPROVED"), (date(2026, 9, 21), 40, "APPROVED")])
    run_auto_invoicing(db, today=date(2026, 9, 2))  # August: 40h
    assert _decision(db, project).decision == "SENT"
    run_auto_invoicing(db, today=TODAY)  # September: 120h, +200%
    held = db.query(InvoiceAutomationDecision).filter_by(project_id=project.id, period_start=date(2026, 9, 1)).one()
    assert held.decision == "HELD" and "changed 200%" in held.reasons[0]

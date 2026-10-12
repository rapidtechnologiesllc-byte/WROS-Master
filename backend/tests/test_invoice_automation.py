"""Auto-invoicing drafts last month's approved timesheets and gives the draft to Finance
(Senior Manager or above) to review: nothing reaches a client until such a person approves it,
and then it is emailed automatically, once. Unapproved weeks wait, anomalies are flagged on
the review task, and a period is never drafted or emailed twice."""
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
from app.services.invoice_automation_service import run_auto_invoicing, send_after_approval
from app.services.invoice_service import InvoiceApproverNotAllowed, approve_invoice, is_invoice_approver
from tests.hiring_fixtures import finance_approver

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


def _approve(db, invoice, user):
    approve_invoice(db, invoice, approved_by=user.UserID)
    db.commit()
    return send_after_approval(db, invoice, user.UserID)


def _emails(queued):
    return [q for q in queued if q[0] == "send_invoice_email"]


def _review_task(db, project):
    return db.query(Task).filter(Task.category == "FINANCE", Task.title.like(f"%{project.name}%")).one()


def test_clean_month_waits_for_finance_then_is_emailed_once(db, queued):
    approver = finance_approver(db, level=9)
    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED"), (date(2026, 9, 14), 40, "APPROVED")])
    assert run_auto_invoicing(db, today=TODAY)["awaiting"] >= 1
    decision = _decision(db, project)
    invoice = db.get(Invoice, decision.invoice_id)
    assert decision.decision == "PENDING_REVIEW" and invoice.status == "DRAFT" and invoice.total_usd_cents == 80 * RATE
    assert not _emails(queued)
    task = _review_task(db, project)
    assert task.title.startswith("Approve invoice")
    assigned = db.query(type(approver)).filter_by(UserID=task.assigned_to_user_id).one()
    assert is_invoice_approver(db, assigned)

    assert _approve(db, invoice, approver) is True
    assert _decision(db, project).decision == "SENT"
    assert _emails(queued) == [("send_invoice_email", f"invoice-email-{invoice.id}-1")]
    assert send_after_approval(db, invoice, approver.UserID) is False  # never twice
    run_auto_invoicing(db, today=TODAY)  # the next day: nothing drafted or sent again
    assert db.query(Invoice).filter_by(project_id=project.id).count() == 1 and len(_emails(queued)) == 1


@pytest.mark.parametrize("level, specialization", [(8, "Finance"), (11, "Engineering")])
def test_only_finance_senior_manager_or_above_can_approve(db, queued, level, specialization):
    from app.models.role_template import RoleTemplate

    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED")])
    run_auto_invoicing(db, today=TODAY)
    invoice = db.get(Invoice, _decision(db, project).invoice_id)
    user = finance_approver(db, level=level)
    role = db.get(RoleTemplate, user.role_template_id)
    role.specialization, role.display_name, role.name = specialization, specialization, f"{specialization}-{_uid()}"
    db.flush()
    with pytest.raises(InvoiceApproverNotAllowed):
        approve_invoice(db, invoice, approved_by=user.UserID)
    assert invoice.status == "DRAFT" and not _emails(queued)


def test_unapproved_week_waits_without_a_decision(db, queued):
    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED"), (date(2026, 9, 14), 40, "SUBMITTED")])
    run_auto_invoicing(db, today=TODAY)
    assert _decision(db, project) is None and db.query(Invoice).filter_by(project_id=project.id).count() == 0


@pytest.mark.parametrize("weeks, contact, reason", [
    ([(date(2026, 9, 7), 72, "APPROVED")], True, "billed 72h in one week"),
    ([(date(2026, 9, 7), 40, "APPROVED")], False, "no active ACCOUNTS contact"),
])
def test_anomalies_are_flagged_on_the_review_task(db, queued, weeks, contact, reason):
    project = _project(db, weeks=weeks, contact=contact)
    run_auto_invoicing(db, today=TODAY)
    decision = _decision(db, project)
    assert decision.decision == "PENDING_REVIEW" and reason in " ".join(decision.reasons)
    assert db.get(Invoice, decision.invoice_id).status == "DRAFT" and not _emails(queued)
    assert reason in _review_task(db, project).description


def test_approved_invoice_without_an_accounts_contact_is_not_sent(db, queued):
    approver = finance_approver(db)
    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED")], contact=False)
    run_auto_invoicing(db, today=TODAY)
    invoice = db.get(Invoice, _decision(db, project).invoice_id)
    assert _approve(db, invoice, approver) is False
    assert invoice.status == "APPROVED" and _decision(db, project).decision == "PENDING_REVIEW" and not _emails(queued)


def test_a_total_far_from_last_month_is_flagged(db, queued):
    approver = finance_approver(db)
    project = _project(db, weeks=[(date(2026, 8, 3), 40, "APPROVED"), (date(2026, 9, 7), 40, "APPROVED"),
                                  (date(2026, 9, 14), 40, "APPROVED"), (date(2026, 9, 21), 40, "APPROVED")])
    run_auto_invoicing(db, today=date(2026, 9, 2))  # August: 40h
    _approve(db, db.get(Invoice, _decision(db, project).invoice_id), approver)
    run_auto_invoicing(db, today=TODAY)  # September: 120h, +200%
    september = db.query(InvoiceAutomationDecision).filter_by(project_id=project.id,
                                                              period_start=date(2026, 9, 1)).one()
    assert september.decision == "PENDING_REVIEW" and "changed 200%" in september.reasons[0]


def test_approve_endpoint_refuses_anyone_but_finance_senior_manager_plus(db, queued):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app
    from app.models.role_template import RoleTemplate
    from app.models.user import Users

    project = _project(db, weeks=[(date(2026, 9, 7), 40, "APPROVED")])
    run_auto_invoicing(db, today=TODAY)
    invoice = db.get(Invoice, _decision(db, project).invoice_id)
    # org-level like the seeded Admin role, so it sees the invoice and only the Finance rule refuses it
    admin_role = RoleTemplate(tenant_id=1, name=f"admin-{_uid()}", display_name="Admin", enabled=True,
                              hierarchy_level=17, org_level_access=True)
    db.add(admin_role)
    db.flush()
    admin = Users(UserID=f"A-{_uid()}", UserName="Admin", UserEmail=f"a{_uid()}@blitzenx.com", UserPassword="x",
                  UserRole="admin", tenant_id=1, role_template_id=admin_role.id, password_reset_required=False)
    db.add(admin)
    junior = finance_approver(db, level=8)
    director = finance_approver(db, level=11)
    db.commit()

    def headers(user):
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}

    app.dependency_overrides[get_db] = lambda: db
    rbac = "app.services.role_template_permission_service.RoleTemplatePermissionService.has_permission"
    try:
        client = TestClient(app)
        url = f"/api/v1/invoices/{invoice.id}/approve"
        for user in (admin, junior):
            with patch(rbac, return_value=True):  # admin and junior hold invoices:create; only the Finance rule decides
                response = client.post(url, headers=headers(user))
            assert response.status_code == 403 and "Only Finance" in response.json()["detail"]
        assert db.get(Invoice, invoice.id).status == "DRAFT" and not _emails(queued)
        approved = client.post(url, headers=headers(director))  # its own role permission, no patch
        assert approved.status_code == 200, approved.text
        assert _decision(db, project).decision == "SENT" and len(_emails(queued)) == 1
    finally:
        app.dependency_overrides.clear()

"""Revenue chain: timesheet -> invoice -> email to client -> paid -> recognised revenue ->
line / partner / org P&L, plus the offer salary that makes cost known and the
weekly timesheet reminders."""
import uuid
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate
from app.models.client import Client, ClientContact
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice_delivery import InvoiceDelivery
from app.models.offer import Offer
from app.models.partner_incentive import PartnerIncentiveRule
from app.models.project import Project
from app.models.revenue import Revenue
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.services import invoice_service as invoices
from app.services import pnl_service
from app.services import revenue_chain_service as chain
from app.services.delivery_errors import DeliveryDeferred
from app.services.message_handlers.send_invoice_email_handler import SendInvoiceEmailHandler
from tests.hiring_fixtures import finance_approver

SEPT = (date(2026, 9, 1), date(2026, 9, 30))
RATE = 10_000  # $100/h
SALARY = 1_000_000  # $10,000/month; loaded x1.3 (10% statutory + 20% overhead)
LINE_COST = 300_006  # round(1_300_000 / 173.33 * 40)


class FakeMailbox:
    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{uuid.uuid4().hex[:8]}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html, "ref": ref}
        return mid, f"conv-{mid}", f"<{mid}@x>"

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    role = RoleTemplate(tenant_id=1, name=f"partner-{_uid()}", display_name="Partner")
    db.add(role)
    db.flush()
    partner = Users(UserID=f"P-{_uid()}", UserName="Pat Partner", UserEmail=f"pat{_uid()}@x.com",
                    UserPassword="h", UserRole="partner", tenant_id=1, role_template_id=role.id)
    db.add(partner)
    db.flush()
    unit = BusinessUnit(name=f"axion-{_uid()}", display_name="Axion", partner_user_id=partner.UserID)
    db.add(unit)
    db.flush()
    db.add(CostRateConfig(business_unit_id=unit.id, statutory_pct=10, overhead_pct=20))
    client = Client(tenant_id=1, company_name="Builders Insurance", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    db.add(ClientContact(tenant_id=1, client_id=client.id, name="AP Team", email="ap@builders.example",
                         role_type="ACCOUNTS", is_primary=True))
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Guidewire Developer", jobDescription="d",
               jobSkills="Guidewire", jobExperience="5", jobLocation="Remote")
    project = Project(tenant_id=1, client_id=client.id, name="PolicyCenter upgrade", delivery_engine="CORE")
    db.add_all([job, project])
    db.flush()
    worker = Employee(tenant_id=1, first_name="Sam", last_name="Lee", email=f"sam{_uid()}@x.com",
                      joining_date=date(2025, 1, 1), status="ALLOCATED", bu_id=unit.id, base_salary_usd_cents=SALARY)
    bench = Employee(tenant_id=1, first_name="Bo", last_name="Bench", email=f"bo{_uid()}@x.com",
                     joining_date=date(2025, 1, 1), status="BENCH", bu_id=unit.id, base_salary_usd_cents=SALARY // 2)
    db.add_all([worker, bench])
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=worker.id, client_id=client.id, demand_id=job.jobID,
                                    project_id=project.id, billing_rate_usd_cents=RATE, status="ACTIVE",
                                    start_date=date(2025, 1, 1))
    db.add(allocation)
    db.flush()
    sheets = []
    for week, status in ((date(2026, 9, 7), "APPROVED"), (date(2026, 9, 14), "APPROVED"), (date(2026, 9, 21), "SUBMITTED")):
        ts = Timesheet(tenant_id=1, employee_id=worker.id, allocation_id=allocation.id, week_starting_date=week,
                       total_hours=40, billable_hours=40, non_billable_hours=0, status=status)
        db.add(ts)
        sheets.append(ts)
    db.commit()
    return SimpleNamespace(partner=partner, unit=unit, client=client, job=job, project=project, worker=worker,
                           bench=bench, allocation=allocation, sheets=sheets)


def _invoice(db, world, status="APPROVED"):
    invoice = invoices.generate_invoice(db, world.project, period_start=date(2026, 9, 7), period_end=date(2026, 9, 14),
                                        tenant_id=1)
    db.commit()
    if status != "DRAFT":
        invoices.approve_invoice(db, invoice, approved_by=finance_approver(db).UserID)
        db.commit()
    return invoice


def _send(db, invoice, mailbox):
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        delivery = invoices.request_invoice_email(db, invoice, requested_by=None)
    message = SimpleNamespace(id="m1", payload={"invoice_id": invoice.id})
    return delivery, SendInvoiceEmailHandler.process(message, db, mailbox=mailbox)


# ---- invoice -> client -----------------------------------------------------------------

def test_invoice_bills_approved_weeks_once_and_never_twice(db, world):
    invoice = _invoice(db, world, status="DRAFT")
    assert invoice.total_usd_cents == 2 * 40 * RATE
    with pytest.raises(invoices.AlreadyInvoiced):
        invoices.generate_invoice(db, world.project, period_start=date(2026, 9, 7), period_end=date(2026, 9, 14))


def test_send_emails_the_accounts_contact_then_marks_sent_exactly_once(db, world):
    invoice = _invoice(db, world)
    mailbox = FakeMailbox()
    delivery, result = _send(db, invoice, mailbox)
    db.expire_all()
    assert result["status"] == "sent" and invoice.status == "SENT" and invoice.sent_at is not None
    assert delivery.status == "SENT" and len(mailbox.sent) == 1
    sent = next(iter(mailbox.drafts.values()))
    assert sent["to"] == "ap@builders.example" and "Builders Insurance" in sent["html"]
    assert "Sam Lee" in sent["html"] and "USD 8,000.00" in sent["html"]
    again = SendInvoiceEmailHandler.process(SimpleNamespace(id="m2", payload={"invoice_id": invoice.id}), db,
                                            mailbox=mailbox)
    assert again["status"] == "already_sent" and len(mailbox.sent) == 1


def test_crash_between_draft_and_send_sends_the_same_draft_once(db, world):
    invoice = _invoice(db, world)
    mailbox = FakeMailbox()
    with patch.object(FakeMailbox, "send", side_effect=RuntimeError("network")):
        with pytest.raises(RuntimeError):
            _send(db, invoice, mailbox)
    db.rollback()
    db.expire_all()
    assert invoice.status == "APPROVED"
    SendInvoiceEmailHandler.process(SimpleNamespace(id="m2", payload={"invoice_id": invoice.id}), db, mailbox=mailbox)
    assert len(mailbox.drafts) == 1 and len(mailbox.sent) == 1


def test_unsent_invoice_stays_approved_when_graph_is_not_configured(db, world):
    invoice = _invoice(db, world)
    with patch("app.services.thunder_mail.graph_mailbox.GraphServiceAuth.is_configured", return_value=False):
        with pytest.raises(DeliveryDeferred):
            _send(db, invoice, None)
    db.rollback()
    db.expire_all()
    assert invoice.status == "APPROVED" and invoice.sent_at is None


def test_no_accounts_contact_blocks_sending_instead_of_guessing(db, world):
    invoice = _invoice(db, world)
    db.query(ClientContact).filter_by(client_id=world.client.id).update({"is_active": False})
    with pytest.raises(invoices.MissingBillingContact):
        invoices.request_invoice_email(db, invoice, requested_by=None)
    assert invoice.status == "APPROVED"


def test_draft_invoice_cannot_be_sent(db, world):
    invoice = _invoice(db, world, status="DRAFT")
    with pytest.raises(invoices.InvalidInvoiceTransition):
        invoices.request_invoice_email(db, invoice, requested_by=None)


def test_revenue_chain_and_invoice_routes_are_mounted():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert {"/api/v1/revenue-chain/lines", "/api/v1/revenue-chain/summary", "/api/v1/revenue-chain/pnl",
            "/api/v1/invoices/{invoice_id}/send", "/api/v1/invoices/{invoice_id}/record-external-delivery"} <= paths


def test_portal_delivery_needs_a_note_and_marks_sent(db, world):
    invoice = _invoice(db, world)
    with pytest.raises(invoices.InvalidInvoiceTransition):
        invoices.record_external_delivery(db, invoice, recorded_by=None, note=" ")
    invoices.record_external_delivery(db, invoice, recorded_by=None, note="Uploaded to Ariba")
    db.commit()
    assert invoice.status == "SENT"
    assert db.query(InvoiceDelivery).filter_by(invoice_id=invoice.id).one().channel == "EXTERNAL"


# ---- paid -> recognised revenue --------------------------------------------------------

def test_paid_invoice_recognises_revenue_cost_margin_and_partner_share_once(db, world):
    db.add(PartnerIncentiveRule(tenant_id=1, partner_user_id=world.partner.UserID, incentive_type="REVENUE_SHARE",
                                revenue_share_pct=10))
    invoice = _invoice(db, world)
    invoices.record_external_delivery(db, invoice, recorded_by=None, note="portal")
    invoices.mark_invoice_paid(db, invoice, paid_at=datetime(2026, 10, 5))
    db.commit()
    rows = db.query(Revenue).filter_by(invoice_id=invoice.id).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.revenue_usd_cents == 800_000 and row.cost_usd_cents == 2 * LINE_COST
    assert row.gross_margin_usd_cents == 800_000 - 2 * LINE_COST and row.gross_margin_pct == 25
    assert row.partner_id == world.partner.UserID and row.business_type == "CORE"
    assert row.partner_revenue_share_pct == 10 and row.partner_revenue_share_usd_cents == 80_000
    assert row.recognized_at == datetime(2026, 10, 5)
    assert chain.recognize_revenue(db, invoice).id == row.id


def test_unknown_salary_records_revenue_with_unknown_cost_not_zero(db, world):
    world.worker.base_salary_usd_cents = None
    invoice = _invoice(db, world)
    invoices.record_external_delivery(db, invoice, recorded_by=None, note="portal")
    invoices.mark_invoice_paid(db, invoice)
    row = db.query(Revenue).filter_by(invoice_id=invoice.id).one()
    assert row.revenue_usd_cents == 800_000 and row.cost_usd_cents is None and row.gross_margin_usd_cents is None


# ---- the chain and the P&L -------------------------------------------------------------

def test_each_line_traces_candidate_to_cash(db, world):
    _invoice(db, world)
    lines = chain.chain_lines(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert [line["timesheet_status"] for line in lines] == ["APPROVED", "APPROVED", "SUBMITTED"]
    first = lines[0]
    assert first["employee_name"] == "Sam Lee" and first["job_title"] == "Guidewire Developer"
    assert first["project_name"] == "PolicyCenter upgrade" and first["client_name"] == "Builders Insurance"
    assert first["partner_user_id"] == world.partner.UserID and first["partner_name"] == "Pat Partner"
    assert first["billed_usd_cents"] == 400_000 and first["cost_usd_cents"] == LINE_COST
    assert first["margin_usd_cents"] == 400_000 - LINE_COST
    assert lines[2]["billed_usd_cents"] == 0 and lines[2]["pending_approval_usd_cents"] == 400_000


def test_pnl_lines_partner_and_org_all_add_up(db, world):
    _invoice(db, world)
    report = chain.pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    payroll = round(SALARY * 1.3) + round(SALARY // 2 * 1.3)
    assert report["revenue_usd_cents"] == 800_000 and report["pending_approval_usd_cents"] == 400_000
    assert report["delivery_cost_usd_cents"] == 3 * LINE_COST
    assert report["total_cost_usd_cents"] == payroll and report["cost_data_complete"] is True
    assert report["margin_usd_cents"] == 800_000 - payroll
    partner = next(r for r in report["by_partner"] if r["key"] == world.partner.UserID)
    assert partner["revenue_usd_cents"] == report["revenue_usd_cents"]
    assert partner["total_cost_usd_cents"] == report["total_cost_usd_cents"]
    by_client = {r["name"]: r for r in report["by_client"]}
    assert by_client["Builders Insurance"]["billed_usd_cents"] == 800_000


def test_missing_salary_marks_pnl_incomplete_and_names_the_employee(db, world):
    world.bench.base_salary_usd_cents = None
    db.commit()
    report = chain.pnl(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert report["cost_data_complete"] is False and report["margin_usd_cents"] is None
    assert world.bench.id in report["missing_cost_employee_ids"]


def test_line_without_project_is_flagged_as_unbillable(db, world):
    world.allocation.project_id = None
    db.commit()
    lines = chain.chain_lines(db, start=SEPT[0], end=SEPT[1], tenant_id=1)
    assert all("NO_PROJECT_CANNOT_INVOICE" in line["flags"] for line in lines)
    assert lines[0]["unbilled_usd_cents"] == 400_000


def test_summary_by_employee_and_bu_pnl_use_the_same_numbers(db, world):
    _invoice(db, world)
    rows = chain.summarize(chain.chain_lines(db, start=SEPT[0], end=SEPT[1], tenant_id=1), "employee")
    assert rows[0]["key"] == world.worker.id and rows[0]["earned_usd_cents"] == 800_000
    bu = pnl_service.get_bu_pnl(db, business_unit_id=world.unit.id, year=2026, month=9)
    report = chain.pnl(db, start=SEPT[0], end=SEPT[1])
    section = next(r for r in report["by_business_unit"] if r["key"] == world.unit.id)
    assert bu["revenue_usd_cents"] == section["revenue_usd_cents"] == 800_000
    assert bu["cost_usd_cents"] == section["total_cost_usd_cents"]


def test_payroll_is_prorated_for_a_mid_month_joiner(db, world):
    world.bench.joining_date = date(2026, 9, 16)
    db.commit()
    costs = chain.CostBook(db)
    assert costs.period(world.bench, *SEPT) == round(round(SALARY // 2 * 1.3) * 15 / 30)


# ---- offer -> employee cost, timesheet reminders -----------------------------------------

def test_accepted_offer_salary_becomes_monthly_employee_cost(db, world):
    from app.services.employee_conversion_service import monthly_salary_from_offer

    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@x.com", candidatePassword="h")
    db.add(candidate)
    db.flush()
    db.add(Offer(id=_uid(), tenant_id=1, candidate_id=candidate.candidateID, job_id=world.job.jobID,
                 created_by_user_id=world.partner.UserID, position_title="Dev", base_salary_usd_cents=12_000_000,
                 expected_start_date=date(2026, 11, 1), status="ACCEPTED", accepted_at=datetime(2026, 10, 1)))
    db.flush()
    assert monthly_salary_from_offer(db, candidate, world.job) == 1_000_000


def test_timesheet_reminders_cover_last_week_and_one_failure_does_not_stop_others(db, world):
    from app.services import timesheet_nag_service as nag

    with patch.object(nag, "trigger_timesheet_nag", side_effect=[RuntimeError("smtp"), object()]) as trigger, \
         patch.object(nag, "scan_missing_timesheets", return_value=[world.worker, world.bench]):
        result = nag.run_timesheet_nag_job(db, today=date(2026, 10, 8))
    assert result["week_starting_date"] == "2026-09-28"
    assert result["processed"] == 1 and result["failed_employee_ids"] == [world.worker.id]
    assert trigger.call_args.kwargs["week_starting_date"] == date(2026, 9, 28)

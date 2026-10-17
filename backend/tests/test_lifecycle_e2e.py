"""One employee through the whole revenue lifecycle, over the real HTTP API:

accepted offer -> convert to employee (cost from the offer) -> submit to a client job ->
client interview -> client selects -> placed (allocated to the client's project) ->
employee logs and submits a timesheet -> manager approves -> invoice generated, approved,
delivered -> payment recorded (bank transaction, PAID, revenue recognised) ->
employee logs an expense -> manager approves it -> partner P&L and org P&L show the
income, the delivery cost and the expense, and the finance/partner screens' endpoints answer.
"""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.offer_letter import OfferLetter
from app.models.project import Project
from app.models.revenue import Revenue
from app.models.tenant import Tenant
from app.models.user import Jobs, Users
from tests.hiring_fixtures import clear_hiring, finance_approver, full_access_role

TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())
RATE = 10_000  # client bill rate, $100/h
CTC_INR = 2_400_000  # offer letter annual CTC
FX = 80.0  # INR per USD -> $30,000/yr -> $2,500/month base


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
def api(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    queued = []

    def enqueue(task_name, task_id=None, data=None, **kw):
        queued.append(task_name)
        return {"status": "queued", "task_id": task_id or "t", "message_id": task_id or "t"}

    with patch("app.services.message_queue_service.MessageQueueService.enqueue", side_effect=enqueue), \
         patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True), \
         patch("app.core.config.settings.FX_INR_PER_USD", FX):
        yield TestClient(app), queued
    app.dependency_overrides.clear()


def _login(user):
    token = create_access_token({"sub": user.UserID, "type": "user", "tenant_id": user.tenant_id,
                                 "role_template_id": user.role_template_id, "email": user.UserEmail})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    admin_role = full_access_role(db)
    admin = Users(UserID=f"ADM-{_uid()}", UserName="Finance Admin", UserEmail=f"fin{_uid()}@blitzenx.com",
                  UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=admin_role.id)
    partner = Users(UserID=f"PTR-{_uid()}", UserName="Pat Partner", UserEmail=f"pat{_uid()}@blitzenx.com",
                    UserPassword="x", UserRole="partner", tenant_id=1, role_template_id=admin_role.id)
    db.add_all([admin, partner])
    db.flush()
    unit = BusinessUnit(tenant_id=1, name=f"axion-{_uid()}", display_name="Axion", partner_user_id=partner.UserID)
    db.add(unit)
    db.flush()
    db.add(CostRateConfig(business_unit_id=unit.id, statutory_pct=10, overhead_pct=20))
    client = Client(tenant_id=1, company_name="Builders Insurance", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name="PolicyCenter upgrade", delivery_engine="CORE")
    db.add(project)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, project_id=project.id, business_unit_id=unit.id,
               jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire", jobExperience="6",
               jobLocation="Remote", jobStatus="active", billing_rate_usd_cents=RATE,
               required_start_date=MONDAY - timedelta(days=14))
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"sam{_uid()}@example.com",
                          candidatePassword="x", candidateFirstName="Sam", candidateLastName="Lee", tenant_id=1,
                          total_experience_months=72, thunder_enabled=False,
                          candidateCurrentLocation="Pune, Maharashtra, India")
    db.add_all([job, candidate])
    db.flush()
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Guidewire Developer", salary="24,00,000",
                        joining_date=MONDAY - timedelta(days=30), offer_expire_date=MONDAY,
                        offer_status="Accepted", responded_at=datetime.utcnow() - timedelta(days=40))
    db.add(offer)
    db.commit()
    clear_hiring(db, candidate, offer)  # screen, L1, L2, documents, BGV
    return dict(admin=admin, partner=partner, unit=unit, client=client, project=project, job=job,
                candidate=candidate, admin_role=admin_role)


def ok(response, code=200):
    assert response.status_code == code, f"{response.request.method} {response.request.url.path}: {response.text}"
    return response.json()


def test_candidate_to_partner_and_org_pnl(db, api, world):
    client, queued = api
    admin_h = _login(world["admin"])

    # offer accepted -> employee; the offer's CTC becomes the monthly cost
    converted = client.post("/api/v1/employees/convert-candidate", headers=admin_h, json={
        "candidate_id": world["candidate"].candidateID, "employee_email": f"sam.lee{_uid()}@blitzenx.com",
        "joining_date": (MONDAY - timedelta(days=30)).isoformat(), "business_unit_id": world["unit"].id,
        "role_ids": [world["admin_role"].id],
    })
    assert converted.status_code in (200, 201), converted.text
    employee = db.query(Employee).filter_by(candidate_id=world["candidate"].candidateID).one()
    assert employee.base_salary_usd_cents == round(CTC_INR / FX * 100 / 12)
    assert employee.status == "BENCH"  # on the bench: no client yet
    db.refresh(world["candidate"])  # joined: full-time, and India from the profile location
    assert (world["candidate"].employment_type, world["candidate"].country) == ("FULLTIME", "IN")

    # Buddy Program graduated before any client (CEO 2026-10-14); the bench is where it runs
    record = ok(client.post("/api/v1/buddy-program/records", headers=admin_h, json={
        "employee_id": employee.id, "buddy_engineer_user_id": world["admin"].UserID,
        "program_start_date": (MONDAY - timedelta(days=30)).isoformat(),
        "expected_end_date": (MONDAY - timedelta(days=1)).isoformat()}))
    ok(client.post(f"/api/v1/buddy-program/records/{record['id']}/graduate", headers=admin_h,
                   json={"notes": "All KPIs met"}))
    db.refresh(employee)
    assert (employee.buddy_program_status, employee.status) == ("GRADUATED", "SPECIALITY_READY")
    # the job is on a Core project: Core certification first. No API grants it yet (who may
    # certify is with the CEO); set as the certification record would.
    employee.core_certified, employee.core_certified_date = True, MONDAY - timedelta(days=2)
    db.commit()

    # submitted to the client's job, client interviews and selects
    sub = ok(client.post("/api/v1/submissions", headers=admin_h, json={
        "demand_id": world["job"].jobID, "candidate_id": world["candidate"].candidateID}))
    for status in ("CLIENT_INTERVIEW_REQUESTED", "OFFER_EXTENDED"):
        ok(client.post(f"/api/v1/submissions/{sub['id']}/client-response", headers=admin_h,
                       json={"new_status": status, "client_feedback": "ok"}))
    # not placed until the client confirms a start date
    early = client.post(f"/api/v1/submissions/{sub['id']}/client-response", headers=admin_h,
                        json={"new_status": "PLACED", "client_feedback": "ok"})
    assert early.status_code == 409
    onboarding = [o for o in ok(client.get("/api/v1/client-onboarding", headers=admin_h)) if o["submission_id"] == sub["id"]]
    assert len(onboarding) == 1 and onboarding[0]["status"] == "PENDING"
    started = ok(client.post(f"/api/v1/client-onboarding/{onboarding[0]['id']}/confirm-start", headers=admin_h,
                             json={"confirmed_start_date": (MONDAY - timedelta(days=14)).isoformat()}))
    assert started["status"] == "STARTED" and started["allocation_id"]
    db.expire_all()
    assert employee.status == "ALLOCATED"
    allocations = ok(client.get("/api/v1/my/allocations", headers=_login(_user_of(db, employee))))["allocations"]
    assert len(allocations) == 1 and allocations[0]["project_id"] == world["project"].id

    # the employee logs this week's hours and submits; the manager approves
    emp_h = _login(_user_of(db, employee))
    sheet = ok(client.get(f"/api/v1/my/timesheet/current?allocation_id={allocations[0]['id']}", headers=emp_h))
    days = [MONDAY + timedelta(days=i) for i in range(TODAY.weekday() + 1)][:5]
    ok(client.put(f"/api/v1/my/timesheet/{sheet['id']}/entries", headers=emp_h, json={"entries": [
        {"entry_date": d.isoformat(), "hours": 8, "entry_type": "BILLABLE"} for d in days]}))
    ok(client.post(f"/api/v1/my/timesheet/{sheet['id']}/submit", headers=emp_h))
    ok(client.post(f"/api/v1/timesheets/{sheet['id']}/approve", headers=admin_h, json={}))
    hours = 8 * len(days)

    # invoice: generated from approved time, approved, delivered, paid
    invoice = ok(client.post("/api/v1/invoices/generate", headers=admin_h, json={
        "project_id": world["project"].id, "period_start": MONDAY.isoformat(),
        "period_end": (MONDAY + timedelta(days=6)).isoformat()}))
    assert invoice["total_usd_cents"] == hours * RATE
    # only Finance at Senior Manager+ approves invoices: the admin is refused, the Finance Director approves
    assert client.post(f"/api/v1/invoices/{invoice['id']}/approve", headers=admin_h).status_code == 403
    ok(client.post(f"/api/v1/invoices/{invoice['id']}/approve", headers=_login(finance_approver(db))))
    ok(client.post(f"/api/v1/invoices/{invoice['id']}/record-external-delivery", headers=admin_h,
                   json={"note": "Uploaded to client portal"}))
    paid = ok(client.post(f"/api/v1/invoices/{invoice['id']}/record-payment", headers=admin_h, json={
        "paid_on": TODAY.isoformat(), "amount_usd_cents": hours * RATE, "reference": "UTR123"}))
    assert paid["status"] == "PAID"
    assert db.query(BankTransaction).filter_by(matched_invoice_id=invoice["id"], reconciled=True).count() == 1
    revenue = db.query(Revenue).filter_by(invoice_id=invoice["id"]).one()
    assert revenue.revenue_usd_cents == hours * RATE and revenue.partner_id == world["partner"].UserID

    # the employee logs a client expense; the manager approves it
    expense = ok(client.post("/api/v1/expenses", headers=emp_h, json={
        "purpose": "CLIENT_CURRENT", "client_id": world["client"].id, "expense_category": "TRAVEL",
        "amount_usd_cents": 12_345, "expense_date": TODAY.isoformat(), "receipt_ref": "receipt-1"}), 201)
    assert client.post(f"/api/v1/expenses/{expense['id']}/manager-approve", headers=emp_h).status_code == 403
    ok(client.post(f"/api/v1/expenses/{expense['id']}/manager-approve", headers=admin_h))

    # partner P&L and org P&L: income, delivery cost, expense
    period = f"start={MONDAY.isoformat()}&end={(MONDAY + timedelta(days=6)).isoformat()}"
    report = ok(client.get(f"/api/v1/revenue-chain/pnl?{period}", headers=admin_h))
    mine = next(r for r in report["by_partner"] if r["key"] == world["partner"].UserID)
    assert mine["revenue_usd_cents"] == hours * RATE and mine["collected_usd_cents"] == hours * RATE
    assert mine["expense_cost_usd_cents"] == 12_345 and mine["delivery_cost_usd_cents"] > 0
    assert mine["total_cost_usd_cents"] == (mine["delivery_cost_usd_cents"] + mine["bench_cost_usd_cents"]
                                            + 12_345)
    assert report["revenue_usd_cents"] >= hours * RATE and report["expense_cost_usd_cents"] >= 12_345
    summary = ok(client.get(f"/api/v1/revenue-chain/summary?{period}&group_by=partner", headers=admin_h))
    assert any(r["key"] == world["partner"].UserID and r["billed_usd_cents"] == hours * RATE
               for r in summary["rows"])
    org = ok(client.get(f"/api/v1/pnl/org?year={MONDAY.year}&month={MONDAY.month}", headers=admin_h))
    assert org["total_revenue_usd_cents"] >= hours * RATE
    bu = ok(client.get(f"/api/v1/pnl/bu/{world['unit'].id}?year={MONDAY.year}&month={MONDAY.month}",
                       headers=admin_h))
    assert bu["revenue_usd_cents"] >= hours * RATE

    # the partner and CFO screens' endpoints answer
    ok(client.get(f"/api/v1/agents/partner-roi/{world['partner'].UserID}/kpis", headers=admin_h))
    ok(client.get("/api/v1/agents/cfo/financial-snapshot", headers=admin_h))
    ok(client.get("/api/v1/agents/cfo/bu-comparison", headers=admin_h))
    breakdown = ok(client.get(f"/api/v1/agents/cfo/cost-breakdown?year_month={MONDAY:%Y-%m}", headers=admin_h))
    assert breakdown["data"]["expense_cost_usd"] >= 123.45
    ok(client.get("/api/v1/bank-transactions/unreconciled", headers=admin_h))


def _user_of(db, employee):
    return db.query(Users).filter_by(UserID=employee.wros_user_id).one()


def test_allocation_to_a_job_without_a_client_is_a_clear_422(db, api, world):
    client, _ = api
    world["job"].client_id = None
    employee = Employee(buddy_program_status="GRADUATED", core_certified=True, core_certified_date=date(2026, 1, 1), tenant_id=1, first_name="B", last_name="E", email=f"b{_uid()}@x.com",
                        joining_date=TODAY - timedelta(days=60), status="ACTIVE", bu_id=world["unit"].id)
    db.add(employee)
    db.commit()
    response = client.post("/api/v1/allocations", headers=_login(world["admin"]), json={
        "employee_id": employee.id, "demand_id": world["job"].jobID})
    assert response.status_code == 422 and "no client" in response.text

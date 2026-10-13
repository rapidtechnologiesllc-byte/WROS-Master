"""Business-unit visibility, slice 3: delivery and finance operations (CEO 2026-10-12).

Employees belong to Employee.bu_id; projects, invoices and client-linked expenses to their
client's BU; an allocation (and a timesheet) to its employee's BU OR its client's BU. Partner A
must never list, open or act on BU B's records; org-level users see everything; a user always
sees their own timesheets; tasks are acted on only by their owner (or an org-level user)."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from tests.scope_fixtures import ApiClient, ids, two_bu_world, uid


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
def w(db):
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


MONDAY = date.today() - timedelta(days=date.today().weekday() + 7)


def _employee(db, bu_id, name, wros_user_id=None):
    from app.models.employee import Employee

    emp = Employee(tenant_id=1, first_name=name, last_name=uid(), email=f"{uid()}@emp.test",
                   joining_date=date(2025, 1, 1), bu_id=bu_id, wros_user_id=wros_user_id)
    db.add(emp)
    db.flush()
    return emp


def _side(db, w, bu, client, job, label):
    """One BU's delivery-to-cash chain: employee, project, allocation, timesheet, invoice,
    expense."""
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.expense import ExpenseRecord
    from app.models.invoice import Invoice
    from app.models.project import Project
    from app.models.timesheet import Timesheet

    emp = _employee(db, bu.id, f"Emp {label}")
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {label} {uid()}")
    db.add(project)
    db.flush()
    alloc = EmployeeAllocation(tenant_id=1, employee_id=emp.id, demand_id=job.jobID, client_id=client.id,
                               project_id=project.id, start_date=MONDAY - timedelta(days=30))
    db.add(alloc)
    db.flush()
    timesheet = Timesheet(tenant_id=1, employee_id=emp.id, allocation_id=alloc.id, week_starting_date=MONDAY)
    invoice = Invoice(tenant_id=1, project_id=project.id, client_id=client.id,
                      billing_period_start=MONDAY, billing_period_end=MONDAY + timedelta(days=6))
    expense = ExpenseRecord(tenant_id=1, logged_by_user_id=w.org_user.UserID, purpose="CLIENT_CURRENT",
                            client_id=client.id, expense_category="MEALS", amount_usd_cents=1000,
                            receipt_ref="r", expense_date=MONDAY)
    db.add_all([timesheet, invoice, expense])
    db.flush()
    return SimpleNamespace(employee=emp, project=project, allocation=alloc, timesheet=timesheet,
                           invoice=invoice, expense=expense)


@pytest.fixture
def chain(db, w):
    a = _side(db, w, w.bu_a, w.client_a, w.job_a, "A")
    b = _side(db, w, w.bu_b, w.client_b, w.job_b, "B")
    db.commit()
    return SimpleNamespace(a=a, b=b)


# --- employees -------------------------------------------------------------------------------

def test_employee_list_and_detail_follow_employee_bu(w, chain, api):
    mine = ids(api.get(w.partner_a, "/api/v1/employees").json())
    assert chain.a.employee.id in mine and chain.b.employee.id not in mine
    everything = ids(api.get(w.org_user, "/api/v1/employees").json())
    assert {chain.a.employee.id, chain.b.employee.id} <= everything
    assert api.get(w.partner_a, f"/api/v1/employees/{chain.b.employee.id}").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/employees/{chain.a.employee.id}").status_code == 200
    assert api.get(w.org_user, f"/api/v1/employees/{chain.b.employee.id}").status_code == 200


def test_employee_writes_stay_inside_scope(w, chain, api):
    b_emp, a_emp = chain.b.employee.id, chain.a.employee.id
    assert api.put(w.partner_a, f"/api/v1/employees/{b_emp}/organization",
                   json={"business_unit_id": w.bu_a.id}).status_code == 404
    assert api.put(w.partner_a, f"/api/v1/employees/{a_emp}/organization",
                   json={"business_unit_id": w.bu_b.id}).status_code == 403
    assert api.put(w.partner_a, f"/api/v1/employees/{b_emp}/certifications",
                   json={"guidewire_certification_current": "ACE"}).status_code == 404
    assert api.post(w.partner_a, f"/api/v1/employees/{b_emp}/mark-bench", json={"reason": "OTHER"}).status_code == 404
    created = api.post(w.partner_a, "/api/v1/employees", json={
        "first_name": "New", "last_name": "Hire", "email": f"{uid()}@emp.test",
        "joining_date": str(date.today()), "business_unit_id": w.bu_b.id})
    assert created.status_code == 403


def test_bench_cost_summary_is_scoped(w, chain, api):
    for emp in (chain.a.employee.id, chain.b.employee.id):
        assert api.post(w.org_user, f"/api/v1/employees/{emp}/mark-bench", json={"reason": "OTHER"}).status_code == 200
    mine = ids(api.get(w.partner_a, "/api/v1/employees/bench-cost-summary").json(), "employee_id")
    assert chain.a.employee.id in mine and chain.b.employee.id not in mine
    everything = ids(api.get(w.org_user, "/api/v1/employees/bench-cost-summary").json(), "employee_id")
    assert {chain.a.employee.id, chain.b.employee.id} <= everything


def test_utilization_summary_is_scoped(db, w, chain, api):
    from app.models.resource_management import EmployeeUtilizationMetric

    for emp in (chain.a.employee, chain.b.employee):
        db.add(EmployeeUtilizationMetric(tenant_id=1, employee_id=emp.id, period_start=MONDAY, utilization_pct=50,
                                         billable_hours=20, bench_hours=20))
    db.commit()
    mine = ids(api.get(w.partner_a, "/api/v1/employees/utilization-summary").json(), "employee_id")
    assert chain.a.employee.id in mine and chain.b.employee.id not in mine


# --- allocations -----------------------------------------------------------------------------

def test_allocation_list_and_end_are_scoped(w, chain, api):
    mine = ids(api.get(w.partner_a, "/api/v1/allocations").json())
    assert chain.a.allocation.id in mine and chain.b.allocation.id not in mine
    everything = ids(api.get(w.org_user, "/api/v1/allocations").json())
    assert {chain.a.allocation.id, chain.b.allocation.id} <= everything
    ended = api.post(w.partner_a, f"/api/v1/allocations/{chain.b.allocation.id}/end",
                     json={"end_date": str(date.today())})
    assert ended.status_code == 404


def test_allocation_is_visible_to_employee_bu_and_client_bu(db, w, chain, api):
    """A's employee placed at B's client: A owns the person, B owns the revenue."""
    from app.models.employee_allocation import EmployeeAllocation

    cross = EmployeeAllocation(tenant_id=1, employee_id=chain.a.employee.id, demand_id=w.job_b.jobID,
                               client_id=w.client_b.id, start_date=MONDAY, utilization_pct=10)
    db.add(cross)
    db.commit()
    assert cross.id in ids(api.get(w.partner_a, "/api/v1/allocations").json())
    assert cross.id in ids(api.get(w.partner_b, "/api/v1/allocations").json())


def test_allocation_dropdowns_offer_only_in_scope_records(w, chain, api):
    body = api.get(w.partner_a, "/api/v1/allocations/dropdowns/for-create").json()
    employees, demands = ids(body["employees"]), ids(body["demands"])
    assert chain.a.employee.id in employees and chain.b.employee.id not in employees
    assert w.job_a.jobID in demands and w.job_b.jobID not in demands


def test_cannot_allocate_onto_another_bus_records(w, chain, api):
    other_employee = api.post(w.partner_a, "/api/v1/allocations", json={
        "employee_id": chain.b.employee.id, "demand_id": w.job_a.jobID, "start_date": str(date.today())})
    assert other_employee.status_code == 404
    other_demand = api.post(w.partner_a, "/api/v1/allocations", json={
        "employee_id": chain.a.employee.id, "demand_id": w.job_b.jobID, "start_date": str(date.today())})
    assert other_demand.status_code == 404


# --- projects --------------------------------------------------------------------------------

def test_project_list_and_by_id_routes_are_scoped(w, chain, api):
    mine = ids(api.get(w.partner_a, "/api/v1/projects").json())
    assert chain.a.project.id in mine and chain.b.project.id not in mine
    assert {chain.a.project.id, chain.b.project.id} <= ids(api.get(w.org_user, "/api/v1/projects").json())
    b = chain.b.project.id
    for path in (f"/api/v1/projects/{b}/milestones", f"/api/v1/projects/{b}/unfilled-roles",
                 f"/api/v1/projects/{b}/expected-revenue"):
        assert api.get(w.partner_a, path).status_code == 404, path
        assert api.get(w.org_user, path).status_code == 200, path
    assert api.post(w.partner_a, f"/api/v1/projects/{b}/status", json={"status": "ON_HOLD"}).status_code == 404
    assert api.post(w.partner_a, f"/api/v1/projects/{b}/milestones",
                    json={"title": "m", "due_date": str(date.today())}).status_code == 404
    assert api.get(w.partner_a, f"/api/v1/projects/{chain.a.project.id}/milestones").status_code == 200


def test_cannot_create_project_for_another_bus_client(w, api):
    created = api.post(w.partner_a, "/api/v1/projects", json={
        "client_id": w.client_b.id, "name": "Sneaky", "billing_type": "TIME_AND_MATERIALS", "currency": "USD"})
    assert created.status_code == 404


# --- timesheets ------------------------------------------------------------------------------

def test_timesheet_list_and_by_id_routes_are_scoped(w, chain, api):
    mine = ids(api.get(w.partner_a, "/api/v1/timesheets").json())
    assert chain.a.timesheet.id in mine and chain.b.timesheet.id not in mine
    assert {chain.a.timesheet.id, chain.b.timesheet.id} <= ids(api.get(w.org_user, "/api/v1/timesheets").json())
    b = chain.b.timesheet.id
    for path in (f"/api/v1/timesheets/{b}", f"/api/v1/timesheets/{b}/anomalies", f"/api/v1/timesheets/{b}/disputes"):
        assert api.get(w.partner_a, path).status_code == 404, path
        assert api.get(w.org_user, path).status_code == 200, path
    assert api.post(w.partner_a, f"/api/v1/timesheets/{b}/submit").status_code == 404
    assert api.post(w.partner_a, f"/api/v1/timesheets/{b}/approve").status_code == 404
    assert api.put(w.partner_a, f"/api/v1/timesheets/{b}/entries", json={"entries": []}).status_code == 404
    assert api.post(w.partner_a, "/api/v1/timesheets/weekly-draft", json={
        "allocation_id": chain.b.allocation.id, "week_starting_date": str(MONDAY)}).status_code == 404


def test_user_always_sees_own_timesheet(db, w, chain, api):
    from app.models.task import Task
    from app.models.timesheet import Timesheet

    me = _employee(db, w.bu_b.id, "Me", wros_user_id=w.partner_a.UserID)
    internal = Task(tenant_id=1, title="Internal work", assigned_to_user_id=w.partner_a.UserID)
    db.add(internal)
    db.flush()
    own = Timesheet(tenant_id=1, employee_id=me.id, task_id=internal.id, week_starting_date=MONDAY)
    db.add(own)
    db.commit()
    assert own.id in ids(api.get(w.partner_a, "/api/v1/timesheets").json())
    assert api.get(w.partner_a, f"/api/v1/timesheets/{own.id}").status_code == 200


# --- invoices --------------------------------------------------------------------------------

def test_invoice_list_and_by_id_routes_are_scoped(w, chain, api):
    mine = ids(api.get(w.partner_a, "/api/v1/invoices").json())
    assert chain.a.invoice.id in mine and chain.b.invoice.id not in mine
    assert {chain.a.invoice.id, chain.b.invoice.id} <= ids(api.get(w.org_user, "/api/v1/invoices").json())
    b = chain.b.invoice.id
    assert api.get(w.partner_a, f"/api/v1/invoices/{b}").status_code == 404
    assert api.get(w.org_user, f"/api/v1/invoices/{b}").status_code == 200
    assert api.post(w.partner_a, f"/api/v1/invoices/{b}/approve").status_code == 404
    assert api.post(w.partner_a, "/api/v1/invoices/generate", json={
        "project_id": chain.b.project.id, "period_start": str(MONDAY),
        "period_end": str(MONDAY + timedelta(days=6))}).status_code == 404


# --- expenses --------------------------------------------------------------------------------

def test_expense_list_and_actions_are_scoped(db, w, chain, api):
    from app.models.expense import ExpenseRecord

    unattributed_b = ExpenseRecord(tenant_id=1, logged_by_user_id=w.org_user.UserID, purpose="CONFERENCE",
                                   business_unit_id=w.bu_b.id, expense_category="MEALS", amount_usd_cents=5,
                                   receipt_ref="r", expense_date=MONDAY)
    db.add(unattributed_b)
    db.commit()
    mine = ids(api.get(w.partner_a, "/api/v1/expenses").json())
    assert chain.a.expense.id in mine
    assert chain.b.expense.id not in mine and unattributed_b.id not in mine
    everything = ids(api.get(w.org_user, "/api/v1/expenses").json())
    assert {chain.a.expense.id, chain.b.expense.id, unattributed_b.id} <= everything
    assert api.post(w.partner_a, f"/api/v1/expenses/{chain.b.expense.id}/approve").status_code == 404
    assert api.post(w.partner_a, f"/api/v1/expenses/{chain.b.expense.id}/manager-approve").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/clients/{w.client_b.id}/investment-position").status_code == 404
    assert api.get(w.partner_a, f"/api/v1/clients/{w.client_a.id}/investment-position").status_code == 200


# --- tasks / timeline ------------------------------------------------------------------------

def test_tasks_are_acted_on_by_their_owner_only(db, w, api):
    from app.models.task import Task

    task = Task(tenant_id=1, title="B's task", assigned_to_user_id=w.partner_b.UserID,
                created_by_user_id=w.partner_b.UserID)
    db.add(task)
    db.commit()
    assert api.get(w.partner_a, f"/api/v1/tasks/{task.id}/updates").status_code == 404
    assert api.post(w.partner_a, f"/api/v1/tasks/{task.id}/complete").status_code == 404
    assert api.post(w.partner_a, f"/api/v1/tasks/{task.id}/confirm-urgent").status_code == 404
    assert api.get(w.partner_b, f"/api/v1/tasks/{task.id}/updates").status_code == 200
    assert api.get(w.org_user, f"/api/v1/tasks/{task.id}/updates").status_code == 200


def test_activity_timeline_follows_the_entity(w, chain, api):
    for entity_type, a_id, b_id in (("client", w.client_a.id, w.client_b.id),
                                    ("employee", chain.a.employee.id, chain.b.employee.id),
                                    ("job", w.job_a.jobID, w.job_b.jobID)):
        assert api.get(w.partner_a, f"/api/v1/activity-timeline/{entity_type}/{b_id}").status_code == 404
        assert api.get(w.partner_a, f"/api/v1/activity-timeline/{entity_type}/{a_id}").status_code == 200
        assert api.get(w.org_user, f"/api/v1/activity-timeline/{entity_type}/{b_id}").status_code == 200

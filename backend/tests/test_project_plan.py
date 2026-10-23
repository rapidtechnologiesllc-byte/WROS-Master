"""Projects carry a plan (CEO 2026-10-23, delivery accuracy): start/end dates, billing type and a
project manager, set on create and editable (PATCH /projects/{id}). The dates make the fixed-bid
burn rate computable, and the expected-revenue estimate costs people at the same loaded cost the
P&L uses (revenue_chain_service.CostBook), so the two margins never disagree."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.opportunity import Opportunity
from app.models.project import BILLING_TYPES, Project
from app.services import project_service
from app.services.client_revenue_dashboard_service import get_client_revenue_dashboard
from app.services.revenue_chain_service import CostBook
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
    world = two_bu_world(db)
    world.client_a.line_type = "CORE"
    world.client_b.line_type = "CORE"
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    with patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}) as enqueue:
        client.enqueue = enqueue
        yield client
    client.close()


def _project(db, client, **kw):
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {uid()}", delivery_engine="CORE", **kw)
    db.add(project)
    db.commit()
    return project


# --- create and edit -----------------------------------------------------------------------

def test_create_takes_dates_billing_type_and_manager(w, api):
    res = api.post(w.org_user, "/api/v1/projects", json={
        "client_id": w.client_a.id, "name": "ClaimCenter rollout", "currency": "USD", "business_type": "PROJECT",
        "billing_type": "FIXED_BID", "start_date": "2026-01-01", "end_date": "2026-12-31",
        "manager_user_id": w.partner_a.UserID})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["billing_type"] == "FIXED_BID"
    assert (body["start_date"], body["end_date"]) == ("2026-01-01", "2026-12-31")
    assert body["manager_user_id"] == w.partner_a.UserID and body["manager_name"] == "Partner A"
    # the queue is told which tenant the project belongs to (never guessed from "the only tenant")
    assert api.enqueue.call_args.kwargs["tenant_id"] == 1


@pytest.mark.parametrize("change, message", [
    ({"billing_type": "RETAINER"}, "billing_type must be one of"),
    ({"start_date": "2026-06-01", "end_date": "2026-05-01"}, "is before start_date"),
    ({"manager_user_id": "U-nobody"}, "not an active user"),
])
def test_create_rejects_an_invalid_plan(w, api, change, message):
    res = api.post(w.org_user, "/api/v1/projects", json={
        "client_id": w.client_a.id, "name": "Bad plan", "currency": "USD", "business_type": "PROJECT", **change})
    assert res.status_code == 400 and message in res.json()["detail"]


def test_patch_edits_and_clears_the_plan(db, w, api):
    project = _project(db, w.client_a)
    res = api.patch(w.org_user, f"/api/v1/projects/{project.id}", json={
        "name": "  Renamed  ", "start_date": "2026-02-01", "end_date": "2026-08-31", "billing_type": "FIXED_BID",
        "manager_user_id": w.partner_a.UserID})
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Renamed" and res.json()["billing_type"] == "FIXED_BID"

    # only the fields sent change; null clears a date or the manager
    res = api.patch(w.org_user, f"/api/v1/projects/{project.id}", json={"end_date": None, "manager_user_id": None})
    body = res.json()
    assert body["start_date"] == "2026-02-01" and body["end_date"] is None and body["manager_user_id"] is None
    assert body["name"] == "Renamed" and body["billing_type"] == "FIXED_BID"
    assert api.get(w.org_user, f"/api/v1/projects/{project.id}").json()["start_date"] == "2026-02-01"


@pytest.mark.parametrize("change, message", [
    ({"name": None}, "cannot be empty"),
    ({"billing_type": None}, "cannot be cleared"),
    ({"billing_type": "RETAINER"}, "billing_type must be one of"),
    ({"end_date": "2025-01-01"}, "is before start_date"),
    ({"manager_user_id": "U-nobody"}, "not an active user"),
])
def test_patch_rejects_an_invalid_change_and_keeps_the_project(db, w, api, change, message):
    project = _project(db, w.client_a, start_date=date(2026, 1, 1))
    res = api.patch(w.org_user, f"/api/v1/projects/{project.id}", json=change)
    assert res.status_code == 400 and message in res.json()["detail"]
    assert api.get(w.org_user, f"/api/v1/projects/{project.id}").json()["billing_type"] == "TIME_AND_MATERIALS"


def test_a_terminated_user_cannot_be_the_manager(db, w, api):
    from datetime import datetime

    w.partner_b.terminated_at = datetime.utcnow()
    db.commit()
    project = _project(db, w.client_a)
    res = api.patch(w.org_user, f"/api/v1/projects/{project.id}", json={"manager_user_id": w.partner_b.UserID})
    assert res.status_code == 400


def test_get_and_patch_are_scoped_to_the_callers_business_units(db, w, api):
    theirs = _project(db, w.client_b)
    assert api.get(w.partner_a, f"/api/v1/projects/{theirs.id}").status_code == 404
    assert api.patch(w.partner_a, f"/api/v1/projects/{theirs.id}", json={"name": "x"}).status_code == 404
    assert api.get(w.org_user, f"/api/v1/projects/{theirs.id}").status_code == 200


def test_options_come_from_the_backend_lists(w, api):
    options = api.get(w.org_user, "/api/v1/projects/options").json()
    assert options["billing_types"] == list(BILLING_TYPES)
    assert options["status_transitions"]["ACTIVE"] == sorted(project_service.PROJECT_STATUS_TRANSITIONS["ACTIVE"])
    assert options["currencies_by_engine"]["CORE"] == ["USD"]
    assert {w.partner_a.UserID, w.org_user.UserID} <= ids(options, "user_id")


def test_status_transition_and_milestones_are_saved(db, w, api):
    """These routes used to answer without committing: the transition was lost and creating a
    milestone failed."""
    project = _project(db, w.client_a)
    assert api.post(w.org_user, f"/api/v1/projects/{project.id}/status", json={"status": "ON_HOLD"}).status_code == 200
    db.expire_all()
    assert db.query(Project).get(project.id).status == "ON_HOLD"

    created = api.post(w.org_user, f"/api/v1/projects/{project.id}/milestones",
                       json={"title": "UAT", "due_date": "2026-03-01"})
    assert created.status_code == 200, created.text
    done = api.post(w.org_user, f"/api/v1/projects/{project.id}/milestones/{created.json()['id']}/complete",
                    json={"completion_date": "2026-03-04"})
    assert done.status_code == 200 and done.json()["delay_days"] == 3
    milestones = api.get(w.org_user, f"/api/v1/projects/{project.id}/milestones").json()["milestones"]
    assert [m["is_complete"] for m in milestones] == ["COMPLETE"]


# --- burn rate: dates + FIXED_BID -> computable ----------------------------------------------

def test_fixed_bid_burn_rate_is_computable_once_dates_are_set(db, w, api):
    opportunity = Opportunity(tenant_id=1, client_id=w.client_a.id, stage="CONTRACT",
                              revenue_value_usd_cents=1_000_000, currency="USD")
    db.add(opportunity)
    db.flush()
    project = _project(db, w.client_a, opportunity_id=opportunity.id)
    assert get_client_revenue_dashboard(db, w.client_a)["burn_rate_pct"] is None

    today = date.today()
    api.patch(w.org_user, f"/api/v1/projects/{project.id}", json={
        "billing_type": "FIXED_BID", "start_date": str(today - timedelta(days=50)),
        "end_date": str(today + timedelta(days=50))})
    db.expire_all()
    burn = get_client_revenue_dashboard(db, w.client_a)["burn_rate_pct"]
    assert burn is not None  # half the timeline gone, nothing earned yet
    assert burn == 0


# --- expected revenue at loaded cost ---------------------------------------------------------

def test_expected_revenue_costs_people_at_the_pnl_loaded_cost(db, w):
    db.add(CostRateConfig(business_unit_id=w.bu_a.id, statutory_pct=10, overhead_pct=20))
    employee = Employee(tenant_id=1, first_name="Sam", last_name=uid(), email=f"{uid()}@x.test",
                        joining_date=date(2025, 1, 1), bu_id=w.bu_a.id, base_salary_usd_cents=1_000_000)
    db.add(employee)
    db.flush()
    project = _project(db, w.client_a)
    now = date(2026, 1, 5)
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=w.client_a.id, demand_id=w.job_a.jobID,
                              project_id=project.id, billing_rate_usd_cents=10_000, status="ACTIVE",
                              start_date=date(2025, 6, 1), end_date=now + timedelta(days=70)))
    db.commit()

    result = project_service.calculate_project_expected_revenue(db, project, now=now)
    hours = settings.STANDARD_DAILY_HOURS * 70 * 5 / 7
    hourly = CostBook(db).hourly(employee, now)
    assert hourly == pytest.approx(1_300_000 / settings.STANDARD_MONTHLY_HOURS)  # salary x 1.3, not raw salary
    assert result["expected_revenue_usd_cents"] == round(10_000 * hours)
    assert result["margin_usd_cents"] == round(10_000 * hours - hourly * hours)
    assert result["margin_indicator"] == "HEALTHY"  # $100 bill vs ~$75 loaded cost: 25% margin


def test_expected_revenue_without_cost_config_is_insufficient_not_zero(db, w):
    employee = Employee(tenant_id=1, first_name="Ana", last_name=uid(), email=f"{uid()}@x.test",
                        joining_date=date(2025, 1, 1), bu_id=w.bu_b.id, base_salary_usd_cents=1_000_000)
    db.add(employee)
    db.flush()
    project = _project(db, w.client_b)
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=w.client_b.id, demand_id=w.job_b.jobID,
                              project_id=project.id, billing_rate_usd_cents=10_000, status="ACTIVE",
                              start_date=date(2025, 6, 1), end_date=date.today() + timedelta(days=30)))
    db.commit()
    result = project_service.calculate_project_expected_revenue(db, project)
    assert result["margin_usd_cents"] is None and result["margin_indicator"] == "INSUFFICIENT_DATA"


def test_expected_revenue_counts_only_the_span_still_ahead(db, w):
    """An allocation that starts in the future is estimated from its start, not from today."""
    db.add(CostRateConfig(business_unit_id=w.bu_a.id, statutory_pct=0, overhead_pct=0))
    employee = Employee(tenant_id=1, first_name="Li", last_name=uid(), email=f"{uid()}@x.test",
                        joining_date=date(2025, 1, 1), bu_id=w.bu_a.id, base_salary_usd_cents=500_000)
    db.add(employee)
    db.flush()
    project = _project(db, w.client_a)
    now = date(2026, 1, 5)
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=w.client_a.id, demand_id=w.job_a.jobID,
                              project_id=project.id, billing_rate_usd_cents=7_000, status="ACTIVE",
                              start_date=now + timedelta(days=28), end_date=now + timedelta(days=98)))
    db.commit()
    result = project_service.calculate_project_expected_revenue(db, project, now=now)
    assert result["expected_revenue_usd_cents"] == round(7_000 * settings.STANDARD_DAILY_HOURS * 70 * 5 / 7)



def test_winning_an_opportunity_with_an_unknown_billing_type_is_a_400(db, w, api):
    opportunity = Opportunity(tenant_id=1, client_id=w.client_a.id, stage="NEGOTIATION",
                              revenue_value_usd_cents=500_000, currency="USD")
    db.add(opportunity)
    db.commit()
    res = api.post(w.org_user, f"/api/v1/opportunities/{opportunity.id}/transition",
                   json={"new_stage": "CONTRACT", "billing_type": "RETAINER"})
    assert res.status_code == 400 and "billing_type must be one of" in res.json()["detail"]
    assert db.query(Project).filter(Project.opportunity_id == opportunity.id).count() == 0

"""Editing an employee from the Employees drawer (CEO 2026-10-24): details, employment changes
(notice, exit, leave) with their consequences, and the Hire-Train-Deploy track.

Every call goes through the real API as a signed-in user on the test's rolled-back transaction.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.resource_management import BenchPoolEntry
from app.models.user import Users
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def world(db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    unit = factories.business_unit(db)
    client = Client(tenant_id=1, company_name=f"Client {factories.uid()}", business_unit_id=unit.id,
                    payment_terms_days=30)
    db.add(client)
    db.flush()
    job = factories.job(db, client_id=client.id, business_unit_id=unit.id, jobTitle="Guidewire Developer")
    project = Project(tenant_id=1, client_id=client.id, name="PolicyCenter upgrade", delivery_engine="CORE")
    db.add(project)
    db.flush()
    employee = factories.employee(db, first_name="Sam", last_name="Lee", status="BENCH", bu_id=unit.id,
                                  buddy_program_status="GRADUATED")
    db.commit()
    return SimpleNamespace(admin=admin, unit=unit, job=job, project=project, employee=employee)


def _allocate(api, world):
    response = api.post(world.admin, "/api/v1/allocations", json={
        "employee_id": world.employee.id, "demand_id": world.job.jobID, "project_id": world.project.id,
        "utilization_pct": 100.0, "start_date": "2026-10-01"})
    assert response.status_code == 200, response.text
    return response.json()


def _change(api, world, **body):
    return api.post(world.admin, f"/api/v1/employees/{world.employee.id}/employment", json=body)


# --- details ---------------------------------------------------------------------------------

def test_details_edit_name_title_location_and_email(api, world):
    response = api.patch(world.admin, f"/api/v1/employees/{world.employee.id}", json={
        "first_name": " Samuel ", "current_title": "Senior Engineer", "work_location": "HYBRID",
        "email": "samuel.lee@example.com"})
    assert response.status_code == 200, response.text
    item = response.json()
    assert (item["first_name"], item["current_title"], item["work_location"], item["email"]) == \
        ("Samuel", "Senior Engineer", "HYBRID", "samuel.lee@example.com")


def test_details_refuse_blank_name_unknown_location_and_duplicate_email(api, world, db):
    other = factories.employee(db, email="taken@example.com")
    db.commit()
    url = f"/api/v1/employees/{world.employee.id}"
    assert api.patch(world.admin, url, json={"last_name": "  "}).status_code == 400
    assert api.patch(world.admin, url, json={"work_location": "MOON"}).status_code == 400
    assert api.patch(world.admin, url, json={"email": other.email}).status_code == 409


def test_email_of_someone_with_a_login_changes_in_users_and_access(api, world, db):
    login = factories.user(db)
    db.query(Employee).filter(Employee.id == world.employee.id).update({Employee.wros_user_id: login.UserID})
    db.commit()
    response = api.patch(world.admin, f"/api/v1/employees/{world.employee.id}", json={"email": "new@example.com"})
    assert response.status_code == 409
    assert "Users & Access" in response.json()["detail"]


def test_edit_options_come_from_the_model(api, world):
    options = api.get(world.admin, "/api/v1/employees/edit-options").json()
    assert "HYBRID" in options["work_locations"] and options["htd_phases"][0] == "INDUCTION"


# --- employment ------------------------------------------------------------------------------

def test_notice_period_records_the_last_day_and_keeps_the_deployment(api, world):
    _allocate(api, world)
    last_day = (date.today() + timedelta(days=30)).isoformat()
    response = _change(api, world, action="START_NOTICE", effective_date=last_day, reason="Resigned")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["employment_status"] == "SERVING_NOTICE"
    assert item["exit_date"] == last_day
    assert item["deployment_status"] == "PROJECT"
    assert item["employment_actions"] == ["RECORD_EXIT"]


def test_notice_needs_a_future_last_day_and_a_reason(api, world):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert _change(api, world, action="START_NOTICE", effective_date=yesterday, reason="x").status_code == 400
    assert _change(api, world, action="START_NOTICE", reason="x").status_code == 400
    future = (date.today() + timedelta(days=5)).isoformat()
    assert _change(api, world, action="START_NOTICE", effective_date=future, reason=" ").status_code == 400


def test_exit_ends_allocations_closes_the_login_and_moves_them_to_past(api, world, db):
    login = factories.user(db)
    db.query(Employee).filter(Employee.id == world.employee.id).update({Employee.wros_user_id: login.UserID})
    db.commit()
    allocation = _allocate(api, world)
    response = _change(api, world, action="RECORD_EXIT", reason="Terminated")
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["employment_status"] == "TERMINATED"
    assert item["deployment_status"] is None
    assert item["exit_date"] == date.today().isoformat()
    assert item["employment_actions"] == []
    db.expire_all()
    ended = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == allocation["id"]).one()
    assert (ended.status, ended.end_date) == ("ENDED", date.today())
    assert db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == world.employee.id).first() is None
    assert db.query(Users).filter(Users.UserID == login.UserID).one().terminated_at is not None


def test_exit_from_the_bench_leaves_the_bench_pool(api, world, db):
    from app.services.resource_management_service import mark_employee_on_bench

    mark_employee_on_bench(db, db.query(Employee).filter(Employee.id == world.employee.id).one())
    db.commit()
    assert _change(api, world, action="RECORD_EXIT", reason="Let go").status_code == 200
    assert db.query(BenchPoolEntry).filter(BenchPoolEntry.employee_id == world.employee.id).first() is None


def test_exit_cannot_be_in_the_future_and_is_final(api, world):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert _change(api, world, action="RECORD_EXIT", effective_date=tomorrow, reason="x").status_code == 400
    assert _change(api, world, action="RECORD_EXIT", reason="x").status_code == 200
    assert _change(api, world, action="START_LEAVE", reason="x").status_code == 409


def test_exit_waits_for_a_pending_margin_decision(api, world, db):
    allocation = _allocate(api, world)
    db.query(EmployeeAllocation).filter(EmployeeAllocation.id == allocation["id"]).update(
        {EmployeeAllocation.status: "PENDING_MARGIN_APPROVAL"})
    db.commit()
    response = _change(api, world, action="RECORD_EXIT", reason="x")
    assert response.status_code == 400
    assert "margin approval" in response.json()["detail"]


def test_leave_and_back_returns_to_the_allocation(api, world):
    _allocate(api, world)
    on_leave = _change(api, world, action="START_LEAVE", reason="Medical").json()
    assert on_leave["employment_status"] == "ON_LEAVE"
    assert on_leave["employment_actions"] == ["END_LEAVE"]
    back = _change(api, world, action="END_LEAVE", reason="Returned").json()
    assert back["employment_status"] == "EMPLOYED"
    assert back["status"] == "ALLOCATED"


def test_unknown_action_is_refused(api, world):
    assert _change(api, world, action="PROMOTE", reason="x").status_code == 400


# --- HTD -------------------------------------------------------------------------------------

def test_htd_track_shows_as_htd_until_completed(api, world):
    url = f"/api/v1/employees/{world.employee.id}/htd"
    started = api.put(world.admin, url, json={"htd_track": True}).json()
    assert (started["htd_track"], started["htd_phase"], started["deployment_status"]) == (True, "INDUCTION", "HTD")
    assert started["htd_start_date"] == date.today().isoformat()
    done = api.put(world.admin, url, json={"htd_track": True, "htd_phase": "COMPLETED"}).json()
    assert done["deployment_status"] == "BENCH"
    off = api.put(world.admin, url, json={"htd_track": False}).json()
    # taken off: the start and end stay, they are the P&L's HTD cost window (htd_service)
    assert off["htd_track"] is False and off["htd_start_date"] == date.today().isoformat()
    assert api.put(world.admin, url, json={"htd_track": True, "htd_phase": "NAPPING"}).status_code == 400

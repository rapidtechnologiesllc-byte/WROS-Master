"""Allocation API (S-251/S-252): the four endpoints as they exist.

  POST /allocations                     allocate an employee to a client job (the demand)
  GET  /allocations                     list, optionally by employee or job
  GET  /allocations/dropdowns/for-create employees and live client jobs for the form
  POST /allocations/{id}/end            end an allocation

Every call is made as a real signed-in user through the permission matrix, on the test's
own rolled-back transaction.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.models.client import Client
from app.models.employee import Employee
from app.models.project import Project
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
    return SimpleNamespace(admin=admin, unit=unit, client=client, job=job, project=project, employee=employee)


def _allocate(api, world, **overrides):
    body = {"employee_id": world.employee.id, "demand_id": world.job.jobID, "project_id": world.project.id,
            "utilization_pct": 80.0, "role": "Senior Engineer", "start_date": "2026-10-01"}
    body.update(overrides)
    return api.post(world.admin, "/api/v1/allocations", json=body)


def test_create_allocation_bills_the_jobs_client(api, world):
    response = _allocate(api, world)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["employee_id"] == world.employee.id
    assert item["demand_id"] == world.job.jobID
    assert item["project_id"] == world.project.id
    assert item["client_id"] == world.client.id
    assert item["status"] == "ACTIVE"
    assert item["employee_name"] == "Sam Lee"


@pytest.mark.parametrize("field, detail", [
    ("employee_id", "Employee not found."),
    ("demand_id", "Demand not found."),
    ("project_id", "Project not found."),
])
def test_unknown_employee_job_or_project_is_404(api, world, field, detail):
    response = _allocate(api, world, **{field: "does-not-exist"})
    assert response.status_code == 404
    assert response.json()["detail"] == detail


def test_second_active_allocation_needs_allow_concurrent(api, world, db):
    assert _allocate(api, world, utilization_pct=50.0).status_code == 200
    second_job = factories.job(db, client_id=world.client.id, business_unit_id=world.unit.id)
    db.commit()
    assert _allocate(api, world, demand_id=second_job.jobID, utilization_pct=50.0).status_code == 409
    allowed = _allocate(api, world, demand_id=second_job.jobID, utilization_pct=50.0, allow_concurrent=True)
    assert allowed.status_code == 200, allowed.text


def test_buddy_program_in_progress_blocks_client_deployment(api, world, db):
    world.employee.buddy_program_status = "IN_PROGRESS"
    db.commit()
    assert _allocate(api, world).status_code == 409


def test_list_filters_by_employee(api, world, db):
    created = _allocate(api, world).json()
    other = factories.employee(db, status="BENCH", bu_id=world.unit.id, buddy_program_status="GRADUATED")
    db.commit()
    mine = api.get(world.admin, f"/api/v1/allocations?employee_id={world.employee.id}").json()["allocations"]
    assert [a["id"] for a in mine] == [created["id"]]
    assert api.get(world.admin, f"/api/v1/allocations?employee_id={other.id}").json()["allocations"] == []


def test_dropdowns_offer_the_employee_and_the_live_client_job(api, world):
    response = api.get(world.admin, "/api/v1/allocations/dropdowns/for-create")
    assert response.status_code == 200, response.text
    data = response.json()
    assert world.employee.id in {e["id"] for e in data["employees"]}
    job = next(d for d in data["demands"] if d["id"] == world.job.jobID)
    assert job["client_name"] == world.client.company_name


def test_end_allocation_records_the_end_date(api, world, db):
    created = _allocate(api, world).json()
    response = api.post(world.admin, f"/api/v1/allocations/{created['id']}/end", json={"end_date": "2026-12-31"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ENDED"
    assert response.json()["end_date"] == "2026-12-31"
    db.expire_all()
    assert db.get(Employee, world.employee.id).status != "ALLOCATED"


def test_ending_an_unknown_allocation_is_404(api, world):
    assert api.post(world.admin, "/api/v1/allocations/nope/end", json={}).status_code == 404


def test_allocating_needs_the_allocations_permission(api, world, db):
    nobody = factories.user(db)  # a role with no permissions
    db.commit()
    response = api.post(nobody, "/api/v1/allocations", json={"employee_id": world.employee.id,
                                                      "demand_id": world.job.jobID})
    assert response.status_code == 403

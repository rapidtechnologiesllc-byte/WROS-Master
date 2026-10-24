"""Project work is allocated to the project, not a client job (CEO 2026-10-24): the user picks the
project, the role and the bill rate; Staff Aug still picks the client job. Every downstream step
(placement rules, margin guard, edit, list, employee summary) works without a job."""
from datetime import date, timedelta

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from tests.test_allocation_api import _allocate, api, world  # noqa: F401 -- fixtures


def _project_body(world, **overrides):
    body = {"employee_id": world.employee.id, "project_id": world.project.id, "role": "Guidewire Integration Lead",
            "billing_rate_usd_cents": 12500, "start_date": "2026-10-01",
            "end_date": (date.today() + timedelta(days=200)).isoformat()}
    body.update(overrides)
    return body


def _core_certified(db, world):
    db.query(Employee).filter(Employee.id == world.employee.id).update({Employee.core_certified: True})
    db.commit()


def test_project_work_needs_no_client_job(api, world, db):
    _core_certified(db, world)
    response = api.post(world.admin, "/api/v1/allocations", json=_project_body(world))
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["demand_id"] is None and item["project_id"] == world.project.id
    assert item["client_id"] == world.client.id
    assert item["demand_job_title"] == "Guidewire Integration Lead"
    assert item["billing_rate_usd_cents"] == 12500
    db.expire_all()
    assert db.query(Employee).filter(Employee.id == world.employee.id).one().status == "ALLOCATED"
    summary = api.get(world.admin, f"/api/v1/employees/{world.employee.id}").json()
    assert [a["job_title"] for a in summary["active_allocations"]] == ["Guidewire Integration Lead"]


def test_project_work_needs_a_role_and_a_bill_rate(api, world, db):
    _core_certified(db, world)
    assert api.post(world.admin, "/api/v1/allocations", json=_project_body(world, role=" ")).status_code == 422
    assert api.post(world.admin, "/api/v1/allocations",
                    json=_project_body(world, billing_rate_usd_cents=None)).status_code == 422
    neither = _project_body(world, project_id=None)
    assert api.post(world.admin, "/api/v1/allocations", json=neither).status_code == 422


def test_the_core_certification_rule_still_applies_to_a_core_project(api, world):
    assert world.project.delivery_engine == "CORE"
    response = api.post(world.admin, "/api/v1/allocations", json=_project_body(world))
    assert response.status_code == 409
    assert "Core" in response.text


def test_a_project_allocation_can_be_extended(api, world, db):
    _core_certified(db, world)
    item = api.post(world.admin, "/api/v1/allocations", json=_project_body(world)).json()
    new_end = (date.today() + timedelta(days=400)).isoformat()
    response = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                         json={"end_date": new_end, "reason": "Phase two signed with the client"})
    assert response.status_code == 200, response.text
    assert response.json()["allocation"]["end_date"] == new_end


def test_staff_aug_still_allocates_to_the_client_job(api, world, db):
    item = _allocate(api, world).json()
    assert item["demand_id"] == world.job.jobID
    row = db.query(EmployeeAllocation).filter(EmployeeAllocation.id == item["id"]).one()
    assert row.demand_id == world.job.jobID


def test_the_form_lists_live_projects(api, world):
    dropdowns = api.get(world.admin, "/api/v1/allocations/dropdowns/for-create").json()
    project = next(p for p in dropdowns["projects"] if p["id"] == world.project.id)
    assert project["client_id"] == world.client.id and project["delivery_engine"] == "CORE"



def test_margin_preview_for_project_work(api, world):
    response = api.post(world.admin, "/api/v1/allocations/margin-preview",
                        json={"employee_id": world.employee.id, "project_id": world.project.id,
                              "role": "Lead", "billing_rate_usd_cents": 12500})
    assert response.status_code == 200, response.text
    assert "margin_check" in response.json()

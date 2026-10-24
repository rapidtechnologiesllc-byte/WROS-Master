"""The employee profile page's API (CEO 2026-10-24): one read with every section, edits per
section, the reporting line, and money only for Finance."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.employee import Employee
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _role_with(db, grants):
    """A role granting exactly these {resource: (view, edit)} (contract resources, created if missing)."""
    from app.contracts.api_contract import MODULES_AND_RESOURCES

    role = RoleTemplate(tenant_id=1, name=f"profile-{factories.uid()}", display_name="Profile", hierarchy_level=5,
                        enabled=True, org_level_access=True)
    db.add(role)
    db.flush()
    for name, (view, edit) in grants.items():
        module_name = next(m for m, names in MODULES_AND_RESOURCES.items() if name in names)
        module = db.query(Module).filter_by(name=module_name).first()
        if module is None:
            module = Module(tenant_id=1, name=module_name, display_name=module_name, enabled=True)
            db.add(module)
            db.flush()
        resource = db.query(Resource).filter_by(module_id=module.id, name=name).first()
        if resource is None:
            resource = Resource(tenant_id=1, module_id=module.id, name=name, display_name=name, enabled=True)
            db.add(resource)
            db.flush()
        db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1,
                                      can_view=view, can_edit=edit))
    db.flush()
    return role


@pytest.fixture
def world(db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    hr = factories.user(db, role_template_id=_role_with(db, {"employees": (True, True)}).id)
    unit = factories.business_unit(db)
    employee = factories.employee(db, first_name="Asha", last_name="Rao", status="BENCH", bu_id=unit.id,
                                  base_salary_usd_cents=900000, pan_number="ABCDE1234F",
                                  bank_account_number_encrypted="encrypted-blob")
    db.commit()
    return SimpleNamespace(admin=admin, hr=hr, unit=unit, employee=employee)


def _profile(api, user, world):
    response = api.get(user, f"/api/v1/employees/{world.employee.id}/profile")
    assert response.status_code == 200, response.text
    return response.json()


def test_profile_has_every_section(api, world):
    profile = _profile(api, world.admin, world)
    for section in ("personal", "job", "programs", "finance", "history", "reporting_team", "options"):
        assert section in profile
    assert profile["first_name"] == "Asha"
    assert profile["employment_status"] == "EMPLOYED" and profile["deployment_status"] == "BENCH"
    assert profile["job"]["business_unit_name"] == world.unit.name
    assert profile["origin"] is None  # not hired through a candidate record


def test_ids_are_masked_and_bank_details_never_sent(api, world):
    finance = _profile(api, world.admin, world)["finance"]
    assert finance["pan_number"] == "••••••234F"
    assert finance["bank_on_file"] is True
    assert "encrypted-blob" not in str(_profile(api, world.admin, world))


def test_salary_only_for_finance(api, world):
    assert _profile(api, world.admin, world)["finance"]["base_salary_usd_cents"] == 900000
    hr_view = _profile(api, world.hr, world)
    assert hr_view["finance"]["base_salary_usd_cents"] is None
    assert hr_view["finance"]["compensation_visible"] is False
    listed = api.get(world.hr, "/api/v1/employees").json()["employees"]
    assert all(e["base_salary_usd_cents"] is None for e in listed)


def test_personal_and_job_sections_edit(api, world):
    response = api.patch(world.hr, f"/api/v1/employees/{world.employee.id}", json={
        "legal_name": "Asha Kumari Rao", "personal_email": "Asha@Home.org", "phone": "+91 98765 43210",
        "date_of_birth": "1994-05-01", "current_address": "12 MG Road, Pune",
        "emergency_contact_name": "Ravi Rao", "emergency_contact_phone": "+91 99999 00000",
        "employment_type": "CONTRACT", "confirmation_date": "2025-07-01", "visa_status": "H1B",
        "total_experience_months": 84})
    assert response.status_code == 200, response.text
    profile = _profile(api, world.hr, world)
    assert profile["personal"]["personal_email"] == "asha@home.org"
    assert profile["personal"]["date_of_birth"] == "1994-05-01"
    assert profile["employment_type"] == "CONTRACT"
    assert profile["job"]["confirmation_date"] == "2025-07-01"
    assert profile["job"]["total_experience_months"] == 84


@pytest.mark.parametrize("body, status", [
    ({"date_of_birth": (date.today() + timedelta(days=1)).isoformat()}, 400),
    ({"personal_email": "not-an-email"}, 400),
    ({"employment_type": "VOLUNTEER"}, 400),
    ({"confirmation_date": "2020-01-01"}, 400),  # before joining (2025-01-01)
    ({"total_experience_months": -3}, 400),
    ({"joining_date": "2025-02-01"}, 409),  # already joined
])
def test_edits_are_validated(api, world, body, status):
    assert api.patch(world.hr, f"/api/v1/employees/{world.employee.id}", json=body).status_code == status


def test_money_and_ids_need_finance_edit(api, world, db):
    url = f"/api/v1/employees/{world.employee.id}"
    assert api.patch(world.hr, url, json={"base_salary_usd_cents": 1}).status_code == 403
    assert api.patch(world.hr, url, json={"pan_number": "x"}).status_code == 403
    assert api.patch(world.admin, url, json={"base_salary_usd_cents": 1000000, "pan_number": " abcde9999z "}
                     ).status_code == 200
    db.expire_all()
    row = db.query(Employee).filter(Employee.id == world.employee.id).one()
    assert (row.base_salary_usd_cents, row.pan_number) == (1000000, "ABCDE9999Z")


def test_manager_of_someone_without_a_login_is_recorded_and_shown(api, world, db):
    boss = factories.user(db, UserName="Meera Iyer")
    boss_row = factories.employee(db, wros_user_id=boss.UserID, first_name="Meera", last_name="Iyer")
    db.commit()
    response = api.put(world.hr, f"/api/v1/employees/{world.employee.id}/manager", json={"manager_user_id": boss.UserID})
    assert response.status_code == 200, response.text
    manager = _profile(api, world.hr, world)["job"]["reporting_manager"]
    assert manager == {"user_id": boss.UserID, "name": "Meera Iyer", "employee_id": boss_row.id}
    assert [m["name"] for m in _profile_of(api, world.hr, boss_row.id)["reporting_team"]] == ["Asha Rao"]


def _profile_of(api, user, employee_id):
    return api.get(user, f"/api/v1/employees/{employee_id}/profile").json()


def test_unknown_manager_is_404(api, world):
    assert api.put(world.hr, f"/api/v1/employees/{world.employee.id}/manager",
                   json={"manager_user_id": "nobody"}).status_code == 404


def test_history_lists_status_changes_newest_first(api, world):
    api.post(world.hr, f"/api/v1/employees/{world.employee.id}/employment",
             json={"action": "START_NOTICE", "effective_date": (date.today() + timedelta(days=20)).isoformat(),
                   "reason": "Resigned"})
    history = _profile(api, world.hr, world)["history"]
    assert history[0]["kind"] == "STATUS"
    assert history[0]["to"] == {"status": "NOTICE_PERIOD"} and history[0]["reason"] == "Resigned"

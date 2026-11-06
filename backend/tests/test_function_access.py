"""CEO 2026-11-06: HR and Recruitment get the access their jobs need and land on their own pages.
Colleague names on working screens need no user-admin rights, and pay stays with Finance."""
import pytest

from app.core import authority
from app.core.db_contract import LEADERSHIP_ROLES, ensure_role
from app.models.employee import Employee
from app.models.org_structure import Department
from app.models.role_template import Module, Resource, RoleTemplate
from tests.scope_fixtures import ApiClient, uid
from tests.test_expense_review_and_pnl import _logger, db, w  # noqa: F401 -- fixtures


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _person(db, w, function, home):
    """A person in the function, holding its add-on: the same code as startup creates the role."""
    spec = LEADERSHIP_ROLES[function]
    module = db.query(Module).filter_by(name="Personal", tenant_id=1).first() or \
        Module(name="Personal", display_name="Personal", tenant_id=1)
    db.add(module)
    db.flush()
    for name in [n for names in spec["permissions"].values() for n in names]:
        if db.query(Resource).filter_by(name=name).first() is None:
            db.add(Resource(module_id=module.id, name=name, display_name=name, tenant_id=1))
    db.flush()
    ensure_role(db, function, spec, 1)
    department = Department(id=f"dept-{uid()}", tenant_id=1, name=f"{function} {uid()}", active=True,
                            home_screen=home, sees_all_business_units=True)
    db.add(department)
    user = _logger(db, w)
    user.role_template_id = db.query(RoleTemplate).filter_by(name=function, tenant_id=1).one().id
    user.department_id = department.id
    db.commit()
    return user


@pytest.mark.parametrize("function,home", [("Recruitment", "recruitment"), ("HR", "workforce")])
def test_each_function_lands_on_its_page(db, w, function, home):
    assert authority.home_dashboard(db, _person(db, w, function, home)) == home


@pytest.mark.parametrize("function,home", [("Recruitment", "recruitment"), ("HR", "workforce")])
def test_they_keep_their_own_work(db, w, function, home):
    user = _person(db, w, function, home)
    for resource in ("my-tasks", "my-timesheet", "my-expenses", "my-referrals"):
        assert authority.has_permission(db, user, f"{resource}.view"), resource


@pytest.mark.parametrize("function,home", [("Recruitment", "recruitment"), ("HR", "workforce")])
def test_neither_function_holds_pay_or_admin_rights(db, w, function, home):
    user = _person(db, w, function, home)
    for resource in ("finance-operations", "revenue", "payroll", "users-access-control", "admin-settings"):
        assert not authority.has_permission(db, user, f"{resource}.view"), resource


def test_a_recruiter_can_work_recruitment_but_not_employee_records(db, w):
    user = _person(db, w, "Recruitment", "recruitment")
    for resource in ("candidates", "jobs", "interviews", "offer-letters", "submissions", "convert-to-employee"):
        assert authority.has_permission(db, user, f"{resource}.edit"), resource
    assert not authority.has_permission(db, user, "employees.view")


def test_a_recruiter_moves_the_pipeline_but_cant_make_someone_an_employee(db, w):
    user = _person(db, w, "Recruitment", "recruitment")
    assert authority.has_permission(db, user, "convert-to-employee.edit")
    assert not authority.has_permission(db, user, "convert-to-employee.create")


def test_hr_sees_an_employee_without_their_pay(db, w, api):
    hr = _person(db, w, "HR", "workforce")
    other = db.query(Employee).filter_by(wros_user_id=_logger(db, w).UserID).one()
    other.base_salary_usd_cents, other.pay_amount_cents = 1_000_000, 1_000_000
    db.commit()
    res = api.get(hr, f"/api/v1/employees/{other.id}/profile")
    assert res.status_code == 200, res.text
    finance = res.json()["finance"]
    assert finance["base_salary_usd_cents"] is None and finance["pay_amount_cents"] is None


def test_hr_cant_change_anyones_pay(db, w, api):
    hr = _person(db, w, "HR", "workforce")
    other = db.query(Employee).filter_by(wros_user_id=_logger(db, w).UserID).one()
    db.commit()
    assert api.patch(hr, f"/api/v1/employees/{other.id}", json={"pay_amount_cents": 1}).status_code == 403


def test_the_directory_names_colleagues_without_their_access(db, w, api):
    recruiter = _person(db, w, "Recruitment", "recruitment")
    res = api.get(recruiter, "/api/v1/hr/users/directory")
    assert res.status_code == 200, res.text
    row = next(u for u in res.json()["users"] if u["user_id"] == recruiter.UserID)
    assert row["user_name"] == recruiter.UserName and "role_template_id" not in row and "permission_role" not in row


def test_the_full_user_list_stays_with_user_admins(db, w, api):
    assert api.get(_person(db, w, "Recruitment", "recruitment"), "/api/v1/hr/users/all").status_code == 403


def test_a_contractor_gets_no_directory(db, w, api):
    ensure_role(db, "Contractor", LEADERSHIP_ROLES["Contractor"], 1)
    user = _logger(db, w)
    user.role_template_id = db.query(RoleTemplate).filter_by(name="Contractor", tenant_id=1).one().id
    db.commit()
    assert api.get(user, "/api/v1/hr/users/directory").status_code == 403


def test_function_names_reach_working_screens_but_changing_them_stays_with_admins(db, w, api):
    recruiter = _person(db, w, "Recruitment", "recruitment")
    assert api.get(recruiter, "/api/v1/org/departments").status_code == 200
    assert api.post(recruiter, "/api/v1/org/departments", json={"name": "Nope"}).status_code == 403

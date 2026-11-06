"""CEO 2026-11-06: most people land on their own employee page, so it has to work for them: what they are
on and what they hold, their own contact details to correct, and nothing that only others may do or see."""
from datetime import date

import pytest

from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.role_template import RoleTemplate
from tests.scope_fixtures import ApiClient, uid
from tests.test_expense_review_and_pnl import _logger, db, w  # noqa: F401 -- fixtures


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def me(db, w):
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role

    user = _logger(db, w)
    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"], 1)
    user.role_template_id = db.query(RoleTemplate).filter_by(name="Employee", tenant_id=1).one().id  # the self-service role
    db.commit()
    return user


def _record(db, user):
    return db.query(Employee).filter_by(wros_user_id=user.UserID).one()


def _profile(api, user, employee):
    res = api.get(user, f"/api/v1/employees/{employee.id}/profile")
    assert res.status_code == 200, res.text
    return res.json()


def test_their_page_shows_what_they_are_on_without_what_it_bills(db, w, me, api):
    employee = _record(db, me)
    employee.billing_rate_usd_cents = 9_000
    client = Client(tenant_id=1, company_name=f"Client {uid()}", business_unit_id=w.bu_a.id)
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name=f"Project {uid()}", delivery_engine="CORE", currency="USD")
    db.add(project)
    db.flush()
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=client.id, project_id=project.id, status="ACTIVE", role="Developer",
                              utilization_pct=100, start_date=date(2026, 1, 1), billing_rate_usd_cents=9_000))
    db.commit()
    profile = _profile(api, me, employee)
    assert profile["is_self"] is True and profile["can_view_employees"] is False
    assert profile["finance"]["billing_rate_usd_cents"] is None
    row = profile["own_allocations"][0]
    assert row["client"] == client.company_name and row["role"] == "Developer" and "billing_rate_usd_cents" not in row


def test_they_can_correct_their_own_contact_details(db, me, api):
    res = api.patch(me, "/api/v1/employees/me/details", json={"phone": " +15550100 ", "emergency_contact_name": "Sam"})
    assert res.status_code == 200, res.text
    db.expire_all()
    employee = _record(db, me)
    assert employee.phone == "+15550100" and employee.emergency_contact_name == "Sam"


@pytest.mark.parametrize("field,value", [("current_title", "CEO"), ("base_salary_usd_cents", 1), ("first_name", "X")])
def test_they_cant_change_their_job_pay_or_name(db, me, api, field, value):
    assert api.patch(me, "/api/v1/employees/me/details", json={field: value}).status_code == 403


def test_a_bad_personal_email_is_refused(me, api):
    assert api.patch(me, "/api/v1/employees/me/details", json={"personal_email": "nope"}).status_code == 400


def test_they_see_their_own_certificates_and_nobody_elses(db, w, me, api):
    assert api.get(me, f"/api/v1/employees/{_record(db, me).id}/certificates").status_code == 200
    other = _record(db, _logger(db, w))
    db.commit()
    assert api.get(me, f"/api/v1/employees/{other.id}/certificates").status_code == 404


def test_a_login_with_no_employee_record_gets_a_clear_answer(w, api):
    assert api.patch(w.org_user, "/api/v1/employees/me/details", json={"phone": "1"}).status_code in (200, 404)

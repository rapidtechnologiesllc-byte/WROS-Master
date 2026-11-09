"""CEO 2026-11-09: an employee's job title is picked from the roles (Users & Access > Manage Roles). For someone
who signs in it is their role, which sets their level and access: only those who manage Users & Access change
it, never their own, and the login and the employee record always say the same."""
from datetime import date

import pytest

from app.models.employee import Employee
from app.models.org_structure import OrgRole
from app.models.user import Users
from tests.scope_fixtures import ApiClient, uid
from tests.test_expense_review_and_pnl import _logger, db, w  # noqa: F401 -- fixtures
from tests.test_function_access import _person


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def roles(db):
    names = (f"Lead Consultant {uid()}", f"Manager {uid()}")
    for name, level in zip(names, (6, 8)):
        db.add(OrgRole(tenant_id=1, name=name, hierarchy_level=level, active=True))
    db.commit()
    return names


def _record(db, user):
    return db.query(Employee).filter_by(wros_user_id=user.UserID).one()


def _patch(api, viewer, employee, title):
    return api.patch(viewer, f"/api/v1/employees/{employee.id}", json={"current_title": title})


def test_a_title_must_be_a_role(db, w, api, roles):
    worker = Employee(tenant_id=1, first_name="No", last_name=uid(), email=f"{uid()}@x.test",
                      joining_date=date(2025, 1, 1), status="ACTIVE", bu_id=w.bu_a.id)
    db.add(worker)
    db.commit()
    assert _patch(api, w.org_user, worker, "Chief Happiness Officer").status_code == 422
    assert _patch(api, w.org_user, worker, roles[1].lower()).status_code == 200
    db.refresh(worker)
    assert worker.current_title == roles[1]  # the role's own spelling


def test_changing_the_title_of_someone_who_signs_in_changes_their_role(db, w, api, roles):
    person = _logger(db, w)
    db.commit()
    response = _patch(api, w.org_user, _record(db, person), roles[0])
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(Users, person.UserID).job_title == roles[0] and _record(db, person).current_title == roles[0]


def test_nobody_changes_their_own_role_here(db, w, api, roles):
    me = w.org_user
    if not db.query(Employee).filter_by(wros_user_id=me.UserID).first():
        db.add(Employee(tenant_id=1, first_name="Me", last_name=uid(), email=f"{uid()}@x.test",
                        joining_date=date(2025, 1, 1), status="ACTIVE", bu_id=w.bu_a.id, wros_user_id=me.UserID))
        db.commit()
    assert _patch(api, me, _record(db, me), roles[1]).status_code == 403


def test_without_access_management_a_signed_in_persons_title_is_read_only(db, w, api, roles):
    hr = _person(db, w, "HR", "workforce")  # edits employee records, not access
    person = _logger(db, w)
    db.commit()
    response = _patch(api, hr, _record(db, person), roles[0])
    assert response.status_code == 403 and "Users & Access" in response.json()["detail"]
    profile = api.get(hr, f"/api/v1/employees/{_record(db, person).id}/profile").json()
    assert profile["title_is_role"] is True and profile["can_change_title"] is False
    assert roles[0] in profile["options"]["roles"]


def test_a_role_changed_in_users_and_access_shows_on_the_employee_record(db, w, api, roles):
    person = _logger(db, w)
    db.commit()
    response = api.put(w.org_user, f"/api/v1/hr/users/{person.UserID}", json={"job_title": roles[1]})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert _record(db, person).current_title == roles[1]

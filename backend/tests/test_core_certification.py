"""Direct certification (CEO 2026-10-14): Buddy graduated + 90 approved billable Staff Aug days with
no escalation in them -> the daily sweep raises an approval task for the BU Head -> approve, or
reject through a Flash discussion that becomes follow-up tasks (that discussion runs in the Flash
bubble: tests/test_flash_conversation_api.py)."""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.business_unit import BusinessUnit, BusinessUnitLocationHead
from app.models.client import Client
from app.models.core_certification import CoreCertificationRequest
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.location import Location
from app.models.task import Task
from app.models.timesheet import Timesheet, TimesheetEntry
from app.models.user import Users
from app.services import core_certification_service as service
from tests.hiring_fixtures import full_access_role

TODAY = date(2026, 10, 14)


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
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _user(db, role, name="User"):
    user = Users(UserID=f"U-{_uid()}", UserName=name, UserEmail=f"{_uid()}@blitzenx.com", UserPassword="x",
                 UserRole="user", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(user)
    db.flush()
    return user


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


@pytest.fixture
def org(db):
    role = full_access_role(db)
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="Guidewire BU")
    company = Location(tenant_id=1, name=f"co-{_uid()}")
    db.add_all([unit, company])
    db.flush()
    head = _user(db, role, "Head")
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=head.UserID))
    staff_aug = Client(tenant_id=1, company_name=f"SA {_uid()}", line_type="SPECIALITY")
    core = Client(tenant_id=1, company_name=f"Direct {_uid()}", line_type="CORE")
    db.add_all([staff_aug, core])
    db.flush()
    db.commit()
    return type("Org", (), dict(role=role, unit=unit, company=company, head=head, staff_aug=staff_aug, core=core))


def _employee(db, org, *, buddy="GRADUATED", manager=None, login=None):
    e = Employee(tenant_id=1, first_name="Ravi", last_name=_uid(), email=f"{_uid()}@blitzenx.com",
                 joining_date=date(2025, 1, 1), status="ALLOCATED", buddy_program_status=buddy,
                 bu_id=org.unit.id, company_id=org.company.id, reporting_manager_user_id=manager,
                 wros_user_id=login)
    db.add(e)
    db.flush()
    return e


def _billable(db, employee, client, days, *, start=TODAY - timedelta(days=200), status="APPROVED"):
    """`days` weekday billable entries from `start`, on one allocation at `client`."""
    job = Demand(tenant_id=1, client_id=client.id, job_title="Role", work_location="REMOTE", status="OPEN")
    db.add(job)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id, client_id=client.id,
                                    start_date=start, status="ACTIVE")
    db.add(allocation)
    db.flush()
    day, added, sheets = start - timedelta(days=start.weekday()), 0, {}
    while added < days:
        if day.weekday() < 5 and day >= start:
            monday = day - timedelta(days=day.weekday())
            if monday not in sheets:
                sheets[monday] = Timesheet(tenant_id=1, employee_id=employee.id, allocation_id=allocation.id,
                                           week_starting_date=monday, status=status)
                db.add(sheets[monday])
                db.flush()
            db.add(TimesheetEntry(timesheet_id=sheets[monday].id, entry_date=day, hours=8, entry_type="BILLABLE"))
            added += 1
        day += timedelta(days=1)
    db.flush()
    return allocation


# --------------------------------------------------------------------------- eligibility

def test_eligibility_counts_approved_billable_staff_aug_days_only(db, org):
    e = _employee(db, org)
    _billable(db, e, org.staff_aug, 89)
    _billable(db, e, org.core, 30, start=TODAY - timedelta(days=60))  # Core days never count
    assert service.eligibility(db, e)["billable_days"] == 89 and not service.eligibility(db, e)["eligible"]
    other = _employee(db, org)
    _billable(db, other, org.staff_aug, 120, status="SUBMITTED")  # not approved
    assert service.eligibility(db, other)["billable_days"] == 0
    _billable(db, e, org.staff_aug, 1, start=TODAY - timedelta(days=5))
    assert service.eligibility(db, e)["eligible"] is True


def test_buddy_must_be_graduated(db, org):
    e = _employee(db, org, buddy="IN_PROGRESS")
    _billable(db, e, org.staff_aug, 95)
    check = service.eligibility(db, e)
    assert not check["eligible"] and "Buddy Program" in check["reasons"][0]


def test_an_escalation_restarts_the_count_even_once_resolved(db, org):
    e = _employee(db, org)
    _billable(db, e, org.staff_aug, 100, start=TODAY - timedelta(days=200))
    raised = datetime.combine(TODAY - timedelta(days=30), datetime.min.time()) + timedelta(hours=15)
    db.add(EmployeeEscalation(tenant_id=1, employee_id=e.id, reason="Client complaint", status="RESOLVED",
                              raised_at=raised))
    db.flush()
    check = service.eligibility(db, e)
    assert check["counted_from"] == raised.date() + timedelta(days=1)
    assert check["billable_days"] < 30 and not check["eligible"]  # only days after the escalation day


# --------------------------------------------------------------------------- the sweep

def test_sweep_raises_one_task_for_the_bu_head_and_is_idempotent(db, org):
    e = _employee(db, org)
    _billable(db, e, org.staff_aug, 90)
    no_head = _employee(db, org)
    no_head.company_id = None  # no BU Head resolvable
    _billable(db, no_head, org.staff_aug, 90)
    db.commit()

    result = service.run_daily_sweep(db, today=TODAY)
    assert result["requested"] == 1 and result["no_bu_head"] == 1
    request = db.query(CoreCertificationRequest).filter_by(employee_id=e.id).one()
    task = db.query(Task).filter_by(id=request.task_id).one()
    assert (request.status, request.bu_head_user_id, request.billable_days) == ("PENDING", org.head.UserID, 90)
    assert task.assigned_to_user_id == org.head.UserID and "/workforce/core-certification" in task.description
    assert task.link == f"/my-tasks?flash=core_cert:{request.id}"  # opens the decision in Flash
    assert e.core_eligible_from == TODAY

    assert service.run_daily_sweep(db, today=TODAY).get("requested", 0) == 0
    assert db.query(CoreCertificationRequest).filter_by(employee_id=e.id).count() == 1


def test_pending_request_follows_a_new_bu_head(db, org):
    e = _employee(db, org)
    _billable(db, e, org.staff_aug, 90)
    db.commit()
    service.run_daily_sweep(db, today=TODAY)
    new_head = _user(db, org.role, "New head")
    db.query(BusinessUnitLocationHead).filter_by(business_unit_id=org.unit.id).update(
        {BusinessUnitLocationHead.head_user_id: new_head.UserID})
    db.commit()
    assert service.run_daily_sweep(db, today=TODAY)["reassigned"] == 1
    request = db.query(CoreCertificationRequest).filter_by(employee_id=e.id).one()
    assert request.bu_head_user_id == new_head.UserID
    assert db.query(Task).filter_by(id=request.task_id).one().assigned_to_user_id == new_head.UserID


# --------------------------------------------------------------------------- approve / close

def _pending(db, org, **kw):
    e = _employee(db, org, **kw)
    _billable(db, e, org.staff_aug, 90)
    db.commit()
    service.run_daily_sweep(db, today=TODAY)
    return e, db.query(CoreCertificationRequest).filter_by(employee_id=e.id, status="PENDING").one()


def test_bu_head_approves_and_the_employee_is_core_certified(db, org, api):
    e, request = _pending(db, org)
    outsider = _user(db, org.role, "Outsider")
    db.commit()
    url = f"/api/v1/core-certification/requests/{request.id}/approve"
    assert api.post(url, headers=_h(outsider)).status_code == 403
    listed = api.get("/api/v1/core-certification/requests?status=PENDING", headers=_h(org.head)).json()["requests"]
    row = next(r for r in listed if r["id"] == request.id)
    assert row["can_decide"] and row["still_eligible"]

    response = api.post(url, headers=_h(org.head))
    assert response.status_code == 200, response.text
    db.refresh(e)
    assert e.core_certified and e.core_certified_date == date.today()
    assert db.query(Task).filter_by(id=request.task_id).one().status == "COMPLETED"
    assert api.post(url, headers=_h(org.head)).status_code == 409  # already decided


def test_the_bu_partner_can_decide_when_the_head_is_away(db, org, api):
    e, request = _pending(db, org)
    partner = _user(db, org.role, "Partner")
    org.unit.partner_user_id = partner.UserID
    db.commit()
    assert api.post(f"/api/v1/core-certification/requests/{request.id}/approve", headers=_h(partner)).status_code == 200


def test_no_longer_eligible_cannot_be_approved_and_is_closed(db, org, api):
    e, request = _pending(db, org)
    db.add(EmployeeEscalation(tenant_id=1, employee_id=e.id, reason="Missed client deadline"))
    db.commit()
    response = api.post(f"/api/v1/core-certification/requests/{request.id}/approve", headers=_h(org.head))
    assert response.status_code == 409 and "No longer eligible" in response.json()["detail"]
    closed = api.post(f"/api/v1/core-certification/requests/{request.id}/close", headers=_h(org.head))
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"


def test_partner_dashboard_counts_the_approved_certification(db, org):
    from app.services.training_certification_service import get_core_certified_employees

    e = _employee(db, org)
    e.core_certified, e.core_certified_date = True, TODAY
    db.flush()
    names = [row["name"] for row in get_core_certified_employees(db, org.unit.id)]
    assert f"Ravi {e.last_name}" in names


# --------------------------------------------------------------------------- set on the employee page (CEO 2026-11-09)

def _set(api, user, employee, eligible, reason=None):
    return api.put(f"/api/v1/core-certification/employees/{employee.id}", headers=_h(user),
                   json={"eligible": eligible, "reason": reason})


def test_a_bu_leader_sets_core_eligible_and_the_override_is_on_record(db, org, api):
    from app.models.employee import EmployeeEmploymentHistory

    e = _employee(db, org, buddy="IN_PROGRESS")  # the rules say not yet
    db.commit()
    response = _set(api, org.head, e, True, "Assessed on the client's Direct project")
    assert response.status_code == 200, response.text
    assert response.json()["rules_agree"] is False
    db.refresh(e)
    assert e.core_certified and e.core_certified_date == date.today()
    row = db.query(EmployeeEmploymentHistory).filter_by(employee_id=e.id, change_type="CORE_ELIGIBLE").one()
    assert row.new_value == "true" and row.changed_by == "Head"
    assert "Assessed on the client's Direct project" in row.reason and "the rules say not yet" in row.reason


def test_setting_it_closes_a_pending_request(db, org, api):
    e, request = _pending(db, org)
    assert _set(api, org.head, e, True).status_code == 200
    db.refresh(request)
    assert request.status == "APPROVED" and request.decided_by_user_id == org.head.UserID
    assert db.query(Task).filter_by(id=request.task_id).one().status == "COMPLETED"


def test_someone_who_does_not_lead_the_unit_cannot_set_it(db, org, api):
    e = _employee(db, org)
    outsider = _user(db, org.role, "Outsider")
    db.commit()
    assert _set(api, outsider, e, True).status_code == 403
    db.refresh(e)
    assert not e.core_certified


def test_someone_on_the_core_engine_cannot_be_set_to_not_eligible(db, org, api):
    e = _employee(db, org)
    e.core_certified, e.delivery_engine = True, "CORE"
    db.commit()
    response = _set(api, org.head, e, False)
    assert response.status_code == 409 and "Core engine" in response.json()["detail"]


def test_setting_the_same_value_says_so(db, org, api):
    e = _employee(db, org)
    db.commit()
    assert "Already not eligible" in _set(api, org.head, e, False).json()["detail"]


def test_the_employee_page_shows_the_flag_the_rules_and_who_may_set_it(db, org, api):
    e = _employee(db, org, buddy="IN_PROGRESS")
    db.commit()
    core = api.get(f"/api/v1/employees/{e.id}/profile", headers=_h(org.head)).json()["core"]
    assert core["eligible"] is False and core["can_set"] is True
    assert core["rules"]["eligible"] is False and any("Buddy Program" in r for r in core["rules"]["reasons"])
    outsider = _user(db, org.role, "Outsider")
    db.commit()
    assert api.get(f"/api/v1/employees/{e.id}/profile", headers=_h(outsider)).json()["core"]["can_set"] is False


def test_a_direct_pull_conflict_is_a_task_for_the_bu_head_and_closes_when_decided(db, org, monkeypatch):
    """CEO 2026-11-09: the Direct Pull screen is off the menu; each conflict is a decision task."""
    from app.core import authority
    from app.services import core_pull_service as pull

    e = _employee(db, org)
    e.core_certified = True
    allocation = _billable(db, e, org.staff_aug, 1)
    db.get(Demand, allocation.demand_id).delivery_engine = "SPECIALITY"
    wanted = Demand(tenant_id=1, client_id=org.core.id, job_title="Direct architect", work_location="REMOTE",
                    status="OPEN", delivery_engine="CORE")
    db.add(wanted)
    db.flush()
    event = pull.detect_core_pull_conflict(db, e, wanted)
    task = db.query(Task).filter_by(link=pull.decision_link(event.id)).one()
    assert task.assigned_to_user_id == org.head.UserID and task.title.startswith("Decide a Direct Pull")
    assert pull.detect_core_pull_conflict(db, e, wanted).id == event.id  # the same conflict: no second task
    assert db.query(Task).filter_by(link=pull.decision_link(event.id)).count() == 1

    monkeypatch.setattr(authority, "is_bu_leader", lambda db, user: True)
    pull.override_core_pull(db, event, actor=org.head, justification="Client renewal depends on them this quarter; moving them now would put the account at risk " * 2)
    db.refresh(task)
    assert task.status == "COMPLETED"

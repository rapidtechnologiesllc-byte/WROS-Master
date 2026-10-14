"""Core certification (CEO 2026-10-14): Buddy graduated + 90 approved billable Staff Aug days with
no escalation in them -> the daily sweep raises an approval task for the BU Head -> approve, or
reject through a Flash discussion that becomes follow-up tasks."""
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
    core = Client(tenant_id=1, company_name=f"Core {_uid()}", line_type="CORE")
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


# --------------------------------------------------------------------------- reject with Flash

def _chat(api, request, user, message):
    response = api.post(f"/api/v1/core-certification/requests/{request.id}/reject-chat", headers=_h(user),
                        json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def test_rejection_discussion_becomes_follow_up_tasks_then_a_new_review(db, org, api):
    manager = _user(db, org.role, "Manager")
    e, request = _pending(db, org, manager=manager.UserID)  # no login: 'employee' falls back to the head

    assert "Why are you not approving" in _chat(api, request, org.head, "")["reply"]
    assert "checked again" in _chat(api, request, org.head, "Client says ownership of defects is weak")["reply"]
    # two criteria in one go; the second has no days yet
    reply = _chat(api, request, org.head, "client feedback 30 days owner manager, Guidewire certification")["reply"]
    assert "'Guidewire certification'" in reply and "how many days" in reply
    summary = _chat(api, request, org.head, "45 employee")["reply"]
    assert "client feedback: re-check in 30 days, owner the reporting manager" in summary
    assert "Guidewire certification: re-check in 45 days, owner the employee (the employee has no login" in summary
    done = _chat(api, request, org.head, "yes")
    assert done["done"] and "2 follow-up task(s)" in done["reply"]

    db.refresh(request)
    assert request.status == "REJECTED" and request.rejection_reason == "Client says ownership of defects is weak"
    plan = {item["criterion"]: item for item in request.follow_up_plan}
    assert plan["client feedback"]["owner_user_id"] == manager.UserID and plan["client feedback"]["days"] == 30
    assert plan["Guidewire certification"]["owner_user_id"] == org.head.UserID
    tasks = db.query(Task).filter(Task.id.in_([i["task_id"] for i in request.follow_up_plan])).all()
    assert len(tasks) == 2 and all(t.due_date for t in tasks)
    assert request.chat_state is None

    # no new review while follow-ups are open or the longest period (45 days) has not passed
    later = TODAY + timedelta(days=50)
    assert service.run_daily_sweep(db, today=later).get("requested", 0) == 0
    for t in tasks:
        t.status = "COMPLETED"
    db.commit()
    assert service.run_daily_sweep(db, today=TODAY + timedelta(days=10)).get("requested", 0) == 0
    assert service.run_daily_sweep(db, today=later)["requested"] == 1


def test_rejection_can_be_cancelled_and_the_request_stays_pending(db, org, api):
    e, request = _pending(db, org)
    _chat(api, request, org.head, "")
    assert _chat(api, request, org.head, "cancel")["done"]
    db.refresh(request)
    assert request.status == "PENDING" and request.chat_state is None


def test_partner_dashboard_counts_the_approved_certification(db, org):
    from app.services.training_certification_service import get_core_certified_employees

    e = _employee(db, org)
    e.core_certified, e.core_certified_date = True, TODAY
    db.flush()
    names = [row["name"] for row in get_core_certified_employees(db, org.unit.id)]
    assert f"Ravi {e.last_name}" in names

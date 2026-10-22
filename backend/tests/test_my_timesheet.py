"""My Timesheet (self-service): the screen's API contract, the explicit "not linked" answer, and
the back-dating window (settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS) -- an employee can still fill
last week on a Monday."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models.demand import Demand
from app.models.employee_allocation import EmployeeAllocation
from app.models.timesheet import MAX_SUBMISSION_LOOKBACK_WEEKS, Timesheet
from app.services import employee_self_service as self_service
from tests.test_core_certification import _employee, _h, _user, api, db, org  # noqa: F401 -- fixtures


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


@pytest.fixture
def worker(db, org):
    """An allocated employee with a login, allocated since six weeks ago."""
    login = _user(db, org.role, "Worker")
    employee = _employee(db, org, login=login.UserID)
    job = Demand(tenant_id=1, client_id=org.staff_aug.id, job_title="Guidewire Dev", work_location="REMOTE",
                 status="OPEN")
    db.add(job)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id,
                                    client_id=org.staff_aug.id, start_date=date.today() - timedelta(weeks=6),
                                    status="ACTIVE")
    db.add(allocation)
    db.commit()
    return type("Worker", (), dict(login=login, employee=employee, allocation=allocation))


def test_an_unlinked_login_gets_the_reason_not_an_empty_screen(api, db, org):
    stranger = _user(db, org.role, "No Employee")
    db.commit()
    for path in ("/api/v1/my/allocations", "/api/v1/my/timesheet/weeks", "/api/v1/my/timesheet/history"):
        res = api.get(path, headers=_h(stranger))
        assert res.status_code == 404
        assert "isn't linked to an employee record" in res.json()["detail"]


def test_lists_are_wrapped_the_way_the_screen_reads_them(api, worker):
    allocations = api.get("/api/v1/my/allocations", headers=_h(worker.login)).json()
    assert [a["id"] for a in allocations["allocations"]] == [worker.allocation.id]
    weeks = api.get("/api/v1/my/timesheet/weeks", headers=_h(worker.login)).json()
    assert weeks["back_weeks"] == settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS
    assert len(weeks["weeks"]) == settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS + 1
    assert weeks["weeks"][0] == _monday(date.today()).isoformat()
    assert api.get("/api/v1/my/timesheet/history", headers=_h(worker.login)).json() == {"timesheets": []}


def test_last_week_can_be_filled_and_submitted(api, db, worker):
    last_monday = _monday(date.today()) - timedelta(weeks=1)
    with patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}):
        sheet = api.get("/api/v1/my/timesheet/current", headers=_h(worker.login),
                        params={"allocation_id": worker.allocation.id, "week_starting": last_monday.isoformat()})
        assert sheet.status_code == 200, sheet.text
        sheet = sheet.json()
        assert sheet["week_starting_date"] == last_monday.isoformat() and sheet["status"] == "DRAFT"
        entries = [{"entry_date": (last_monday + timedelta(days=i)).isoformat(), "hours": 8, "entry_type": "BILLABLE"}
                   for i in range(5)]
        saved = api.put(f"/api/v1/my/timesheet/{sheet['id']}/entries", headers=_h(worker.login),
                        json={"entries": entries})
        assert saved.status_code == 200, saved.text
        assert saved.json()["total_hours"] == 40
        submitted = api.post(f"/api/v1/my/timesheet/{sheet['id']}/submit", headers=_h(worker.login))
        assert submitted.status_code == 200, submitted.text
    assert db.get(Timesheet, sheet["id"]).status == "SUBMITTED"
    history = api.get("/api/v1/my/timesheet/history", headers=_h(worker.login)).json()["timesheets"]
    assert [h["id"] for h in history] == [sheet["id"]]
    # without a week it is still this week
    this_week = api.get("/api/v1/my/timesheet/current", headers=_h(worker.login),
                        params={"allocation_id": worker.allocation.id}).json()
    assert this_week["week_starting_date"] == _monday(date.today()).isoformat()


@pytest.mark.parametrize("week, reason", [
    (lambda m: m - timedelta(weeks=settings.TIMESHEET_SELF_SERVICE_BACK_WEEKS + 1), "week(s) back"),
    (lambda m: m + timedelta(weeks=1), "has not started yet"),
    (lambda m: m - timedelta(days=2), "not a Monday"),
])
def test_weeks_outside_the_window_are_refused(api, worker, week, reason):
    res = api.get("/api/v1/my/timesheet/current", headers=_h(worker.login),
                  params={"allocation_id": worker.allocation.id,
                          "week_starting": week(_monday(date.today())).isoformat()})
    assert res.status_code == 422 and reason in res.json()["detail"]


def test_a_week_before_the_allocation_started_is_refused(api, db, worker):
    worker.allocation.start_date = _monday(date.today())
    db.commit()
    res = api.get("/api/v1/my/timesheet/current", headers=_h(worker.login),
                  params={"allocation_id": worker.allocation.id,
                          "week_starting": (_monday(date.today()) - timedelta(weeks=1)).isoformat()})
    assert res.status_code == 422 and "outside this allocation" in res.json()["detail"]


def test_someone_elses_allocation_is_forbidden(api, db, org, worker):
    other = _user(db, org.role, "Other")
    _employee(db, org, login=other.UserID)
    db.commit()
    res = api.get("/api/v1/my/timesheet/current", headers=_h(other),
                  params={"allocation_id": worker.allocation.id})
    assert res.status_code == 403


def test_a_window_wider_than_the_submission_window_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "TIMESHEET_SELF_SERVICE_BACK_WEEKS", MAX_SUBMISSION_LOOKBACK_WEEKS + 1)
    with pytest.raises(RuntimeError, match="submission window"):
        self_service.allowed_weeks()


def test_timesheet_allocation_picker_lists_active_allocations_by_employee(api, db, org, worker):
    admin = _user(db, org.role, "Timesheet Admin")
    db.commit()
    res = api.get("/api/v1/timesheets/allocations", headers=_h(admin))
    assert res.status_code == 200, res.text
    mine = [e for e in res.json()["employees"] if e["employee_id"] == worker.employee.id]
    assert len(mine) == 1 and [a["id"] for a in mine[0]["allocations"]] == [worker.allocation.id]


def test_admin_timesheet_events_carry_the_tenant(api, db, org, worker):
    admin = _user(db, org.role, "Timesheet Admin")
    db.commit()
    with patch("app.api.v1.endpoints.timesheets.MessageQueueService.enqueue", return_value={}) as enqueue:
        res = api.post("/api/v1/timesheets/weekly-draft", headers=_h(admin),
                       json={"allocation_id": worker.allocation.id,
                             "week_starting_date": _monday(date.today()).isoformat()})
    assert res.status_code == 200, res.text
    assert enqueue.call_args.kwargs["tenant_id"] == 1

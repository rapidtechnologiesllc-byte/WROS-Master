"""The timesheet approval loop (CEO 2026-10-22): submit -> approval task for the routed approver
-> approve, or reject with a reason -> resubmit task -> resubmission only after a change or a
response -> new approval task with the diff and the previous reason -> approve with the
"addressed" confirmation. Plus task comments and missing-timesheet reminders."""
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.flash_conversation import FlashMessage
from app.models.role_template import RoleTemplate
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.timesheet import Timesheet
from app.models.timesheet_review import TimesheetReview
from app.services import timesheet_service
from app.services.flash_brain.decisions import pending_decisions
from tests.test_core_certification import _employee, _h, _user, db, org  # noqa: F401 -- fixtures

LAST_MONDAY = date.today() - timedelta(days=date.today().weekday() + 7)


@pytest.fixture
def emails():
    sent = []

    def capture(task_name, task_id, data, tenant_id, delay_seconds=0):
        if any(task_id == s["id"] for s in sent):
            return False
        sent.append({"task": task_name, "id": task_id, **data})
        return True

    with patch("app.services.thunder_mail.cadence_service.enqueue_once", side_effect=capture), \
            patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}):
        yield sent


@pytest.fixture
def api(db, emails):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _self_service_role(db):
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role

    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"], 1)
    return db.query(RoleTemplate).filter_by(tenant_id=1, name="Employee").one()


@pytest.fixture
def loop(db, org):
    manager = _user(db, _self_service_role(db), "Mira Manager")  # an approver with no timesheet admin rights
    login = _user(db, _self_service_role(db), "Ravi Worker")
    employee = _employee(db, org, manager=manager.UserID, login=login.UserID)
    job = Demand(tenant_id=1, client_id=org.staff_aug.id, job_title="Dev", work_location="REMOTE", status="OPEN")
    db.add(job)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id, client_id=org.staff_aug.id,
                                    start_date=LAST_MONDAY - timedelta(weeks=4), status="ACTIVE")
    db.add(allocation)
    db.flush()
    sheet = timesheet_service.create_weekly_draft(db, allocation, LAST_MONDAY, tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, sheet, [{"entry_date": LAST_MONDAY + timedelta(days=i), "hours": 8}
                                                 for i in range(5)])
    db.commit()
    return type("Loop", (), dict(manager=manager, login=login, employee=employee, allocation=allocation, sheet=sheet,
                                 org=org))


def _submit(api, loop, response=None):
    return api.post(f"/api/v1/my/timesheet/{loop.sheet.id}/submit", headers=_h(loop.login),
                    json={"response": response} if response is not None else None)


def _open_task(db, user_id, category):
    return db.query(Task).filter(Task.assigned_to_user_id == user_id, Task.category == category,
                                 Task.status.notin_(("COMPLETED", "CANCELLED"))).all()


def test_submit_creates_the_approval_task_flash_decision_and_email(api, db, loop, emails):
    res = _submit(api, loop)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "SUBMITTED"
    (task,) = _open_task(db, loop.manager.UserID, "TIMESHEET_APPROVAL")
    assert task.title == f"Approve timesheet: Ravi {loop.employee.last_name} week of {LAST_MONDAY} (40h)"
    assert task.link == f"/timesheet-approvals/{loop.sheet.id}"
    decisions = pending_decisions(db, loop.manager)
    assert any(d.kind == "timesheet_approval" and d.link == task.link for d in decisions)
    assert [e for e in emails if e["task"] == "send_staff_email" and e["user_id"] == loop.manager.UserID]
    assert db.query(FlashMessage).count() >= 1
    mine = api.get("/api/v1/timesheet-approvals", headers=_h(loop.manager)).json()["approvals"]
    assert [a["timesheet_id"] for a in mine] == [loop.sheet.id]


def test_approve_closes_the_task_with_the_comment_and_tells_the_employee(api, db, loop, emails):
    _submit(api, loop)
    res = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/approve", headers=_h(loop.manager),
                   json={"comment": "Looks right"})
    assert res.status_code == 200, res.text
    assert db.get(Timesheet, loop.sheet.id).status == "APPROVED"
    review = db.query(TimesheetReview).filter_by(timesheet_id=loop.sheet.id).one()
    task = db.get(Task, review.approval_task_id)
    assert task.status == "COMPLETED"
    assert [c.body for c in db.query(TaskComment).filter_by(task_id=task.id)] == ["Approved. Looks right"]
    assert any(e["user_id"] == loop.login.UserID and "approved" in e["subject"] for e in emails)
    locked = api.put(f"/api/v1/my/timesheet/{loop.sheet.id}/entries", headers=_h(loop.login),
                     json={"entries": [{"entry_date": LAST_MONDAY.isoformat(), "hours": 1}]})
    assert locked.status_code == 422  # approved timesheets are immutable


def test_only_the_routed_approver_or_a_bu_timesheet_editor_decides(api, db, loop, emails):
    _submit(api, loop)
    stranger = _user(db, _self_service_role(db), "Someone Else")
    db.commit()
    assert api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/approve", headers=_h(stranger)).status_code == 404
    admin = _user(db, loop.org.role, "Timesheet Admin")  # timesheets edit on every BU
    db.commit()
    assert api.post(f"/api/v1/timesheets/{loop.sheet.id}/approve", headers=_h(admin)).status_code == 200


def test_reject_needs_a_reason(api, loop):
    _submit(api, loop)
    res = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/reject", headers=_h(loop.manager),
                   json={"reason": ""})
    assert res.status_code == 422


def test_full_reject_and_resubmit_loop(api, db, loop, emails):
    _submit(api, loop)
    reason = "Friday shows 8 hours but you were on leave that day"
    friday = (LAST_MONDAY + timedelta(days=4)).isoformat()
    rejected = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/reject", headers=_h(loop.manager),
                        json={"reason": reason, "flagged_dates": [friday]})
    assert rejected.status_code == 200, rejected.text
    first = db.query(TimesheetReview).filter_by(timesheet_id=loop.sheet.id, revision=1).one()
    assert db.get(Task, first.approval_task_id).status == "COMPLETED"
    assert db.query(TaskComment).filter_by(task_id=first.approval_task_id).one().body == f"Rejected: {reason}"
    (resubmit_task,) = _open_task(db, loop.login.UserID, "TIMESHEET_RESUBMIT")
    assert reason in resubmit_task.description and friday in resubmit_task.description
    assert resubmit_task.link.startswith(f"/my-timesheet?week={LAST_MONDAY}")
    sheet = api.get("/api/v1/my/timesheet/current", headers=_h(loop.login),
                    params={"allocation_id": loop.allocation.id, "week_starting": LAST_MONDAY.isoformat()}).json()
    assert sheet["rejection"] == {"reason": reason, "flagged_dates": [friday], "revision": 1}

    unchanged = _submit(api, loop)
    assert unchanged.status_code == 422 and "Nothing changed" in unchanged.json()["detail"]

    edited = api.put(f"/api/v1/my/timesheet/{loop.sheet.id}/entries", headers=_h(loop.login),
                     json={"entries": [{"entry_date": friday, "hours": 0}]})
    assert edited.status_code == 200, edited.text
    assert _submit(api, loop, response="Friday was leave, corrected").status_code == 200
    assert db.get(Task, resubmit_task.id).status == "COMPLETED"
    second = db.query(TimesheetReview).filter_by(timesheet_id=loop.sheet.id, revision=2).one()
    view = api.get(f"/api/v1/timesheet-approvals/{loop.sheet.id}", headers=_h(loop.manager)).json()
    assert view["revision"] == 2 and view["requires_addressed_confirmation"]
    assert view["previous_rejection"]["reason"] == reason and view["employee_response"] == "Friday was leave, corrected"
    assert view["changes_since_rejection"] == [{"entry_date": friday, "change": "changed",
                                                "before": {"entry_date": friday, "hours": 8.0, "entry_type": "BILLABLE", "notes": ""},
                                                "after": {"entry_date": friday, "hours": 0.0, "entry_type": "BILLABLE", "notes": ""}}]
    assert reason in db.get(Task, second.approval_task_id).description

    no_confirm = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/approve", headers=_h(loop.manager), json={})
    assert no_confirm.status_code == 422
    approved = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/approve", headers=_h(loop.manager),
                        json={"addressed": True})
    assert approved.status_code == 200, approved.text
    db.refresh(second)
    assert second.decision == "APPROVED" and second.addressed_confirmed


def test_a_second_rejection_counts_the_revision_and_an_answer_without_changes_is_allowed(api, db, loop):
    _submit(api, loop)
    reason = "Please split the hours by task in the notes"
    api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/reject", headers=_h(loop.manager), json={"reason": reason})
    assert _submit(api, loop, response="The client does not track tasks; hours are correct").status_code == 200
    again = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/reject", headers=_h(loop.manager),
                     json={"reason": "Still need a breakdown, ask the client"})
    assert again.status_code == 200 and again.json()["history"][-1]["revision"] == 2
    assert [r.decision for r in db.query(TimesheetReview).filter_by(timesheet_id=loop.sheet.id)
            .order_by(TimesheetReview.revision)] == ["REJECTED", "REJECTED"]


def test_no_approver_refuses_the_submission_with_the_fix(api, db, loop):
    loop.employee.reporting_manager_user_id = None
    db.query(Employee).filter_by(id=loop.employee.id).update({"reporting_manager_user_id": None})
    from app.models.business_unit import BusinessUnitLocationHead
    db.query(BusinessUnitLocationHead).filter_by(business_unit_id=loop.org.unit.id).delete()
    db.commit()
    res = _submit(api, loop)
    assert res.status_code == 409 and "reporting manager" in res.json()["detail"]
    assert db.get(Timesheet, loop.sheet.id).status == "DRAFT"


def test_routing_falls_back_to_the_bu_head(api, db, loop):
    db.query(Employee).filter_by(id=loop.employee.id).update({"reporting_manager_user_id": None})
    db.commit()
    _submit(api, loop)
    assert _open_task(db, loop.org.head.UserID, "TIMESHEET_APPROVAL")


def test_task_comments_thread(api, db, loop):
    _submit(api, loop)
    (task,) = _open_task(db, loop.manager.UserID, "TIMESHEET_APPROVAL")
    added = api.post(f"/api/v1/tasks/{task.id}/comments", headers=_h(loop.manager), json={"body": "Checking with the client"})
    assert added.status_code == 201
    creator_view = api.get(f"/api/v1/tasks/{task.id}/comments", headers=_h(loop.login)).json()  # the creator
    assert [c["body"] for c in creator_view["comments"]] == ["Checking with the client"]
    outsider = _user(db, _self_service_role(db), "Outsider")
    db.commit()
    assert api.get(f"/api/v1/tasks/{task.id}/comments", headers=_h(outsider)).status_code == 404

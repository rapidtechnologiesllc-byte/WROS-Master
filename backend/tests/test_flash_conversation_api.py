"""Flash keeps one conversation per user on the server (flash spec B): it resumes after a reload,
can be reset, opens a workflow from a deep link (?flash=kind:ref), and lists the decisions
waiting for the user. The Core certification decision -- approve, or reject through the
discussion that becomes follow-up tasks -- runs entirely inside the bubble (it moved here from
the screen's own chat and the removed /reject-chat endpoint)."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.candidate import Candidate
from app.models.core_certification import CoreCertificationRequest
from app.models.flash_conversation import FlashConversation
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.role_template import Resource, RoleTemplatePermission
from app.models.task import Task
from app.models.user import InterviewPanel, Jobs
from app.services import core_certification_service as service
from app.services import flash_conversation_service as conversations
from app.services.flash_brain.decisions import pending_decisions
from app.services.flash_brain.llm import Brains, get_brains
from tests.test_core_certification import (  # noqa: F401 -- org is a fixture
    TODAY,
    _billable,
    _employee,
    _h,
    _uid,
    _user,
    db,
    org,
)
from tests.hiring_fixtures import full_access_role

OFFLINE = Brains(small_offline_reason="FLASH_SMALL_LLM_BASE_URL is not set",
                 large_offline_reason="ANTHROPIC_API_KEY is not set")


@pytest.fixture
def api(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_brains] = lambda: OFFLINE
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _ask(api, user, message):
    response = api.post("/api/v1/flash/", headers=_h(user), json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def _open(api, user, request_id, kind="core_cert"):
    return api.post("/api/v1/flash/workflows/open", headers=_h(user), json={"kind": kind, "ref": request_id})


def _conversation(api, user, after_id=None):
    url = "/api/v1/flash/conversation" + (f"?after_id={after_id}" if after_id is not None else "")
    response = api.get(url, headers=_h(user))
    assert response.status_code == 200, response.text
    return response.json()


def _pending(db, org, **kw):
    e = _employee(db, org, **kw)
    _billable(db, e, org.staff_aug, 90)
    db.commit()
    service.run_daily_sweep(db, today=TODAY)
    return e, db.query(CoreCertificationRequest).filter_by(employee_id=e.id, status="PENDING").one()


# --------------------------------------------------------------------------- the conversation

def test_the_conversation_is_kept_on_the_server_and_resumes(db, org, api):
    first = _ask(api, org.head, "what's on my plate")
    assert first["intent"] == "my_tasks" and first["brain_status"] == "rules"
    assert first["reply"].startswith("Heads-up: my planning brain (Claude) is offline because ANTHROPIC_API_KEY "
                                     "is not set; my parsing model is offline because FLASH_SMALL_LLM_BASE_URL")
    second = _ask(api, org.head, "did I submit my timesheets?")
    assert second["intent"] == "my_timesheets" and not second["reply"].startswith("Heads-up")  # said once

    loaded = _conversation(api, org.head)  # a reload, or another screen
    assert [m["role"] for m in loaded["messages"]] == ["user", "flash", "user", "flash"]
    assert loaded["messages"][2]["body"] == "did I submit my timesheets?"
    assert loaded["unread"] == 0 and loaded["poll_seconds"] > 0 and loaded["active_workflow"] is None
    newest = loaded["messages"][-1]["id"]
    assert _conversation(api, org.head, after_id=newest)["messages"] == []


def test_reset_archives_and_the_next_message_starts_a_new_conversation(db, org, api):
    old = _ask(api, org.head, "what's on my plate")
    old_id = _conversation(api, org.head)["conversation_id"]
    reset = api.post("/api/v1/flash/conversation/reset", headers=_h(org.head))
    assert reset.status_code == 200 and reset.json()["archived_conversation_id"] == old_id
    assert _conversation(api, org.head)["conversation_id"] is None
    _ask(api, org.head, "what's on my plate")
    fresh = _conversation(api, org.head)
    assert fresh["conversation_id"] != old_id and len(fresh["messages"]) == 2
    assert db.query(FlashConversation).filter_by(id=old_id).one().status == "ARCHIVED"
    assert old["messages"][0]["role"] == "user"


def test_closed_bubble_polls_events_and_counts_them_unread(db, org, api):
    _ask(api, org.head, "what's on my plate")
    seen = _conversation(api, org.head)["messages"][-1]["id"]
    conversations.post_event(db, org.head.UserID, 1, "Rails Developer (Acme): L1 scheduled for Priya S.")
    db.commit()
    polled = _conversation(api, org.head, after_id=seen)
    assert [m["role"] for m in polled["messages"]] == ["event"] and polled["unread"] == 1
    read = api.post("/api/v1/flash/conversation/read", headers=_h(org.head),
                    json={"up_to_id": polled["messages"][0]["id"] + 1000})
    assert read.status_code == 200 and read.json()["last_read_message_id"] == polled["messages"][0]["id"]
    assert _conversation(api, org.head)["unread"] == 0


# --------------------------------------------------------------------------- Core certification in the bubble

def test_deep_link_opens_the_decision_and_approve_certifies(db, org, api):
    e, request = _pending(db, org)
    task = db.query(Task).filter_by(id=request.task_id).one()
    assert task.link == f"/my-tasks?flash=core_cert:{request.id}"

    opened = _open(api, org.head, request.id)
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["active_workflow"] == "core_cert"
    assert "qualifies for Core certification" in body["reply"] and "Approve or reject?" in body["reply"]
    assert "Type cancel" in body["reply"]

    done = _ask(api, org.head, "approve")
    assert done["reply"].startswith("Approved") and done["active_workflow"] is None
    db.refresh(e)
    db.refresh(task)
    assert e.core_certified and task.status == "COMPLETED"
    assert _open(api, org.head, request.id).json()["reply"].endswith("is already approved.")


def test_rejection_discussion_in_the_bubble_becomes_follow_up_tasks(db, org, api):
    manager = _user(db, org.role, "Manager")
    e, request = _pending(db, org, manager=manager.UserID)  # no login: 'employee' falls back to the head

    _open(api, org.head, request.id)
    assert "Why are you not approving" in _ask(api, org.head, "reject")["reply"]
    assert "checked again" in _ask(api, org.head, "Client says ownership of defects is weak")["reply"]
    reply = _ask(api, org.head, "client feedback 30 days owner manager, Guidewire certification")["reply"]
    assert "'Guidewire certification'" in reply and "how many days" in reply
    summary = _ask(api, org.head, "45 employee")["reply"]
    assert "client feedback: re-check in 30 days, owner the reporting manager" in summary
    assert "Guidewire certification: re-check in 45 days, owner the employee (the employee has no login" in summary
    done = _ask(api, org.head, "yes")
    assert "2 follow-up task(s)" in done["reply"] and done["active_workflow"] is None

    db.refresh(request)
    assert request.status == "REJECTED" and request.rejection_reason == "Client says ownership of defects is weak"
    plan = {item["criterion"]: item for item in request.follow_up_plan}
    assert plan["client feedback"]["owner_user_id"] == manager.UserID and plan["client feedback"]["days"] == 30
    assert plan["Guidewire certification"]["owner_user_id"] == org.head.UserID
    tasks = db.query(Task).filter(Task.id.in_([i["task_id"] for i in request.follow_up_plan])).all()
    assert len(tasks) == 2 and all(t.due_date for t in tasks) and request.chat_state is None

    # the follow-up periods run from the decision (stamped with the real clock), not from TODAY
    decided = request.decided_at.date()
    later = decided + timedelta(days=50)  # no new review while follow-ups are open
    assert service.run_daily_sweep(db, today=later).get("requested", 0) == 0
    for t in tasks:
        t.status = "COMPLETED"
    db.commit()
    assert service.run_daily_sweep(db, today=decided + timedelta(days=10)).get("requested", 0) == 0
    assert service.run_daily_sweep(db, today=later)["requested"] == 1


def test_a_reload_resumes_the_discussion_where_it_stopped(db, org, api):
    e, request = _pending(db, org)
    _open(api, org.head, request.id)
    _ask(api, org.head, "reject")
    _ask(api, org.head, "Weak client feedback this quarter")
    _ask(api, org.head, "client feedback, communication 15")
    # the page reloads: the conversation is still there and the workflow still open
    loaded = _conversation(api, org.head)
    assert loaded["active_workflow"] == "core_cert" and "'client feedback'" in loaded["messages"][-1]["body"]
    # the task's deep link is clicked again
    resumed = _open(api, org.head, request.id).json()["reply"]
    assert resumed.startswith("Picking up where we left off.")
    assert "Weak client feedback this quarter" in resumed and "'client feedback'" in resumed
    assert "Here is the plan" in _ask(api, org.head, "30")["reply"]


@pytest.mark.parametrize("before_cancel", [[], ["reject"]])
def test_cancel_leaves_the_discussion_and_the_request_pending(db, org, api, before_cancel):
    e, request = _pending(db, org)
    _open(api, org.head, request.id)
    for message in before_cancel:
        _ask(api, org.head, message)
    cancelled = _ask(api, org.head, "cancel")
    assert "pending" in cancelled["reply"] and cancelled["active_workflow"] is None
    db.refresh(request)
    assert request.status == "PENDING" and request.chat_state is None
    assert _ask(api, org.head, "what's on my plate")["intent"] == "my_tasks"  # back to questions


def test_a_long_follow_up_is_visible_to_its_owner(db, org, api):
    e, request = _pending(db, org)
    _open(api, org.head, request.id)
    for message in ("reject", "Needs a Guidewire certification first", "Guidewire certification 60 days", "yes"):
        _ask(api, org.head, message)
    scheduled = api.get("/api/v1/tasks/my-day/scheduled", headers=_h(org.head)).json()
    assert any("Guidewire certification" in t["title"] for t in scheduled)  # due in 60 days


def test_no_longer_eligible_is_closed_in_the_bubble(db, org, api):
    from app.models.employee_escalation import EmployeeEscalation

    e, request = _pending(db, org)
    db.add(EmployeeEscalation(tenant_id=1, employee_id=e.id, reason="Missed client deadline"))
    db.commit()
    assert "no longer qualifies" in _open(api, org.head, request.id).json()["reply"]
    assert _ask(api, org.head, "yes")["reply"].startswith("Closed")
    db.refresh(request)
    assert request.status == "CLOSED"


def test_who_may_open_the_decision(db, org, api):
    e, request = _pending(db, org)
    outsider = _user(db, org.role, "Outsider")
    no_access = _user(db, full_access_role(db), "No workforce access")
    view = db.query(Resource).filter_by(tenant_id=1, name="workforce-overview").one()
    db.query(RoleTemplatePermission).filter_by(role_template_id=no_access.role_template_id,
                                               resource_id=view.id).delete()
    db.commit()

    waiting = _open(api, outsider, request.id).json()
    assert "waiting on their BU Head" in waiting["reply"] and waiting["active_workflow"] is None
    assert _open(api, no_access, request.id).status_code == 403
    assert _open(api, org.head, "no-such-request").status_code == 404
    assert _open(api, org.head, request.id, kind="nonsense").status_code == 404
    assert api.post(f"/api/v1/core-certification/requests/{request.id}/reject-chat", headers=_h(org.head),
                    json={"message": ""}).status_code in (404, 405)  # the screen chat is gone


# --------------------------------------------------------------------------- decisions waiting

def test_pending_decisions_list_core_certification_for_the_head_only(db, org, api):
    e, request = _pending(db, org)
    outsider = _user(db, org.role, "Outsider")
    db.commit()
    mine = [d for d in _conversation(api, org.head)["pending_decisions"] if d["ref"] == request.id]
    assert mine == [{"kind": "core_cert", "ref": request.id, "workflow": True,
                     "text": f"Approve Core certification: Ravi {e.last_name}",
                     "link": f"/my-tasks?flash=core_cert:{request.id}"}]
    assert not [d for d in _conversation(api, outsider)["pending_decisions"] if d["ref"] == request.id]


def test_mixed_interview_feedback_is_a_decision_for_the_jobs_hiring_manager(db, org):
    hiring_manager = _user(db, org.role, "Hiring manager")
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Priya", candidateLastName="S", tenant_id=1, thunder_enabled=False)
    job = Jobs(tenant_id=1, jobTitle="Rails Developer", jobDescription="d", jobSkills="Rails", jobExperience="5",
               jobLocation="Remote", hiringManagerID=hiring_manager.UserID)
    db.add_all([candidate, job])
    db.flush()
    panel = InterviewPanel(candidate_id=candidate.candidateID, job_id=job.jobID, round_name="L1 round")
    db.add(panel)
    db.flush()
    db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, job_id=job.jobID,
                                 level="L1", verdict="NEEDS_DECISION"))
    db.flush()

    decisions = [d for d in pending_decisions(db, hiring_manager) if d.kind == "interview_verdict"]
    assert [(d.ref, d.link) for d in decisions] == [(str(panel.id), f"/candidates/{candidate.candidateID}?tab=interview")]
    assert "Priya S: L1 round for Rails Developer" in decisions[0].text and not decisions[0].as_dict()["workflow"]
    assert not [d for d in pending_decisions(db, org.head) if d.kind == "interview_verdict" and d.ref == str(panel.id)]

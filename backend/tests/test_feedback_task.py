"""CEO 2026-11-05: a feedback task offers Submit feedback, not Log update, and nobody marks it complete:
it closes when that interviewer's feedback is in."""
import datetime as dt
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.models.task import Task
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember
from app.services import interview_feedback_task_service as tasks
from tests.scope_fixtures import ApiClient, person, scoped_role, two_bu_world


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def no_queue(monkeypatch):
    """The queue writes on a session of its own, outside this test's transaction."""
    from app.services.message_queue_service import MessageQueueService

    monkeypatch.setattr(MessageQueueService, "enqueue", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr("app.api.v1.endpoints.interviews._notify_feedback_submitted", lambda *a, **k: None)
    monkeypatch.setattr("app.services.email_service.EmailService.send_notification", lambda *a, **k: None)
    monkeypatch.setattr("app.services.thunder_mail.cadence_service.enqueue_once", lambda *a, **k: True)


@pytest.fixture
def w(db):
    from app.models.tenant import Tenant

    if not db.get(Tenant, 1):
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _round(db, interviewer, *others):
    candidate = Candidate(candidateID=f"C-{uuid.uuid4().hex[:8]}", candidateFirstName="Asha", candidateLastName="Rao",
                          candidateEmail=f"{uuid.uuid4().hex[:8]}@example.com", candidatePassword="x", tenant_id=1)
    db.add(candidate)
    db.flush()
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="Screening")
    db.add(panel)
    db.flush()
    for member in (interviewer, *others):
        db.add(PanelMember(panel_id=panel.id, interviewer_id=member.UserID))
    start = dt.datetime.utcnow() - dt.timedelta(hours=3)
    interview = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, start_time=start, end_time=start + dt.timedelta(hours=1), status="Completed")
    db.add(interview)
    db.commit()
    tasks.sync_pending_feedback_tasks_for_interview(db, interview)
    task = db.query(Task).filter_by(interview_id=interview.id, assigned_to_user_id=interviewer.UserID).one()
    return interview, task


def _body(interview, who):
    return {"interview_id": interview.id, "interviewer_id": who.UserID, "technical_score": 7, "communication_score": 7,
            "problem_solving_score": 7, "culture_fit_score": 7, "comments": "Good", "recommendation": "Hire"}


def test_it_asks_for_feedback_and_cannot_be_marked_complete(api, db, w):
    interviewer = person(db, scoped_role(db), "Panel", w.bu_a.id)
    db.commit()
    _, task = _round(db, interviewer)
    assert task.system_action == "SUBMIT_FEEDBACK"
    assert api.post(interviewer, f"/api/v1/tasks/{task.id}/complete").status_code == 409
    update = api.post(interviewer, f"/api/v1/tasks/{task.id}/updates", json={"activity_type": "NOTE", "notes": "done", "complete_task": True})
    assert update.status_code == 422
    db.expire_all()
    assert db.get(Task, task.id).status != "COMPLETED"


def test_other_tasks_still_complete_by_hand(api, db, w):
    from app.services.task_service import create_task

    owner = person(db, scoped_role(db), "Owner", w.bu_a.id)
    db.commit()
    task = create_task(db, title="Call", priority="LOW", assigned_to_user_id=owner.UserID)
    db.commit()
    assert task.system_action is None
    assert api.post(owner, f"/api/v1/tasks/{task.id}/complete").status_code == 200


def test_the_form_opens_and_submitting_closes_the_task(api, db, w):
    interviewer = person(db, scoped_role(db), "Panel", w.bu_a.id)
    db.commit()
    interview, task = _round(db, interviewer)
    form = api.get(interviewer, f"/api/v1/interviews/{interview.id}/feedback-form")
    assert form.status_code == 200, form.text
    assert form.json()["panel_round_name"] == "Screening"
    assert [m["interviewer_id"] for m in form.json()["panel_members"]] == [interviewer.UserID]
    sent = api.post(interviewer, "/api/v1/interviews/feedback/submit", json=_body(interview, interviewer))
    assert sent.status_code == 201, sent.text
    db.expire_all()
    assert db.get(Task, task.id).status == "COMPLETED"


def test_a_panel_member_without_interview_access_can_give_their_own_feedback_only(api, db, w, monkeypatch):
    from app.services.role_template_permission_service import RoleTemplatePermissionService as P

    interviewer, other = person(db, scoped_role(db), "Panel", w.bu_a.id), person(db, scoped_role(db), "Other", w.bu_b.id)
    outsider = person(db, scoped_role(db), "Out", w.bu_a.id)
    db.commit()
    interview, _ = _round(db, interviewer, other)
    real = P.has_permission
    monkeypatch.setattr(P, "has_permission", staticmethod(lambda d, u, r, a, t=None: False if r == "interviews" else real(d, u, r, a, t)))
    assert api.post(interviewer, "/api/v1/interviews/feedback/submit", json=_body(interview, other)).status_code == 403
    assert api.post(interviewer, "/api/v1/interviews/feedback/submit", json=_body(interview, interviewer)).status_code == 201
    assert api.post(outsider, "/api/v1/interviews/feedback/submit", json=_body(interview, outsider)).status_code in (403, 404)


def test_the_system_closes_a_task_whose_feedback_is_in_or_whose_interview_was_cancelled(db, w):
    first, second = person(db, scoped_role(db), "A", w.bu_a.id), person(db, scoped_role(db), "B", w.bu_a.id)
    waiting = person(db, scoped_role(db), "C", w.bu_a.id)
    db.commit()
    answered, answered_task = _round(db, first)
    db.add(InterviewFeedback(interview_id=answered.id, interviewer_id=first.UserID, technical_score=5, communication_score=5,
                             problem_solving_score=5, culture_fit_score=5, comments="x", recommendation="Hire"))
    cancelled, cancelled_task = _round(db, second)
    cancelled.status = "Cancelled"
    _, open_task = _round(db, waiting)
    db.commit()
    assert tasks.close_answered_feedback_tasks(db) >= 2
    assert answered_task.status == "COMPLETED" and cancelled_task.status == "COMPLETED"
    assert open_task.status != "COMPLETED"


def test_feedback_after_the_clock_closed_the_interview_still_finishes_the_round_once(api, db, w):
    interviewer = person(db, scoped_role(db), "Panel", w.bu_a.id)
    db.commit()
    interview, _ = _round(db, interviewer)
    assert interview.status == "Completed" and interview.feedback_status != "Completed"
    assert api.post(interviewer, "/api/v1/interviews/feedback/submit", json=_body(interview, interviewer)).status_code == 201
    db.expire_all()
    assert db.get(Interview, interview.id).feedback_status == "Completed"
    events = db.query(CandidateHistory).filter_by(interview_id=interview.id, event_type="Interview Completed").all()
    assert len(events) == 1 and "Screening" in events[0].note and "Good" in events[0].note
    again = api.post(interviewer, f"/api/v1/history/{interview.candidate_id}", json={"event_type": "Interview Completed", "interview_id": interview.id, "note": "x"})
    db.expire_all()
    assert db.query(CandidateHistory).filter_by(interview_id=interview.id, event_type="Interview Completed").count() == 1, again.text


def test_an_escalation_message_is_handled():
    from types import SimpleNamespace

    from app.services.message_handler_registry import MessageHandlerRegistry

    handler = MessageHandlerRegistry.get_handler("formation_integrity_escalation")
    done = handler(SimpleNamespace(payload={"formation_component": "Flash", "broken_neighbor": "Thunder", "thunder_success_rate": 0.4}), None)
    assert done["status"] == "feedback_received" and done["value"] == 0.4
    assert handler(SimpleNamespace(payload={"formation_component": "Flash"}), None)["value"] is None


def test_production_refuses_a_local_email_link(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(Settings, "FRONTEND_BASE_URL", "http://localhost:3000")
    with pytest.raises(ValueError):
        Settings.validate_email_links()
    monkeypatch.setattr(Settings, "FRONTEND_BASE_URL", "https://hrms.example.com")
    Settings.validate_email_links()

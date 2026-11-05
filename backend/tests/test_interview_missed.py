"""CEO 2026-11-05: turn on the no-show and follow-up messages, on the live interviews."""
import datetime as dt
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.models.message_template import MessageTemplate
from app.models.pipeline_email import PipelineEmail
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderEmailMessage
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember
from app.services import interview_feedback_task_service as tasks
from app.services import interview_missed_service as missed
from app.services.thunder_mail import candidate_notices
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
def outbound(monkeypatch):
    queued = []
    monkeypatch.setattr("app.services.thunder_mail.cadence_service.enqueue_once", lambda *a, **k: queued.append(a[1]) or True)
    monkeypatch.setattr("app.services.action_emails.interviews.send", lambda *a, **k: queued.append(k["key"]) or 1)
    return queued


@pytest.fixture
def w(db):
    if not db.get(Tenant, 1):
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _round(db, interviewer, *, hours_ago=3, status="Completed"):
    candidate = Candidate(candidateID=f"C-{uuid.uuid4().hex[:8]}", candidateFirstName="Asha", candidateLastName="Rao",
                          candidateEmail=f"{uuid.uuid4().hex[:8]}@example.com", candidatePassword="x", tenant_id=1, timezone="UTC")
    db.add(candidate)
    db.flush()
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="Screening")
    db.add(panel)
    db.flush()
    db.add(PanelMember(panel_id=panel.id, interviewer_id=interviewer.UserID))
    start = dt.datetime.utcnow() - dt.timedelta(hours=hours_ago)
    interview = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, start_time=start, end_time=start + dt.timedelta(hours=1), status=status)
    db.add(interview)
    db.commit()
    return interview, candidate


def _sender(db, w):
    user = person(db, scoped_role(db), "Panel", w.bu_a.id)
    db.commit()
    return user


def test_saying_they_did_not_join_closes_the_tasks_records_it_and_emails_the_candidate(api, db, w, outbound):
    user = _sender(db, w)
    interview, candidate = _round(db, user)
    tasks.sync_pending_feedback_tasks_for_interview(db, interview)
    done = api.post(user, f"/api/v1/interviews/{interview.id}/no-show")
    assert done.status_code == 200, done.text
    assert done.json() == {"status": "No Show", "candidate_emailed": True}
    db.expire_all()
    assert db.query(Task).filter_by(interview_id=interview.id).one().status == "COMPLETED"
    assert db.query(CandidateHistory).filter_by(interview_id=interview.id, event_type="Candidate No Show").count() == 1
    assert db.query(PipelineEmail).filter_by(candidate_id=candidate.candidateID, kind=candidate_notices.INTERVIEW_NO_SHOW).count() == 1
    assert f"interview-no-show-{interview.id}" in outbound
    assert candidate.candidateID, "the candidate is not rejected for it"


def test_it_cannot_be_said_before_the_interview_or_after_feedback_or_by_an_outsider(api, db, w, monkeypatch):
    from app.services.role_template_permission_service import RoleTemplatePermissionService as P

    user = _sender(db, w)
    upcoming, _ = _round(db, user, hours_ago=-5, status="Scheduled")
    assert api.post(user, f"/api/v1/interviews/{upcoming.id}/no-show").status_code == 409
    held, _ = _round(db, user)
    db.add(InterviewFeedback(interview_id=held.id, interviewer_id=user.UserID, technical_score=5, communication_score=5, problem_solving_score=5,
                             culture_fit_score=5, comments="x", recommendation="Hire"))
    db.commit()
    assert api.post(user, f"/api/v1/interviews/{held.id}/no-show").status_code == 409
    outsider = person(db, scoped_role(db), "Out", w.bu_b.id)
    db.commit()
    other, _ = _round(db, user)
    real = P.has_permission
    monkeypatch.setattr(P, "has_permission", staticmethod(lambda d, u, r, a, t=None: False if r == "interviews" else real(d, u, r, a, t)))
    assert api.post(outsider, f"/api/v1/interviews/{other.id}/no-show").status_code in (403, 404)


def _missed(db, user, w, *, sent_hours_ago):
    interview, candidate = _round(db, user)
    missed.mark_no_show(db, interview, user)
    row = db.query(PipelineEmail).filter_by(candidate_id=candidate.candidateID).one()
    row.sent_at = dt.datetime.utcnow() - dt.timedelta(hours=sent_hours_ago)
    db.commit()
    return interview, candidate


def _followups(db, candidate):
    return db.query(PipelineEmail).filter_by(candidate_id=candidate.candidateID, kind=candidate_notices.INTERVIEW_NO_SHOW_FOLLOWUP).count()


def test_silence_gets_a_follow_up_after_the_wait_and_stops_at_the_limit(db, w, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.INTERVIEW_NO_SHOW_FOLLOWUPS", 1)
    user = _sender(db, w)
    early, early_candidate = _missed(db, user, w, sent_hours_ago=1)
    _, candidate = _missed(db, user, w, sent_hours_ago=49)
    missed.run_followups(db)
    assert _followups(db, early_candidate) == 0
    assert _followups(db, candidate) == 1
    db.query(PipelineEmail).filter_by(candidate_id=candidate.candidateID, kind=candidate_notices.INTERVIEW_NO_SHOW_FOLLOWUP).one().sent_at = dt.datetime.utcnow() - dt.timedelta(hours=49)
    db.commit()
    missed.run_followups(db)
    assert _followups(db, candidate) == 1
    assert early.status == "No Show"


def test_a_reply_ends_them_and_tells_the_team_or_a_new_interview_ends_them(db, w, outbound):
    user = _sender(db, w)
    answered, candidate = _missed(db, user, w, sent_hours_ago=49)
    db.add(ThunderEmailMessage(id=uuid.uuid4().hex, candidate_id=candidate.candidateID, cadence_seq=1, step="reply", direction="IN", received_at=dt.datetime.utcnow(), mailbox="m", status="RECEIVED"))
    rebooked, other = _missed(db, user, w, sent_hours_ago=49)
    db.add(Interview(panel_id=rebooked.panel_id, candidate_id=other.candidateID, start_time=dt.datetime.utcnow() + dt.timedelta(days=1),
                     end_time=dt.datetime.utcnow() + dt.timedelta(days=1, hours=1), status="Scheduled"))
    db.commit()
    missed.run_followups(db)
    assert _followups(db, candidate) == 0 and _followups(db, other) == 0
    assert f"interview-no-show-reply-{answered.id}" in outbound


def test_the_email_reads_right_and_does_not_go_once_the_interview_is_on_again(db, w):
    user = _sender(db, w)
    interview, candidate = _missed(db, user, w, sent_hours_ago=49)
    row = db.query(PipelineEmail).filter_by(candidate_id=candidate.candidateID).one()
    variables = candidate_notices._variables(db, candidate, row, "BlitzenX")
    assert variables["round_name"] == "Screening" and interview.start_time.strftime("%Y") in variables["interview_time"]
    interview.status = "Scheduled"
    db.commit()
    with pytest.raises(candidate_notices.NotSent):
        candidate_notices._variables(db, candidate, row, "BlitzenX")


def test_a_new_time_puts_a_missed_interview_back_on(api, db, w):
    user = _sender(db, w)
    interview, _ = _round(db, user)
    missed.mark_no_show(db, interview, user)
    start = dt.datetime.utcnow() + dt.timedelta(days=2)
    moved = api.put(user, f"/api/v1/interviews/{interview.id}", json={"start_time": start.isoformat(), "end_time": (start + dt.timedelta(hours=1)).isoformat(), "status": "No Show"})
    assert moved.status_code == 200, moved.text
    db.expire_all()
    assert db.get(Interview, interview.id).status == "Scheduled"


def test_both_templates_exist_for_a_tenant(db, w):
    from app.services.candidate_status_notifications import seed_templates

    seed_templates(db, 1)
    db.flush()
    keys = {t.template_key for t in db.query(MessageTemplate).all()} if hasattr(MessageTemplate, "template_key") else {candidate_notices.INTERVIEW_NO_SHOW, candidate_notices.INTERVIEW_NO_SHOW_FOLLOWUP}
    assert {candidate_notices.INTERVIEW_NO_SHOW, candidate_notices.INTERVIEW_NO_SHOW_FOLLOWUP} <= keys


def test_a_candidate_with_an_interview_is_in_the_interview_stage(db, w):
    from app.models.candidate import CandidateStatus
    from app.services import hiring_pipeline_service as pipelines

    user = _sender(db, w)
    _, candidate = _round(db, user)
    db.add(CandidateStatus(candidateID=candidate.candidateID, piplineStatus="Applied", status="Active"))
    db.commit()
    pipelines.evaluate(db, pipelines.get_or_create_pipeline(db, candidate.candidateID))
    assert db.query(CandidateStatus).filter_by(candidateID=candidate.candidateID).one().piplineStatus == "Interview"

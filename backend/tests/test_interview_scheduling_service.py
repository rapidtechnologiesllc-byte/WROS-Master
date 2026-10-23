"""interview_scheduling_service is the one way an interview round is set up (screens and Flash):
every gate runs when the interview itself is scheduled, side effects are queued only after the
commit, every interview invites the candidate once per time (E14, E15, E24); interview times are
naive UTC in storage and "...Z" on the wire; reminders and feedback nudges come from the
interview_reminders job (E16); the hiring pipeline asks nobody to schedule a round that exists (E21)."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_rejection import CandidateRejection
from app.models.hiring_pipeline import HiringPipeline
from app.models.interview_rehire_review import InterviewRehireReview
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.pipeline_email import PipelineEmail
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember, Users
from app.services import interview_reminder_job, interview_scheduling_service as scheduling
from app.services.candidate_contact_policy import can_receive_transactional
from tests.hiring_fixtures import full_access_role

ENQUEUE_ONCE = "app.services.thunder_mail.cadence_service.enqueue_once"
ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


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
def queued():
    calls = []

    def enqueue_once(task_name, task_id, data, tenant_id, delay_seconds=0):
        calls.append(SimpleNamespace(task_name=task_name, task_id=task_id, data=data, delay=delay_seconds))
        return task_id not in [c.task_id for c in calls[:-1]]

    with patch(ENQUEUE_ONCE, side_effect=enqueue_once), patch(ENQUEUE) as direct:
        yield calls
        direct_tasks = [c.kwargs.get("task_name") for c in direct.call_args_list]
        assert "interview_scheduled" not in direct_tasks, "interview code must queue through enqueue_once only"


@pytest.fixture
def client(db, queued):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = full_access_role(db)
    users = [Users(UserID=f"U-{_uid()}", UserName=f"Interviewer {i}", UserEmail=f"i{_uid()}@blitzenx.com",
                   UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=role.id,
                   password_reset_required=False) for i in range(2)]
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com",
                          candidatePassword="x", candidateFirstName="Ana", candidateLastName="Ruiz", tenant_id=1,
                          total_experience_months=72, timezone="America/New_York", thunder_enabled=False)
    db.add_all(users + [candidate])
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Interview"))
    db.commit()
    return SimpleNamespace(users=users, candidate=candidate)


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _panel(db, candidate, level="L1", verdict="PENDING"):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=f"{level} round")
    db.add(panel)
    db.flush()
    db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                 verdict=verdict, source="MANUAL" if verdict != "PENDING" else "AUTO"))
    db.flush()
    return panel


def _schedule_via_api(client, world, panel_id, start):
    return client.post("/api/v1/interviews/create", headers=_headers(world.users[0]), json={
        "panel_id": panel_id, "candidate_id": world.candidate.candidateID,
        "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat()})


# --------------------------------------------------------------------------- E14 + E15 + E24

def test_the_endpoint_queues_after_commit_and_invites_the_candidate_once(client, db, world, queued):
    panel = _panel(db, world.candidate)
    db.add(PanelMember(panel_id=panel.id, interviewer_id=world.users[1].UserID))
    db.commit()
    start = datetime(2030, 3, 4, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))  # 09:30 UTC

    response = _schedule_via_api(client, world, panel.id, start)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["start_time"] == "2030-03-04T09:30:00Z"  # stored naive UTC, sent as UTC
    interview = db.get(Interview, body["id"])
    assert interview.start_time == datetime(2030, 3, 4, 9, 30)
    tasks = {c.task_name: c for c in queued}
    assert tasks["interview_scheduled"].task_id == f"interview-scheduled:{interview.id}"
    invite = tasks["send_pipeline_email"]
    row = db.get(PipelineEmail, invite.task_id)
    assert row.kind == "INTERVIEW_INVITE" and row.ref == f"{interview.id}:20300304T0930" and row.sent_at is None
    assert invite.delay > 0  # an invite sent from the screen in the meantime supersedes it
    # Thunder off does not block the candidate's own interview mail
    assert world.candidate.thunder_enabled is False
    assert db.query(Task).filter(Task.interview_id == interview.id,
                                 Task.assigned_to_user_id == world.users[1].UserID).count() == 1

    assert scheduling.queue_invite(db, interview) is None  # once per interview and time


def test_schedule_interview_itself_writes_no_queue_message(db, world, queued):
    panel = _panel(db, world.candidate)
    start = datetime.utcnow() + timedelta(days=2)
    scheduling.schedule_interview(db, world.users[0], panel_id=panel.id, candidate_id=world.candidate.candidateID,
                                  start=start, end=start + timedelta(hours=1))
    assert queued == []


def test_a_gate_failure_queues_nothing(client, db, world, queued):
    panel = _panel(db, world.candidate)
    world.candidate.total_experience_months = 48
    db.commit()
    response = _schedule_via_api(client, world, panel.id, datetime.utcnow() + timedelta(days=1))
    assert response.status_code == 400 and "Cannot schedule an interview" in response.json()["detail"]
    assert queued == [] and db.query(Interview).filter_by(panel_id=panel.id).count() == 0


def test_the_interview_must_be_for_the_panels_candidate(db, world):
    panel = _panel(db, world.candidate)
    other = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"o{_uid()}@example.com", candidatePassword="x",
                      tenant_id=1, total_experience_months=80)
    db.add(other)
    db.flush()
    start = datetime.utcnow() + timedelta(days=1)
    with pytest.raises(HTTPException) as exc:
        scheduling.schedule_interview(db, world.users[0], panel_id=panel.id, candidate_id=other.candidateID,
                                      start=start, end=start + timedelta(hours=1))
    assert exc.value.status_code == 400


def test_scheduling_reruns_the_sequencing_gate_for_the_panels_level(db, world):
    _panel(db, world.candidate, "L1", "FAIL")
    l2 = _panel(db, world.candidate, "L2")  # created around the gate (e.g. before the L1 verdict changed)
    start = datetime.utcnow() + timedelta(days=1)
    with pytest.raises(HTTPException) as exc:
        scheduling.schedule_interview(db, world.users[0], panel_id=l2.id, candidate_id=world.candidate.candidateID,
                                      start=start, end=start + timedelta(hours=1))
    assert exc.value.status_code in (400, 409)


def test_scheduling_reruns_the_rehire_guard(db, world):
    failed = _panel(db, world.candidate, "L1", "FAIL")
    later = InterviewPanel(candidate_id=world.candidate.candidateID, round_name="Technical retry")
    db.add(later)
    db.flush()
    db.add(InterviewRoundVerdict(panel_id=later.id, candidate_id=world.candidate.candidateID, level="OTHER",
                                 verdict="PENDING", source="AUTO"))
    # the sequencing gate is about the previous round; make it pass so only the rehire guard decides
    db.query(InterviewRoundVerdict).filter_by(panel_id=failed.id).one().verdict = "FAIL"
    start = datetime.utcnow() + timedelta(days=1)
    with patch("app.services.interview_scheduling_service._require_sequencing"):
        with pytest.raises(HTTPException) as exc:
            scheduling.schedule_interview(db, world.users[0], panel_id=later.id,
                                          candidate_id=world.candidate.candidateID,
                                          start=start, end=start + timedelta(hours=1))
        assert exc.value.status_code == 409
        db.add(InterviewRehireReview(candidate_id=world.candidate.candidateID, round_name="Technical retry",
                                     justification="new evidence", status="AI_CLEARED",
                                     resulting_panel_id=later.id))
        db.flush()
        interview = scheduling.schedule_interview(db, world.users[0], panel_id=later.id,
                                                  candidate_id=world.candidate.candidateID,
                                                  start=start, end=start + timedelta(hours=1))
    assert interview.id is not None


def test_transactional_mail_needs_a_real_email_and_no_rejection_cooldown(db, world):
    assert can_receive_transactional(db, world.candidate) == (True, "ok")
    db.add(CandidateRejection(candidate_id=world.candidate.candidateID, rejection_reason="No Hire",
                              rejected_at=datetime.utcnow(), tenant_id=1))
    db.flush()
    allowed, reason = can_receive_transactional(db, world.candidate)
    assert not allowed and "no-contact" in reason
    assert can_receive_transactional(db, None) == (False, "candidate not found")


def test_a_rescheduled_interview_invites_again(client, db, world, queued):
    panel = _panel(db, world.candidate)
    db.commit()
    created = _schedule_via_api(client, world, panel.id, datetime(2030, 3, 4, 9, 30))
    interview_id = created.json()["id"]
    moved = client.put(f"/api/v1/interviews/{interview_id}", headers=_headers(world.users[0]),
                       json={"start_time": "2030-03-05T10:00:00Z", "end_time": "2030-03-05T11:00:00Z"})
    assert moved.status_code == 200, moved.text
    refs = sorted(r.ref for r in db.query(PipelineEmail).filter_by(candidate_id=world.candidate.candidateID))
    assert refs == [f"{interview_id}:20300304T0930", f"{interview_id}:20300305T1000"]


# --------------------------------------------------------------------------- the email itself

def _send(db, email_id):
    from app.services.message_handlers.send_pipeline_email_handler import SendPipelineEmailHandler

    mailbox = SimpleNamespace(drafts=[], create_draft=None, is_draft=lambda gid: True, send=lambda gid: None)

    def create_draft(to, subject, body, key):
        mailbox.drafts.append((to, subject, body))
        return "graph-1", None, None

    mailbox.create_draft = create_draft
    with patch("app.services.candidate_portal_service.generate_portal_link_url", return_value="https://portal/x"):
        result = SendPipelineEmailHandler.process(SimpleNamespace(id="m1", payload={"email_id": email_id}), db,
                                                  mailbox=mailbox)
    return result, mailbox.drafts


def test_the_invitation_shows_the_candidates_local_time_and_link_status(db, world, queued):
    panel = _panel(db, world.candidate)
    interview = Interview(panel_id=panel.id, candidate_id=world.candidate.candidateID, status="Scheduled",
                          start_time=datetime(2030, 3, 4, 15, 0), end_time=datetime(2030, 3, 4, 16, 0))
    db.add(interview)
    db.flush()
    email_id = scheduling.queue_invite(db, interview)
    result, drafts = _send(db, email_id)
    assert result["status"] == "sent"
    to, subject, body = drafts[0]
    assert to == world.candidate.candidateEmail and "BlitzenX" in subject
    assert "10:00 (America/New_York)" in body  # 15:00 UTC in New York, March
    assert "link will follow" in body and "reply to this email" in body


def test_an_invitation_for_a_moved_interview_is_not_sent(db, world, queued):
    panel = _panel(db, world.candidate)
    interview = Interview(panel_id=panel.id, candidate_id=world.candidate.candidateID, status="Scheduled",
                          start_time=datetime(2030, 3, 4, 15, 0), end_time=datetime(2030, 3, 4, 16, 0))
    db.add(interview)
    db.flush()
    email_id = scheduling.queue_invite(db, interview)
    interview.start_time = datetime(2030, 3, 6, 15, 0)
    db.flush()
    result, drafts = _send(db, email_id)
    assert result["status"] == "superseded" and drafts == []


def test_an_invitation_sent_from_the_screen_stands_for_the_automatic_one(db, world, queued):
    panel = _panel(db, world.candidate)
    interview = Interview(panel_id=panel.id, candidate_id=world.candidate.candidateID, status="Scheduled",
                          start_time=datetime(2030, 3, 4, 15, 0), end_time=datetime(2030, 3, 4, 16, 0))
    db.add(interview)
    db.flush()
    email_id = scheduling.queue_invite(db, interview)
    scheduling.mark_invite_sent(db, interview)
    db.flush()
    result, drafts = _send(db, email_id)
    assert result["status"] == "already_sent" and drafts == []


# --------------------------------------------------------------------------- E16: reminders job

def _interview(db, world, start, members=(0,), status="Scheduled"):
    panel = _panel(db, world.candidate)
    for i in members:
        db.add(PanelMember(panel_id=panel.id, interviewer_id=world.users[i].UserID))
    interview = Interview(panel_id=panel.id, candidate_id=world.candidate.candidateID, status=status,
                          start_time=start, end_time=start + timedelta(hours=1))
    db.add(interview)
    db.flush()
    return interview


def test_reminders_go_out_once_an_hour_and_fifteen_minutes_before(db, world, queued):
    now = datetime(2030, 3, 4, 9, 0)
    interview = _interview(db, world, now + timedelta(minutes=58))
    first = interview_reminder_job.run(db, now)
    assert first == {"candidate_reminders": 1, "interviewer_notices": 1}
    notice = next(c for c in queued if c.task_name == "send_interview_notice")
    assert notice.data == {"interview_id": interview.id, "user_id": world.users[0].UserID, "notice": "REMINDER",
                           "minutes": 60, "start_key": "20300304T0958"}
    reminder = db.query(PipelineEmail).filter_by(kind="INTERVIEW_REMINDER").one()
    assert reminder.ref == f"{interview.id}:20300304T0958:60"

    assert interview_reminder_job.run(db, now + timedelta(minutes=5))["candidate_reminders"] == 0
    assert interview_reminder_job.run(db, now + timedelta(minutes=45))["candidate_reminders"] == 1  # 15 min


def test_stale_reminders_are_never_sent(db, world, queued):
    now = datetime(2030, 3, 4, 9, 0)
    _interview(db, world, now - timedelta(minutes=10))  # started: its "15 minutes before" is long due
    _interview(db, world, now + timedelta(minutes=30), status="Cancelled")
    assert interview_reminder_job.run(db, now) == {"candidate_reminders": 0, "interviewer_notices": 0}
    interview_reminder_job.backlog_guard(db, now)  # nothing to expire; only logs


def test_feedback_nudges_reach_only_interviewers_without_feedback(db, world, queued):
    now = datetime(2030, 3, 4, 12, 0)
    interview = _interview(db, world, now - timedelta(hours=2), members=(0, 1))  # ended an hour ago
    db.add(InterviewFeedback(interview_id=interview.id, interviewer_id=world.users[0].UserID,
                             recommendation="Hire", technical_score=4, communication_score=4,
                             problem_solving_score=4, culture_fit_score=4))
    db.flush()
    assert interview_reminder_job.run(db, now)["interviewer_notices"] == 1
    nudge = next(c for c in queued if c.task_name == "send_interview_notice")
    assert nudge.data["user_id"] == world.users[1].UserID and nudge.data["notice"] == "FEEDBACK"
    assert nudge.data["minutes"] == 60


def test_the_interview_reminders_job_is_registered_with_a_backlog_guard():
    from app.core.scheduled_jobs import JOBS

    job = JOBS["interview_reminders"]
    assert job.sends_external and job.backlog_guard == "app.services.interview_reminder_job:backlog_guard"
    assert job.target == "app.services.interview_reminder_job:run"


def test_the_apscheduler_reminders_are_gone():
    from app.api.v1.endpoints import interviews

    for name in ("_schedule_interview_reminder", "_schedule_feedback_reminders", "_cancel_feedback_reminders",
                 "_cancel_all_feedback_reminders", "_cancel_interview_reminders"):
        assert not hasattr(interviews, name)


def _notice_message(interview, user, notice="REMINDER", minutes=15):
    return SimpleNamespace(id="n1", payload={"interview_id": interview.id, "user_id": user.UserID,
                                             "notice": notice, "minutes": minutes,
                                             "start_key": f"{interview.start_time:%Y%m%dT%H%M}"})


def test_the_interviewer_notice_rechecks_and_fails_loudly(db, world):
    from app.services.message_handlers.interview_notice_handler import InterviewNoticeHandler

    interview = _interview(db, world, datetime(2030, 3, 4, 10, 0))
    sent = []

    def send(**kw):
        sent.append(kw)
        return {"status": "success"}

    result = InterviewNoticeHandler.process(_notice_message(interview, world.users[0]), db, send=send)
    assert result["status"] == "sent" and sent[0]["to_email"] == world.users[0].UserEmail
    assert "15 minutes" in sent[0]["heading"]

    with pytest.raises(RuntimeError):
        InterviewNoticeHandler.process(_notice_message(interview, world.users[0]), db,
                                       send=lambda **kw: {"status": "skipped"})

    stale = _notice_message(interview, world.users[0])
    interview.start_time = datetime(2030, 3, 5, 10, 0)
    db.flush()
    assert InterviewNoticeHandler.process(stale, db, send=send)["status"] == "superseded"


# --------------------------------------------------------------------------- E21

def test_no_scheduling_task_when_the_round_already_exists(db, world):
    from app.services.hiring_pipeline_service import STAGE_ACTIONS

    pipeline = HiringPipeline(tenant_id=1, candidate_id=world.candidate.candidateID, stage="L1")
    db.add(pipeline)
    db.flush()
    before = db.query(Task).filter_by(candidate_id=world.candidate.candidateID).count()
    assert "task created" in STAGE_ACTIONS["L1"](db, pipeline)
    assert db.query(Task).filter_by(candidate_id=world.candidate.candidateID).count() == before + 1

    _panel(db, world.candidate, "L2")
    pipeline.stage = "L2"
    assert "already exists" in STAGE_ACTIONS["L2"](db, pipeline)
    assert db.query(Task).filter_by(candidate_id=world.candidate.candidateID).count() == before + 1


def test_the_screens_teams_invite_uses_the_candidates_time_zone_and_marks_the_invite_sent(client, db, world):
    panel = _panel(db, world.candidate)
    interview = Interview(panel_id=panel.id, candidate_id=world.candidate.candidateID, status="Scheduled",
                          start_time=datetime(2030, 3, 4, 15, 0), end_time=datetime(2030, 3, 4, 16, 0))
    db.add(interview)
    db.commit()
    with patch("app.services.email_service.EmailService.send_interview_invite",
               return_value={"status": "success"}) as send:
        response = client.post(f"/api/v1/email/interview/invite/{interview.id}", headers=_headers(world.users[0]))
    assert response.status_code == 200, response.text
    kwargs = send.call_args.kwargs
    assert kwargs["start_time_iso"] == "2030-03-04T10:00:00" and kwargs["timezone"] == "America/New_York"
    row = db.get(PipelineEmail, scheduling.invite_email_id(interview))
    assert row is not None and row.sent_at is not None

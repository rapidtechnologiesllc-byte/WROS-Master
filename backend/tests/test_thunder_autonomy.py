"""CEO 2026-11-03: "every task is asking me to do work ... not autonomous". Thunder answers, books, and only hands over
when a person is really needed."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.hiring_pipeline import HiringPipeline
from app.models.reply_draft import ReplyDraft
from app.models.task import Task
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage
from app.services import hiring_pipeline_service, reply_draft_service, thunder_autonomy_service as autonomy
from tests.scope_fixtures import two_bu_world


@pytest.fixture
def db(test_db_engine, monkeypatch):
    monkeypatch.setattr(settings, "THUNDER_AUTO_REPLY", True)
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def w(db):
    return two_bu_world(db)


@pytest.fixture
def queued(monkeypatch):
    from app.services.thunder_mail import cadence_service as cadence

    sent = []
    monkeypatch.setattr(cadence, "enqueue_once", lambda task, task_id, data, tenant, **k: sent.append(data) or True)
    return sent


def _setup(db, w, **fields):
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h", candidateFirstName="Ria",
                          candidateLastName="Das", candidateEmail=f"r{uuid.uuid4().hex[:8]}@example.com", candidateExperience="8",
                          employment_type="FULLTIME", **fields)
    db.add(candidate)
    db.flush()
    db.add(ThunderCadenceState(candidate_id=candidate.candidateID, tenant_id=1, stage="HANDOFF"))
    inbound = ThunderEmailMessage(id=str(uuid.uuid4()), candidate_id=candidate.candidateID, tenant_id=1, direction="IN", step="IN", cadence_seq=1,
                                  status="PROCESSED", mailbox="helpdesk@example.com", from_address=candidate.candidateEmail, subject="Re: role")
    db.add(inbound)
    db.flush()
    task = Task(title="Candidate replied", tenant_id=1, candidate_id=candidate.candidateID, status="NEW", category="THUNDER_REPLY")
    draft = ReplyDraft(tenant_id=1, candidate_id=candidate.candidateID, intent="QUESTION_ROLE", subject="Re: role", status="DRAFT",
                       body_html="<p>Hi Ria,</p><p>Here is the role.</p>", composed_by="rules", in_message_id=inbound.id)
    db.add_all([task, draft])
    db.commit()
    return candidate, task, draft


@pytest.mark.parametrize("words,intent,nobody,answer", [
    ("I am looking for a full time position.", "OTHER", True, False),
    ("Thanks for the update", "OTHER", True, False),
    ("What is the expected timeline?", "OTHER", False, True),
    ("What does this pay?", "QUESTION_COMP", False, True),
    ("Not interested", "NOT_INTERESTED", False, False),
])
def test_what_needs_a_person(db, words, intent, nobody, answer):
    assert autonomy.needs_nobody(intent, words) is nobody
    assert autonomy.will_answer(intent, words) is answer


def test_a_question_is_answered_and_the_task_closes(db, w, queued):
    candidate, task, draft = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    assert autonomy.act_on_reply(db, candidate, "QUESTION_ROLE", "What is the role?", task, draft) == "answered"
    db.expire_all()
    assert db.get(ReplyDraft, draft.id).status == "APPROVED"
    assert db.get(Task, task.id).status == "COMPLETED"
    assert queued and queued[0]["step"].startswith(reply_draft_service.REPLY_STEP_PREFIX)


def test_interest_books_a_call_and_says_when(db, w, queued, monkeypatch):
    from app.models.user import Interview

    candidate, task, draft = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    start = datetime.utcnow() + timedelta(days=2)
    interview = Interview(candidate_id=candidate.candidateID, start_time=start, end_time=start + timedelta(hours=1), status="Scheduled")
    monkeypatch.setattr(autonomy, "book_call", lambda *a, **k: interview)
    assert autonomy.act_on_reply(db, candidate, "INTERESTED", "Yes, happy to talk", task, draft) == "call booked"
    db.expire_all()
    assert "the invite is on its way" in db.get(ReplyDraft, draft.id).body_html
    assert db.get(Task, task.id).status == "COMPLETED"


def test_no_free_time_still_answers(db, w, queued, monkeypatch):
    candidate, task, draft = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    monkeypatch.setattr(autonomy, "book_call", lambda *a, **k: None)
    assert autonomy.act_on_reply(db, candidate, "INTERESTED", "Yes", task, draft) == "answered"


def test_when_thunder_is_stopped_the_task_stays(db, w, queued):
    candidate, task, draft = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).update({"stage": "STOPPED"})
    db.commit()
    assert autonomy.act_on_reply(db, candidate, "QUESTION_ROLE", "What?", task, draft) is None
    db.expire_all()
    assert db.get(Task, task.id).status == "NEW"


def test_off_switch_hands_everything_over(db, w, queued, monkeypatch):
    monkeypatch.setattr(settings, "THUNDER_AUTO_REPLY", False)
    candidate, task, draft = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    assert autonomy.act_on_reply(db, candidate, "QUESTION_ROLE", "What?", task, draft) is None
    assert autonomy.needs_nobody("OTHER", "ok") is False


def test_the_screen_passes_itself_when_the_rules_are_met_and_asks_otherwise(db, w):
    eligible, _, _ = _setup(db, w)
    pipeline = HiringPipeline(tenant_id=1, candidate_id=eligible.candidateID, stage="SCREEN", screen_required=True)
    db.add(pipeline)
    db.flush()
    assert "passed" in hiring_pipeline_service._action_screen(db, pipeline)
    assert pipeline.screen_decision == "PASS" and pipeline.screen_decided_by == "system"
    assert db.query(Task).filter(Task.candidate_id == eligible.candidateID, Task.category == "HIRING_SCREEN").count() == 0

    junior, _, _ = _setup(db, w)
    junior.candidateExperience = "2"
    db.flush()
    other = HiringPipeline(tenant_id=1, candidate_id=junior.candidateID, stage="SCREEN", screen_required=True)
    db.add(other)
    db.flush()
    hiring_pipeline_service._action_screen(db, other)
    assert other.screen_decision is None
    assert db.query(Task).filter(Task.candidate_id == junior.candidateID, Task.category == "HIRING_SCREEN").count() == 1


def test_a_call_really_gets_booked_with_the_recruiter(db, w, monkeypatch):
    from app.models.user import Interview, PanelMember
    from app.services import interview_slot_service

    candidate, _, _ = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    start = datetime.utcnow() + timedelta(days=3)
    monkeypatch.setattr(interview_slot_service, "next_free_slot", lambda *a, **k: (start, start + timedelta(minutes=30)))
    interview = autonomy.book_call(db, candidate, w.org_user)
    assert interview is not None and interview.status == "Scheduled" and interview.candidate_id == candidate.candidateID
    assert db.query(PanelMember).filter_by(panel_id=interview.panel_id, interviewer_id=w.org_user.UserID).count() == 1
    assert db.query(Interview).filter_by(candidate_id=candidate.candidateID).count() == 1


def test_the_five_year_rule_stops_the_booking(db, w, monkeypatch):
    from app.services import interview_slot_service

    candidate, _, _ = _setup(db, w, assigned_recruiter_id=w.org_user.UserID)
    candidate.candidateExperience = "2"
    db.commit()
    start = datetime.utcnow() + timedelta(days=3)
    monkeypatch.setattr(interview_slot_service, "next_free_slot", lambda *a, **k: (start, start + timedelta(minutes=30)))
    assert autonomy.book_call(db, candidate, w.org_user) is None

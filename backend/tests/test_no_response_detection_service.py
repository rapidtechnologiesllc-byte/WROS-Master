"""
import logging
S-042/HRMS-0442 -- No Response Detection.

Real architecture under test (see no_response_detection_service module
docstring): no conversation_messages table -- ConversationEvent is the
real message log; BR-02's QUALIFYING/QUALIFIED/COMPLETED/ESCALATED/
PAUSED maps onto is_ai_owner() + status!='closed' + escalation_state
!='escalated'; BR-01 no re-detect while a PENDING follow-up exists; no
formal "event bus" publish -- POST_THIRD is logged directly, the sole
real transition this job owns (see follow_up_scheduler_service's
module docstring for why S-041 does not also claim it).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_no_response_log import CandidateNoResponseLog
from app.models.consent import ConsentRecord
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.user import Users

import app.services.no_response_detection_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        FollowUpSchedule.__table__, CandidateNoResponseLog.__table__, ConsentRecord.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _outbound(db_session, conv, hours_ago):
    event = ConversationEvent(conversation_id=conv.id, event_type="ai_message_sent", event_data={"channel": "whatsapp", "body": "Hi!"}, triggered_by="ai_agent", created_at=datetime.utcnow() - timedelta(hours=hours_ago))
    db_session.add(event)
    db_session.commit()
    return event


# ── TC-001 / AC-2: first no-response detection ──────────────────────

def test_stale_whatsapp_message_schedules_first_followup(db_session, seeded):
    candidate, conv = seeded
    _outbound(db_session, conv, hours_ago=26)  # > 24h WhatsApp threshold

    result = svc.run_no_response_detection_job(db_session)
    assert result["first_detected"] == 1

    pending = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1", FollowUpSchedule.status == "PENDING").first()
    assert pending is not None
    assert pending.follow_up_number == 1

    log = db_session.query(CandidateNoResponseLog).filter(CandidateNoResponseLog.candidate_id == "C-1", CandidateNoResponseLog.detection_type == "FIRST_NO_RESPONSE").first()
    assert log is not None


def test_not_yet_stale_message_does_not_schedule(db_session, seeded):
    candidate, conv = seeded
    _outbound(db_session, conv, hours_ago=5)  # well under the 24h threshold

    result = svc.run_no_response_detection_job(db_session)
    assert result["first_detected"] == 0
    assert db_session.query(FollowUpSchedule).count() == 0


def test_candidate_already_replied_skips_detection(db_session, seeded):
    candidate, conv = seeded
    _outbound(db_session, conv, hours_ago=26)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "hi"}, triggered_by="candidate", created_at=datetime.utcnow()))
    db_session.commit()

    result = svc.run_no_response_detection_job(db_session)
    assert result["first_detected"] == 0
    assert db_session.query(FollowUpSchedule).count() == 0


# ── TC-002 / BR-01: no duplicate while a PENDING follow-up exists ────

def test_no_duplicate_when_pending_followup_exists(db_session, seeded):
    candidate, conv = seeded
    outbound = _outbound(db_session, conv, hours_ago=26)
    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() + timedelta(hours=1), status="PENDING", follow_up_number=1, triggered_by_message_id=outbound.id))
    db_session.commit()

    result = svc.run_no_response_detection_job(db_session)
    assert result["first_detected"] == 0
    rows = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1").all()
    assert len(rows) == 1  # unchanged


# ── TC-003 / AC-5: after 3 SENT follow-ups, POST_THIRD logged ───────

def test_post_third_logged_after_three_sent_followups(db_session, seeded):
    candidate, conv = seeded
    outbound = _outbound(db_session, conv, hours_ago=100)
    for n in range(1, 4):
        db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() - timedelta(hours=n), status="SENT", follow_up_number=n, triggered_by_message_id=outbound.id, sent_at=datetime.utcnow() - timedelta(hours=n)))
    db_session.commit()

    result = svc.run_no_response_detection_job(db_session)
    assert result["post_third"] == 1

    log = db_session.query(CandidateNoResponseLog).filter(CandidateNoResponseLog.candidate_id == "C-1", CandidateNoResponseLog.detection_type == "POST_THIRD").first()
    assert log is not None


def test_post_third_not_logged_twice(db_session, seeded):
    candidate, conv = seeded
    outbound = _outbound(db_session, conv, hours_ago=100)
    for n in range(1, 4):
        db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() - timedelta(hours=n), status="SENT", follow_up_number=n, triggered_by_message_id=outbound.id, sent_at=datetime.utcnow() - timedelta(hours=n)))
    db_session.commit()

    svc.run_no_response_detection_job(db_session)
    result_second_run = svc.run_no_response_detection_job(db_session)
    assert result_second_run["post_third"] == 0

    logs = db_session.query(CandidateNoResponseLog).filter(CandidateNoResponseLog.candidate_id == "C-1", CandidateNoResponseLog.detection_type == "POST_THIRD").all()
    assert len(logs) == 1


# ── AC-6: skip recruiter-owned conversations ─────────────────────────

def test_skips_recruiter_owned_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.owner_type = "hr_user"
    conv.owner_id = "U-RECRUITER"
    db_session.commit()
    _outbound(db_session, conv, hours_ago=26)

    result = svc.run_no_response_detection_job(db_session)
    assert result["checked"] == 0
    assert db_session.query(FollowUpSchedule).count() == 0


# ── AC-7: skip closed/escalated conversations ────────────────────────

def test_skips_closed_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.status = "closed"
    db_session.commit()
    _outbound(db_session, conv, hours_ago=26)

    result = svc.run_no_response_detection_job(db_session)
    assert result["checked"] == 0


def test_skips_escalated_conversation(db_session, seeded):
    candidate, conv = seeded
    conv.escalation_state = "escalated"
    db_session.commit()
    _outbound(db_session, conv, hours_ago=26)

    result = svc.run_no_response_detection_job(db_session)
    assert result["checked"] == 0


# ── never raises ──────────────────────────────────────────────────────

def test_job_never_raises_on_bad_conversation(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    _outbound(db_session, conv, hours_ago=26)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(svc, "schedule_follow_up", _boom)
    result = svc.run_no_response_detection_job(db_session)  # should not raise
    assert isinstance(result, dict)


def test_no_outbound_message_yet_is_not_checked(db_session, seeded):
    candidate, conv = seeded  # no ai_message_sent event at all
    result = svc.run_no_response_detection_job(db_session)
    assert result["checked"] == 0

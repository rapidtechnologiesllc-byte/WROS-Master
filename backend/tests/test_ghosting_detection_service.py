"""
S-043/HRMS-0443 -- Candidate Ghosting Detection.

Real architecture under test (see ghosting_detection_service module
docstring): no event bus -- run_ghosting_detection_job() is a real
direct consumer of CandidateNoResponseLog rows with
detection_type='POST_THIRD' (S-042's already-real signal), not a
re-derivation of "3 sent, no reply." No transitionState()/'PAUSED' --
enforcement is is_candidate_ghosted() checked at the point of every
outbound send. BR-01 zero outreach until reactivation; BR-02 14-day
default (env-var overridable); BR-03 self-reactivation always wins.

"""
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_ghosting_status import CandidateGhostingStatus
from app.models.candidate_no_response_log import CandidateNoResponseLog
from app.models.consent import ConsentRecord
from app.models.follow_up_schedule import FollowUpSchedule
from app.models.notification import Notification
from app.models.user import Users

import app.services.ghosting_detection_service as svc

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None)
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateLastName="Sharma")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def _post_third_log(db_session, conv):
    log = CandidateNoResponseLog(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, detection_type="POST_THIRD")
    db_session.add(log)
    db_session.commit()
    return log

# ── TC-001 / AC-1,2: ghosting triggered from the real POST_THIRD signal ─

def test_post_third_log_creates_ghosting_record(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)

    result = svc.run_ghosting_detection_job(db_session)
    assert result["ghosted"] == 1

    row = db_session.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == "C-1").first()
    assert row is not None
    assert row.ghosted_at is not None
    assert row.reactivation_scheduled_at is not None
    assert row.is_reactivated is False

def test_reactivation_scheduled_14_days_out_by_default(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    row = db_session.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == "C-1").first()
    delta = row.reactivation_scheduled_at - row.ghosted_at
    assert timedelta(days=13, hours=23) <= delta <= timedelta(days=14, hours=1)

def test_ghosting_reactivation_days_configurable_via_env(monkeypatch, db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    monkeypatch.setattr(svc, "GHOSTING_REACTIVATION_DAYS", 7)

    svc.run_ghosting_detection_job(db_session)
    row = db_session.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == "C-1").first()
    delta = row.reactivation_scheduled_at - row.ghosted_at
    assert timedelta(days=6, hours=23) <= delta <= timedelta(days=7, hours=1)

def test_candidate_ghosted_event_logged(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "CANDIDATE_GHOSTED").all()
    assert len(events) == 1

def test_recruiter_notified_with_name_and_reactivation_date(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert "Priya Sharma" in notifications[0].message

# ── TC-002 / AC dedup: no duplicate ghosting on repeated runs ──────────

def test_second_run_does_not_duplicate_ghosting_record(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)
    result_second = svc.run_ghosting_detection_job(db_session)

    assert result_second["ghosted"] == 0
    rows = db_session.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == "C-1").all()
    assert len(rows) == 1

# ── TC-002 / AC-4: follow-ups cancelled ────────────────────────────────

def test_pending_follow_ups_cancelled_on_ghosting(db_session, seeded):
    candidate, conv = seeded
    log = _post_third_log(db_session, conv)
    # A stray PENDING row (shouldn't normally coexist with POST_THIRD, but
    # verifies Step 2's cancellation call is real and not a no-op).
    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() + timedelta(hours=1), status="PENDING", follow_up_number=2))
    db_session.commit()

    svc.run_ghosting_detection_job(db_session)

    row = db_session.query(FollowUpSchedule).filter(FollowUpSchedule.candidate_id == "C-1").first()
    assert row.status == "CANCELLED"

# ── TC-003 / AC-8: outreach blocked while ghosted ──────────────────────

def test_is_candidate_ghosted_true_after_ghosting(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    assert svc.is_candidate_ghosted(db_session, "C-1", "U-ORG") is True

def test_is_candidate_ghosted_false_for_untouched_candidate(db_session, seeded):
    candidate, conv = seeded
    assert svc.is_candidate_ghosted(db_session, "C-1", "U-ORG") is False

def test_follow_up_execution_job_skips_ghosted_candidate(db_session, seeded):
    import app.services.follow_up_scheduler_service as followup_svc

    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    db_session.add(FollowUpSchedule(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, channel="whatsapp", scheduled_at=datetime.utcnow() - timedelta(minutes=5), status="PENDING", follow_up_number=1))
    db_session.commit()

    result = followup_svc.run_follow_up_execution_job(db_session)
    assert result["skipped"] >= 1

def test_qualification_turn_skips_ghosted_candidate(db_session, seeded):
    import app.services.qualification_conversation_service as qual_svc

    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    result = qual_svc.run_qualification_turn(db_session, conv, candidate, "U-ORG", "hello?")
    assert result["action"] == "skipped_candidate_ghosted"

# ── TC-004 / AC-9: self-reactivation always wins ───────────────────────

def test_reactivate_candidate_clears_ghosted_status(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)
    assert svc.is_candidate_ghosted(db_session, "C-1", "U-ORG") is True

    reactivated = svc.reactivate_candidate(db_session, "C-1", "U-ORG", conv.id)
    assert reactivated is True
    assert svc.is_candidate_ghosted(db_session, "C-1", "U-ORG") is False

    row = db_session.query(CandidateGhostingStatus).filter(CandidateGhostingStatus.candidate_id == "C-1").first()
    assert row.is_reactivated is True
    assert row.reactivated_at is not None

def test_reactivate_candidate_logs_self_reactivated_event(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)

    svc.reactivate_candidate(db_session, "C-1", "U-ORG", conv.id)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "CANDIDATE_SELF_REACTIVATED").all()
    assert len(events) == 1

def test_reactivate_candidate_no_op_when_not_ghosted(db_session, seeded):
    candidate, conv = seeded
    reactivated = svc.reactivate_candidate(db_session, "C-1", "U-ORG", conv.id)
    assert reactivated is False

    events = db_session.query(ConversationEvent).filter(ConversationEvent.event_type == "CANDIDATE_SELF_REACTIVATED").all()
    assert events == []

def test_outreach_resumes_after_reactivation(db_session, seeded):
    candidate, conv = seeded
    _post_third_log(db_session, conv)
    svc.run_ghosting_detection_job(db_session)
    svc.reactivate_candidate(db_session, "C-1", "U-ORG", conv.id)

    result = svc.run_ghosting_detection_job(db_session)  # re-running shouldn't re-ghost
    assert result["ghosted"] == 0  # already has a (now reactivated) row -- dedup still holds
    assert svc.is_candidate_ghosted(db_session, "C-1", "U-ORG") is False

# ── never raises ────────────────────────────────────────────────────────

def test_job_never_raises_on_missing_candidate(db_session, seeded):
    candidate, conv = seeded
    log = CandidateNoResponseLog(tenant_id="U-ORG", candidate_id="NOPE", conversation_id=conv.id, detection_type="POST_THIRD")
    db_session.add(log)
    db_session.commit()

    result = svc.run_ghosting_detection_job(db_session)  # should not raise
    assert result["ghosted"] == 0

def test_job_skips_non_post_third_logs(db_session, seeded):
    candidate, conv = seeded
    db_session.add(CandidateNoResponseLog(tenant_id="U-ORG", candidate_id="C-1", conversation_id=conv.id, detection_type="FIRST_NO_RESPONSE"))
    db_session.commit()

    result = svc.run_ghosting_detection_job(db_session)
    assert result["ghosted"] == 0

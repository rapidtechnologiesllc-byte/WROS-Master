"""
Phase 3 Part A1 -- Thunder Conversation Core (app.services.thunder_service).

Proves the two guarantees `03-THUNDER-AGENTIC-LAYER.md` requires of
send_thunder_message() that the pre-existing send_whatsapp_message()
gate didn't already cover -- consent and debounce -- without
re-proving R-08 itself (already covered by test_whatsapp_routing.py;
here we only confirm send_thunder_message() doesn't bypass it), plus
build_candidate_context()'s cross-channel aggregation.

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
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.internal_note import InternalNote
from app.models.notification import Notification
from app.models.user import Jobs, Users

from app.services.ai_conversation_service import AI_AGENT_NAME
import app.services.whatsapp_routing_service as routing
from app.services.whatsapp_routing_service import ConversationOwnedByHuman
from app.services.thunder_service import (
    ConsentNotGiven,
    DuplicateMessageSuppressed,
    build_candidate_context,
    has_active_consent,
    send_thunder_message,
)


@pytest.fixture(autouse=True)
def _default_whatsapp_number(monkeypatch):
    monkeypatch.setattr(routing, "DEFAULT_WHATSAPP_NUMBER", "+10005550000")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, Jobs.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateAIAssignment.__table__,
        Notification.__table__, ConsentRecord.__table__, InternalNote.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def fixtures(db_session):
    org_owner = Users(UserID="U-ORG", UserRole="Admin", UserEmail="admin@blitzenx.com", UserPassword="h")
    recruiter = Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword="h")
    db_session.add_all([org_owner, recruiter])
    db_session.commit()

    candidate = Candidate(
        candidateID="C-100", candidateEmail="cand100@example.com", candidatePassword="h",
        candidateMobile="+19995551234", timezone="Asia/Kolkata",
    )
    db_session.add(candidate)
    db_session.commit()

    conversation = CandidateConversation(
        tenant_id=org_owner.UserID, candidate_id=candidate.candidateID,
        status="open", ai_agent_name=AI_AGENT_NAME, channel_preference="whatsapp",
        owner_type="ai_agent", owner_id=AI_AGENT_NAME,
    )
    db_session.add(conversation)
    db_session.commit()

    return org_owner, recruiter, candidate, conversation


def _grant_consent(db, candidate_id, *, given=True, captured_at=None):
    record = ConsentRecord(
        subject_type="candidate", subject_id=candidate_id,
        consent_type="whatsapp_outreach", consent_given=given,
    )
    if captured_at is not None:
        record.captured_at = captured_at
    db.add(record)
    db.commit()
    return record


# ---------------------------------------------------------------------------
# has_active_consent
# ---------------------------------------------------------------------------

def test_has_active_consent_false_when_no_record(db_session, fixtures):
    _, _, candidate, _ = fixtures
    assert has_active_consent(db_session, candidate.candidateID) is False


def test_has_active_consent_true_when_granted(db_session, fixtures):
    _, _, candidate, _ = fixtures
    _grant_consent(db_session, candidate.candidateID, given=True)
    assert has_active_consent(db_session, candidate.candidateID) is True


def test_has_active_consent_latest_record_wins_on_revocation(db_session, fixtures):
    _, _, candidate, _ = fixtures
    _grant_consent(db_session, candidate.candidateID, given=True, captured_at=datetime(2026, 1, 1))
    _grant_consent(db_session, candidate.candidateID, given=False, captured_at=datetime(2026, 1, 2))
    assert has_active_consent(db_session, candidate.candidateID) is False


# ---------------------------------------------------------------------------
# send_thunder_message -- consent gate
# ---------------------------------------------------------------------------

def test_send_rejected_without_consent(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    with pytest.raises(ConsentNotGiven):
        send_thunder_message(
            db_session, conversation, candidate, "Hi there",
            sender_type="ai_agent", whatsapp_client=lambda *a: True,
        )
    assert db_session.query(ConversationEvent).count() == 0


def test_send_succeeds_with_consent(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)
    event = send_thunder_message(
        db_session, conversation, candidate, "Hi there",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    assert event.event_type == "ai_message_sent"
    assert event.event_data["body"] == "Hi there"


# ---------------------------------------------------------------------------
# send_thunder_message -- R-08 ownership lock is NOT bypassed
# ---------------------------------------------------------------------------

def test_send_still_enforces_r08_ownership_lock(db_session, fixtures):
    _, recruiter, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)
    conversation.owner_type = "hr_user"
    conversation.owner_id = recruiter.UserID
    db_session.add(conversation)
    db_session.commit()

    with pytest.raises(ConversationOwnedByHuman):
        send_thunder_message(
            db_session, conversation, candidate, "Thunder trying to jump in",
            sender_type="ai_agent", whatsapp_client=lambda *a: True,
        )


# ---------------------------------------------------------------------------
# send_thunder_message -- debounce
# ---------------------------------------------------------------------------

def _backdate_last_event(db, conversation, *, seconds_ago):
    event = (
        db.query(ConversationEvent)
        .filter(ConversationEvent.conversation_id == conversation.id)
        .order_by(ConversationEvent.id.desc())
        .first()
    )
    event.created_at = datetime.utcnow() - timedelta(seconds=seconds_ago)
    db.add(event)
    db.commit()


def test_duplicate_send_within_debounce_window_is_suppressed(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)

    send_thunder_message(
        db_session, conversation, candidate, "Same message",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    with pytest.raises(DuplicateMessageSuppressed):
        send_thunder_message(
            db_session, conversation, candidate, "Same message",
            sender_type="ai_agent", whatsapp_client=lambda *a: True,
        )


def test_different_message_within_window_is_not_suppressed(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)

    send_thunder_message(
        db_session, conversation, candidate, "First message",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    event = send_thunder_message(
        db_session, conversation, candidate, "Second, different message",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    assert event.event_data["body"] == "Second, different message"


def test_same_message_after_debounce_window_elapses_is_allowed(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)

    send_thunder_message(
        db_session, conversation, candidate, "Same message",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    # Simulate the debounce window having elapsed by backdating the
    # already-inserted event's real (DB-clock) timestamp, rather than
    # passing a synthetic `now` into send_thunder_message -- the function
    # always compares against real wall-clock time, matching how
    # ConversationEvent.created_at is actually populated (func.now()).
    _backdate_last_event(db_session, conversation, seconds_ago=61)

    event = send_thunder_message(
        db_session, conversation, candidate, "Same message",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    assert event.event_data["body"] == "Same message"


# ---------------------------------------------------------------------------
# send_thunder_message -- channel scoping
# ---------------------------------------------------------------------------

def test_non_whatsapp_channel_not_implemented(db_session, fixtures):
    _, _, candidate, conversation = fixtures
    _grant_consent(db_session, candidate.candidateID)
    with pytest.raises(NotImplementedError):
        send_thunder_message(
            db_session, conversation, candidate, "Hi", sender_type="ai_agent", channel="email",
        )


# ---------------------------------------------------------------------------
# build_candidate_context
# ---------------------------------------------------------------------------

def test_context_desire_profile_is_none_not_fabricated(db_session, fixtures):
    _, _, candidate, _ = fixtures
    context = build_candidate_context(db_session, candidate)
    assert context["desire_profile"] is None


def test_context_aggregates_cross_channel_history_in_order(db_session, fixtures):
    _, _, candidate, conversation = fixtures

    # Email event (as ai_conversation_service would log it), older.
    db_session.add(ConversationEvent(
        conversation_id=conversation.id, event_type="ai_message_sent",
        event_data={"channel": "email", "body": "Missing-fields email"},
        triggered_by="ai_agent", created_at=datetime(2026, 3, 1, 9, 0, 0),
    ))
    db_session.commit()

    # WhatsApp event, newer, via the real send path.
    _grant_consent(db_session, candidate.candidateID)
    send_thunder_message(
        db_session, conversation, candidate, "WhatsApp follow-up",
        sender_type="ai_agent", whatsapp_client=lambda *a: True,
    )
    for event in db_session.query(ConversationEvent).filter(
        ConversationEvent.event_data.isnot(None)
    ).all():
        if event.event_data.get("body") == "WhatsApp follow-up":
            event.created_at = datetime(2026, 3, 1, 10, 0, 0)
    db_session.commit()

    db_session.add(InternalNote(
        candidate_id=candidate.candidateID, content="Strong technical background",
        category="General", created_by_id="U-REC",
    ))
    db_session.commit()

    context = build_candidate_context(db_session, candidate)

    channels = [item["channel"] for item in context["message_history"]]
    assert channels == ["email", "whatsapp"]
    assert context["message_history"][0]["body"] == "Missing-fields email"
    assert context["message_history"][1]["body"] == "WhatsApp follow-up"
    assert len(context["internal_notes"]) == 1
    assert context["internal_notes"][0]["content"] == "Strong technical background"
    assert context["current_owner_type"] == "ai_agent"
    assert context["active_conversation_id"] == conversation.id


def test_context_reflects_current_owner_after_takeover(db_session, fixtures):
    _, recruiter, candidate, conversation = fixtures
    conversation.owner_type = "hr_user"
    conversation.owner_id = recruiter.UserID
    db_session.add(conversation)
    db_session.commit()

    context = build_candidate_context(db_session, candidate)
    assert context["current_owner_type"] == "hr_user"
    assert context["current_owner_id"] == recruiter.UserID


def test_context_includes_real_open_jobs_and_excludes_closed(db_session, fixtures):
    """Real bug fix, 2026-07-23: Thunder deflected "what roles do you
    have" to HR because build_candidate_context() never included any
    job data. Only jobStatus != "Closed" should surface."""
    _, _, candidate, _ = fixtures

    db_session.add_all([
        Jobs(
            jobID="J-OPEN", jobTitle="Lead Guidewire Business Analyst",
            jobDescription="...", jobSkills="Guidewire, BA, PolicyCenter",
            jobExperience="5-8 years", jobLocation="Remote",
            jobStatus="Open", noOfPositions=2,
        ),
        Jobs(
            jobID="J-LEAN", jobTitle="Java Developer",
            jobDescription="...", jobSkills="Java, Spring",
            jobExperience="3-5 years", jobLocation="Bangalore",
            jobStatus="Lean", noOfPositions=1,
        ),
        Jobs(
            jobID="J-CLOSED", jobTitle="Should Not Appear",
            jobDescription="...", jobSkills="N/A",
            jobExperience="0-1 years", jobLocation="Remote",
            jobStatus="Closed", noOfPositions=0,
        ),
    ])
    db_session.commit()

    context = build_candidate_context(db_session, candidate)

    job_ids = {job["job_id"] for job in context["open_jobs"]}
    assert job_ids == {"J-OPEN", "J-LEAN"}
    guidewire_job = next(j for j in context["open_jobs"] if j["job_id"] == "J-OPEN")
    assert guidewire_job["title"] == "Lead Guidewire Business Analyst"
    assert guidewire_job["experience_required"] == "5-8 years"


def test_context_includes_candidate_own_profile_for_matching(db_session, fixtures):
    """Without the candidate's own skills/experience/title in context,
    Thunder has nothing concrete to compare open jobs against."""
    _, _, candidate, _ = fixtures
    candidate.candidateJobTitle = "Guidewire Business Analyst"
    candidate.candidateSkills = "Guidewire, PolicyCenter, BillingCenter"
    candidate.candidateExperience = "6 years"
    candidate.total_experience_months = 72
    db_session.add(candidate)
    db_session.commit()

    context = build_candidate_context(db_session, candidate)

    profile = context["candidate_profile"]
    assert profile["job_title"] == "Guidewire Business Analyst"
    assert profile["skills"] == "Guidewire, PolicyCenter, BillingCenter"
    assert profile["total_experience_months"] == 72

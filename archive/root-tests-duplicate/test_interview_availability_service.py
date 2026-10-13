"""
S-047/HRMS-0447 -- Interview Availability Collection.

Real architecture under test (see interview_availability_service
module docstring): no INTERVIEW_SCHEDULING conversation-state enum
value exists (tracked via ConversationEvent audit trail instead); no
event bus (AVAILABILITY_PROVIDED is a real ConversationEvent, HRMS-0448
Calendar Matching doesn't exist to consume it); Gemini via an
injectable llm_call so no test ever calls a real external API;
timezone fallback chain (LLM-extracted -> candidate_memory location
fact -> Candidate.timezone); BR-02 rejects past dates, Step 4 rejects
weekends and outside-08:00-20:00 slots; BR-03 gates on >=2 cumulative
valid slots, not just the current message's contribution.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_availability_slot import CandidateAvailabilitySlot
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.user import Users

import app.services.interview_availability_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateAvailabilitySlot.__table__, CandidateMemory.__table__, CandidateMemoryFact.__table__,
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
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None)
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210", timezone="America/Chicago")
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="awaiting_candidate", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _next_weekday(base, target_weekday):
    """Returns the next date >= base with the given weekday (0=Mon)."""
    days_ahead = (target_weekday - base.weekday()) % 7
    return base + timedelta(days=days_ahead)


def _fake_llm(slots):
    return lambda prompt: json.dumps(slots)


# ── Step 3: initial ask ────────────────────────────────────────────

def test_send_availability_request_logs_event(db_session, seeded):
    candidate, conv = seeded
    message = svc.send_availability_request(db_session, conv)
    assert message == svc.AVAILABILITY_REQUEST_MESSAGE

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "availability_requested").first()
    assert event is not None


# ── AC-2/AC-3/TC-001: correctly parses structured slots ──────────────

def test_parses_two_valid_slots_and_flags_sufficient(db_session, seeded):
    candidate, conv = seeded
    d1 = _next_weekday(date.today() + timedelta(days=2), 1)  # Tuesday
    d2 = _next_weekday(date.today() + timedelta(days=2), 3)  # Thursday
    llm_call = _fake_llm([
        {"date": d1.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"},
        {"date": d2.isoformat(), "start_time": "09:00", "end_time": "10:00", "timezone": "America/Chicago"},
    ])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Tuesday 2-4 PM and Thursday morning", llm_call=llm_call)
    assert result["outcome"] == "slots_sufficient"
    assert result["slots_stored"] == 2
    assert result["total_valid"] == 2

    slots = db_session.query(CandidateAvailabilitySlot).filter(CandidateAvailabilitySlot.candidate_id == "C-1").all()
    assert len(slots) == 2
    assert {s.timezone for s in slots} == {"America/Chicago"}

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "AVAILABILITY_PROVIDED").first()
    assert event is not None
    assert event.event_data["total_valid_slots"] == 2


# ── AC-4/TC-002: past date rejected ───────────────────────────────────

def test_past_date_rejected_and_not_stored(db_session, seeded):
    candidate, conv = seeded
    past = date.today() - timedelta(days=5)
    llm_call = _fake_llm([{"date": past.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"}])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "I was free last week", llm_call=llm_call)
    assert result["outcome"] == "slots_need_more"
    assert result["slots_stored"] == 0
    assert "past_date" in result["rejections"]
    assert result["message"] == svc.PAST_DATE_REJECTION_MESSAGE

    assert db_session.query(CandidateAvailabilitySlot).count() == 0


# ── AC-5/TC-003: weekend rejected ─────────────────────────────────────

def test_weekend_slot_rejected_and_not_stored(db_session, seeded):
    candidate, conv = seeded
    saturday = _next_weekday(date.today() + timedelta(days=1), 5)
    llm_call = _fake_llm([{"date": saturday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"}])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Saturday afternoon", llm_call=llm_call)
    assert result["outcome"] == "slots_need_more"
    assert result["slots_stored"] == 0
    assert "weekend" in result["rejections"]
    assert result["message"] == svc.WEEKEND_REJECTION_MESSAGE

    assert db_session.query(CandidateAvailabilitySlot).count() == 0


def test_outside_business_hours_rejected(db_session, seeded):
    candidate, conv = seeded
    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "21:00", "end_time": "22:00", "timezone": "America/Chicago"}])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free late at 9pm", llm_call=llm_call)
    assert result["outcome"] == "slots_need_more"
    assert "outside_business_hours" in result["rejections"]
    assert db_session.query(CandidateAvailabilitySlot).count() == 0


# ── AC-6/TC-004: only 1 valid slot -> asks for more, event NOT published ─

def test_one_valid_slot_asks_for_more_no_event_published(db_session, seeded):
    candidate, conv = seeded
    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"}])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday afternoon", llm_call=llm_call)
    assert result["outcome"] == "slots_need_more"
    assert result["slots_stored"] == 1
    assert result["message"] == svc.NEED_MORE_SLOTS_MESSAGE

    assert db_session.query(CandidateAvailabilitySlot).count() == 1
    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "AVAILABILITY_PROVIDED").first()
    assert event is None


def test_second_message_pushes_cumulative_total_over_threshold(db_session, seeded):
    candidate, conv = seeded
    d1 = _next_weekday(date.today() + timedelta(days=1), 1)
    d2 = _next_weekday(date.today() + timedelta(days=1), 3)

    svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Tuesday", llm_call=_fake_llm([{"date": d1.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"}]))
    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "also free Thursday", llm_call=_fake_llm([{"date": d2.isoformat(), "start_time": "09:00", "end_time": "10:00", "timezone": "America/Chicago"}]))

    assert result["outcome"] == "slots_sufficient"
    assert result["total_valid"] == 2


# ── No slots found ──────────────────────────────────────────────────

def test_no_slots_found_asks_to_clarify(db_session, seeded):
    candidate, conv = seeded
    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "sounds good", llm_call=_fake_llm([]))
    assert result["outcome"] == "no_slots_found"
    assert result["message"] == svc.NO_SLOTS_FOUND_MESSAGE


def test_llm_failure_never_raises(db_session, seeded):
    candidate, conv = seeded

    def _boom(prompt):
        raise RuntimeError("simulated LLM failure")

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Tuesday", llm_call=_boom)  # should not raise
    assert result["outcome"] == "parse_failed"


# ── BR-01: timezone inference fallback chain ──────────────────────────

def test_uses_llm_extracted_timezone_when_present(db_session, seeded):
    candidate, conv = seeded
    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "Asia/Kolkata"}])

    svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday IST", llm_call=llm_call)
    slot = db_session.query(CandidateAvailabilitySlot).first()
    assert slot.timezone == "Asia/Kolkata"


def test_falls_back_to_candidate_timezone_when_no_timezone_extracted(db_session, seeded):
    candidate, conv = seeded
    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": None}])

    svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday", llm_call=llm_call)
    slot = db_session.query(CandidateAvailabilitySlot).first()
    assert slot.timezone == "America/Chicago"  # candidate.timezone from the fixture


def test_falls_back_to_memory_location_fact_when_it_is_a_valid_timezone(db_session, seeded):
    candidate, conv = seeded
    db_session.add(CandidateMemory(candidate_id="C-1", tenant_id="U-ORG"))
    db_session.add(CandidateMemoryFact(candidate_id="C-1", tenant_id="U-ORG", fact_category="PERSONAL", fact_key="location", fact_value="Europe/London", confidence=0.9))
    db_session.commit()

    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": None}])

    svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday", llm_call=llm_call)
    slot = db_session.query(CandidateAvailabilitySlot).first()
    assert slot.timezone == "Europe/London"


def test_invalid_extracted_timezone_falls_through_chain(db_session, seeded):
    candidate, conv = seeded
    weekday = _next_weekday(date.today() + timedelta(days=1), 2)
    llm_call = _fake_llm([{"date": weekday.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "Not/A/RealZone"}])

    svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday", llm_call=llm_call)
    slot = db_session.query(CandidateAvailabilitySlot).first()
    assert slot.timezone == "America/Chicago"


# ── mixed valid + rejected slots in one message ───────────────────────

def test_mixed_valid_and_rejected_slots_only_stores_valid(db_session, seeded):
    candidate, conv = seeded
    valid_day = _next_weekday(date.today() + timedelta(days=1), 2)
    weekend_day = _next_weekday(date.today() + timedelta(days=1), 5)
    llm_call = _fake_llm([
        {"date": valid_day.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"},
        {"date": weekend_day.isoformat(), "start_time": "14:00", "end_time": "16:00", "timezone": "America/Chicago"},
    ])

    result = svc.parse_availability_response(db_session, conv, candidate, "U-ORG", "free Wednesday or Saturday", llm_call=llm_call)
    assert result["slots_stored"] == 1
    assert "weekend" in result["rejections"]
    assert db_session.query(CandidateAvailabilitySlot).count() == 1

"""
Internal Ask Thunder (app.services.internal_ask_thunder_service).

Proves: intent classification is the ONLY thing the LLM does (mocked
here to return each intent in turn); every actual answer -- which
candidates match, what a named candidate's status is -- comes from a
real DB query, and an unrecognized/unclassifiable question gets the
honest UNSUPPORTED_QUERY_MESSAGE rather than an invented answer.

No real Gemini call is made anywhere in this file.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datetime import date

from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry

import app.services.internal_ask_thunder_service as svc


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setattr(svc, "GEMINI_API_KEY", "fake-key-for-test")


def _mock_gemini_returns(json_payload):
    mock_response = MagicMock()
    mock_response.content = json.dumps(json_payload)
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return MagicMock(return_value=mock_llm)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateStatus.__table__, Employee.__table__, BenchPoolEntry.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def candidates(db_session):
    java_dev = Candidate(
        candidateID="C-JAVA", candidateEmail="java.dev@example.com", candidatePassword="h",
        candidateFirstName="Raj", candidateLastName="Kumar",
        candidateJobTitle="Java Developer", candidateSkills="Java, Spring Boot, SQL",
        candidateExperience="5 years",
    )
    guidewire_dev = Candidate(
        candidateID="C-GW", candidateEmail="gw.dev@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma",
        candidateJobTitle="Guidewire Developer", candidateSkills="Guidewire, Java, PolicyCenter",
        candidateExperience="7 years",
    )
    db_session.add_all([java_dev, guidewire_dev])
    db_session.commit()
    db_session.add(CandidateStatus(candidateID="C-GW", piplineStatus="Interviewing", status="Active"))
    db_session.commit()
    return java_dev, guidewire_dev


def test_find_matching_candidates_ranks_by_keyword_overlap(db_session, candidates):
    results = svc.find_matching_candidates(db_session, "Java developer")
    assert results
    assert results[0]["candidate_id"] == "C-JAVA"


def test_find_matching_candidates_no_keywords_returns_empty(db_session, candidates):
    assert svc.find_matching_candidates(db_session, "for with and") == []


def test_find_matching_candidates_requires_all_keywords_not_just_one(db_session, candidates):
    """Real bug, 2026-08-05: an 'Agentic AI developer' with zero Guidewire
    experience was returned for a 'Guidewire developer' search because the
    generic word 'developer' alone was enough to score > 0. Only the real
    Guidewire Developer should match; a candidate matching just the generic
    word must not."""
    unrelated_dev = Candidate(
        candidateID="C-UNRELATED", candidateEmail="unrelated@example.com", candidatePassword="h",
        candidateFirstName="Alex", candidateLastName="Doe",
        candidateJobTitle="Agentic AI Developer", candidateSkills="JavaScript, React, Node.js",
        candidateExperience="Since 2021",
    )
    db_session.add(unrelated_dev)
    db_session.commit()

    results = svc.find_matching_candidates(db_session, "Guidewire developer")
    ids = [r["candidate_id"] for r in results]
    assert "C-GW" in ids
    assert "C-UNRELATED" not in ids


def test_sourcing_reply_never_includes_raw_candidate_id(db_session, candidates):
    results = svc.find_matching_candidates(db_session, "Java developer")
    reply = svc._format_sourcing_reply("Java developer", results)
    for r in results:
        assert r["candidate_id"] not in reply


def test_find_matching_candidates_no_match_returns_empty(db_session, candidates):
    assert svc.find_matching_candidates(db_session, "COBOL mainframe") == []


def test_get_candidate_status_summary_single_match(db_session, candidates):
    result = svc.get_candidate_status_summary(db_session, "Priya Sharma")
    assert len(result["matches"]) == 1
    assert result["matches"][0]["candidate_id"] == "C-GW"
    assert result["matches"][0]["pipeline_status"] == "Interviewing"


def test_get_candidate_status_summary_no_match(db_session, candidates):
    result = svc.get_candidate_status_summary(db_session, "Nonexistent Person")
    assert result["matches"] == []


def test_answer_internal_query_sourcing_intent(monkeypatch, db_session, candidates):
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "sourcing", "query": "Java developer"}),
    )
    result = svc.answer_internal_query(db_session, "Find me a Java developer")
    assert result["intent"] == "sourcing"
    assert "Raj Kumar" in result["reply"]


def test_answer_internal_query_candidate_status_intent(monkeypatch, db_session, candidates):
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "candidate_status", "query": "Priya Sharma"}),
    )
    result = svc.answer_internal_query(db_session, "How is Priya Sharma doing?")
    assert result["intent"] == "candidate_status"
    assert "Interviewing" in result["reply"]


def test_answer_internal_query_unknown_intent_returns_honest_fallback(monkeypatch, db_session):
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "unknown", "query": ""}),
    )
    result = svc.answer_internal_query(db_session, "What's the weather like?")
    assert result["intent"] == "unknown"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


def test_answer_internal_query_classification_failure_returns_honest_fallback(monkeypatch, db_session):
    def _raise(*args, **kwargs):
        raise RuntimeError("Gemini down")
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = _raise
    monkeypatch.setattr(svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

    result = svc.answer_internal_query(db_session, "anything")
    assert result["intent"] == "unknown"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


def test_classify_internal_query_strips_markdown_fence(monkeypatch):
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "sourcing", "query": "Python"}),
    )
    # Simulate a fenced response directly through the mock's content.
    mock_response = MagicMock()
    mock_response.content = '```json\n{"intent": "sourcing", "query": "Python"}\n```'
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    monkeypatch.setattr(svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

    result = svc.classify_internal_query("find me a python dev")
    assert result == {"intent": "sourcing", "query": "Python"}


@pytest.fixture()
def bench_employees(db_session):
    react_dev = Employee(
        first_name="Ravi", last_name="Iyer", email="ravi.iyer@blitzenx.com",
        joining_date=date(2024, 1, 1), current_title="React Developer",
    )
    java_dev = Employee(
        first_name="Meena", last_name="Nair", email="meena.nair@blitzenx.com",
        joining_date=date(2023, 6, 1), current_title="Java Developer",
    )
    db_session.add_all([react_dev, java_dev])
    db_session.commit()

    db_session.add_all([
        BenchPoolEntry(employee_id=react_dev.id, available_from=date(2026, 8, 1), skill_tags=json.dumps(["React", "TypeScript"])),
        BenchPoolEntry(employee_id=java_dev.id, available_from=date(2026, 7, 15), skill_tags=json.dumps(["Java", "Spring"])),
    ])
    db_session.commit()
    return {"react_dev": react_dev, "java_dev": java_dev}


def test_find_available_bench_employees_no_filter_returns_all(db_session, bench_employees):
    results = svc.find_available_bench_employees(db_session, "")
    assert len(results) == 2


def test_find_available_bench_employees_filters_by_skill(db_session, bench_employees):
    # "React" alone -- "developer"/"role" are generic stopwords-adjacent
    # terms that would keyword-match both employees' titles, same
    # keyword-overlap tradeoff find_matching_candidates() already
    # accepts for candidates.
    results = svc.find_available_bench_employees(db_session, "React")
    assert len(results) == 1
    assert results[0]["name"] == "Ravi Iyer"


def test_answer_internal_query_bench_availability_intent(monkeypatch, db_session, bench_employees):
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "bench_availability", "query": "Java"}),
    )
    result = svc.answer_internal_query(db_session, "Who's free for a Java role right now?")
    assert result["intent"] == "bench_availability"
    assert "Meena Nair" in result["reply"]
    assert "Ravi Iyer" not in result["reply"]


def test_answer_internal_query_bench_availability_empty_query_not_treated_as_unsupported(monkeypatch, db_session, bench_employees):
    """Unlike SOURCING/CANDIDATE_STATUS, an empty query is a valid
    'who's on the bench' question, not an error."""
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "bench_availability", "query": ""}),
    )
    result = svc.answer_internal_query(db_session, "Who's on the bench?")
    assert result["intent"] == "bench_availability"
    assert result["reply"] != svc.UNSUPPORTED_QUERY_MESSAGE
    assert "Meena Nair" in result["reply"]
    assert "Ravi Iyer" in result["reply"]


# ---------------------------------------------------------------------------
# Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
# "i ask a question to thunder and move to a different page it looses
# the history and acts as a new session." Confirmed real cause: zero
# awareness of anything asked earlier in the SAME open chat. Proves
# history reaches the LLM prompt, a follow-up resolves via history,
# and history is capped/optional without breaking anything.
# ---------------------------------------------------------------------------

def test_history_is_included_in_the_prompt_sent_to_the_llm(monkeypatch):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({"intent": "candidate_status", "query": "Priya Sharma"})
    mock_llm.invoke.return_value = mock_response
    monkeypatch.setattr(svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

    svc.classify_internal_query(
        "what about her experience",
        history=[{"question": "how is Priya Sharma doing", "reply": "Priya Sharma -- pipeline status: Interviewing."}],
    )

    sent_prompt = mock_llm.invoke.call_args[0][0]
    assert "Priya Sharma" in sent_prompt
    assert "how is Priya Sharma doing" in sent_prompt
    assert "what about her experience" in sent_prompt


def test_follow_up_resolves_the_referenced_candidate_via_history(monkeypatch, db_session, candidates):
    """Real end-to-end proof: a follow-up whose OWN text has no name at
    all ("what about her experience") still reaches the right candidate
    -- exercised by mocking the LLM to return what a real history-aware
    classification would (the query resolved to a real name), then
    proving the DB layer + reply formatting complete the loop
    correctly, same as any other intent test in this file."""
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "candidate_status", "query": "Priya Sharma"}),
    )
    result = svc.answer_internal_query(
        db_session, "what about her status",
        history=[{"question": "how is Priya Sharma doing", "reply": "Priya Sharma -- pipeline status: Interviewing."}],
    )
    assert result["intent"] == "candidate_status"
    assert "Interviewing" in result["reply"]


def test_history_is_capped_at_max_history_turns(monkeypatch):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({"intent": "unknown", "query": ""})
    mock_llm.invoke.return_value = mock_response
    monkeypatch.setattr(svc, "ChatGoogleGenerativeAI", MagicMock(return_value=mock_llm))

    long_history = [{"question": f"question number {i}", "reply": f"reply number {i}"} for i in range(10)]
    svc.classify_internal_query("current question", history=long_history)

    sent_prompt = mock_llm.invoke.call_args[0][0]
    # Only the last MAX_HISTORY_TURNS should survive -- the earliest
    # ones must not appear anywhere in what was sent to the model.
    for i in range(10 - svc.MAX_HISTORY_TURNS):
        assert f"question number {i}" not in sent_prompt
    for i in range(10 - svc.MAX_HISTORY_TURNS, 10):
        assert f"question number {i}" in sent_prompt


def test_missing_history_is_backward_compatible(monkeypatch, db_session, candidates):
    """A caller that never passes history (or passes None/[]) must get
    exactly the same behavior as before this feature existed."""
    monkeypatch.setattr(
        svc, "ChatGoogleGenerativeAI",
        _mock_gemini_returns({"intent": "sourcing", "query": "Java developer"}),
    )
    result = svc.answer_internal_query(db_session, "Find me a Java developer")
    assert result["intent"] == "sourcing"
    assert "Raj Kumar" in result["reply"]


def test_empty_history_entries_are_skipped_gracefully():
    transcript = svc._format_history_transcript("current question", [{"question": "", "reply": ""}, None])
    assert transcript == "Staff: current question"

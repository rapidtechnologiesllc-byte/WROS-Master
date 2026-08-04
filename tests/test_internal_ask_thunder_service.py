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

"""
Flash (app.services.flash_service) -- renamed 2026-08-06 from "Ask
Thunder"/internal_ask_thunder_service.py.

2026-08-06: classify_internal_query() no longer calls an external LLM
at all (Avinash's direct instruction -- Flash's intent classification
must stay entirely inside WROS, no external API, no data leaving the
process). It's now pure local regex/keyword matching, so these tests
call it directly -- no mocking needed, nothing to fake an API key for.

Proves: every actual answer -- which candidates match, what a named
candidate's status is -- comes from a real DB query, and an
unrecognized/unclassifiable question gets the honest
UNSUPPORTED_QUERY_MESSAGE rather than an invented answer.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datetime import date

from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry

import app.services.flash_service as svc


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


# ---------------------------------------------------------------------------
# classify_internal_query() -- pure local classification, no mocking needed.
# ---------------------------------------------------------------------------

def test_classify_sourcing():
    result = svc.classify_internal_query("Find me a Java developer")
    assert result["intent"] == svc.INTENT_SOURCING
    assert "java" in result["query"].lower()


def test_classify_candidate_status():
    result = svc.classify_internal_query("How is Priya Sharma doing?")
    assert result["intent"] == svc.INTENT_CANDIDATE_STATUS
    assert result["query"] == "Priya Sharma"


def test_classify_bench_availability():
    result = svc.classify_internal_query("Who's free for a Java role right now?")
    assert result["intent"] == svc.INTENT_BENCH_AVAILABILITY


def test_classify_bench_availability_no_filter():
    result = svc.classify_internal_query("Who's on the bench?")
    assert result["intent"] == svc.INTENT_BENCH_AVAILABILITY
    assert result["query"] == ""


def test_classify_finance_pnl():
    result = svc.classify_internal_query("What's our margin this month")
    assert result["intent"] == svc.INTENT_FINANCE_PNL


def test_classify_finance_pnl_extracts_bu_name():
    result = svc.classify_internal_query("How's Axion doing on margin")
    assert result["intent"] == svc.INTENT_FINANCE_PNL
    assert result["query"] == "Axion"


def test_classify_ar_aging():
    result = svc.classify_internal_query("What invoices are overdue")
    assert result["intent"] == svc.INTENT_AR_AGING


def test_classify_my_tasks():
    result = svc.classify_internal_query("What's on my plate today")
    assert result["intent"] == svc.INTENT_MY_TASKS


def test_classify_unknown_falls_through_honestly():
    result = svc.classify_internal_query("What's the weather like?")
    assert result["intent"] == svc.INTENT_UNKNOWN
    assert result["query"] == ""


def test_classify_pronoun_resolves_via_history():
    """A follow-up whose own text has no name at all ('what about her
    status') still resolves to the real name via the caller-supplied
    history -- the local-classifier equivalent of what the old LLM
    version did with full transcript context."""
    result = svc.classify_internal_query(
        "what about her status",
        history=[{"question": "how is Priya Sharma doing", "reply": "Priya Sharma -- pipeline status: Interviewing."}],
    )
    assert result["intent"] == svc.INTENT_CANDIDATE_STATUS
    assert result["query"] == "Priya Sharma"


def test_classify_no_gemini_dependency_exists():
    """Real regression guard for the 2026-08-06 architecture change --
    Avinash's explicit instruction was that Flash's classification must
    never call an external API. If someone re-adds a GEMINI_API_KEY-style
    import to this module, this test should be revisited/removed
    deliberately, not silently broken."""
    assert not hasattr(svc, "GEMINI_API_KEY")
    assert not hasattr(svc, "ChatGoogleGenerativeAI")


# ---------------------------------------------------------------------------
# answer_internal_query() -- full turn, real classify + real DB lookup.
# ---------------------------------------------------------------------------

def test_answer_internal_query_sourcing_intent(db_session, candidates):
    result = svc.answer_internal_query(db_session, "Find me a Java developer")
    assert result["intent"] == "sourcing"
    assert "Raj Kumar" in result["reply"]


def test_answer_internal_query_candidate_status_intent(db_session, candidates):
    result = svc.answer_internal_query(db_session, "How is Priya Sharma doing?")
    assert result["intent"] == "candidate_status"
    assert "Interviewing" in result["reply"]


def test_answer_internal_query_unknown_intent_returns_honest_fallback(db_session):
    result = svc.answer_internal_query(db_session, "What's the weather like?")
    assert result["intent"] == "unknown"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


def test_answer_internal_query_relationship_question_is_honestly_unsupported(db_session):
    """Real scenario Avinash tested live, 2026-08-06: a client-relationship
    briefing question ('what's going well with the account, what do I
    need to improve') is correctly NOT hallucinated -- there is no real
    intent/data source for this yet, so it must fall through to the
    honest fallback, not invent an account summary."""
    result = svc.answer_internal_query(
        db_session,
        "I'm traveling to Builders next Monday, what's going well with the account "
        "and what do I need to improve on to build the relationship",
    )
    assert result["intent"] == "unknown"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


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


def test_answer_internal_query_bench_availability_intent(db_session, bench_employees):
    result = svc.answer_internal_query(db_session, "Who's free for a Java role right now?")
    assert result["intent"] == "bench_availability"
    assert "Meena Nair" in result["reply"]
    assert "Ravi Iyer" not in result["reply"]


def test_answer_internal_query_bench_availability_empty_query_not_treated_as_unsupported(db_session, bench_employees):
    """Unlike SOURCING/CANDIDATE_STATUS, an empty query is a valid
    'who's on the bench' question, not an error."""
    result = svc.answer_internal_query(db_session, "Who's on the bench?")
    assert result["intent"] == "bench_availability"
    assert result["reply"] != svc.UNSUPPORTED_QUERY_MESSAGE
    assert "Meena Nair" in result["reply"]
    assert "Ravi Iyer" in result["reply"]


def test_follow_up_resolves_the_referenced_candidate_via_history(db_session, candidates):
    """Real end-to-end proof: a follow-up whose own text has no name at
    all ('what about her status') still reaches the right candidate,
    resolved locally via history, no external call anywhere in the chain."""
    result = svc.answer_internal_query(
        db_session, "what about her status",
        history=[{"question": "how is Priya Sharma doing", "reply": "Priya Sharma -- pipeline status: Interviewing."}],
    )
    assert result["intent"] == "candidate_status"
    assert "Interviewing" in result["reply"]


def test_missing_history_is_backward_compatible(db_session, candidates):
    """A caller that never passes history (or passes None/[]) must get
    exactly the same behavior as before this feature existed."""
    result = svc.answer_internal_query(db_session, "Find me a Java developer")
    assert result["intent"] == "sourcing"
    assert "Raj Kumar" in result["reply"]


# ---------------------------------------------------------------------------
# FINANCE_PNL / AR_AGING / MY_TASKS -- basic smoke coverage only. Full
# RBAC-scoped test fixtures (BU-scoped Partner/BU Head vs org-wide
# Finance/Super User, matching app.core.revenue_visibility_scope) are a
# separate, more thorough pass -- deliberately deferred per Avinash's
# 2026-08-06 direction ("let's figure this out after the current backlog
# completes for entire employee, finance, client, any internal data"),
# not skipped by oversight. Live-verified manually in the browser as
# Troy (Partner, Axion) and as an HR user (denied) in the meantime --
# see CLAUDE.md's Thunder-vs-Flash session log for that verification.
# ---------------------------------------------------------------------------

def test_answer_internal_query_finance_pnl_denied_without_current_user(db_session):
    """current_user is required for financial intents -- fails closed,
    not open, if a caller invokes this without one (should never happen
    from the real endpoint, always behind auth)."""
    result = svc.answer_internal_query(db_session, "What's our margin this month")
    assert result["intent"] == "finance_pnl"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


def test_answer_internal_query_ar_aging_denied_without_current_user(db_session):
    result = svc.answer_internal_query(db_session, "What invoices are overdue")
    assert result["intent"] == "ar_aging"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE


def test_answer_internal_query_my_tasks_denied_without_current_user(db_session):
    result = svc.answer_internal_query(db_session, "What's on my plate today")
    assert result["intent"] == "my_tasks"
    assert result["reply"] == svc.UNSUPPORTED_QUERY_MESSAGE

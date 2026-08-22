"""
S-038/HRMS-0438 -- Compensation Fit Score.

Real architecture under test (see compensation_scoring_service module
docstring): candidates.expected_ctc doesn't exist -- read from
candidate_memory_facts (category=SALARY, key=expected_ctc) and always
run through response_parser_service.normalize_salary() since the only
live producer (facts_extraction_service) stores raw strings, not
pre-normalized values; jobs.budget_min/budget_max lazily parsed from
the free-text salaryRange (LPA assumed); BR-01 null expected_ctc or no
budget -> neutral 50; the under-budget-min rule is unreachable given
rule ordering, implemented per the AC/TC (first-match-wins), not the
unreachable narrative rule; score_breakdown flat-merges with
technical_scoring_service's keys, never overwrites; BR-02 flags are
advisory only, never auto-reject.

"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_memory import CandidateMemory, CandidateMemoryFact
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, Users

import app.services.compensation_scoring_service as svc

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
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    job = Jobs(jobID="J-1", jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire", jobExperience="5+ years", jobLocation="Bangalore", salaryRange="20 LPA")
    db_session.add_all([owner, candidate, job])
    db_session.commit()
    return candidate, job

def _set_expected_ctc(db_session, raw_value):
    db_session.add(CandidateMemoryFact(tenant_id="U-ORG", candidate_id="C-1", fact_category="SALARY", fact_key="expected_ctc", fact_value=raw_value, confidence=0.9))
    db_session.commit()

# ── TC-001: within budget ────────────────────────────────────────────

def test_within_budget_scores_100(db_session, seeded):
    candidate, job = seeded  # budget parses to 20 LPA = 20,00,000 * 100 paise
    _set_expected_ctc(db_session, "18 LPA")

    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 100
    assert result["score_breakdown"]["pct_over_budget"] == 0.0

def test_exactly_at_budget_max_scores_100(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "20 LPA")
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 100

# ── TC-002: 12% over -> 40 ────────────────────────────────────────────

def test_twelve_percent_over_scores_40(db_session, seeded):
    candidate, job = seeded  # budget_max = 20 LPA; 12% over = 22.4 LPA
    _set_expected_ctc(db_session, "22.4 LPA")
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 40

def test_five_percent_over_scores_70(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "21 LPA")  # 5% over
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 70

# ── TC-003: 25% over -> 10 + flag ────────────────────────────────────

def test_twenty_five_percent_over_scores_10_and_creates_flag(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "25 LPA")  # 25% over
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 10

    flags = db_session.query(CandidateJobFlag).filter(CandidateJobFlag.candidate_id == "C-1", CandidateJobFlag.job_id == "J-1").all()
    assert len(flags) == 1
    assert flags[0].flag_type == "COMPENSATION_MISMATCH"
    assert flags[0].severity == "HIGH"
    assert flags[0].is_resolved is False

def test_no_flag_created_when_within_threshold(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "21 LPA")  # 5% over -- below the 20% flag threshold
    svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    flags = db_session.query(CandidateJobFlag).filter(CandidateJobFlag.candidate_id == "C-1", CandidateJobFlag.job_id == "J-1").all()
    assert flags == []

def test_recalculating_updates_existing_flag_not_duplicate(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "25 LPA")
    svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")

    flags = db_session.query(CandidateJobFlag).filter(CandidateJobFlag.candidate_id == "C-1", CandidateJobFlag.job_id == "J-1").all()
    assert len(flags) == 1

# ── TC-004 / BR-01: null expected_ctc -> neutral 50 ─────────────────

def test_null_expected_ctc_scores_50_neutral(db_session, seeded):
    candidate, job = seeded  # no fact set at all
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 50

def test_unparseable_expected_ctc_scores_50_neutral(db_session, seeded):
    candidate, job = seeded
    _set_expected_ctc(db_session, "negotiable")  # no number -- normalize_salary() returns None
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 50

def test_no_budget_set_scores_50_neutral(db_session, seeded):
    candidate, job = seeded
    job.salaryRange = ""  # no numbers -- budget_max stays None after lazy parse
    db_session.commit()
    _set_expected_ctc(db_session, "22 LPA")

    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")
    assert result["compensation_score"] == 50

# ── BR-02: never auto-rejects ─────────────────────────────────────────

def test_flag_is_advisory_only_score_still_computed(db_session, seeded):
    """Even at the worst score (10) with a HIGH-severity flag created,
    the job's own status field is left completely untouched -- this is
    purely advisory, never an auto-reject."""
    candidate, job = seeded
    job_status_before = job.jobStatus
    _set_expected_ctc(db_session, "30 LPA")  # 50% over

    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")

    assert result["compensation_score"] == 10
    assert job.jobStatus == job_status_before

# ── score_breakdown merge (not overwrite) with technical_scoring_service ─

def test_score_breakdown_merges_with_existing_technical_data(db_session, seeded):
    candidate, job = seeded
    # Simulate technical_scoring_service having already written its keys.
    existing = CandidateJobScore(tenant_id="U-ORG", candidate_id="C-1", job_id="J-1", technical_score=85, score_breakdown={"skill_match_pct": 100, "matched_skills": ["Guidewire"]})
    db_session.add(existing)
    db_session.commit()

    _set_expected_ctc(db_session, "18 LPA")
    result = svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")

    assert result["technical_score"] == 85  # untouched
    assert result["score_breakdown"]["skill_match_pct"] == 100  # preserved, not erased
    assert result["score_breakdown"]["expected_ctc_paise"] is not None  # compensation's own key added

def test_technical_rescore_does_not_erase_compensation_data(db_session, seeded):
    """The reverse direction -- a technical rescore must not wipe out
    compensation's keys either."""
    import app.services.technical_scoring_service as tech_svc

    candidate, job = seeded
    _set_expected_ctc(db_session, "25 LPA")
    svc.calculate_compensation_score(db_session, "C-1", "J-1", "U-ORG")

    tech_svc.calculate_technical_score(db_session, "C-1", "J-1", "U-ORG")

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert "expected_ctc_paise" in row.score_breakdown
    assert "skill_match_pct" in row.score_breakdown

# ── recalculate_for_candidate() ────────────────────────────────────────

def test_recalculate_for_candidate_scores_linked_job(db_session, seeded):
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()
    _set_expected_ctc(db_session, "18 LPA")

    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert len(results) == 1
    assert results[0]["compensation_score"] == 100

def test_recalculate_for_candidate_never_raises(db_session, seeded, monkeypatch):
    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    def _boom(db, cid, jid, tid):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(svc, "calculate_compensation_score", _boom)
    results = svc.recalculate_for_candidate(db_session, candidate, "U-ORG")
    assert results == []

# ── wired into facts_extraction_service.extract_facts() ────────────────

def test_extract_facts_triggers_recalculation_when_expected_ctc_extracted(db_session, seeded):
    import json
    import app.services.facts_extraction_service as facts_svc
    from app.models.candidate_ai import CandidateConversation, ConversationEvent

    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder")
    db_session.add(conv)
    db_session.commit()

    llm_response = json.dumps([{"fact_category": "SALARY", "fact_key": "expected_ctc", "fact_value": "18 LPA", "confidence": 0.9}])
    facts_svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "I'm expecting 18 LPA", llm_call=lambda p: llm_response)

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row is not None
    assert row.compensation_score == 100

def test_extract_facts_does_not_recalculate_when_expected_ctc_not_extracted(db_session, seeded):
    import json
    import app.services.facts_extraction_service as facts_svc
    from app.models.candidate_ai import CandidateConversation, ConversationEvent

    candidate, job = seeded
    candidate.job_id = "J-1"
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder")
    db_session.add(conv)
    db_session.commit()

    llm_response = json.dumps([{"fact_category": "PERSONAL", "fact_key": "location", "fact_value": "Bangalore", "confidence": 0.9}])
    facts_svc.extract_facts(db_session, candidate, "U-ORG", conv.id, "I'm in Bangalore", llm_call=lambda p: llm_response)

    row = db_session.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == "C-1", CandidateJobScore.job_id == "J-1").first()
    assert row is None

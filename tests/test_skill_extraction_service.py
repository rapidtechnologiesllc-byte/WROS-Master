"""
S-029/HRMS-0429 -- Skill Extraction & Tagging from Resume.

Real architecture adaptations under test (see skill_extraction_service
module docstring): candidateSkills (Text) cascade is comma-joined,
not a JSONB array; "ON CONFLICT DO NOTHING" is query-then-skip.
Synonym library is the real seed set in app.constants.skill_synonyms.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Users

import app.services.skill_extraction_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateSkillTag.__table__,
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
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


# ── normalize_skills() ───────────────────────────────────────────────

def test_normalize_skills_maps_synonyms_to_canonical():
    result = svc.normalize_skills(["GWCC", "GWPC", "Java 8", "j2ee"])
    canonicals = [r["canonical"] for r in result]
    assert "Guidewire" in canonicals
    assert "Java" in canonicals


def test_normalize_skills_deduplicates_same_canonical():
    result = svc.normalize_skills(["GWCC", "GWPC"])  # both -> Guidewire
    assert len(result) == 1
    assert result[0]["canonical"] == "Guidewire"


def test_normalize_skills_case_insensitive():
    result = svc.normalize_skills(["gwcc"])
    assert result[0]["canonical"] == "Guidewire"


def test_normalize_skills_unknown_skill_preserved_with_lower_confidence():
    result = svc.normalize_skills(["Acme Framework 3.0"])
    assert result[0]["canonical"] == "Acme Framework 3.0"  # BR-03: not discarded
    assert result[0]["confidence"] == 0.8


def test_normalize_skills_known_skill_full_confidence():
    result = svc.normalize_skills(["Guidewire"])
    assert result[0]["confidence"] == 1.0


def test_normalize_skills_empty_input():
    assert svc.normalize_skills([]) == []
    assert svc.normalize_skills(None) == []


# ── extract_and_tag_skills() ─────────────────────────────────────────

def test_extract_and_tag_skills_populates_tags_and_candidate_skills(db_session, seeded):
    candidate, conv = seeded
    result = svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["GWCC", "GWPC", "Java 8", "j2ee", "SQL"], conversation=conv)

    assert result["skills_count"] == 3  # Guidewire, Java, SQL -- deduplicated
    tags = db_session.query(CandidateSkillTag).filter(CandidateSkillTag.candidate_id == "C-1").all()
    assert len(tags) == 3

    db_session.refresh(candidate)
    assert "Guidewire" in candidate.candidateSkills
    assert "Java" in candidate.candidateSkills
    assert "SQL" in candidate.candidateSkills


def test_extract_and_tag_skills_duplicate_canonical_only_one_row(db_session, seeded):
    candidate, conv = seeded
    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["GWCC", "GWPC", "Guidewire PolicyCenter"], conversation=conv)

    tags = db_session.query(CandidateSkillTag).filter(CandidateSkillTag.candidate_id == "C-1", CandidateSkillTag.skill_canonical == "Guidewire").all()
    assert len(tags) == 1  # AC-6/TC-004


def test_extract_and_tag_skills_does_not_overwrite_existing_tag(db_session, seeded):
    candidate, conv = seeded
    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["GWCC"], conversation=conv)
    first_tag = db_session.query(CandidateSkillTag).filter(CandidateSkillTag.candidate_id == "C-1").first()
    original_raw = first_tag.skill_raw

    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["GWPC"], conversation=conv)  # also -> Guidewire

    tags = db_session.query(CandidateSkillTag).filter(CandidateSkillTag.candidate_id == "C-1", CandidateSkillTag.skill_canonical == "Guidewire").all()
    assert len(tags) == 1
    assert tags[0].skill_raw == original_raw  # untouched, "DO NOTHING"


def test_extract_and_tag_skills_unknown_skill_logs_event(db_session, seeded):
    candidate, conv = seeded
    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["Acme Framework 3.0"], conversation=conv)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "SKILL_NOT_IN_SYNONYM_LIBRARY").all()
    assert len(events) == 1
    assert events[0].event_data["raw"] == "Acme Framework 3.0"


def test_extract_and_tag_skills_publishes_skills_extracted_event(db_session, seeded):
    candidate, conv = seeded
    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["Guidewire", "Java"], conversation=conv)

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "candidate.skills_extracted").all()
    assert len(events) == 1
    assert events[0].event_data["skills_count"] == 2


def test_extract_and_tag_skills_empty_raw_skills_no_crash(db_session, seeded):
    candidate, conv = seeded
    result = svc.extract_and_tag_skills(db_session, candidate, "U-ORG", [], conversation=conv)
    assert result["skills_count"] == 0


# ── get_unknown_skill_suggestions() ──────────────────────────────────

def test_get_unknown_skill_suggestions_returns_low_confidence_only(db_session, seeded):
    candidate, conv = seeded
    svc.extract_and_tag_skills(db_session, candidate, "U-ORG", ["Guidewire", "Acme Framework 3.0"], conversation=conv)

    suggestions = svc.get_unknown_skill_suggestions(db_session, "U-ORG")
    skills = [s["skill"] for s in suggestions]
    assert "Acme Framework 3.0" in skills
    assert "Guidewire" not in skills

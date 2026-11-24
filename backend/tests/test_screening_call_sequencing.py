"""CEO 2026-11-16: an L1 interview could not be scheduled because Thunder had booked a "Screening call" for a candidate
the hiring pipeline already counted as screened, and every new round waits for the latest one to pass. A pending
screening round no longer blocks once screening is done, and Thunder no longer books one for someone screened."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.hiring_pipeline import HiringPipeline
from app.models.user import InterviewPanel
from app.services import thunder_autonomy_service as autonomy
from app.services.interview_sequencing_service import (
    PriorRoundNotPassed, enforce_interview_sequencing_gate, screening_done,
)
from app.services.interview_verdict_service import ensure_verdict_row
from tests.scope_fixtures import two_bu_world


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def world(db):
    return two_bu_world(db)


def _candidate(db, **pipeline):
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                          candidateFirstName="Veera", candidateLastName="K", candidateExperience="10",
                          candidateEmail=f"v{uuid.uuid4().hex[:8]}@example.com", employment_type="FULLTIME")
    db.add(candidate)
    db.flush()
    if pipeline:
        db.add(HiringPipeline(tenant_id=1, candidate_id=candidate.candidateID, **pipeline))
        db.flush()
    return candidate


def _round(db, candidate, name, level):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=name)
    db.add(panel)
    db.flush()
    ensure_verdict_row(db, panel, level)
    return panel


def test_a_pending_screening_call_does_not_block_l1_once_the_pipeline_has_them_screened(db):
    for pipeline in ({"screen_decision": "PASS"}, {"screen_decision": "SKIP"}, {"screen_required": False}):
        candidate = _candidate(db, **pipeline)
        _round(db, candidate, "Screening call", "SCREEN")
        assert screening_done(db, candidate.candidateID)
        enforce_interview_sequencing_gate(db, candidate.candidateID, level="L1")  # no refusal


def test_a_pending_screening_call_still_blocks_while_screening_is_open(db):
    for pipeline in ({"screen_decision": None}, {"screen_decision": "FAIL"}, {}):
        candidate = _candidate(db, **pipeline)
        _round(db, candidate, "Screening call", "SCREEN")
        with pytest.raises(PriorRoundNotPassed, match="Screening call"):
            enforce_interview_sequencing_gate(db, candidate.candidateID, level="L1")


def test_any_other_pending_round_still_blocks_the_next(db):
    candidate = _candidate(db, screen_decision="PASS")
    _round(db, candidate, "L1 Technical", "L1")
    with pytest.raises(PriorRoundNotPassed, match="L1 Technical"):
        enforce_interview_sequencing_gate(db, candidate.candidateID, level="OTHER")


def test_thunder_books_no_screening_call_for_a_screened_candidate(db, world):
    candidate = _candidate(db, screen_decision="PASS")
    assert autonomy.book_call(db, candidate, world.org_user) is None
    assert db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate.candidateID).count() == 0

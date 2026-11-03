"""Recruiter edits are recorded as SLM corrections (production log 2026-11-02: every candidate edit
failed with "record_correction() got an unexpected keyword argument 'candidate_id'")."""
import pytest
from sqlalchemy.orm import Session

from app.models.slm_feedback import SLMFeedback
from app.services.slm_feedback_engine import SLMFeedbackEngine, feedback_session_for


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_two_corrections_of_one_candidate_are_both_kept_and_anonymous(db):
    candidate_id = "CAN-746cd347-8d2e-4806-936f-8e653be66407"
    ids = [feedback_session_for(candidate_id) for _ in range(2)]
    assert ids[0] != ids[1] and ids[0][:24] == ids[1][:24]  # unique per row, grouped by candidate
    assert candidate_id not in ids[0] and "746cd347" not in ids[0]
    for session_id, field in zip(ids, ("title", "skills")):
        SLMFeedbackEngine.record_correction(db=db, feedback_session_id=session_id, field_name=field,
                                            parsed_value="old", corrected_value="new")
    db.commit()
    assert db.query(SLMFeedback).filter(SLMFeedback.feedback_session_id.in_(ids)).count() == 2

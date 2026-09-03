"""
Document review <-> Task linkage (2026-08-05). Avinash's rule: rejecting
a document reopens/creates a real Task marked pending on the candidate;
approving it closes that Task. Throwaway SQLite -- never the real database.
"""
import os
import logging
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.document import CandidateDocument
from app.models.task import Task
from app.models.user import Users

import app.services.document_task_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateDocument.__table__, Task.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def candidate_and_document(db_session):
    candidate = Candidate(
        candidateID="C-DOC", candidateEmail="doc@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Rao",
    )
    db_session.add(candidate)
    db_session.commit()

    document = CandidateDocument(
        candidate_id="C-DOC", document_type="pan", original_filename="pan.pdf",
        stored_filename="pan-stored.pdf", file_size=1024, file_extension=".pdf",
        uploaded_by="C-DOC", is_verified=False,
    )
    db_session.add(document)
    db_session.commit()
    return candidate, document

def test_reject_creates_a_pending_task(db_session, candidate_and_document):
    _, document = candidate_and_document
    svc.sync_task_for_document_decision(db_session, document, "Rejected", "U-HR", reason="Blurry scan")

    task = db_session.query(Task).filter(Task.document_id == document.id).first()
    assert task is not None
    assert task.candidate_id == "C-DOC"
    assert task.status == "NEW"
    assert "PAN Card" in task.title
    assert "Blurry scan" in task.description

def test_approve_with_no_prior_rejection_creates_no_task(db_session, candidate_and_document):
    _, document = candidate_and_document
    svc.sync_task_for_document_decision(db_session, document, "Verified", "U-HR")

    assert db_session.query(Task).filter(Task.document_id == document.id).count() == 0

def test_approve_after_rejection_closes_the_task(db_session, candidate_and_document):
    _, document = candidate_and_document
    svc.sync_task_for_document_decision(db_session, document, "Rejected", "U-HR", reason="Blurry scan")
    svc.sync_task_for_document_decision(db_session, document, "Verified", "U-HR")

    task = db_session.query(Task).filter(Task.document_id == document.id).first()
    assert task.status == "COMPLETED"
    assert task.completed_at is not None

def test_second_rejection_reopens_the_same_task_not_a_duplicate(db_session, candidate_and_document):
    _, document = candidate_and_document
    svc.sync_task_for_document_decision(db_session, document, "Rejected", "U-HR", reason="Blurry scan")
    first_task_id = db_session.query(Task).filter(Task.document_id == document.id).first().id

    svc.sync_task_for_document_decision(db_session, document, "Verified", "U-HR")
    svc.sync_task_for_document_decision(db_session, document, "Rejected", "U-HR", reason="Wrong document type")

    tasks = db_session.query(Task).filter(Task.document_id == document.id).all()
    assert len(tasks) == 1
    assert tasks[0].id == first_task_id
    assert tasks[0].status == "NEW"
    assert tasks[0].completed_at is None
    assert "Wrong document type" in tasks[0].description

def test_pending_decision_is_a_no_op(db_session, candidate_and_document):
    _, document = candidate_and_document
    svc.sync_task_for_document_decision(db_session, document, "Pending", "U-HR")

    assert db_session.query(Task).count() == 0

def test_never_raises_on_missing_candidate(db_session, candidate_and_document):
    """Fail-soft, not fail-closed -- the document's own verification
    already committed by the time this runs; a Task-sync bug must
    never surface as a 500 on a verification the HR user already
    successfully performed."""
    _, document = candidate_and_document
    db_session.query(Candidate).filter(Candidate.candidateID == "C-DOC").delete()
    db_session.commit()

    svc.sync_task_for_document_decision(db_session, document, "Rejected", "U-HR", reason="test")  # must not raise

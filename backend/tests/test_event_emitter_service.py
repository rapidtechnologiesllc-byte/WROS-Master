"""
import logging
S-078/HRMS-0478 -- Event Emission Layer for AI Actions.

Real architecture under test (see event_emitter_service module
docstring): "lightweight version" per Avinash's explicit direction --
a real event_log table + emit(), no message bus/pub-sub/retry queue
(nothing in this codebase subscribes yet, so there is no real failure
mode for a retry queue to protect against).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.event_log import EventLog
from app.models.user import Users

import app.services.event_emitter_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__, EventLog.__table__,
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
    db_session.add(Users(UserID="U-ORG", UserRole="Super User", UserEmail="org@blitzenx.com", UserPassword="h"))
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add(candidate)
    db_session.commit()
    return candidate

def test_emit_candidate_scoped_event_creates_row(db_session, seeded):
    event_id = svc.emit(db_session, "candidate.qualified", {"score": 82}, "U-ORG", "C-1")
    row = db_session.query(EventLog).filter(EventLog.id == event_id).first()
    assert row is not None
    assert row.event_type == "candidate.qualified"
    assert row.event_version == "v1"
    assert row.tenant_id == "U-ORG"
    assert row.candidate_id == "C-1"
    assert row.payload == {"score": 82}

def test_emit_non_candidate_scoped_event_allows_no_candidate_id(db_session, seeded):
    event_id = svc.emit(db_session, "supervisor.cycle_completed", {"candidates_evaluated": 3}, "U-ORG")
    row = db_session.query(EventLog).filter(EventLog.id == event_id).first()
    assert row.candidate_id is None

def test_emit_unknown_event_type_raises(db_session, seeded):
    with pytest.raises(svc.EventDefinitionNotFoundError):
        svc.emit(db_session, "not.a.real.event", {}, "U-ORG", "C-1")

def test_emit_missing_tenant_id_raises(db_session, seeded):
    with pytest.raises(svc.EventValidationError):
        svc.emit(db_session, "candidate.qualified", {}, "", "C-1")

def test_emit_candidate_scoped_without_candidate_id_raises_br02(db_session, seeded):
    with pytest.raises(svc.EventValidationError):
        svc.emit(db_session, "candidate.qualified", {}, "U-ORG")

def test_get_events_filters_by_type_and_candidate(db_session, seeded):
    svc.emit(db_session, "candidate.qualified", {}, "U-ORG", "C-1")
    svc.emit(db_session, "interview.confirmed", {}, "U-ORG", "C-1")
    svc.emit(db_session, "supervisor.cycle_completed", {}, "U-ORG")

    all_events = svc.get_events(db_session, "U-ORG")
    assert len(all_events) == 3

    qualified_only = svc.get_events(db_session, "U-ORG", event_type="candidate.qualified")
    assert len(qualified_only) == 1

    candidate_only = svc.get_events(db_session, "U-ORG", candidate_id="C-1")
    assert len(candidate_only) == 2

def test_get_events_scoped_to_tenant(db_session, seeded):
    db_session.add(Users(UserID="U-OTHER", UserRole="Super User", UserEmail="other@blitzenx.com", UserPassword="h"))
    db_session.commit()
    svc.emit(db_session, "supervisor.cycle_completed", {}, "U-ORG")
    svc.emit(db_session, "supervisor.cycle_completed", {}, "U-OTHER")

    events = svc.get_events(db_session, "U-ORG")
    assert len(events) == 1
    assert events[0]["tenant_id"] == "U-ORG"

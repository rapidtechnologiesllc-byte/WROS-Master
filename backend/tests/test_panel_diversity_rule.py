"""
Panel diversity backlog item, 2026-08-05
(wros_interview_regrouping_and_rehire_guard_priority): "we also need to
ensure that same panel is not used if different jobs, different clients
but same candidate ... allows us to get different perspective on the
candidate." Advisory only -- POST /panel-members/assign still succeeds,
it just returns a diversity_warning when the interviewer already served
on a DIFFERENT job's panel for this same candidate. Throwaway SQLite --
never the real database.
"""
import os
import logging
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.user import InterviewPanel, Jobs, PanelMember, Users

from app.api.v1.endpoints.interviews import _panel_diversity_warning

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__,
        InterviewPanel.__table__, PanelMember.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_candidate(db, candidate_id="C-1"):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=f"{candidate_id}@example.com",
        candidatePassword="h", candidateFirstName="Priya", candidateLastName="Rao",
    )
    db.add(candidate)
    db.commit()
    return candidate

def _make_panel(db, candidate_id, job_id=None, round_name="Tech"):
    panel = InterviewPanel(candidate_id=candidate_id, job_id=job_id, round_name=round_name)
    db.add(panel)
    db.commit()
    return panel

def test_no_warning_when_interviewer_has_no_history_with_candidate(db_session):
    _make_candidate(db_session, "C-1")
    panel = _make_panel(db_session, "C-1", job_id="J-1")

    assert _panel_diversity_warning(db_session, panel, "U-INT-1") is None

def test_warns_when_interviewer_previously_served_on_different_job(db_session):
    _make_candidate(db_session, "C-1")
    old_panel = _make_panel(db_session, "C-1", job_id="J-1")
    db_session.add(PanelMember(panel_id=old_panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    new_panel = _make_panel(db_session, "C-1", job_id="J-2")

    warning = _panel_diversity_warning(db_session, new_panel, "U-INT-1")
    assert warning is not None
    assert "U-INT-1" in warning

def test_no_warning_for_same_job_different_round_reuse(db_session):
    """Reusing the same interviewer across L1/L2 of the SAME job is
    normal and not a diversity concern."""
    _make_candidate(db_session, "C-1")
    l1_panel = _make_panel(db_session, "C-1", job_id="J-1", round_name="L1")
    db_session.add(PanelMember(panel_id=l1_panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    l2_panel = _make_panel(db_session, "C-1", job_id="J-1", round_name="L2")

    assert _panel_diversity_warning(db_session, l2_panel, "U-INT-1") is None

def test_warns_when_current_panel_has_no_job_id_but_history_exists(db_session):
    """Can't determine job-sameness without a job_id on the new panel --
    treat any prior panel involvement for this candidate as a concern
    rather than silently skipping the check."""
    _make_candidate(db_session, "C-1")
    old_panel = _make_panel(db_session, "C-1", job_id="J-1")
    db_session.add(PanelMember(panel_id=old_panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    new_panel = _make_panel(db_session, "C-1", job_id=None)

    assert _panel_diversity_warning(db_session, new_panel, "U-INT-1") is not None

def test_no_warning_for_different_candidate(db_session):
    _make_candidate(db_session, "C-1")
    _make_candidate(db_session, "C-2")
    old_panel = _make_panel(db_session, "C-1", job_id="J-1")
    db_session.add(PanelMember(panel_id=old_panel.id, interviewer_id="U-INT-1"))
    db_session.commit()

    other_candidate_panel = _make_panel(db_session, "C-2", job_id="J-2")

    assert _panel_diversity_warning(db_session, other_candidate_panel, "U-INT-1") is None

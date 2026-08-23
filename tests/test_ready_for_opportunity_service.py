"""
Ready-for-opportunity workflow.

Proves: start_watching() is idempotent (no duplicate active watches),
scan_new_job_for_matches() only nudges plausible skill matches (never
every watched candidate), the nudge send is mocked here (real send
behavior is offer_decision_service/thunder_service's own already-
tested territory) so this file proves the MATCHING and WATCH-STATE
logic, and the scan never fires on a schedule -- it's a plain function
call, exercised here exactly the way create_job's background task
calls it.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.candidate_opportunity_watch import CandidateOpportunityWatch
from app.models.user import Jobs

import app.services.ready_for_opportunity_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateConversation.__table__, Jobs.__table__, CandidateOpportunityWatch.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_candidate(db, cid, *, skills, title):
    c = Candidate(candidateID=cid, candidateEmail=f"{cid}@example.com", candidatePassword="h", candidateSkills=skills, candidateJobTitle=title, candidateFirstName="Test")
    db.add(c)
    db.commit()
    return c


def _make_job(db, jid, *, skills, title):
    j = Jobs(jobID=jid, jobTitle=title, jobDescription="desc", jobSkills=skills, jobExperience="3-5 years", jobLocation="Remote", jobStatus="active")
    db.add(j)
    db.commit()
    return j


def test_start_watching_is_idempotent(db_session):
    candidate = _make_candidate(db_session, "C1", skills="Java, Spring", title="Java Developer")
    w1 = svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    w2 = svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    db_session.commit()
    assert w1.id == w2.id
    assert db_session.query(CandidateOpportunityWatch).count() == 1


def test_scan_ignores_non_matching_candidates(db_session):
    candidate = _make_candidate(db_session, "C1", skills="Java, Spring", title="Java Developer")
    svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    db_session.commit()

    job = _make_job(db_session, "J1", skills="React, TypeScript, Frontend", title="React Developer")

    with patch("app.services.thunder_service.send_thunder_message"):
        matched = svc.scan_new_job_for_matches(db_session, job)
    assert matched == []

    watch = db_session.query(CandidateOpportunityWatch).filter(CandidateOpportunityWatch.candidate_id == "C1").first()
    assert watch.is_active is True  # unmatched -- still watching


def test_scan_matches_and_deactivates_watch(db_session):
    candidate = _make_candidate(db_session, "C1", skills="Java, Spring, Microservices", title="Java Developer")
    svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    conversation = CandidateConversation(tenant_id="mgr1", candidate_id="C1", status="closed")
    db_session.add(conversation)
    db_session.commit()

    job = _make_job(db_session, "J1", skills="Java, Spring, AWS", title="Senior Java Engineer")

    with patch("app.services.thunder_service.send_thunder_message") as mock_send:
        matched = svc.scan_new_job_for_matches(db_session, job)

    assert len(matched) == 1
    assert mock_send.called

    watch = db_session.query(CandidateOpportunityWatch).filter(CandidateOpportunityWatch.candidate_id == "C1").first()
    assert watch.is_active is False  # matched -- no longer just watching
    assert watch.matched_job_id == "J1"
    assert watch.nudged_at is not None


def test_scan_no_conversation_leaves_watch_active_for_next_job(db_session):
    """No conversation to nudge through yet -- match isn't lost, the
    candidate stays watched so a later job (once they have a real
    conversation) can still reach them."""
    candidate = _make_candidate(db_session, "C1", skills="Java, Spring", title="Java Developer")
    svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    db_session.commit()

    job = _make_job(db_session, "J1", skills="Java, Spring", title="Java Developer")

    with patch("app.services.thunder_service.send_thunder_message"):
        matched = svc.scan_new_job_for_matches(db_session, job)

    assert matched == []
    watch = db_session.query(CandidateOpportunityWatch).filter(CandidateOpportunityWatch.candidate_id == "C1").first()
    assert watch.is_active is True


def test_scan_only_considers_active_watches(db_session):
    candidate = _make_candidate(db_session, "C1", skills="Java, Spring", title="Java Developer")
    watch = svc.start_watching(db_session, candidate, reason="OFFER_DECLINED")
    watch.is_active = False  # already matched/resolved previously
    db_session.add(watch)
    db_session.commit()

    job = _make_job(db_session, "J1", skills="Java, Spring", title="Java Developer")

    with patch("app.services.thunder_service.send_thunder_message"):
        matched = svc.scan_new_job_for_matches(db_session, job)
    assert matched == []

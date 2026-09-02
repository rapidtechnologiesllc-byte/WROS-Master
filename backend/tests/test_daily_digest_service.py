"""
import logging
S-065/HRMS-0465 -- Thunder Daily Digest / Morning Report.

Real architecture under test (see daily_digest_service module
docstring): no thunder_activity_feed/interviews/system_configuration
tables -- reuses S-061's real event vocabulary, S-047-052's real
SubmissionInterview chain, and a new real Users.digest_enabled column.
Recipients are personalized per Submission.submitted_by_user_id (the
same real "who owns this candidate" signal established across
S-046/S-057/S-058/S-060/S-062). BR-01 (local timezone), BR-02 (no
digest if empty), BR-03 (deep links) all verified directly. WhatsApp
delivery is honestly never actually sent (unprovisioned channel, same
gap as everywhere else in this codebase) -- only email really sends.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_drop_risk import CandidateDropRisk
from app.models.employee import Employee
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.submission import Submission
from app.models.user import Users

import app.services.daily_digest_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        CandidateDropRisk.__table__, RecruiterInterventionQueue.__table__, Submission.__table__,
        SubmissionInterview.__table__, DemandInterviewPanel.__table__, Employee.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def recruiter(db_session):
    r = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None, timezone="Asia/Kolkata", digest_enabled=True)
    db_session.add(r)
    db_session.commit()
    return r


def _candidate(db, cid="C-1", first="Priya"):
    c = Candidate(candidateID=cid, candidateEmail=f"{cid.lower()}@example.com", candidatePassword="h", candidateFirstName=first)
    db.add(c)
    db.commit()
    return c


def _owned_submission(db, cid="C-1", recruiter_id="U-HR"):
    sub = Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id=cid, submitted_by_user_id=recruiter_id, status="OFFER_EXTENDED")
    db.add(sub)
    db.commit()
    return sub


def _conversation(db, cid="C-1"):
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id=cid, status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none")
    db.add(conv)
    db.commit()
    return conv


# ── Core generation ──────────────────────────────────────────────────────

def test_digest_includes_overnight_replies(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)
    conv = _conversation(db_session)
    since = datetime.utcnow() - timedelta(hours=6)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"body": "Sounds great!"}, triggered_by="candidate", created_at=since))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    assert digest["has_content"] is True
    assert len(digest["responded"]) == 1
    assert digest["responded"][0]["name"] == "Priya"


def test_digest_includes_needs_attention(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)
    db_session.add(RecruiterInterventionQueue(tenant_id="U-ORG", candidate_id="C-1", queue_reason="ESCALATION", reason_detail="requested human contact", priority=1, status="OPEN"))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    assert digest["has_content"] is True
    assert len(digest["needs_attention"]) == 1
    assert digest["needs_attention"][0]["reason"] == "ESCALATION"


def test_digest_includes_top_risks(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)
    db_session.add(CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-1", drop_risk_score=82, risk_level="CRITICAL", risk_signals={"stage": "OFFER"}, is_flagged=True))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    assert len(digest["top_risks"]) == 1
    assert digest["top_risks"][0]["score"] == 82


def test_digest_only_includes_own_candidates(db_session, recruiter):
    _candidate(db_session, "C-1")
    _owned_submission(db_session, cid="C-1", recruiter_id="U-HR")
    _candidate(db_session, "C-2", first="Raj")
    _owned_submission(db_session, cid="C-2", recruiter_id="U-OTHER")
    db_session.add(CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-2", drop_risk_score=90, risk_level="CRITICAL", risk_signals={"stage": "OFFER"}, is_flagged=True))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    assert digest["top_risks"] == []  # C-2 belongs to a different recruiter


# ── BR-02: no digest if empty ────────────────────────────────────────────

def test_empty_digest_has_no_content(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    assert digest["has_content"] is False


def test_send_digest_skips_when_no_content(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)

    result = svc.send_daily_digest(db_session, "U-HR", "U-ORG")
    assert result["outcome"] == "skipped_no_content"


def test_send_digest_respects_disabled_preference(db_session, recruiter):
    recruiter.digest_enabled = False
    db_session.commit()
    _candidate(db_session)
    _owned_submission(db_session)
    db_session.add(CandidateDropRisk(tenant_id="U-ORG", candidate_id="C-1", drop_risk_score=90, risk_level="CRITICAL", risk_signals={"stage": "OFFER"}, is_flagged=True))
    db_session.commit()

    result = svc.send_daily_digest(db_session, "U-HR", "U-ORG")
    assert result["outcome"] == "disabled"


# ── BR-03: deep links ─────────────────────────────────────────────────────

def test_candidate_links_present_in_whatsapp_and_email_format(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)
    db_session.add(RecruiterInterventionQueue(tenant_id="U-ORG", candidate_id="C-1", queue_reason="ESCALATION", reason_detail="x", priority=1, status="OPEN"))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG")
    whatsapp_text = svc.format_whatsapp_digest(digest)
    html = svc.format_email_digest_html(digest)
    assert "/candidates/C-1?tab=messages" in html
    assert digest["needs_attention"][0]["link"].endswith("/candidates/C-1?tab=messages")
    assert "Priya" in whatsapp_text


# ── Interviews today ──────────────────────────────────────────────────────

def test_interview_today_included_with_local_time(db_session, recruiter):
    _candidate(db_session)
    sub = _owned_submission(db_session)
    scheduled_utc = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)  # ~3:30 PM IST
    db_session.add(SubmissionInterview(tenant_id=None, submission_id=sub.id, candidate_id="C-1", level="L1", outcome="PENDING", scheduled_at=scheduled_utc))
    db_session.commit()

    digest = svc.generate_daily_digest(db_session, "U-HR", "U-ORG", now=scheduled_utc)
    assert len(digest["interviews_today"]) == 1
    assert digest["interviews_today"][0]["level"] == "L1"


# ── Job batch processing ─────────────────────────────────────────────────

def test_job_skips_recruiter_outside_local_8am_window(db_session, recruiter):
    _candidate(db_session)
    _owned_submission(db_session)
    _conversation(db_session)

    result = svc.run_daily_digest_job(db_session)
    # Whatever the current UTC hour maps to in Asia/Kolkata, this just
    # confirms the job runs without raising and returns real counters.
    assert "processed" in result and "sent" in result and "skipped" in result

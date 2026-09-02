"""
import logging
S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.

Real architecture under test (see bulk_engagement_service module
docstring): dedup reuses R-07's real create_candidate_safe(); no
system_configuration table -- the 20/min rate is a real module
constant enforced by real batching + sleep_fn injection; BR-02 reuses
the real CandidateConversation existence check; engagement itself
reuses the real, already-shipped auto_assign_ai_agent_on_creation().

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.bulk_engagement import BulkEngagementError, BulkEngagementJob
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.notification import Notification
from app.models.user import Users, Jobs

import app.services.bulk_engagement_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Jobs.__table__, Candidate.__table__, CandidateConversation.__table__,
        ConversationEvent.__table__, CandidateAIAssignment.__table__, ConsentRecord.__table__,
        BulkEngagementJob.__table__, BulkEngagementError.__table__, Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded_hr(db_session):
    db_session.add(Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None))
    db_session.commit()


CSV_VALID = """name,email,phone,location,current_employer,skills
John Smith,john@example.com,+919876543210,Bangalore,Acme,Python,Guidewire
Jane Doe,jane@example.com,+919876543211,Mumbai,Beta,Java
"""


# ── TC-001: CSV import ────────────────────────────────────────────────────

def test_import_creates_candidates(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    assert result["imported"] == 2
    assert result["skipped_duplicates"] == 0
    assert len(result["candidate_ids"]) == 2
    assert db_session.query(Candidate).count() == 2


def test_import_missing_required_column_raises(db_session, seeded_hr):
    with pytest.raises(svc.CsvMissingRequiredColumn):
        svc.import_candidates_from_csv(db_session, "email,phone\na@b.com,123\n", "U-HR", "U-ORG")


def test_import_row_missing_name_is_error(db_session, seeded_hr):
    csv_text = "name,email\n,noemail@example.com\n"
    result = svc.import_candidates_from_csv(db_session, csv_text, "U-HR", "U-ORG")
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "name" in result["errors"][0]["reason"].lower()


def test_import_row_missing_email_is_error_not_fabricated(db_session, seeded_hr):
    csv_text = "name,email\nNo Email Person,\n"
    result = svc.import_candidates_from_csv(db_session, csv_text, "U-HR", "U-ORG")
    assert result["imported"] == 0
    assert len(result["errors"]) == 1
    assert "email" in result["errors"][0]["reason"].lower()


def test_import_duplicate_is_skipped_not_erred(db_session, seeded_hr):
    svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    assert result["imported"] == 0
    assert result["skipped_duplicates"] == 2


# ── TC-004: max rows ──────────────────────────────────────────────────────

def test_csv_over_200_rows_raises(db_session, seeded_hr):
    header = "name,email\n"
    rows = "\n".join(f"Person {i},person{i}@example.com" for i in range(201))
    with pytest.raises(svc.CsvTooLarge):
        svc.import_candidates_from_csv(db_session, header + rows, "U-HR", "U-ORG")


# ── Launch + max size ────────────────────────────────────────────────────

def test_launch_creates_job(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")
    assert launch["total_candidates"] == 2
    job = db_session.query(BulkEngagementJob).filter(BulkEngagementJob.id == launch["bulk_job_id"]).first()
    assert job.status == "QUEUED"


def test_launch_over_200_raises(db_session, seeded_hr):
    with pytest.raises(svc.BulkTooLarge):
        svc.launch_bulk_engagement(db_session, [f"C-{i}" for i in range(201)], "U-HR", "U-ORG")


# ── TC-002/BR-01: rate limiting via batching ─────────────────────────────

def test_worker_sleeps_between_batches(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")

    sleep_calls = []
    svc.run_bulk_engagement_worker(db_session, launch["bulk_job_id"], sleep_fn=sleep_calls.append, batch_size=1)

    # 2 candidates, batch_size=1 -> 1 sleep between the 2 batches
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 60


def test_worker_no_sleep_when_all_fit_in_one_batch(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")

    sleep_calls = []
    svc.run_bulk_engagement_worker(db_session, launch["bulk_job_id"], sleep_fn=sleep_calls.append, batch_size=20)
    assert sleep_calls == []


# ── TC-003/BR-02: skip already-engaged ───────────────────────────────────

def test_already_engaged_candidate_skipped(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    candidate_id = result["candidate_ids"][0]
    db_session.add(CandidateConversation(tenant_id="U-ORG", candidate_id=candidate_id, status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none"))
    db_session.commit()

    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")
    outcome = svc.run_bulk_engagement_worker(db_session, launch["bulk_job_id"], sleep_fn=lambda s: None)

    assert outcome["skipped_count"] == 1
    # The other candidate has no phone/whatsapp consent so it may fail engagement
    # for a real reason, but must not also be double-counted as skipped.
    job = db_session.query(BulkEngagementJob).filter(BulkEngagementJob.id == launch["bulk_job_id"]).first()
    assert job.skipped_count == 1
    assert job.status == "COMPLETED"


def test_job_status_endpoint_data(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")
    svc.run_bulk_engagement_worker(db_session, launch["bulk_job_id"], sleep_fn=lambda s: None)

    status = svc.get_bulk_job_status(db_session, launch["bulk_job_id"])
    assert status["status"] == "COMPLETED"
    assert status["total_count"] == 2


def test_job_status_unknown_returns_none(db_session):
    assert svc.get_bulk_job_status(db_session, "NOPE") is None


def test_completion_notifies_recruiter(db_session, seeded_hr):
    result = svc.import_candidates_from_csv(db_session, CSV_VALID, "U-HR", "U-ORG")
    launch = svc.launch_bulk_engagement(db_session, result["candidate_ids"], "U-HR", "U-ORG")
    svc.run_bulk_engagement_worker(db_session, launch["bulk_job_id"], sleep_fn=lambda s: None)

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert "Bulk engagement complete" in notifications[0].message

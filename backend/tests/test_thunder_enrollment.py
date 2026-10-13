"""A created candidate enters the Thunder email cadence; existing candidates can be
enrolled in staggered batches, never emailing anyone who shouldn't be contacted."""
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderCadenceState
from app.models.user import Users
from app.services.message_handlers.thunder_engagement_handler import ThunderEngagementHandler
from app.services.thunder_mail import cadence_service
from app.services.linkedin_pipeline_task_service import PLACEHOLDER_EMAIL_DOMAIN
from app.services.thunder_mail.enrollment_service import enroll_existing_candidates

NOW = datetime(2026, 10, 8, 15, 0)


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
def only_these_candidates(db):
    """Enrollment scans every candidate; keep the test to the ones it creates."""
    db.query(ThunderCadenceState).delete()
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
    db.flush()
    if db.query(Users).filter_by(tenant_id=1).first() is None:  # owner of Thunder conversations
        role = RoleTemplate(tenant_id=1, name=f"r-{uuid.uuid4().hex[:6]}", display_name="R")
        db.add(role)
        db.flush()
        db.add(Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserEmail=f"u{uuid.uuid4().hex[:6]}@x.com",
                     UserPassword="h", UserRole="admin", tenant_id=1, role_template_id=role.id))
        db.flush()


def _candidate(db, email=None, **kw):
    candidate = Candidate(candidateID=f"CAN-{uuid.uuid4().hex[:10]}",
                          candidateEmail=email or f"c{uuid.uuid4().hex[:8]}@example.com",
                          candidatePassword="h", candidateFirstName="Avi", tenant_id=1, **kw)
    db.add(candidate)
    db.flush()
    return candidate


def _engage(db, candidate):
    with patch.object(cadence_service, "enqueue_send", return_value=True) as enqueue:
        result = ThunderEngagementHandler.process(
            SimpleNamespace(id="m1", payload={"candidate_id": candidate.candidateID}), db)
    return result, enqueue


def test_created_candidate_gets_email_step1_queued_once(db):
    candidate = _candidate(db)
    result, enqueue = _engage(db, candidate)
    state = db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).one()
    assert result["email_cadence_started"] is True and result["email_step1_queued"] is True
    assert state.next_step == "1" and state.stage == "ACTIVE" and enqueue.call_count == 1

    state.touches_sent, state.next_step = 1, "2"  # step 1 went out
    db.commit()
    again, enqueue = _engage(db, candidate)
    assert again["email_cadence_started"] is False and enqueue.call_count == 0


def test_placeholder_or_disabled_candidate_gets_no_cadence(db):
    for candidate in (_candidate(db, email=f"linkedin-{uuid.uuid4().hex[:6]}@{PLACEHOLDER_EMAIL_DOMAIN}"),
                      _candidate(db, thunder_enabled=False)):
        result, enqueue = _engage(db, candidate)
        assert result["status"] == "skipped" and enqueue.call_count == 0
        assert db.query(ThunderCadenceState).filter_by(candidate_id=candidate.candidateID).count() == 0


def _world(db):
    ok = [_candidate(db) for _ in range(3)]
    employee_candidate = _candidate(db)
    db.add(Employee(tenant_id=1, candidate_id=employee_candidate.candidateID, first_name="E", last_name="E",
                    email=f"e{uuid.uuid4().hex[:6]}@x.com", joining_date=date(2025, 1, 1), status="ACTIVE"))
    hired = _candidate(db)
    db.add(CandidateStatus(candidateID=hired.candidateID, status="Hired"))
    _candidate(db, thunder_enabled=False)
    already = _candidate(db)
    cadence_service.start_cadence(db, already)
    db.commit()
    return ok


def test_dry_run_reports_eligibility_and_writes_nothing(db):
    _world(db)
    before = db.query(ThunderCadenceState).count()
    result = enroll_existing_candidates(db, limit=100, dry_run=True, now=NOW)
    assert result["eligible"] == 3 and result["enrolled"] == 0
    assert result["excluded"]["already an employee"] == 1
    assert result["excluded"]["closed in candidate_status"] == 1
    assert result["excluded"]["thunder disabled for candidate"] == 1
    assert result["excluded"]["already in cadence"] == 1
    assert db.query(ThunderCadenceState).count() == before


def test_enrollment_respects_limit_and_staggers_by_hourly_cap(db):
    ok = _world(db)
    with patch.object(cadence_service.settings, "THUNDER_MAX_SENDS_PER_HOUR", 25):
        result = enroll_existing_candidates(db, limit=2, dry_run=False, now=NOW)
    assert result["enrolled"] == 2 and result["left_for_later"] == 1
    starts = sorted(s.next_action_at for s in db.query(ThunderCadenceState).filter(
        ThunderCadenceState.candidate_id.in_([c.candidateID for c in ok])).all())
    assert starts == [NOW, NOW + timedelta(seconds=144)]

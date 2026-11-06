"""CEO 2026-11-05: delete for the CEO and super users only; junk must not become candidates; past interviews do not stay
Scheduled; shared-services cost "equally distributed in P&L across all BU's that has revenue"."""
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.employee import Employee
from app.models.org_structure import Department
from app.models.task import Task
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember
from app.services import candidate_delete_service, interview_transcript_service, revenue_chain_service
from tests.scope_fixtures import ApiClient, two_bu_world


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def w(db):
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _candidate(db, **fields):
    row = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h", candidateFirstName="Junk",
                    candidateLastName="Record", candidateEmail=f"j{uuid.uuid4().hex[:8]}@example.com", **fields)
    db.add(row)
    db.commit()
    return row


def _interview(db, w, candidate, **fields):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="L1")
    db.add(panel)
    db.flush()
    db.add(PanelMember(panel_id=panel.id, interviewer_id=w.org_user.UserID))
    interview = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, **fields)
    db.add(interview)
    db.flush()
    return interview


def test_delete_removes_everything_attached_and_is_audited(db, w):
    candidate = _candidate(db)
    interview = _interview(db, w, candidate, status="Completed", start_time=datetime.utcnow(), end_time=datetime.utcnow())
    db.add_all([InterviewFeedback(interview_id=interview.id, interviewer_id=w.org_user.UserID, recommendation="Hire"),
                CandidateHistory(candidateID=candidate.candidateID, event_type="Custom", note="x", event_at=datetime.utcnow()),
                CandidateStatus(candidateID=candidate.candidateID, status="Active"),
                Task(title="About junk", candidate_id=candidate.candidateID, tenant_id=1)])
    db.commit()
    cid, iid = candidate.candidateID, interview.id
    candidate_delete_service.delete_candidate(db, candidate, deleted_by=w.org_user.UserID)
    db.expire_all()
    assert db.get(Candidate, cid) is None
    assert db.query(Interview).filter_by(id=iid).count() == 0
    assert db.query(CandidateHistory).filter_by(candidateID=cid).count() == 0
    assert db.query(Task).filter_by(candidate_id=cid).count() == 0
    audit = db.query(AuditLog).filter_by(entity_id=cid, action="delete").one()
    assert audit.user_id == w.org_user.UserID and "Junk Record" in audit.old_value


def test_an_employees_candidate_record_cannot_be_deleted(db, w):
    candidate = _candidate(db)
    db.add(Employee(tenant_id=1, candidate_id=candidate.candidateID, first_name="A", last_name="B", email=f"{uuid.uuid4().hex[:6]}@x.com",
                    employee_number=f"T-{uuid.uuid4().hex[:6]}", joining_date=date(2026, 1, 1), bu_id=w.bu_a.id))
    db.commit()
    with pytest.raises(candidate_delete_service.CandidateDeleteError):
        candidate_delete_service.delete_candidate(db, candidate, deleted_by=w.org_user.UserID)
    assert db.get(Candidate, candidate.candidateID) is not None


def test_only_the_ceo_or_a_super_user_can_delete(api, db, w, monkeypatch):
    from app.core import authority

    candidate = _candidate(db)
    monkeypatch.setattr(authority, "can_delete_records", lambda session, user: False)
    refused = api.delete(w.org_user, f"/api/v1/candidates/{candidate.candidateID}")
    assert refused.status_code == 403, refused.text
    monkeypatch.setattr(authority, "can_delete_records", lambda session, user: True)
    assert api.delete(w.org_user, f"/api/v1/candidates/{candidate.candidateID}").status_code == 200


def test_authority_comes_from_the_role_template(db, w, monkeypatch):
    from app.core import authority

    monkeypatch.setattr(authority, "level", lambda session, user: settings.CEO_LEVEL)
    assert authority.can_delete_records(db, w.partner_a) is True
    monkeypatch.setattr(authority, "level", lambda session, user: 1)
    monkeypatch.setattr(authority, "templates_of", lambda session, user: [SimpleNamespace(can_delete_records=False, specialization=None)])
    assert authority.can_delete_records(db, w.partner_a) is False
    monkeypatch.setattr(authority, "templates_of", lambda session, user: [SimpleNamespace(can_delete_records=True, specialization=None)])
    assert authority.can_delete_records(db, w.partner_a) is True
    monkeypatch.undo()
    assert "can_delete_records" in authority.summary(db, w.partner_a)


def test_a_company_address_is_not_a_candidate():
    from app.services.thunder_mail.forward_intake_service import _is_our_own_address

    users = SimpleNamespace(company_domains={"blitzenx.com"})
    assert _is_our_own_address("employees@blitzenx.com", users.company_domains) is True
    assert _is_our_own_address("someone@gmail.com", users.company_domains) is False


def test_a_past_interview_stops_saying_scheduled(db, w):
    candidate = _candidate(db)
    now = datetime.utcnow()
    past = _interview(db, w, candidate, status="Scheduled", start_time=now - timedelta(days=1), end_time=now - timedelta(hours=23))
    today = _interview(db, w, candidate, status="Scheduled", start_time=now - timedelta(minutes=30), end_time=now + timedelta(minutes=30))
    db.commit()
    assert interview_transcript_service.close_past_interviews(db, now=now) >= 1
    db.expire_all()
    assert db.get(Interview, past.id).status == "Completed"
    assert db.get(Interview, today.id).status == "Scheduled"
    assert db.query(CandidateHistory).filter_by(candidateID=candidate.candidateID, event_type="Interview Completed").count() == 1


def _moves(monkeypatch, db, w, *, revenue_bus, amount=9_000_001):
    """One shared person homed in BU A whose unbilled cost is `amount`."""
    department = Department(id=str(uuid.uuid4()), tenant_id=1, name=f"Finance {uuid.uuid4().hex[:4]}", is_shared_service=True)
    db.add(department)
    db.flush()
    w.org_user.department_id = department.id
    employee = Employee(tenant_id=1, first_name="Acc", last_name="Ount", email=f"{uuid.uuid4().hex[:6]}@x.com", wros_user_id=w.org_user.UserID,
                        employee_number=f"T-{uuid.uuid4().hex[:6]}", joining_date=date(2026, 1, 1), bu_id=w.bu_a.id, is_billable=False,
                        status="ACTIVE")
    db.add(employee)
    db.commit()
    book = SimpleNamespace(by_object=lambda e, s, n: {(w.bu_a.id, "C1", "US"): amount} if e.id == employee.id else {})
    lines = [{"business_unit_id": bu, "earned_usd_cents": 100, "employee_id": "x", "cost_usd_cents": 0, "cost_business_unit_id": bu,
              "cost_company_id": "C1", "country": "US"} for bu in revenue_bus]
    monkeypatch.setattr(revenue_chain_service, "chain_lines", lambda *a, **k: lines)
    return revenue_chain_service.shared_service_moves(db, start=date(2026, 11, 1), end=date(2026, 11, 30), tenant_id=None, costs=book)


def test_the_split_goes_by_weight_and_nothing_is_lost(db, w, monkeypatch):
    pool, by_function = _moves(monkeypatch, db, w, revenue_bus=[w.bu_a.id, w.bu_b.id])
    assert list(by_function.values()) == [9_000_001]
    assert pool == {(w.bu_a.id, "US"): 9_000_001}
    shares = revenue_chain_service.prorated_shares(9_000_001, {w.bu_a.id: 15, w.bu_b.id: 4})
    assert sum(shares.values()) == 9_000_001
    assert abs(shares[w.bu_a.id] - 9_000_001 * 15 / 19) <= 1


def test_with_no_revenue_the_pool_is_still_known(db, w, monkeypatch):
    pool, _ = _moves(monkeypatch, db, w, revenue_bus=[])
    assert pool == {(w.bu_a.id, "US"): 9_000_001}


def test_a_feedback_task_appears_an_hour_after_the_interview_not_before(db, w):
    from app.services.interview_feedback_task_service import remove_early_feedback_tasks, sync_pending_feedback_tasks_for_interview

    candidate = _candidate(db)
    now = datetime.utcnow()
    upcoming = _interview(db, w, candidate, status="Scheduled", start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=1))
    just_ended = _interview(db, w, candidate, status="Scheduled", start_time=now - timedelta(hours=1), end_time=now - timedelta(minutes=30))
    ended = _interview(db, w, candidate, status="Scheduled", start_time=now - timedelta(hours=2), end_time=now - timedelta(minutes=61))
    db.commit()

    def count(interview):
        return db.query(Task).filter_by(interview_id=interview.id).count()

    for interview in (upcoming, just_ended, ended):
        sync_pending_feedback_tasks_for_interview(db, interview)
    db.commit()
    assert (count(upcoming), count(just_ended), count(ended)) == (0, 0, 1)
    db.add(Task(title="Submit feedback: early", interview_id=upcoming.id, candidate_id=candidate.candidateID, tenant_id=1,
                category="INTERVIEW_FEEDBACK", status="NEW", assigned_to_user_id=w.org_user.UserID))
    db.commit()
    assert remove_early_feedback_tasks(db) >= 1
    assert count(upcoming) == 0
    assert interview_transcript_service.run_interview_feedback_job(db)["closed"] >= 1
    db.expire_all()
    assert db.get(Interview, ended.id).status == "Completed"
    assert count(ended) == 1, "one task, not a second one"

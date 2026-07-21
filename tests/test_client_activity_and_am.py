"""
Proves HRMS-0709: BR-01 (account manager notified on assignment, with
history logged) and the client activity timeline aggregation.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client, ClientContact, ClientHistory
from app.models.employee import Employee
from app.models.demand import Demand, DemandHistory
from app.models.candidate import Candidate
from app.models.submission import Submission, SubmissionViolation
from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
from app.services.client_service import assign_account_manager, get_client_activity_timeline
from app.services.submission_service import create_submission, update_client_response


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, ClientContact.__table__, ClientHistory.__table__,
        Employee.__table__, Demand.__table__, DemandHistory.__table__, Candidate.__table__,
        Submission.__table__, SubmissionViolation.__table__,
        DemandInterviewPanel.__table__, SubmissionInterview.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def base_fixtures(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Acme Insurance", status="PROSPECT")
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills="[\"Guidewire\"]", min_experience_years=5.0,
        work_location="REMOTE", status="OPEN",
    )
    db_session.add(demand)
    db_session.commit()

    return tenant, client, demand


def _make_am(db, tenant, email="am@blitzenx.com"):
    emp = Employee(
        tenant_id=tenant.id, first_name="Priya", last_name="Rao", email=email,
        joining_date=date(2025, 1, 1), status="ACTIVE",
    )
    db.add(emp)
    db.commit()
    return emp


# ---------------------------------------------------------------------------
# assign_account_manager (BR-01)
# ---------------------------------------------------------------------------

def test_assign_account_manager_updates_field_and_logs_history(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    am = _make_am(db_session, tenant)

    with patch("app.services.client_service.EmailService.send_notification") as mock_send:
        assign_account_manager(db_session, client, am, changed_by="U1")
        db_session.commit()

    assert client.account_manager_employee_id == am.id
    mock_send.assert_called_once()

    history = db_session.query(ClientHistory).filter(
        ClientHistory.client_id == client.id, ClientHistory.change_type == "ACCOUNT_MANAGER",
    ).all()
    assert len(history) == 1


def test_assign_account_manager_notification_includes_counts(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    am = _make_am(db_session, tenant)

    with patch("app.services.client_service.EmailService.send_notification") as mock_send:
        assign_account_manager(db_session, client, am)
        db_session.commit()

    _, kwargs = mock_send.call_args
    assert "1 active demand(s)" in kwargs["message"]
    assert "0 open submission(s)" in kwargs["message"]


def test_assign_same_am_is_a_noop(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    am = _make_am(db_session, tenant)

    with patch("app.services.client_service.EmailService.send_notification") as mock_send:
        assign_account_manager(db_session, client, am)
        db_session.commit()
        mock_send.reset_mock()
        assign_account_manager(db_session, client, am)
        db_session.commit()

    mock_send.assert_not_called()
    history_count = db_session.query(ClientHistory).filter(
        ClientHistory.client_id == client.id, ClientHistory.change_type == "ACCOUNT_MANAGER",
    ).count()
    assert history_count == 1


def test_notification_failure_does_not_block_assignment(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    am = _make_am(db_session, tenant)

    with patch("app.services.client_service.EmailService.send_notification", side_effect=Exception("SMTP down")):
        assign_account_manager(db_session, client, am)
        db_session.commit()

    assert client.account_manager_employee_id == am.id


# ---------------------------------------------------------------------------
# get_client_activity_timeline
# ---------------------------------------------------------------------------

def test_activity_timeline_includes_demand_created(db_session, base_fixtures):
    tenant, client, demand = base_fixtures

    events = get_client_activity_timeline(db_session, client.id)
    types = [e["event_type"] for e in events]
    assert "DEMAND_CREATED" in types


def test_activity_timeline_includes_submission_and_placement_in_order(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        tenant_id=tenant.id, total_experience_months=72, employment_type="W2_FULLTIME",
    )
    db_session.add(candidate)
    db_session.commit()
    employee = Employee(
        tenant_id=tenant.id, candidate_id=candidate.candidateID, first_name="Sam", last_name="Lee",
        email="sam@blitzenx.com", joining_date=date(2025, 6, 1), status="BENCH",
    )
    db_session.add(employee)
    db_session.commit()

    submission = create_submission(db_session, tenant_id=tenant.id, demand=demand, candidate=candidate)
    db_session.commit()
    update_client_response(db_session, submission, "CLIENT_INTERVIEW_REQUESTED")
    update_client_response(db_session, submission, "OFFER_EXTENDED")
    update_client_response(db_session, submission, "PLACED")
    db_session.commit()

    events = get_client_activity_timeline(db_session, client.id)
    types_in_order = [e["event_type"] for e in events]

    assert "CANDIDATE_SUBMITTED" in types_in_order
    assert "PLACEMENT_CONFIRMED" in types_in_order
    # chronological: submission event must come before its own placement event
    assert types_in_order.index("CANDIDATE_SUBMITTED") < types_in_order.index("PLACEMENT_CONFIRMED")


def test_activity_timeline_empty_for_client_with_no_demands(db_session, base_fixtures):
    tenant, client, demand = base_fixtures
    other_client = Client(tenant_id=tenant.id, company_name="Other Co", status="PROSPECT")
    db_session.add(other_client)
    db_session.commit()

    events = get_client_activity_timeline(db_session, other_client.id)
    assert events == []

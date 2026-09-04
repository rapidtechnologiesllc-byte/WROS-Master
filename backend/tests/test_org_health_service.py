"""
import logging
Executive Signal & Culture Agent -- org-health rollup.

Proves: the snapshot aggregates real existing signals (no fabricated
Client/Project health scores -- see module docstring) and degrades
gracefully to zero/empty when there's nothing to report, rather than
crashing on an empty database.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.resource_management import BenchPoolEntry
from app.models.revenue_leakage import RevenueLeakageFlag
from app.models.sla_breach import CandidateSLABreach
from app.models.task import Task, TaskCapacityAlert, TaskReassignmentRequest
from app.models.user import Users

import app.services.org_health_service as svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, Employee.__table__,
        RecruiterInterventionQueue.__table__, CandidateSLABreach.__table__,
        RevenueLeakageFlag.__table__, BenchPoolEntry.__table__,
        Task.__table__, TaskReassignmentRequest.__table__, TaskCapacityAlert.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def test_snapshot_degrades_gracefully_on_empty_db(db_session):
    snapshot = svc.get_org_health_snapshot(db_session)

    assert snapshot["revenue"]["active_leakage_flags"] == 0
    assert snapshot["workforce"]["overdue_tasks"] == 0
    assert snapshot["workforce"]["open_capacity_alerts"] == 0
    assert "Client Health" in snapshot["note"]  # honest disclosure, not silently omitted

def test_snapshot_counts_real_overdue_tasks(db_session):
    db_session.add(Task(title="Overdue", priority="HIGH", status="NEW", is_escalated=True))
    db_session.add(Task(title="Fine", priority="LOW", status="NEW", is_escalated=False))
    db_session.commit()

    snapshot = svc.get_org_health_snapshot(db_session)
    assert snapshot["workforce"]["overdue_tasks"] == 1

def test_snapshot_counts_open_capacity_alerts(db_session):
    db_session.add_all([
        TaskCapacityAlert(user_id="u1", open_task_count=10, reason="overloaded", is_resolved=False),
        TaskCapacityAlert(user_id="u2", open_task_count=9, reason="overloaded", is_resolved=True),
    ])
    db_session.commit()

    snapshot = svc.get_org_health_snapshot(db_session)
    assert snapshot["workforce"]["open_capacity_alerts"] == 1

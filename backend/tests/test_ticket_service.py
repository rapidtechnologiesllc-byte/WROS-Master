"""
import logging
Help Desk/IT-HR Ticketing. Throwaway SQLite -- never the real database.

Covers: Impact x Urgency -> Priority derivation, category->department
routing (including the unmatched-category no-guess case), SLA due-date
computation feeding Task.due_date (so tickets show up on the daily
list via the existing Task ranking), first-response shifting the live
deadline from Response to Resolution SLA, and SLA breach flagging
riding the existing overdue-escalation job (not a second scan).
"""
import os
import tempfile
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.prompt_execution_log import PromptExecutionLog
from app.models.rbac_template import BusinessUnit
from app.models.org_structure import Department
from app.models.task import Task, TaskCapacityAlert, TaskReassignmentRequest
from app.models.tenant import Tenant
from app.models.ticket import TicketCategoryRoute, TicketDetail, TicketSLAPolicy
from app.models.user import Users

import app.services.task_escalation_service as escalation_svc
import app.services.ticket_service as ticket_svc

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, BusinessUnit.__table__, Department.__table__,
        Users.__table__, Employee.__table__, Notification.__table__, PromptExecutionLog.__table__,
        Task.__table__, TaskReassignmentRequest.__table__, TaskCapacityAlert.__table__,
        TicketCategoryRoute.__table__, TicketSLAPolicy.__table__, TicketDetail.__table__,
    ])
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
    try:
        os.remove(db_path)
    except PermissionError:
        pass

@pytest.fixture()
def seeded(db_session):
    db_session.add(Tenant(id=1, name="BlitzenX"))
    # Department now uses UUID string IDs
    dept1_id = str(uuid4())
    dept2_id = str(uuid4())
    db_session.add_all([
        Department(id=dept1_id, tenant_id=1, business_unit_id=str(uuid4()), name="IT"),
        Department(id=dept2_id, tenant_id=1, business_unit_id=str(uuid4()), name="Facilities")
    ])
    db_session.commit()

    creator = Users(UserID="u1", UserRole="Employee", UserName="u1", UserEmail="u1@blitzenx.com", UserPassword="x", tenant_id=1)
    db_session.add(creator)
    db_session.commit()

    db_session.add_all([
        TicketSLAPolicy(priority="URGENT", response_minutes=30, resolution_minutes=240),
        TicketSLAPolicy(priority="HIGH", response_minutes=120, resolution_minutes=480),
        TicketSLAPolicy(priority="MEDIUM", response_minutes=480, resolution_minutes=4320),
        TicketSLAPolicy(priority="LOW", response_minutes=1440, resolution_minutes=10080),
        TicketCategoryRoute(category="Laptop Issue", department_id=dept1_id),
        TicketCategoryRoute(category="Office Access", department_id=dept2_id),
    ])
    db_session.commit()
    return {"db": db_session, "creator": creator, "dept1_id": dept1_id, "dept2_id": dept2_id}

def test_priority_derived_from_impact_urgency_matrix():
    assert ticket_svc.derive_priority_from_impact_urgency("ORG_WIDE", "CRITICAL") == "URGENT"
    assert ticket_svc.derive_priority_from_impact_urgency("INDIVIDUAL", "LOW") == "LOW"
    assert ticket_svc.derive_priority_from_impact_urgency("DEPARTMENT", "MODERATE") == "MEDIUM"

def test_priority_never_settable_directly_only_derived():
    with pytest.raises(ValueError):
        ticket_svc.derive_priority_from_impact_urgency("NOT_A_REAL_IMPACT", "CRITICAL")

def test_create_ticket_routes_to_configured_department(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = ticket_svc.create_ticket(
        db, title="Laptop won't boot", description="black screen", impact="INDIVIDUAL", urgency="CRITICAL",
        category="Laptop Issue", created_by_user_id="u1", now=now,
    )
    assert task.department_id == 1
    assert task.task_type == "TICKET"
    assert task.priority == "HIGH"  # INDIVIDUAL+CRITICAL

def test_create_ticket_unmatched_category_not_guessed(seeded):
    db = seeded["db"]
    task = ticket_svc.create_ticket(
        db, title="Something unusual", description=None, impact="INDIVIDUAL", urgency="LOW",
        category="Not A Real Category", created_by_user_id="u1",
    )
    assert task.department_id is None  # never guessed -- surfaced for manual triage

def test_sla_due_dates_feed_task_due_date(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = ticket_svc.create_ticket(
        db, title="Urgent outage", description=None, impact="ORG_WIDE", urgency="CRITICAL",
        category="Laptop Issue", created_by_user_id="u1", now=now,
    )
    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    assert detail.response_due_at == now + timedelta(minutes=30)
    assert detail.resolution_due_at == now + timedelta(minutes=240)
    # Task.due_date tracks the RESPONSE deadline first (the live one) --
    # this is what makes the ticket show up on the daily list via the
    # existing Task ranking, no ticket-specific ranking needed.
    assert task.due_date == detail.response_due_at

def test_first_response_shifts_due_date_to_resolution(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = ticket_svc.create_ticket(
        db, title="X", description=None, impact="ORG_WIDE", urgency="CRITICAL",
        category="Laptop Issue", created_by_user_id="u1", now=now,
    )
    responded_at = now + timedelta(minutes=10)
    ticket_svc.record_first_response(db, task, now=responded_at)
    db.refresh(task)
    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    assert detail.first_response_at == responded_at
    assert task.due_date == detail.resolution_due_at

def test_sla_breach_flags_response_when_never_responded(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = ticket_svc.create_ticket(
        db, title="X", description=None, impact="ORG_WIDE", urgency="CRITICAL",
        category="Laptop Issue", created_by_user_id="u1", now=now,
    )
    later = now + timedelta(hours=1)  # past the 30-min response SLA, never responded
    escalation_svc.escalate_overdue_tasks(db, now=later)

    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    assert detail.response_breached is True
    assert detail.resolution_breached is False

def test_sla_breach_flags_resolution_after_response_recorded(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = ticket_svc.create_ticket(
        db, title="X", description=None, impact="ORG_WIDE", urgency="CRITICAL",
        category="Laptop Issue", created_by_user_id="u1", now=now,
    )
    ticket_svc.record_first_response(db, task, now=now + timedelta(minutes=5))
    later = now + timedelta(hours=5)  # past the 4h resolution SLA
    escalation_svc.escalate_overdue_tasks(db, now=later)

    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    assert detail.resolution_breached is True
    assert detail.response_breached is False

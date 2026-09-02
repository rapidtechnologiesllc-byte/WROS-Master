"""
import logging
S-434 -- Org-wide Task Dashboard.

Throwaway SQLite -- never the real database. Covers: org-wide
numbering, Urgent-priority Thunder validation gate, the two-layer
daily ranking algorithm (due-today hard filter, not a blended score),
capacity-aware round-robin, overdue escalation (priority bump capped
at HIGH + manager notification), and manager-approved reassignment.
"""
import os
import tempfile
from datetime import datetime, timedelta, date
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
from app.models.user import Users

import app.services.task_assignment_service as assign_svc
import app.services.task_escalation_service as escalation_svc
import app.services.task_service as task_svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, BusinessUnit.__table__, Department.__table__,
        Users.__table__, Employee.__table__, Notification.__table__, PromptExecutionLog.__table__,
        Task.__table__, TaskReassignmentRequest.__table__, TaskCapacityAlert.__table__,
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


def _make_user(db, user_id, *, department_id=None, tenant_id=None):
    user = Users(
        UserID=user_id, UserRole="Employee", UserName=user_id, UserEmail=f"{user_id}@blitzenx.com",
        UserPassword="x", department_id=department_id, tenant_id=tenant_id,
    )
    db.add(user)
    db.commit()
    return user


def _link_employee_to_manager(db, user_id, *, manager_user_id):
    """Users has no reporting-manager column of its own -- the real
    hierarchy lives on Employee.reporting_manager_user_id, resolved via
    Employee.wros_user_id -> this Users row (see
    task_assignment_service.resolve_reporting_manager)."""
    emp = Employee(
        first_name=user_id, last_name="Test", email=f"{user_id}@blitzenx.com",
        joining_date=date(2026, 1, 1), wros_user_id=user_id, reporting_manager_user_id=manager_user_id,
    )
    db.add(emp)
    db.commit()
    return emp


@pytest.fixture()
def seeded(db_session):
    tenant = Tenant(id=1, name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    # Department now uses UUID string IDs
    dept_id = str(uuid4())
    bu_id = str(uuid4())
    dept = Department(id=dept_id, tenant_id=1, business_unit_id=bu_id, name="IT")
    db_session.add(dept)
    db_session.commit()

    # Manager deliberately NOT in department_id's own round-robin pool
    # (real orgs don't round-robin work to the manager themselves by
    # default) -- keeps the round-robin tests unambiguous.
    manager = _make_user(db_session, "mgr1", department_id=None, tenant_id=1)
    u1 = _make_user(db_session, "u1", department_id=dept_id, tenant_id=1)
    u2 = _make_user(db_session, "u2", department_id=dept_id, tenant_id=1)
    _link_employee_to_manager(db_session, "u1", manager_user_id="mgr1")
    _link_employee_to_manager(db_session, "u2", manager_user_id="mgr1")
    return {"db": db_session, "manager": manager, "u1": u1, "u2": u2, "dept_id": dept_id}


def _plausible_llm(system_prompt, user_prompt, max_tokens, temperature):
    return "PLAUSIBLE: yes | NOTE: Genuinely time-critical."


def _implausible_llm(system_prompt, user_prompt, max_tokens, temperature):
    return "PLAUSIBLE: no | NOTE: Is this blocking something today, or can it wait?"


def test_task_number_is_org_wide_sequential(seeded):
    db = seeded["db"]
    t1 = task_svc.create_task(db, title="First", created_by_user_id="mgr1")
    t2 = task_svc.create_task(db, title="Second", created_by_user_id="mgr1")
    assert t2.id == t1.id + 1


def test_urgent_task_plausible_not_challenged(seeded):
    db = seeded["db"]
    task = task_svc.create_task(
        db, title="Prod outage", priority="URGENT", created_by_user_id="mgr1",
        urgency_llm_call=_plausible_llm,
    )
    assert task.priority == "URGENT"
    assert task.priority_challenged is False
    assert task.priority_challenge_note


def test_urgent_task_implausible_is_challenged_not_blocked(seeded):
    db = seeded["db"]
    task = task_svc.create_task(
        db, title="Update my email signature", priority="URGENT", created_by_user_id="mgr1",
        urgency_llm_call=_implausible_llm,
    )
    # Never blocks creation -- creator's choice stands, just flagged.
    assert task.priority == "URGENT"
    assert task.priority_challenged is True
    assert "wait" in task.priority_challenge_note.lower()


def test_confirm_urgent_clears_challenge(seeded):
    db = seeded["db"]
    task = task_svc.create_task(
        db, title="X", priority="URGENT", created_by_user_id="mgr1", urgency_llm_call=_implausible_llm,
    )
    assert task.priority_challenged is True
    task_svc.confirm_urgent_task(db, task)
    assert task.priority_challenged is False


def test_daily_list_includes_low_priority_due_today_ahead_of_burial(seeded):
    """The exact bug Avinash caught: a blended score could bury a
    Low-priority task due today under a Medium/High task due later.
    Both must appear; due-today Low must not be excluded."""
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    today_low = Task(title="Low due today", priority="LOW", assigned_to_user_id="u1", due_date=now, status="NEW")
    later_high = Task(title="High due next week", priority="HIGH", assigned_to_user_id="u1", due_date=now + timedelta(days=7), status="NEW")
    db.add_all([today_low, later_high])
    db.commit()

    daily = task_svc.get_daily_task_list(db, assigned_to_user_id="u1", now=now)
    ids = [t.id for t in daily]
    assert today_low.id in ids
    assert later_high.id not in ids  # not due today -- correctly excluded from TODAY's list


def test_daily_list_orders_by_priority_within_due_today(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    low = Task(title="Low", priority="LOW", assigned_to_user_id="u1", due_date=now, status="NEW")
    urgent = Task(title="Urgent", priority="URGENT", assigned_to_user_id="u1", due_date=now, status="NEW",
                  priority_challenge_note="ok")
    db.add_all([low, urgent])
    db.commit()

    daily = task_svc.get_daily_task_list(db, assigned_to_user_id="u1", now=now)
    assert daily[0].id == urgent.id
    assert daily[1].id == low.id


def test_overdue_tasks_bump_priority_capped_at_high(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = Task(title="Overdue", priority="MEDIUM", assigned_to_user_id="u1", due_date=now - timedelta(days=1), status="NEW")
    db.add(task)
    db.commit()

    escalated = escalation_svc.escalate_overdue_tasks(db, now=now)
    assert len(escalated) == 1
    assert task.priority == "HIGH"
    assert task.is_escalated is True

    # Bump ceiling: running it again once already HIGH must not reach URGENT.
    task.is_escalated = False
    db.add(task)
    db.commit()
    escalation_svc.escalate_overdue_tasks(db, now=now)
    assert task.priority == "HIGH"


def test_overdue_escalation_notifies_reporting_manager(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = Task(title="Overdue", priority="LOW", assigned_to_user_id="u1", due_date=now - timedelta(hours=2), status="NEW")
    db.add(task)
    db.commit()

    escalation_svc.escalate_overdue_tasks(db, now=now)
    notes = db.query(Notification).filter(Notification.recipient_id == "mgr1").all()
    assert len(notes) == 1
    assert "escalated" in notes[0].message.lower()


def test_round_robin_picks_least_loaded_department_member(seeded):
    db = seeded["db"]
    # u1 already has 2 open tasks, u2 has 0 -- new task should go to u2.
    db.add_all([
        Task(title="a", assigned_to_user_id="u1", status="NEW", priority="MEDIUM"),
        Task(title="b", assigned_to_user_id="u1", status="IN_PROGRESS", priority="MEDIUM"),
    ])
    db.commit()

    task = task_svc.create_task(db, title="New", created_by_user_id="mgr1", department_id=1)
    assert task.assigned_to_user_id == "u2"


def test_round_robin_skips_user_at_wip_cap_and_alerts_manager(seeded):
    db = seeded["db"]
    for i in range(assign_svc.OPEN_TASK_WIP_CAP):
        db.add(Task(title=f"t{i}", assigned_to_user_id="u1", status="NEW", priority="MEDIUM"))
    db.commit()

    task = task_svc.create_task(db, title="New", created_by_user_id="mgr1", department_id=1)
    assert task.assigned_to_user_id == "u2"  # u1 skipped, at cap

    alerts = db.query(TaskCapacityAlert).filter(TaskCapacityAlert.user_id == "u1").all()
    assert len(alerts) == 1
    notes = db.query(Notification).filter(Notification.recipient_id == "mgr1").all()
    assert len(notes) == 1


def test_reassignment_never_auto_applies_requires_manager_approval(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    task = Task(title="Due today", assigned_to_user_id="u1", department_id=1, due_date=now, status="NEW", priority="MEDIUM")
    db.add(task)
    db.commit()

    requests = assign_svc.suggest_todays_reassignments(db, unavailable_user_id="u1", now=now)
    assert len(requests) == 1
    # Not applied yet -- task still assigned to u1 until a manager approves.
    db.refresh(task)
    assert task.assigned_to_user_id == "u1"

    assign_svc.approve_reassignment(db, requests[0], approved_by_user_id="mgr1", final_to_user_id="mgr1")
    db.refresh(task)
    assert task.assigned_to_user_id == "mgr1"  # manager assigned to themselves, overriding the suggestion


def test_reassignment_excludes_tasks_not_due_today(seeded):
    db = seeded["db"]
    now = datetime(2026, 8, 4, 9, 0, 0)
    later = Task(title="Due next week", assigned_to_user_id="u1", department_id=1, due_date=now + timedelta(days=7), status="NEW", priority="MEDIUM")
    db.add(later)
    db.commit()

    requests = assign_svc.suggest_todays_reassignments(db, unavailable_user_id="u1", now=now)
    assert requests == []

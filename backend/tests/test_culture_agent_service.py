"""
Executive Signal & Culture Agent -- quarterly feedback cycle,
recognition draft-and-approve, dissatisfaction triage.

Proves: recognition is drafted, never auto-sent (approve_and_send_recognition
is the one function that ever sends, and requires an explicit
approver); feedback responses get a real, deterministic flag (not an
LLM verdict); closing a cycle creates a real Task rather than silently
resolving flagged concerns itself; concern triage resolves genuine
FAQ-shaped questions itself and escalates anything else to a real Task
-- never pretends to be Avinash.

"""
import os
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.employee import Employee
from app.models.executive_signal import (
    EmployeeConcernIntake, EmployeeFeedbackCycle, EmployeeFeedbackResponse, RecognitionMessageDraft,
)
from app.models.notification import Notification
from app.models.task import Task, TaskCapacityAlert, TaskReassignmentRequest
from app.models.user import Users

import app.services.culture_agent_service as svc

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_employee(db, *, dob=None, user_id=None):
    user = None
    if user_id:
        user = Users(UserID=user_id, UserRole="Employee", UserName=user_id, UserEmail=f"{user_id}@blitzenx.com", UserPassword="x")
        db.add(user)
    employee = Employee(
        first_name="Priya", last_name="Sharma", email="priya@blitzenx.com",
        joining_date=date(2024, 1, 1), date_of_birth=dob, wros_user_id=user_id,
    )
    db.add(employee)
    db.commit()
    return employee

def test_submit_feedback_flags_negative_keyword_response(db_session):
    employee = _make_employee(db_session)
    cycle = svc.start_quarterly_cycle(db_session, "2026-Q3")

    calm = svc.submit_feedback(db_session, cycle, employee, "Things are going well, no complaints.")
    negative = svc.submit_feedback(db_session, cycle, employee, "Honestly I feel really burned out and underpaid lately.")

    assert calm.is_flagged is False
    assert negative.is_flagged is True

def test_close_cycle_creates_review_task_and_summary(db_session):
    employee = _make_employee(db_session)
    cycle = svc.start_quarterly_cycle(db_session, "2026-Q3")
    svc.submit_feedback(db_session, cycle, employee, "This job is toxic and I'm miserable.")

    summary = svc.close_cycle_and_summarize(db_session, cycle, closed_by="U-HR")

    assert summary["response_count"] == 1
    assert summary["flagged_count"] == 1
    assert employee.id in summary["flagged_employee_ids"]
    assert summary["review_task_id"] is not None

    db_session.refresh(cycle)
    assert cycle.status == "CLOSED"

    task = db_session.query(Task).filter(Task.id == summary["review_task_id"]).first()
    assert task is not None
    assert "2026-Q3" in task.title

def test_generate_birthday_drafts_only_matches_today(db_session):
    today = date(2026, 8, 4)
    birthday_employee = _make_employee(db_session, dob=date(1990, 8, 4))
    other_employee = Employee(first_name="Raj", last_name="Kumar", email="raj@blitzenx.com", joining_date=date(2024, 1, 1), date_of_birth=date(1990, 5, 1))
    db_session.add(other_employee)
    db_session.commit()

    drafts = svc.generate_birthday_drafts(db_session, today=today)

    assert len(drafts) == 1
    assert drafts[0].employee_id == birthday_employee.id
    assert drafts[0].status == "DRAFT"

def test_generate_birthday_drafts_idempotent_same_day(db_session):
    today = date(2026, 8, 4)
    _make_employee(db_session, dob=date(1990, 8, 4))

    first = svc.generate_birthday_drafts(db_session, today=today)
    second = svc.generate_birthday_drafts(db_session, today=today)

    assert len(first) == 1
    assert len(second) == 0  # already drafted today -- no duplicate

def test_recognition_never_auto_sent_requires_explicit_approval(db_session):
    employee = _make_employee(db_session, dob=date(1990, 8, 4), user_id="U-EMP")
    drafts = svc.generate_birthday_drafts(db_session, today=date(2026, 8, 4))
    draft = drafts[0]
    assert draft.status == "DRAFT"

    # Not sent yet -- no notification exists.
    assert db_session.query(Notification).count() == 0

    sent = svc.approve_and_send_recognition(db_session, draft, approved_by="U-HR")
    assert sent.status == "SENT"
    assert sent.approved_by == "U-HR"
    assert db_session.query(Notification).count() == 1

def test_recognition_cannot_be_sent_twice(db_session):
    employee = _make_employee(db_session, dob=date(1990, 8, 4), user_id="U-EMP")
    draft = svc.generate_birthday_drafts(db_session, today=date(2026, 8, 4))[0]
    svc.approve_and_send_recognition(db_session, draft, approved_by="U-HR")

    with pytest.raises(ValueError):
        svc.approve_and_send_recognition(db_session, draft, approved_by="U-HR")

def test_reject_recognition_marks_rejected(db_session):
    _make_employee(db_session, dob=date(1990, 8, 4))
    draft = svc.generate_birthday_drafts(db_session, today=date(2026, 8, 4))[0]

    rejected = svc.reject_recognition(db_session, draft)
    assert rejected.status == "REJECTED"

def test_concern_resolves_real_faq_match(db_session):
    employee = _make_employee(db_session)
    intake = svc.submit_concern(db_session, employee, "How do I request PTO for next month?")

    assert intake.category == "RESOLVED"
    assert intake.resolution_text is not None
    assert intake.created_task_id is None

def test_concern_escalates_to_real_task_when_not_faq_shaped(db_session):
    employee = _make_employee(db_session)
    intake = svc.submit_concern(db_session, employee, "I've been having real problems with my manager and it's affecting my work.")

    assert intake.category == "ESCALATED"
    assert intake.created_task_id is not None
    task = db_session.query(Task).filter(Task.id == intake.created_task_id).first()
    assert task is not None
    assert task.priority == "HIGH"

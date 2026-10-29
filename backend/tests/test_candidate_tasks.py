"""Candidate tasks (CEO 2026-10-24): a task about a candidate with what, when and who, and a
repeating keep-in-touch task that goes on until the candidate joins."""
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.task_activity_service import log_task_update
from app.services.task_service import (
    complete_task, create_task, list_candidate_tasks, next_due, open_next_occurrence, stop_repeating,
)
from tests.hiring_fixtures import full_access_role


def uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    if session.query(Tenant).filter_by(id=1).first() is None:
        session.add(Tenant(id=1, name="BlitzenX"))
        session.flush()
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def world(db):
    role = full_access_role(db)
    recruiter = Users(UserID=f"U-{uid()}", UserName="Avinash", UserEmail=f"{uid()}@blitzenx.com", UserPassword="x",
                      UserRole="x", tenant_id=1, role_template_id=role.id)
    candidate = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Neha", candidateLastName="Setia",
                          candidateEmail=f"{uid()}@example.com", candidatePassword="x", tenant_id=1)
    db.add_all([recruiter, candidate])
    db.commit()
    return recruiter, candidate


def monthly_task(db, recruiter, candidate, due):
    return create_task(db, title="Monthly check-in", description="Ask about her notice period", priority="MEDIUM",
                       created_by_user_id=recruiter.UserID, assigned_to_user_id=recruiter.UserID, tenant_id=1,
                       due_date=due, candidate_id=candidate.candidateID, recurrence="MONTHLY")


def test_a_monthly_task_opens_the_next_month_when_completed(db, world):
    recruiter, candidate = world
    due = datetime.utcnow() + timedelta(days=2)
    task = monthly_task(db, recruiter, candidate, due)
    complete_task(db, task)
    tasks = list_candidate_tasks(db, candidate.candidateID, 1)
    following = tasks[0]
    assert following.status == "NEW" and following.recurrence == "MONTHLY" and following.parent_task_id == task.id
    assert following.due_date == next_due(due, "MONTHLY")
    assert following.assigned_to_user_id == recruiter.UserID and following.description == "Ask about her notice period"
    assert [t.id for t in tasks] == [following.id, task.id]  # open first, then done


def test_a_late_completion_never_schedules_the_next_one_in_the_past(db, world):
    recruiter, candidate = world
    task = monthly_task(db, recruiter, candidate, datetime.utcnow() - timedelta(days=70))
    following = open_next_occurrence(db, task)
    assert following.due_date > datetime.utcnow()


def test_the_series_stops_when_the_candidate_joins_or_a_person_stops_it(db, world):
    from app.models.employee import Employee

    recruiter, candidate = world
    task = monthly_task(db, recruiter, candidate, datetime.utcnow())
    stop_repeating(db, task)
    complete_task(db, task)
    assert len(list_candidate_tasks(db, candidate.candidateID, 1)) == 1

    task = monthly_task(db, recruiter, candidate, datetime.utcnow())
    db.add(Employee(tenant_id=1, first_name="Neha", last_name="Setia", email=f"{uid()}@blitzenx.com",
                    joining_date=date.today(), candidate_id=candidate.candidateID))
    db.commit()
    complete_task(db, task)
    assert not [t for t in list_candidate_tasks(db, candidate.candidateID, 1) if t.status == "NEW"]


def test_completing_through_a_logged_update_also_repeats(db, world):
    recruiter, candidate = world
    task = monthly_task(db, recruiter, candidate, datetime.utcnow() + timedelta(days=1))
    log_task_update(db, task, recruiter, activity_type="CALL", notes="Spoke, still thinking", complete_task=True)
    assert db.query(Task).filter_by(parent_task_id=task.id, recurrence="MONTHLY", status="NEW").count() == 1


def test_a_repeat_needs_a_known_interval_and_a_due_date(db, world):
    recruiter, candidate = world
    with pytest.raises(ValueError, match="Repeat must be one of"):
        create_task(db, title="x", created_by_user_id=recruiter.UserID, recurrence="DAILY", due_date=datetime.utcnow())
    with pytest.raises(ValueError, match="needs a due date"):
        create_task(db, title="x", created_by_user_id=recruiter.UserID, recurrence="MONTHLY")


def test_month_ends_are_kept_inside_the_month():
    assert next_due(datetime(2026, 1, 31, 9), "MONTHLY") == datetime(2026, 2, 28, 9)
    assert next_due(datetime(2026, 11, 30, 9), "QUARTERLY") == datetime(2027, 2, 28, 9)
    assert next_due(datetime(2026, 12, 15, 9), "MONTHLY") == datetime(2027, 1, 15, 9)


# ---- through the API (the candidate's Tasks tab) -------------------------------------------

@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(user):
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def test_the_tasks_tab_creates_and_lists_a_candidates_tasks(client, db, world):
    recruiter, candidate = world
    recruiter.password_reset_required = False
    db.commit()
    options = client.get("/api/v1/tasks/options", headers=_headers(recruiter)).json()
    assert "MONTHLY" in [o["value"] for o in options["recurrences"]]

    due = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT09:00:00")
    created = client.post("/api/v1/tasks", headers=_headers(recruiter), json={
        "title": "Monthly check-in", "description": "Until she joins", "due_date": due,
        "candidate_id": candidate.candidateID, "recurrence": "MONTHLY"})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["assigned_to_user_id"] == recruiter.UserID  # no assignee picked: the creator
    assert body["candidate_id"] == candidate.candidateID and body["recurrence"] == "MONTHLY"

    listed = client.get(f"/api/v1/tasks/candidate/{candidate.candidateID}", headers=_headers(recruiter))
    assert listed.status_code == 200, listed.text
    assert [(t["title"], t["assigned_to_name"]) for t in listed.json()] == [("Monthly check-in", "Avinash")]

    bad = client.post("/api/v1/tasks", headers=_headers(recruiter), json={
        "title": "x", "due_date": due, "candidate_id": candidate.candidateID, "assigned_to_user_id": "nobody"})
    assert bad.status_code == 422
    missing = client.get("/api/v1/tasks/candidate/CAN-does-not-exist", headers=_headers(recruiter))
    assert missing.status_code == 404

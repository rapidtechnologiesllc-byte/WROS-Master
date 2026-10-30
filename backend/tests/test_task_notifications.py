"""Task emails: the assignee is mailed when a task is assigned to them (not when they made it for
themselves), when a logged next action becomes a follow-up task, when a task is reassigned to them,
and when an open task falls due. Each email opens the task's record, or the task itself on My Tasks."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.task import Task, TaskReassignmentRequest
from app.services import task_notification_service as notices
from app.services.task_activity_service import log_task_update
from app.services.task_assignment_service import approve_reassignment
from app.services.task_service import create_task
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import person

QUEUE = "app.services.staff_mail_service.queue_staff_email"


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
def people(db):
    role = full_access_role(db)
    return person(db, role, "Owner"), person(db, role, "Boss")


def _title() -> str:
    return f"Task {uuid.uuid4().hex[:8]}"


def test_a_system_task_mails_its_assignee_with_a_link_to_the_task(db, people):
    owner, _ = people
    with patch(QUEUE, return_value=True) as queue:
        task = create_task(db, title=_title(), description="Forwarded email details", tenant_id=1,
                           assigned_to_user_id=owner.UserID, due_date=datetime.utcnow())
    queue.assert_called_once()
    user, = queue.call_args.args
    kwargs = queue.call_args.kwargs
    assert user.UserID == owner.UserID
    assert kwargs["subject"].startswith(f"New task #{task.id}")
    assert kwargs["link_path"] == f"/my-tasks?task={task.id}"
    assert "Forwarded email details" in kwargs["paragraphs"]
    assert kwargs["key"].startswith(f"task-assigned-{task.id}-{owner.UserID}-")


def test_a_task_about_a_candidate_links_to_the_candidate(db, people):
    owner, boss = people
    with patch(QUEUE, return_value=True) as queue:
        create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID,
                    created_by_user_id=boss.UserID, link="/candidates/CAN-9")
    assert queue.call_args.kwargs["link_path"] == "/candidates/CAN-9"
    assert "by Boss" in queue.call_args.kwargs["paragraphs"][0]


def test_a_task_you_made_for_yourself_sends_no_email(db, people):
    owner, _ = people
    with patch(QUEUE, return_value=True) as queue:
        create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID,
                    created_by_user_id=owner.UserID)
    queue.assert_not_called()


def test_a_failed_email_never_undoes_the_task(db, people):
    owner, _ = people
    with patch(QUEUE, side_effect=RuntimeError("queue down")):
        task = create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID)
    assert db.get(Task, task.id) is not None


def test_a_logged_next_action_mails_the_next_step(db, people):
    owner, _ = people
    with patch(QUEUE, return_value=True):
        task = create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID,
                           created_by_user_id=owner.UserID)
    due = datetime.utcnow() + timedelta(days=2)
    with patch(QUEUE, return_value=True) as queue:
        activity = log_task_update(db, task, owner, activity_type="CALL", notes="Spoke to them",
                                   next_action_type="FOLLOW_UP", next_action_due=due)
    queue.assert_called_once()
    assert queue.call_args.kwargs["subject"].startswith("Next step:")
    assert queue.call_args.kwargs["key"].startswith(f"task-next_step-{activity.follow_up_task_id}-")


def test_an_approved_reassignment_mails_the_new_assignee(db, people):
    owner, boss = people
    with patch(QUEUE, return_value=True):
        task = create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID)
    req = TaskReassignmentRequest(task_id=task.id, from_user_id=owner.UserID, suggested_to_user_id=boss.UserID)
    db.add(req)
    db.flush()
    with patch(QUEUE, return_value=True) as queue:
        approve_reassignment(db, req, approved_by_user_id=boss.UserID, final_to_user_id=boss.UserID)
    assert queue.call_args.args[0].UserID == boss.UserID
    assert queue.call_args.kwargs["subject"].startswith(f"Task #{task.id} moved to you")


def _due_task(db, owner, due, created_at, status="NEW") -> Task:
    with patch(QUEUE, return_value=True):
        task = create_task(db, title=_title(), tenant_id=1, assigned_to_user_id=owner.UserID,
                           created_by_user_id=owner.UserID, due_date=due)
    task.created_at, task.status = created_at, status
    db.flush()
    return task


def test_due_reminders_mail_only_tasks_that_just_fell_due(db, people):
    owner, _ = people
    now = datetime.utcnow()
    just_due = _due_task(db, owner, now - timedelta(minutes=10), now - timedelta(days=1))
    created_due = _due_task(db, owner, now - timedelta(minutes=10), now - timedelta(minutes=10))
    stale = _due_task(db, owner, now - timedelta(hours=5), now - timedelta(days=1))
    done = _due_task(db, owner, now - timedelta(minutes=10), now - timedelta(days=1), status="COMPLETED")
    later = _due_task(db, owner, now + timedelta(hours=1), now - timedelta(days=1))
    with patch(QUEUE, return_value=True) as queue:
        result = notices.run_due_reminders(db, now=now)
    mailed = {c.kwargs["key"].split("-")[2] for c in queue.call_args_list}
    assert str(just_due.id) in mailed
    assert not mailed & {str(t.id) for t in (created_due, stale, done, later)}
    assert result["queued"] >= 1


def test_due_reminders_report_failures(db, people):
    owner, _ = people
    now = datetime.utcnow()
    _due_task(db, owner, now - timedelta(minutes=5), now - timedelta(days=1))
    with patch(QUEUE, side_effect=ValueError("no email")), pytest.raises(RuntimeError):
        notices.run_due_reminders(db, now=now)

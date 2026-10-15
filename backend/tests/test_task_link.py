"""A task can carry its own in-app link, which My Tasks opens first: the column is added on
startup by the schema contract, only same-site paths are accepted, and the API returns it.
The Core certification approval task links to the review screen."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.task_service import create_task
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient, person


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_schema_migrations_add_the_link_column(test_db_engine):
    from app.core.db_contract import _run_schema_migrations

    with test_db_engine.begin() as conn:
        conn.execute(text("ALTER TABLE app_schema.tasks DROP COLUMN IF EXISTS link"))
    _run_schema_migrations()
    columns = {c["name"]: c for c in inspect(test_db_engine).get_columns("tasks", schema="app_schema")}
    assert "link" in columns and columns["link"]["nullable"] is True
    _run_schema_migrations()  # idempotent


@pytest.mark.parametrize("link", ["https://evil.example/x", "//evil.example/x", "jobs/1", "/jobs/1 2",
                                  "/\\evil.example", "/" + "a" * 600, ""])
def test_only_in_app_paths_are_accepted(db, link):
    full_access_role(db)
    with pytest.raises(ValueError):
        create_task(db, title="t", tenant_id=1, link=link)


def test_link_is_stored_and_returned_by_my_day(db):
    owner = person(db, full_access_role(db), "Owner")
    task = create_task(db, title=f"Open me {uuid.uuid4().hex[:6]}", tenant_id=1, assigned_to_user_id=owner.UserID,
                       due_date=datetime.utcnow() - timedelta(hours=1), link="/candidates/CAN-1?tab=interview")
    plain = create_task(db, title="No link", tenant_id=1, assigned_to_user_id=owner.UserID,
                        due_date=datetime.utcnow() - timedelta(hours=1))
    assert db.get(Task, task.id).link == "/candidates/CAN-1?tab=interview"
    api = ApiClient(db)
    try:
        rows = {r["id"]: r for r in api.get(owner, "/api/v1/tasks/my-day").json()}
    finally:
        api.close()
    assert rows[task.id]["link"] == "/candidates/CAN-1?tab=interview" and rows[plain.id]["link"] is None


def test_core_certification_approval_task_links_to_the_review_screen(db):
    from app.services import core_certification_service as service

    owner = person(db, full_access_role(db), "Head")
    employee = type("E", (), {"first_name": "Ravi", "last_name": "K", "email": "r@x"})()
    task = service._approval_task(db, employee, owner.UserID, 90, 1)
    assert task.link == service.REVIEW_PATH == "/workforce/core-certification"

"""The polling endpoint every queued create returns (/message-queue/tasks/{id}/status) exists and
shows a task only to its own tenant."""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.message_queue import get_task_status
from app.models.channel_queue import ChannelQueueItem
from app.models.tenant import Tenant
from app.models.user import Users


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _tenant(db, tenant_id):
    if db.query(Tenant).filter_by(id=tenant_id).first() is None:
        db.add(Tenant(id=tenant_id, name=f"tenant-{tenant_id}-{uuid.uuid4().hex[:6]}"))
        db.flush()


def test_task_status_is_visible_to_its_own_tenant_only(db):
    _tenant(db, 1)
    _tenant(db, 2)
    task_id = uuid.uuid4().hex
    db.add(ChannelQueueItem(id=task_id, message_id=task_id, tenant_id=1, type="create_candidate",
                            channel_type="CANDIDATE_QUEUE", status="COMPLETED", payload={}, retry_count=0))
    db.flush()
    own = Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserName="A", UserEmail="a@x.com", UserPassword="x",
                UserRole="x", tenant_id=1)
    other = Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserName="B", UserEmail="b@x.com", UserPassword="x",
                  UserRole="x", tenant_id=2)

    assert get_task_status(task_id, db=db, current_user=own)["status"] == "completed"
    with pytest.raises(HTTPException) as hidden:
        get_task_status(task_id, db=db, current_user=other)
    assert hidden.value.status_code == 404


def test_queued_creates_point_at_the_real_polling_endpoint():
    import pathlib

    app = pathlib.Path(__file__).resolve().parent.parent / "app"
    sources = "".join(p.read_text() for p in app.rglob("*.py"))
    assert "/api/v1/message-queue/status/" not in sources and '"/api/v1/tasks/{message_id}/status"' not in sources
    assert "/api/v1/message-queue/tasks/{" in sources

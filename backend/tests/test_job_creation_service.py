"""job_creation_service.submit_job is the one job-creation path: the Create Job endpoint is a thin
wrapper around it, and Flash calls it directly with the requester as the user."""
import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints import create_job as create_job_endpoint
from app.models.tenant import Tenant
from app.schemas.user import JobCreateRequest
from app.services.job_creation_service import submit_job
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import person

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


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
def queued():
    calls = []

    def enqueue(task_name, task_id=None, data=None, **kw):
        calls.append(SimpleNamespace(task_name=task_name, task_id=task_id, data=data, kw=kw))
        return {"status": "queued", "task_id": task_id}

    with patch(ENQUEUE, side_effect=enqueue):
        yield calls


@pytest.fixture
def creator(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="tenant-1"))
        db.flush()
    user = person(db, full_access_role(db), "Creator")
    db.flush()
    return user


def _request(**extra):
    body = {"job_title": "Rails Developer", "job_description": "Build things", "job_skills": "Ruby on Rails",
            "structured_skills": [{"name": "Ruby on Rails", "is_primary": True}], "min_experience_years": 5, "job_experience": "5+ years",
            "job_location": "Remote", "company_type": "Full time", "company_name": "", "job_status": "active"}
    body.update(extra)
    return JobCreateRequest(**body)


def test_submit_job_queues_the_job_in_the_callers_tenant_and_returns_its_id(db, creator, queued):
    job_id = submit_job(db, creator, _request(contact_person="string"))
    call = next(c for c in queued if c.task_name == "job_created_flash")
    assert call.task_id == f"job_created:{job_id}"
    assert call.data["job_id"] == job_id and call.data["tenant_id"] == creator.tenant_id
    assert call.data["created_by_user_id"] == creator.UserID and call.data["job_status"] == "active"
    assert call.data["contact_person"] is None  # swagger's "string" means not given
    assert call.data["structured_skills"][0]["name"] == "Ruby on Rails"


def test_submit_job_rejects_an_unknown_user_and_queues_nothing(db, creator, queued):
    with pytest.raises(HTTPException) as exc:
        submit_job(db, creator, _request(hiring_manager_id="U-nobody"))
    assert exc.value.status_code == 400 and "hiring_manager_id" in exc.value.detail
    assert queued == []


def test_the_endpoint_is_a_thin_wrapper_around_submit_job():
    source = inspect.getsource(create_job_endpoint.create_job)
    assert "submit_job(db, user, request)" in source
    assert "MessageQueueService" not in source

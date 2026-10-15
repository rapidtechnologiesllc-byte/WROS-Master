"""A live job starts recruiting by itself, whichever way it went live, and the sourcing
report reaches the job's recruiter as a task. The recruiter run no longer crashes when it
finds a watching candidate, and its 4-hourly re-run no longer collides with itself."""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_opportunity_watch import CandidateOpportunityWatch
from app.models.role_template import RoleTemplate
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import Jobs, Users
from app.services import recruiting_service
from app.services.message_handlers.flash_recruiter_handler import FlashRecruiterHandler


def _uid():
    return uuid.uuid4().hex[:8]


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
        calls.append((task_name, task_id, data, kw))
        return {"status": "queued", "task_id": task_id}

    with patch("app.services.message_queue_service.MessageQueueService.enqueue", side_effect=enqueue):
        yield calls


@pytest.fixture
def job(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="R", enabled=True)
    db.add(role)
    db.flush()
    recruiter = Users(UserID=f"R-{_uid()}", UserName="Rae", UserEmail=f"rae{_uid()}@blitzenx.com", UserPassword="x",
                      UserRole="recruiter", tenant_id=1, role_template_id=role.id)
    db.add(recruiter)
    db.flush()
    row = Jobs(tenant_id=1, jobTitle="Kafka Engineer", jobDescription="d", jobSkills="Kafka, Java", jobExperience="5",
               jobLocation="Pune", jobStatus="active", hiringManagerID=recruiter.UserID,
               recuriterID=recruiter.UserID)
    db.add(row)
    db.commit()
    return row


def test_start_recruiting_queues_both_runs_with_unique_ids(job, queued):
    recruiting_service.start_recruiting(job, "approved")
    recruiting_service.start_recruiting(job, "approved")
    names = [c[0] for c in queued]
    assert names.count("flash_recruiter") == 2 and names.count("source_candidates_for_job") == 2
    assert len({c[1] for c in queued}) == 4
    assert all(c[3]["tenant_id"] == 1 for c in queued)


def test_sourcing_report_becomes_a_recruiter_task(db, job):
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"k{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Kiran", candidateLastName="Rao", tenant_id=1)
    db.add(candidate)
    db.commit()
    report = {"job_id": job.jobID, "candidates_available": 12, "top_matches": [
        {"candidate_id": candidate.candidateID, "recency_score": 82, "can_proceed": True},
        {"candidate_id": "CAN-weak", "recency_score": 20, "can_proceed": False}]}
    result = recruiting_service.handle_sourcing_complete(SimpleNamespace(id="m1", payload=report), db)
    task = db.get(Task, result["task_id"])
    assert result["viable_matches"] == 1 and task.assigned_to_user_id == job.recuriterID
    assert "Kiran Rao: 82% skill recency" in task.description and "CAN-weak" not in task.description
    empty = recruiting_service.handle_sourcing_complete(
        SimpleNamespace(id="m2", payload={"job_id": job.jobID, "top_matches": []}), db)
    assert db.get(Task, empty["task_id"]).title.startswith("No viable candidates yet")


def test_recruiter_run_with_a_watching_candidate_does_not_crash_and_reschedules_uniquely(db, job, queued):
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"w{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Wen", candidateLastName="Li", tenant_id=1)
    db.add(candidate)
    db.flush()
    watch = CandidateOpportunityWatch(tenant_id=1, candidate_id=candidate.candidateID, reason="NOT_NOW", is_active=True)
    db.add(watch)
    db.commit()
    message = SimpleNamespace(id="msg-1", payload={"job_id": job.jobID})
    with patch.object(FlashRecruiterHandler, "_check_thunder_health", return_value={"healthy": True, "success_rate": 1.0}), \
            patch("app.services.ready_for_opportunity_service.scan_new_job_for_matches", return_value=[watch]):
        first = FlashRecruiterHandler.process(message, db)
        second = FlashRecruiterHandler.process(SimpleNamespace(id="msg-2", payload={
            "job_id": job.jobID, "previously_matched_candidate_ids": [candidate.candidateID]}), db)
    assert first["candidates_new"] == 1 and second["candidates_new"] == 0
    reruns = [c for c in queued if c[0] == "flash_recruiter"]
    assert len(reruns) == 2 and reruns[0][1] != reruns[1][1]
    # the interval is a setting, and the re-run stays in the job's tenant
    from app.core.config import settings
    assert reruns[0][3]["delay_seconds"] == settings.FLASH_RECRUITER_INTERVAL_HOURS * 3600
    assert reruns[0][3]["tenant_id"] == job.tenant_id == 1

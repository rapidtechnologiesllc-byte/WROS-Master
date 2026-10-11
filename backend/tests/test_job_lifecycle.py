"""A job with hiring or delivery history is closed, never deleted (its interview verdicts
feed the rehire guard); only a job nothing refers to may be deleted."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import InterviewPanel, Jobs
from app.services.job_lifecycle_service import JobHasHistory, assert_deletable, job_history
from tests.hiring_fixtures import full_access_role


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _job(db):
    full_access_role(db)  # ensures tenant 1
    job = Jobs(tenant_id=1, jobTitle="Dev", jobDescription="d", jobSkills="x", jobExperience="5", jobLocation="Remote")
    db.add(job)
    db.flush()
    return job


def test_a_job_with_interview_history_cannot_be_deleted(db):
    job = _job(db)
    candidate = Candidate(candidateID=f"CAN-{uuid.uuid4().hex[:8]}", candidateEmail=f"c{uuid.uuid4().hex[:8]}@x.com",
                          candidatePassword="x", tenant_id=1)
    db.add(candidate)
    db.flush()
    db.add(InterviewPanel(candidate_id=candidate.candidateID, round_name="L1", job_id=job.jobID))
    db.flush()
    assert job_history(db, job.jobID) == {"interview rounds": 1}
    with pytest.raises(JobHasHistory, match="close it instead"):
        assert_deletable(db, job.jobID)


def test_a_job_nothing_refers_to_can_be_deleted(db):
    job = _job(db)
    assert job_history(db, job.jobID) == {}
    assert_deletable(db, job.jobID)

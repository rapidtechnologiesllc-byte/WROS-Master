"""CEO 2026-11-05: no history on a job, a submitted candidate not showing, a raw id as hiring manager, and "it has to be
interlinked and autonomous"."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.flash_mission import FlashMission
from app.models.hiring_pipeline import HiringPipeline
from app.models.opportunity import Opportunity
from app.models.user import Interview, InterviewPanel, Jobs
from app.services import flash_mission_service
from tests.scope_fixtures import ApiClient, two_bu_world


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
def w(db):
    world = two_bu_world(db)
    world.candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                                candidateFirstName="Jane", candidateLastName="Doe",
                                candidateEmail=f"j{uuid.uuid4().hex[:6]}@example.com", candidateExperience="8")
    world.job = world.job_a
    world.job.hiringManagerID = world.partner_a.UserID
    world.job.jobCreatedAt = datetime.utcnow() - timedelta(days=2)
    db.add(world.candidate)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _assign(api, w):
    return api.post(w.org_user, f"/api/v1/jobs/{w.job.jobID}/applications/{w.candidate.candidateID}", json={})


def test_the_history_tells_what_happened_with_links(api, db, w):
    assert _assign(api, w).status_code in (200, 201)
    panel = InterviewPanel(candidate_id=w.candidate.candidateID, job_id=w.job.jobID, round_name="L1")
    db.add(panel)
    db.flush()
    db.add(Interview(panel_id=panel.id, candidate_id=w.candidate.candidateID, status="Scheduled",
                     start_time=datetime.utcnow() + timedelta(days=1), end_time=datetime.utcnow() + timedelta(days=1, hours=1)))
    db.commit()
    response = api.get(w.org_user, f"/api/v1/jobs/{w.job.jobID}/history")
    assert response.status_code == 200, response.text
    body = response.json()
    titles = [e["title"] for e in body["events"]]
    assert any(t.startswith("Job created") for t in titles)
    assert any("Jane Doe" in t and "submitted" in t for t in titles)
    assert any(t == "L1 with Jane Doe" for t in titles)
    assert any(e["link"] == f"/candidates/{w.candidate.candidateID}" for e in body["events"])
    assert body["summary"]["upcoming_interviews"] == 1
    assert body["summary"]["offer_acceptance_pct"] is None


def test_the_job_answers_with_names_client_and_opportunity(api, db, w):
    opportunity = Opportunity(tenant_id=1, client_id=w.client_a.id, stage="PROPOSAL", revenue_value_usd_cents=100)
    db.add(opportunity)
    db.flush()
    w.job.opportunity_id = opportunity.id
    db.commit()
    body = api.get(w.org_user, f"/api/v1/jobs/job-details/{w.job.jobID}").json()
    assert body["hiring_manager_name"] == w.partner_a.UserName
    assert body["client_name"] == w.client_a.company_name
    assert body["opportunity_id"] == opportunity.id and body["opportunity_stage"] == "PROPOSAL"


def test_submitting_links_the_open_pipeline_to_the_job(api, db, w):
    pipeline = HiringPipeline(tenant_id=1, candidate_id=w.candidate.candidateID, stage="SCREEN")
    db.add(pipeline)
    db.commit()
    assert _assign(api, w).status_code in (200, 201)
    db.expire_all()
    assert db.get(HiringPipeline, pipeline.id).job_id == w.job.jobID


def test_an_open_confirmed_job_gets_flash_by_itself_and_only_then(db, w):
    for job in db.query(Jobs).filter(Jobs.jobID.in_([w.job_a.jobID, w.job_b.jobID])).all():
        job.jobStatus, job.recuriterID, job.noOfPositions = "active", w.org_user.UserID, 1
        job.jobCreatedAt, job.confirmation_status = datetime.utcnow(), "CONFIRMED"
    w.job_b.confirmation_status = "POTENTIAL"
    db.commit()
    assert flash_mission_service.start_missions_for_open_jobs(db)["started"] >= 1
    assert db.query(FlashMission).filter(FlashMission.job_id == w.job_a.jobID).count() == 1
    assert db.query(FlashMission).filter(FlashMission.job_id == w.job_b.jobID).count() == 0
    flash_mission_service.start_missions_for_open_jobs(db)
    assert db.query(FlashMission).filter(FlashMission.job_id == w.job_a.jobID).count() == 1

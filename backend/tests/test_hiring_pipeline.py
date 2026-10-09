"""The hiring pipeline derives each candidate's stage from facts, in the CEO's order:
screen -> L1 -> L2 -> offer accepted -> onboarding -> BGV -> bench. The first missing fact
is the blocker; gates refuse to skip ahead; evaluating twice changes nothing; a stage's
action runs once; employees from before the pipeline are grandfathered."""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.background_verification import BackgroundVerification
from app.models.candidate import Candidate, CandidateStatus
from app.models.checklist import CandidateChecklist
from app.models.employee import Employee
from app.models.hiring_pipeline import HiringPipeline, HiringPipelineEvent
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.role_template import RoleTemplate
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.user import InterviewPanel, Users
from app.services import hiring_pipeline_service as hp


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

    def enqueue_once(task_name, task_id, data, tenant_id, delay_seconds=0):
        if any(c[1] == task_id for c in calls):
            return False
        calls.append((task_name, task_id, data))
        return True

    with patch("app.services.thunder_mail.cadence_service.enqueue_once", side_effect=enqueue_once):
        yield calls


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = db.query(RoleTemplate).filter_by(tenant_id=1, name="Super Admin").first() or \
        RoleTemplate(tenant_id=1, name="Super Admin", display_name="Super Admin", enabled=True)
    db.add(role)
    db.flush()
    hr = Users(UserID=f"HR-{_uid()}", UserName="HR", UserEmail=f"hr{_uid()}@blitzenx.com", UserPassword="x",
               UserRole="admin", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(hr)
    db.commit()
    return hr


def _candidate(db, thunder=False):
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Lee", candidateLastName="Park", tenant_id=1, thunder_enabled=thunder)
    db.add(candidate)
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Screening",
                           thunder_assigned_at=datetime.utcnow() if thunder else None))
    db.commit()
    return candidate


def _round(db, candidate, level, verdict):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=level)
    db.add(panel)
    db.flush()
    db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                 verdict=verdict, source="MANUAL"))
    db.commit()


def _offer(db, candidate, status, hr):
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1200000",
                        joining_date=date.today() - timedelta(days=1), offer_expire_date=date.today() + timedelta(days=7),
                        offer_status=status, created_by=hr.UserID, responded_at=datetime.utcnow() - timedelta(hours=1))
    db.add(offer)
    db.commit()
    return offer


def _stage(db, candidate):
    pipeline = hp.get_or_create_pipeline(db, candidate.candidateID)
    hp.evaluate(db, pipeline)
    db.commit()
    return pipeline.stage, pipeline.blockers


def test_full_walk_from_screen_to_bench(db, world, queued):
    candidate = _candidate(db)
    assert _stage(db, candidate) == ("SCREEN", ["recruiter screen pending"])
    hp.record_screen_decision(db, candidate.candidateID, "PASS", world.UserID)
    assert _stage(db, candidate) == ("L1", ["L1 (technical) interview not scheduled"])
    _round(db, candidate, "L1", "NEEDS_DECISION")
    assert _stage(db, candidate)[1] == ["L1 (technical) interview mixed feedback, hiring manager to decide"]
    _round(db, candidate, "L1", "PASS")  # the latest L1 round decides
    assert _stage(db, candidate)[0] == "L2"
    _round(db, candidate, "L2", "PASS")
    assert _stage(db, candidate) == ("OFFER", ["no offer created yet"])
    offer = _offer(db, candidate, "Released", world)
    assert _stage(db, candidate)[1] == ["offer is Released; waiting for the candidate to accept"]
    offer.offer_status = "Accepted"
    db.commit()
    assert _stage(db, candidate) == ("ONBOARDING", ["pre-joining document collection has not started"])
    doc = PreboardingDocument(tenant_id="1", candidate_id=candidate.candidateID, offer_id=offer.id,
                              document_type="PAN", document_label="PAN card", status="RECEIVED", is_mandatory=True)
    checklist = CandidateChecklist(candidate_id=candidate.candidateID, template_name="Pre-joining", status="active")
    db.add_all([doc, checklist])
    db.commit()
    assert _stage(db, candidate)[1] == ["documents not verified: PAN card", "checklists not completed: Pre-joining"]
    doc.status, checklist.status = "VERIFIED", "completed"
    db.commit()
    assert _stage(db, candidate) == ("BGV", ["background verification not started"])
    db.add(BackgroundVerification(tenant_id=1, candidate_id=candidate.candidateID, offer_letter_id=offer.id,
                                  status="PASSED"))
    db.commit()
    assert _stage(db, candidate) == ("BGV", ["BGV cleared; joins the bench now"])
    db.add(Employee(tenant_id=1, candidate_id=candidate.candidateID, first_name="Lee", last_name="Park",
                    email=f"lee{_uid()}@blitzenx.com", joining_date=date.today(), status="BENCH"))
    db.commit()
    assert _stage(db, candidate) == ("BENCH", ["on the bench, not yet submitted to a client"])
    # every transition was recorded, in order
    pipeline = db.query(HiringPipeline).filter_by(candidate_id=candidate.candidateID).one()
    path = [e.to_stage for e in db.query(HiringPipelineEvent).filter_by(pipeline_id=pipeline.id)
            .order_by(HiringPipelineEvent.id) if e.trigger != "action"]
    assert path == ["SCREEN", "L1", "L2", "OFFER", "ONBOARDING", "BGV", "BENCH"]


def test_thunder_candidates_skip_the_recruiter_screen(db, world, queued):
    candidate = _candidate(db, thunder=True)
    assert _stage(db, candidate)[0] == "L1"


@pytest.mark.parametrize("fact, reason", [
    ("screen", "recruiter screen failed"), ("L1", "L1 interview: No Hire"), ("offer", "candidate declined the offer"),
])
def test_failed_gates_close_the_pipeline(db, world, queued, fact, reason):
    candidate = _candidate(db, thunder=True)
    if fact == "screen":
        hp.record_screen_decision(db, candidate.candidateID, "FAIL", world.UserID)
    elif fact == "L1":
        _round(db, candidate, "L1", "FAIL")
    else:
        _round(db, candidate, "L1", "PASS")
        _round(db, candidate, "L2", "PASS")
        _offer(db, candidate, "Rejected", world)
    pipeline = hp.get_or_create_pipeline(db, candidate.candidateID)
    hp.evaluate(db, pipeline)
    assert (pipeline.stage, pipeline.blockers) == ("REJECTED", [reason]) and pipeline.closed_at is not None


def test_gate_refuses_to_skip_ahead(db, world, queued):
    candidate = _candidate(db, thunder=True)
    with pytest.raises(hp.PipelineGateBlocked) as blocked:
        hp.assert_gate(db, candidate.candidateID, "OFFER")
    assert blocked.value.stage == "L1" and blocked.value.blockers == ["L1 (technical) interview not scheduled"]
    _round(db, candidate, "L1", "PASS")
    _round(db, candidate, "L2", "PASS")
    assert hp.assert_gate(db, candidate.candidateID, "OFFER").stage == "OFFER"


def test_evaluating_twice_changes_nothing_and_actions_run_once(db, world, queued):
    candidate = _candidate(db)
    pipeline = hp.evaluate_and_act(db, candidate.candidateID, "test")
    hp.evaluate_and_act(db, candidate.candidateID, "test")
    events = db.query(HiringPipelineEvent).filter_by(pipeline_id=pipeline.id).count()
    hp.evaluate(db, pipeline)
    assert db.query(HiringPipelineEvent).filter_by(pipeline_id=pipeline.id).count() == events
    actions = [q for q in queued if q[0] == hp.STAGE_ACTION_TASK]
    assert len(actions) == 1 and actions[0][2] == {"pipeline_id": pipeline.id, "stage": "SCREEN"}
    assert hp.run_stage_action(db, pipeline.id, "SCREEN") == "recruiter screen task created"
    assert db.query(Task).filter(Task.candidate_id == candidate.candidateID, Task.category == "HIRING_SCREEN").count() == 1
    # a stale action (pipeline moved on) does nothing
    hp.record_screen_decision(db, candidate.candidateID, "SKIP", world.UserID)
    db.commit()
    assert hp.run_stage_action(db, pipeline.id, "SCREEN").startswith("stale")


def test_existing_employees_are_grandfathered(db, world, queued):
    candidate = _candidate(db)
    db.add(Employee(tenant_id=1, candidate_id=candidate.candidateID, first_name="Old", last_name="Hand",
                    email=f"old{_uid()}@blitzenx.com", joining_date=date(2025, 1, 1), status="ACTIVE"))
    db.commit()
    pipeline = hp.get_or_create_pipeline(db, candidate.candidateID)
    assert pipeline.grandfathered and pipeline.stage == "BENCH"


def test_sweep_backfills_without_creating_tasks(db, world, queued):
    candidate = _candidate(db)
    result = hp.run_pipeline_sweep(db)
    assert result["backfilled"] >= 1
    pipeline = db.query(HiringPipeline).filter_by(candidate_id=candidate.candidateID).one()
    assert pipeline.backfilled and pipeline.stage == "SCREEN"
    assert not [q for q in queued if q[0] == hp.STAGE_ACTION_TASK and q[2]["pipeline_id"] == pipeline.id]


def test_pipeline_api(db, world, queued):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        headers = {"Authorization": "Bearer " + create_access_token(
            {"sub": world.UserID, "type": "user", "tenant_id": 1, "role_template_id": world.role_template_id})}
        candidate = _candidate(db)
        view = client.get(f"/api/v1/hiring-pipeline/candidate/{candidate.candidateID}", headers=headers)
        assert view.status_code == 200 and view.json()["stage"] == "SCREEN"
        screened = client.post(f"/api/v1/hiring-pipeline/candidate/{candidate.candidateID}/screen", headers=headers,
                               json={"decision": "pass"})
        assert screened.status_code == 200 and screened.json()["stage"] == "L1"
        bad = client.post(f"/api/v1/hiring-pipeline/candidate/{candidate.candidateID}/screen", headers=headers,
                          json={"decision": "maybe"})
        assert bad.status_code == 400
        listed = client.get("/api/v1/hiring-pipeline?stage=L1", headers=headers)
        assert candidate.candidateID in [p["candidate_id"] for p in listed.json()["pipelines"]]
        assert client.get("/api/v1/hiring-pipeline/candidate/NOPE", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.clear()

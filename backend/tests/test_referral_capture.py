"""Referral capture: Add Candidate with source "Employee Referral" names the referring
employee; the candidate creation handler saves the referral and links the candidate in the
same transaction; the referral then follows the candidate's pipeline (pending bonus on hire)
and shows on My Referrals."""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import Candidate, CandidateStatus
from app.models.referral import EmployeeReferral, ReferralBonus
from app.models.user import Users
from app.services.employee_referral_service import EmployeeReferralService
from app.services.message_handlers.candidate_creation_unified_handler import CandidateCreationUnifiedHandler
from app.services.message_handlers.candidate_status_change_handler import CandidateStatusChangeHandler
from tests import factories
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


@pytest.fixture
def world(db):
    factories.tenant(db, 1)
    role = full_access_role(db)
    db.add(role)
    db.flush()
    user = Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserName="Rita Recruiter", UserEmail=f"r{uuid.uuid4().hex[:6]}@x.com",
                 UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=role.id,
                 password_reset_required=False)
    db.add(user)
    db.flush()
    referrer = factories.employee(db, first_name="Esha", last_name="Patel", status="ACTIVE", wros_user_id=user.UserID)
    exited = factories.employee(db, first_name="Old", last_name="Timer", status="EXITED")
    factories.tenant(db, 2)
    other_tenant = factories.employee(db, tenant_id=2, first_name="Far", last_name="Away", status="ACTIVE")
    job = factories.job(db)
    db.commit()
    return SimpleNamespace(user=user, referrer=referrer, exited=exited, other_tenant=other_tenant, job=job)


@pytest.fixture
def client(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _form(**extra):
    body = {"candidate_email": f"cand-{uuid.uuid4().hex[:8]}@example.com", "candidate_first_name": "Ravi",
            "candidate_last_name": "Kumar", "candidate_current_location": "Austin, TX, USA",
            "candidate_source": "Employee Referral"}
    body.update(extra)
    return body


def _create_through_handler(db, payload):
    payload = {**payload, "thunder_enabled": False, "tenant_id": 1}
    result = CandidateCreationUnifiedHandler._do_process(SimpleNamespace(id="m1", payload=payload, tenant_id=1), db)
    db.commit()
    return db.get(Candidate, result["candidate_id"])


# --- picker -----------------------------------------------------------------------------

def test_picker_lists_current_employees_of_the_tenant_and_preselects_the_caller(client, world):
    response = client.get("/api/v1/referrals/referrers", headers=_headers(world.user))
    assert response.status_code == 200, response.text
    ids = {e["id"] for e in response.json()["employees"]}
    assert world.referrer.id in ids
    assert world.exited.id not in ids
    assert world.other_tenant.id not in ids
    assert response.json()["self_employee_id"] == world.referrer.id


# --- validation before queueing ---------------------------------------------------------

@pytest.mark.parametrize("extra, message", [
    ({}, "Select the employee"),
    ({"referring_employee_id": "no-such-employee"}, "not a current employee"),
])
def test_an_employee_referral_must_name_a_current_employee(client, world, extra, message):
    with patch("app.services.message_queue_service.MessageQueueService.enqueue") as enqueue:
        response = client.post("/api/v1/candidates/create", headers=_headers(world.user), json=_form(**extra))
    assert response.status_code == 400
    assert message in response.json()["detail"]
    enqueue.assert_not_called()


def test_exited_and_other_tenant_employees_are_refused(client, world):
    for employee in (world.exited, world.other_tenant):
        with patch("app.services.message_queue_service.MessageQueueService.enqueue") as enqueue:
            response = client.post("/api/v1/candidates/create", headers=_headers(world.user),
                                   json=_form(referring_employee_id=employee.id))
        assert response.status_code == 400, employee.first_name
        enqueue.assert_not_called()


def test_the_referrer_and_job_travel_in_the_queued_payload(client, world):
    with patch("app.services.message_queue_service.MessageQueueService.enqueue",
               return_value={"task_id": "t", "message_id": "m"}) as enqueue, \
            patch("app.models.channel_queue.ChannelQueueItem"), \
            patch("app.core.database.SessionLocal"):
        client.post("/api/v1/candidates/create", headers=_headers(world.user),
                    json=_form(referring_employee_id=world.referrer.id, job_id=world.job.jobID))
    payload = enqueue.call_args.kwargs["data"]
    assert payload["referring_employee_id"] == world.referrer.id
    assert payload["referral_job_id"] == world.job.jobID


# --- creation handler -------------------------------------------------------------------

def test_creating_the_candidate_saves_and_links_the_referral(db, world):
    candidate = _create_through_handler(db, {**_form(), "referring_employee_id": world.referrer.id,
                                             "referral_job_id": world.job.jobID})
    referral = db.get(EmployeeReferral, candidate.referral_id)
    assert referral is not None
    assert referral.referring_employee_id == world.referrer.id
    assert referral.referred_candidate_id == candidate.candidateID
    assert referral.job_id == world.job.jobID
    assert referral.referral_status == "PENDING"
    assert candidate.recruitment_source == "EMPLOYEE_REFERRAL"


def test_a_referral_without_a_job_is_saved(db, world):
    candidate = _create_through_handler(db, {**_form(), "referring_employee_id": world.referrer.id})
    assert db.get(EmployeeReferral, candidate.referral_id).job_id is None


def test_a_candidate_without_a_referrer_has_no_referral(db, world):
    candidate = _create_through_handler(db, _form(candidate_source="LinkedIn"))
    assert candidate.referral_id is None


def test_a_bad_referrer_fails_the_message_without_retry(db, world):
    with pytest.raises(ValueError):
        _create_through_handler(db, {**_form(), "referring_employee_id": world.exited.id})


# --- pipeline sync and My Referrals -----------------------------------------------------

def _move(db, candidate, new_status):
    status = db.query(CandidateStatus).filter_by(candidateID=candidate.candidateID).first()
    old = status.piplineStatus
    status.piplineStatus = new_status
    db.commit()
    message = SimpleNamespace(id="s1", payload={"candidate_id": candidate.candidateID,
                                                "old_status": old, "new_status": new_status})
    with patch("app.services.candidate_status_notifications.send_status_email", return_value={}):
        return CandidateStatusChangeHandler.process(message, db)


def test_the_referral_follows_the_pipeline_and_a_hire_creates_one_pending_bonus(db, world):
    candidate = _create_through_handler(db, {**_form(), "referring_employee_id": world.referrer.id})
    for pipeline, expected in [("Interview", "INTERVIEW_SCHEDULED"), ("OfferApproval", "OFFERED"), ("Hired", "HIRED")]:
        _move(db, candidate, pipeline)
        assert db.get(EmployeeReferral, candidate.referral_id).referral_status == expected, pipeline
    _move(db, candidate, "Onboarded")  # still HIRED: no second bonus
    bonuses = db.query(ReferralBonus).filter_by(referral_id=candidate.referral_id).all()
    assert len(bonuses) == 1 and bonuses[0].payment_status == "PENDING"


def test_a_paid_bonus_is_final(db, world):
    candidate = _create_through_handler(db, {**_form(), "referring_employee_id": world.referrer.id})
    referral = db.get(EmployeeReferral, candidate.referral_id)
    referral.referral_status = "BONUS_PAID"
    db.commit()
    assert EmployeeReferralService.sync_with_pipeline_status(db, candidate, "Rejected") is None
    assert db.get(EmployeeReferral, candidate.referral_id).referral_status == "BONUS_PAID"


def test_my_referrals_returns_the_fields_the_screen_shows(client, db, world):
    _create_through_handler(db, {**_form(), "referring_employee_id": world.referrer.id,
                                 "referral_job_id": world.job.jobID})
    response = client.get("/api/v1/referrals/referrals/all", headers=_headers(world.user))
    assert response.status_code == 200, response.text
    body = response.json()
    mine = [r for r in body["referrals"] if r["referring_employee_id"] == world.referrer.id]
    assert len(mine) == 1
    row = mine[0]
    assert row["referred_candidate_name"] == "Ravi Kumar"
    assert row["referred_candidate_email"].startswith("cand-")
    assert row["referring_employee_name"] == "Esha Patel"
    assert row["job_title"] == world.job.jobTitle
    assert row["referral_status"] == "PENDING"
    assert row["referral_bonus_amount"] > 0
    assert body["total_potential_bonus"] >= row["referral_bonus_amount"]

"""Employment type by the candidate's country (CEO 2026-10-15): one canonical set of types
(FULLTIME, CONTRACT, C2C, 1099, UNKNOWN) with country labels; India and the US accept FULLTIME and
CONTRACT ("W2 ..." in the US), C2C and 1099 never; UNKNOWN (type or country) may interview but
fails closed at client submission. Enforced at every step: interview selection (ranking, panel,
interview, rehire approval), joining a job, the hiring pipeline, the offer and client submission."""
import json
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import Candidate
from app.models.tenant import Tenant
from app.models.user import InterviewPanel, Jobs, Users
from app.services import employment_type_policy as policy
from app.services.submission_service import check_employment_type_rule
from tests.hiring_fixtures import full_access_role


def _uid():
    return uuid.uuid4().hex[:8]


def _cand(employment_type, country=None, **extra):
    return Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"{_uid()}@example.com", candidatePassword="x",
                     employment_type=employment_type, country=country, **extra)


# --------------------------------------------------------------------------- the rule

@pytest.mark.parametrize("country", ["IN", "US"])
@pytest.mark.parametrize("employment_type", ["FULLTIME", "CONTRACT"])
def test_india_and_the_us_accept_fulltime_and_contract(country, employment_type):
    candidate = _cand(employment_type, country)
    assert check_employment_type_rule(candidate)["allowed"]
    assert policy.interview_check(candidate)["allowed"]


@pytest.mark.parametrize("country", ["IN", "US", None])
@pytest.mark.parametrize("employment_type", ["C2C", "1099"])
def test_c2c_and_1099_are_never_accepted(country, employment_type):
    candidate = _cand(employment_type, country)
    submission = check_employment_type_rule(candidate)
    assert not submission["allowed"] and submission["error"] == "C2C_NOT_ACCEPTED"
    assert not policy.interview_check(candidate)["allowed"]


def test_unknown_type_may_interview_but_is_never_submitted():
    candidate = _cand("UNKNOWN", "IN")
    assert policy.interview_check(candidate)["allowed"]
    result = check_employment_type_rule(candidate)
    assert not result["allowed"] and "Full-time or Contract" in result["message"]


def test_unknown_country_may_interview_but_fails_closed_at_submission():
    for country in (None, "GB"):  # not recorded / not a country we hire in
        candidate = _cand("FULLTIME", country)
        assert policy.interview_check(candidate)["allowed"]
        result = check_employment_type_rule(candidate)
        assert not result["allowed"] and "country" in result["message"]


def test_labels_are_per_country_and_the_message_names_no_company():
    assert policy.label("FULLTIME", "US") == "W2 full-time" and policy.label("CONTRACT", "US") == "W2 contract"
    assert policy.label("FULLTIME", "IN") == "Full-time" and policy.label("C2C", "US") == "Corp-to-corp (C2C)"
    message = check_employment_type_rule(_cand("C2C", "US"))["message"]
    assert message == ("Only W2 full-time or W2 contract candidates are accepted in United States; "
                       "this candidate is Corp-to-corp (C2C).")
    assert [o["value"] for o in policy.options("US")][:2] == ["FULLTIME", "CONTRACT"]
    assert [o["accepted"] for o in policy.options("IN")] == [True, True, False, False, False]


def test_country_comes_from_codes_names_and_free_text_locations():
    assert policy.country_code("Pune, Maharashtra, India") == "IN"
    assert policy.country_code("Austin, Texas, United States") == "US"
    assert policy.country_code("us") == "US" and policy.country_code("IN") == "IN"
    assert policy.country_code("London, United Kingdom") is None and policy.country_code("") is None


def test_the_policy_can_never_accept_c2c_1099_or_unknown():
    labels = {"FULLTIME": "a", "CONTRACT": "b", "C2C": "c", "1099": "d", "UNKNOWN": "e"}
    for bad in ("C2C", "1099", "UNKNOWN", "W2_FULLTIME"):
        raw = json.dumps({"labels": labels, "countries": {"US": {"accepts": {bad: "x"}}}})
        with pytest.raises(policy.EmploymentTypePolicyError):
            policy._parse(raw)
    with pytest.raises(policy.EmploymentTypePolicyError):
        policy._parse(json.dumps({"labels": labels, "countries": {"usa": {"accepts": {}}}}))


# --------------------------------------------------------------------------- every step

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
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    user = Users(UserID=f"U-{_uid()}", UserName="Recruiter", UserEmail=f"r{_uid()}@blitzenx.com", UserPassword="x",
                 UserRole="admin", tenant_id=1, role_template_id=full_access_role(db).id,
                 password_reset_required=False)
    candidate = _cand("C2C", "US", tenant_id=1, total_experience_months=80, candidateFirstName="Lee")
    job = Jobs(tenant_id=1, jobTitle="Engineer", jobDescription="d", jobSkills="Java", jobExperience="5",
               jobLocation="Remote", jobStatus="active")
    db.add_all([user, candidate, job])
    db.commit()
    return SimpleNamespace(user=user, candidate=candidate, job=job)


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True), \
            patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}):
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_a_c2c_candidate_gets_no_interview_round(db, world):
    from app.services.interview_scheduling_service import create_panel, schedule_interview

    with pytest.raises(HTTPException) as exc:
        create_panel(db, world.user, candidate_id=world.candidate.candidateID, job_id=None, round_name="L1")
    assert exc.value.status_code == 400 and "Corp-to-corp (C2C)" in exc.value.detail
    panel = InterviewPanel(candidate_id=world.candidate.candidateID, round_name="L1")  # made before the type was known
    db.add(panel)
    db.flush()
    start = datetime.utcnow() + timedelta(days=1)
    with pytest.raises(HTTPException):
        schedule_interview(db, world.user, panel_id=panel.id, candidate_id=world.candidate.candidateID,
                           start=start, end=start + timedelta(hours=1))


def test_an_unknown_type_is_interviewed(db, world):
    from app.services.interview_scheduling_service import create_panel

    world.candidate.employment_type, world.candidate.country = "UNKNOWN", None
    created = create_panel(db, world.user, candidate_id=world.candidate.candidateID, job_id=None, round_name="L1")
    assert created.panel.id is not None


def test_a_c2c_candidate_cannot_join_a_job_pipeline(api, world):
    response = api.post(f"/api/v1/jobs/{world.job.jobID}/applications/{world.candidate.candidateID}",
                        headers=_headers(world.user), json={})
    assert response.status_code == 422 and "Corp-to-corp (C2C)" in response.text, response.text


def test_the_rehire_approval_and_the_pipeline_apply_the_rule(db, world):
    from app.models.interview_rehire_review import InterviewRehireReview
    from app.services.employment_type_policy import EmploymentTypeNotAccepted
    from app.services.hiring_pipeline_service import evaluate, get_or_create_pipeline
    from app.services.interview_rehire_guard_service import decide_rehire_review

    review = InterviewRehireReview(candidate_id=world.candidate.candidateID, round_name="L1",
                                   justification="new evidence", status="PENDING_HM_APPROVAL")
    db.add(review)
    db.commit()
    with pytest.raises(EmploymentTypeNotAccepted):
        decide_rehire_review(db, review.id, "approve", world.user.UserID)
    db.rollback()

    pipeline = get_or_create_pipeline(db, world.candidate.candidateID)
    pipeline.screen_required = False
    db.flush()
    evaluate(db, pipeline, trigger="test")
    assert pipeline.stage in ("SCREEN", "L1") and pipeline.stage != "L2"


def test_the_offer_is_blocked_for_c2c(db, world):
    from app.services.offer_readiness_service import check_offer_readiness

    result = check_offer_readiness(db, world.candidate.candidateID, world.job.jobID, "1")
    assert not result["is_ready"]
    assert any("Corp-to-corp (C2C)" in b for b in result["blockers"])


def test_the_profile_records_country_and_type_and_the_picker_lists_options(api, db, world):
    picker = api.get("/api/v1/candidates/employment-types", headers=_headers(world.user))
    assert picker.status_code == 200, picker.text
    us = next(c for c in picker.json()["countries"] if c["code"] == "US")
    assert us["options"][0] == {"value": "FULLTIME", "label": "W2 full-time", "accepted": True}

    url = f"/api/v1/candidates/hr/update_candidate/{world.candidate.candidateID}"
    updated = api.put(url, headers=_headers(world.user), json={"candidate_country": "in", "employment_type": "CONTRACT"})
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert (body["candidate_country"], body["employment_type"], body["employment_type_label"]) == \
        ("IN", "CONTRACT", "Contract")
    assert api.put(url, headers=_headers(world.user), json={"employment_type": "W2_FULLTIME"}).status_code == 400
    assert api.put(url, headers=_headers(world.user), json={"candidate_country": "India"}).status_code == 400
    moved = api.put(url, headers=_headers(world.user),
                    json={"candidate_current_location": "Austin, Texas, United States"})
    assert moved.json()["candidate_country"] == "US" and moved.json()["employment_type_label"] == "W2 contract"


def test_db_contract_moves_w2_fulltime_to_fulltime_and_derives_country(db, world):
    from app.core.db_contract import _initialize_employment_types

    # production's table as it stands before the change: VARCHAR(11), W2_FULLTIME allowed
    db.execute(text("ALTER TABLE app_schema.candidates DROP CONSTRAINT IF EXISTS candidate_employment_type"))
    db.execute(text("ALTER TABLE app_schema.candidates ALTER COLUMN employment_type TYPE VARCHAR(11)"))
    legacy = _cand("UNKNOWN", None, tenant_id=1, candidateCurrentLocation="Chennai, Tamil Nadu, India")
    db.add(legacy)
    db.flush()
    db.execute(text("UPDATE app_schema.candidates SET employment_type = 'W2_FULLTIME' WHERE \"candidateID\" = :id"),
               {"id": legacy.candidateID})
    _initialize_employment_types(db)
    _initialize_employment_types(db)  # idempotent
    db.expire_all()
    row = db.get(Candidate, legacy.candidateID)
    assert (row.employment_type, row.country) == ("FULLTIME", "IN")
    # a rolled-back previous release still writes W2_FULLTIME: the database accepts it ...
    db.execute(text("UPDATE app_schema.candidates SET employment_type = 'W2_FULLTIME' "
                    "WHERE \"candidateID\" = :id"), {"id": legacy.candidateID})
    # ... and the next startup converts it again
    _initialize_employment_types(db)
    db.expire_all()
    assert db.get(Candidate, legacy.candidateID).employment_type == "FULLTIME"
    # anything outside the canonical set (plus that one legacy value) is still refused
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(text("UPDATE app_schema.candidates SET employment_type = 'BOGUS' "
                            "WHERE \"candidateID\" = :id"), {"id": legacy.candidateID})

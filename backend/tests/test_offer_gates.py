"""Offers follow the hiring order: no offer is created, generated or released until the
screen, L1 and L2 rounds have passed. Release no longer depends on client-submission
interview rows (nothing wrote them, so every release returned 409). Accepting the offer
moves the candidate into onboarding."""
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.tenant import Tenant
from app.models.user import InterviewPanel, Users
from app.services import hiring_pipeline_service as hp
from tests.hiring_fixtures import full_access_role


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
def client(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True), \
            patch("app.services.offer_release_notification_service.send_offer_release_notification"), \
            patch("app.services.email_service.EmailService.notify_hr_candidate_responded"):
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = full_access_role(db)
    db.add(role)
    db.flush()
    hr = Users(UserID=f"HR-{_uid()}", UserName="HR", UserEmail=f"hr{_uid()}@blitzenx.com", UserPassword="x",
               UserRole="admin", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Kim", candidateLastName="Ode", tenant_id=1, thunder_enabled=True,
                          total_experience_months=84)
    db.add_all([hr, candidate])
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Interview",
                           thunder_assigned_at=datetime.utcnow()))
    db.commit()
    return hr, candidate


def _headers(subject, kind="user", role_template_id=None):
    claims = {"sub": subject, "type": kind, "tenant_id": 1}
    if role_template_id:
        claims["role_template_id"] = role_template_id
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _pass(db, candidate, *levels):
    for level in levels:
        panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=level)
        db.add(panel)
        db.flush()
        db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                     verdict="PASS", source="MANUAL"))
    db.commit()


def _create(client, hr, candidate):
    return client.post("/api/v1/offer-letter/create", headers=_headers(hr.UserID, role_template_id=hr.role_template_id),
                       json={"candidate_id": candidate.candidateID, "position": "Engineer", "salary": "1800000",
                             "joining_date": (date.today() + timedelta(days=20)).isoformat(),
                             "offer_expire_date": (date.today() + timedelta(days=7)).isoformat()})


def test_no_offer_before_l2_passes(client, db, world):
    hr, candidate = world
    blocked = _create(client, hr, candidate)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["blockers"] == ["L1 (technical) interview not scheduled"]
    _pass(db, candidate, "L1")
    assert _create(client, hr, candidate).json()["detail"]["blockers"] == ["L2 (management) interview not scheduled"]
    _pass(db, candidate, "L2")
    created = _create(client, hr, candidate)
    assert created.status_code == 200, created.text


def test_release_needs_verdicts_not_a_client_submission_and_acceptance_starts_onboarding(client, db, world):
    hr, candidate = world
    _pass(db, candidate, "L1", "L2")
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1800000",
                        joining_date=date.today() + timedelta(days=20), offer_expire_date=date.today() + timedelta(days=7),
                        offer_status="Approved", approval_status="Approved", created_by=hr.UserID)
    db.add(offer)
    db.commit()
    released = client.post(f"/api/v1/offer-letter/release/{offer.id}",
                           headers=_headers(hr.UserID, role_template_id=hr.role_template_id))
    assert released.status_code == 200, released.text
    accepted = client.post(f"/api/v1/portal/offers/{offer.id}/respond", headers=_headers(candidate.candidateID, "candidate"),
                           json={"action": "accept"})
    assert accepted.status_code == 200, accepted.text
    pipeline = hp.evaluate_and_act(db, candidate.candidateID, "offer")
    assert pipeline.stage == "ONBOARDING"


def test_release_is_blocked_for_a_candidate_who_failed_l2(client, db, world):
    hr, candidate = world
    _pass(db, candidate, "L1")
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="L2")
    db.add(panel)
    db.flush()
    db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level="L2", verdict="FAIL",
                                 source="MANUAL"))
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1", joining_date=date.today(),
                        offer_expire_date=date.today(), offer_status="Approved", approval_status="Approved",
                        created_by=hr.UserID)
    db.add(offer)
    db.commit()
    response = client.post(f"/api/v1/offer-letter/release/{offer.id}",
                           headers=_headers(hr.UserID, role_template_id=hr.role_template_id))
    assert response.status_code == 409 and response.json()["detail"]["blockers"] == ["L2 interview: No Hire"]


def test_five_year_rule_blocks_offer_create_and_release_even_after_rounds_passed(client, db, world):
    """CEO: the 5-year rule is enforced at every step -- a record corrected after the
    interviews (or rounds entered first) is still stopped at offer create and at release."""
    hr, candidate = world
    _pass(db, candidate, "L1", "L2")
    candidate.total_experience_months = 48
    db.commit()
    blocked = _create(client, hr, candidate)
    assert blocked.status_code == 409 and "5-year rule" in blocked.json()["detail"]["blockers"][0]
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1800000",
                        joining_date=date.today() + timedelta(days=20), offer_expire_date=date.today() + timedelta(days=7),
                        offer_status="Approved", approval_status="Approved", created_by=hr.UserID)
    db.add(offer)
    db.commit()
    released = client.post(f"/api/v1/offer-letter/release/{offer.id}",
                           headers=_headers(hr.UserID, role_template_id=hr.role_template_id))
    assert released.status_code == 409
    assert any("5-year experience requirement" in b for b in released.json()["detail"]["blockers"])

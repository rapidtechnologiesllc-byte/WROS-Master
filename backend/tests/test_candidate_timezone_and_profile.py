"""A candidate's timezone follows their location (Thunder emails in the candidate's working hours),
skills saved only as a comma list show on the profile, and the profile can read Thunder's status."""
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.db_contract import _candidate_timezones_from_location
from app.core.security import create_access_token
from app.models.candidate import Candidate
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.candidate_timezone import timezone_for_location
from tests.hiring_fixtures import full_access_role


@pytest.mark.parametrize("location, zone", [
    ("Chicago, Illinois, United States", "America/Chicago"),
    ("Seattle, WA, USA", "America/Los_Angeles"),
    ("Washington, DC, United States", "America/New_York"),
    ("Toronto, Ontario, Canada", "America/Toronto"),
    ("London, Ontario, Canada", "America/Toronto"),
    ("Pune, Maharashtra, India", "Asia/Kolkata"),
    ("London, United Kingdom", "Europe/London"),
    ("Sydney, NSW, Australia", "Australia/Sydney"),
    ("Chicago", "America/Chicago"),
    ("Indore, IN", None),  # "IN" is India or Indiana: says nothing usable on its own
    ("Remote", None),
    ("", None),
    (None, None),
])
def test_timezone_from_location(location, zone):
    assert timezone_for_location(location) == zone


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _candidate(db, **fields):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                          candidateEmail=f"c{uuid.uuid4().hex[:8]}@example.com", candidateFirstName="Joss", **fields)
    db.add(candidate)
    db.flush()
    return candidate


def test_a_new_candidate_gets_the_timezone_of_their_location(db):
    assert _candidate(db, candidateCurrentLocation="Chicago, Illinois, United States").timezone == "America/Chicago"
    assert _candidate(db, candidateCurrentLocation="Remote").timezone == "Asia/Kolkata"  # default kept


def test_a_new_location_moves_the_timezone_unless_it_was_set_with_it(db):
    candidate = _candidate(db, candidateCurrentLocation="Pune, Maharashtra, India")
    candidate.candidateCurrentLocation = "Austin, Texas, United States"
    db.flush()
    assert candidate.timezone == "America/Chicago"
    candidate.candidateCurrentLocation, candidate.timezone = "Denver, Colorado, United States", "America/Phoenix"
    db.flush()
    assert candidate.timezone == "America/Phoenix"


def test_existing_candidates_get_the_timezone_of_their_location_once(db):
    candidate = _candidate(db, candidateCurrentLocation="Chicago, Illinois, United States")
    db.query(Candidate).filter_by(candidateID=candidate.candidateID).update({"timezone": "Asia/Kolkata"})
    db.expire_all()
    assert _candidate_timezones_from_location(db) >= 1
    db.refresh(candidate)
    assert candidate.timezone == "America/Chicago"


@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(db):
    user = Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserName="Recruiter", UserEmail=f"r{uuid.uuid4().hex[:8]}@blitzenx.com",
                 UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=full_access_role(db).id,
                 password_reset_required=False)
    db.add(user)
    db.commit()
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def test_skills_saved_only_as_a_list_show_on_the_profile(api, db):
    candidate = _candidate(db, candidateSkills="Java, Go, Java, sql queries, ")
    db.commit()
    response = api.get(f"/api/v1/candidates/{candidate.candidateID}", headers=_headers(db))
    assert response.status_code == 200, response.text
    assert [s["name"] for s in response.json()["profile_skills"]] == ["Java", "Go", "sql queries"]


def test_the_profile_reads_thunder_status(api, db):
    candidate = _candidate(db, candidateCurrentLocation="Chicago, Illinois, United States")
    db.commit()
    response = api.get(f"/api/v1/candidates/{candidate.candidateID}/thunder-status", headers=_headers(db))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enrolled"] is False and body["stage_label"] == "Not contacted yet" and body["last_email_at"] is None
    assert any(label.startswith("Your latest resume") for label in body["missing_fields"])

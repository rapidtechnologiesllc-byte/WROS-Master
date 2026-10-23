"""Archive / Unarchive a candidate (account status Inactive / Active): an archived candidate
gets no outreach, and both actions are recorded on the candidate's History."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.user import Users
from app.services.candidate_contact_policy import is_archived, is_contactable
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
def client(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


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
    candidate = factories.candidate(db, candidateEmail=f"real-{uuid.uuid4().hex[:6]}@example.com", thunder_enabled=True)
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Applied"))
    db.commit()
    return user, candidate


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _set(client, user, candidate, status):
    response = client.put(f"/api/v1/status/{candidate.candidateID}", headers=_headers(user), json={"status": status})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"


def _history(db, candidate):
    return [h.event_type for h in db.query(CandidateHistory).filter_by(candidateID=candidate.candidateID)
            .order_by(CandidateHistory.id).all()]


def test_archiving_stops_outreach_and_is_recorded(client, db, world):
    user, candidate = world
    assert is_contactable(db, candidate)[0]

    _set(client, user, candidate, "Inactive")
    assert is_archived(db, candidate.candidateID)
    assert is_contactable(db, candidate) == (False, "candidate archived")
    assert _history(db, candidate)[-1] == "Archived"


def test_unarchiving_allows_outreach_again(client, db, world):
    user, candidate = world
    _set(client, user, candidate, "Inactive")
    _set(client, user, candidate, "Active")
    assert not is_archived(db, candidate.candidateID)
    assert is_contactable(db, candidate)[0]
    assert _history(db, candidate)[-2:] == ["Archived", "Unarchived"]


def test_setting_the_same_status_again_adds_no_history(client, db, world):
    user, candidate = world
    _set(client, user, candidate, "Inactive")
    _set(client, user, candidate, "Inactive")
    assert _history(db, candidate).count("Archived") == 1

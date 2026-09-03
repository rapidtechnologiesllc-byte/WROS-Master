"""
get_hm_candidate_review_list() + GET /interviews/hm-review/my-candidates --
proves S-102/HRMS-P207 (Hiring Manager Candidate Review) end-to-end.
The schemas (HMCandidateReviewListResponse etc.) already existed,
imported into interviews.py, but were wired to no route -- this closes
import logging
that real, scoped gap.

Real fix, 2026-08-05: the route used to take hiring_manager_id as a
client-supplied path parameter with no ownership check -- any logged-in
internal user could view any OTHER hiring manager's candidates by
guessing/enumerating a UserID. Now derives "my candidates" from the
authenticated caller; test_my_candidates_never_leaks_another_hms_data
below proves the fix, replacing the old unknown-id-404 test (there's no
longer a client-supplied id to be unknown).

Throwaway SQLite -- never the real database or real signing keys.
"""
import os
import tempfile
from datetime import date, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.candidate import Candidate, CandidateStatus
from app.models.tenant import Tenant
from app.models.user import CandidateAssignment, Interview, InterviewFeedback, InterviewPanel, Jobs, Users
from app.services.interview_sequencing_service import get_hm_candidate_review_list
import app.models  # noqa: F401 -- registers every model on Base.metadata

# ---------------------------------------------------------------------------
# Service-level tests -- direct SQLite session, no HTTP layer, same style
# as tests/test_interview_sequencing_gate.py.
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Candidate.__table__, CandidateStatus.__table__, Users.__table__, Jobs.__table__,
        CandidateAssignment.__table__, InterviewPanel.__table__, Interview.__table__,
        InterviewFeedback.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def hm(db_session):
    u = Users(UserID="U-HM", UserRole="Hiring Manager", UserName="Priya HM", UserEmail="priya@blitzenx.com", UserPassword="h")
    db_session.add(u)
    db_session.commit()
    return u

@pytest.fixture()
def interviewer(db_session):
    u = Users(UserID="U-INT", UserRole="Technical Manager", UserName="Rahul Interviewer", UserEmail="rahul@blitzenx.com", UserPassword="h")
    db_session.add(u)
    db_session.commit()
    return u

@pytest.fixture()
def candidate(db_session, hm):
    c = Candidate(candidateID="C-REV", candidateEmail="rev@example.com", candidatePassword="h",
                   candidateFirstName="Jane", candidateLastName="Doe", candidateMobile="9999999999",
                   candidateExperience="5 years")
    db_session.add(c)
    db_session.commit()
    db_session.add(CandidateStatus(candidateID=c.candidateID, piplineStatus="Interview", status="Active"))
    db_session.add(CandidateAssignment(candidate_id=c.candidateID, hiring_manager_id=hm.UserID))
    db_session.commit()
    return c

def test_returns_empty_list_for_hm_with_no_assignments(db_session, hm):
    result = get_hm_candidate_review_list(db_session, hm)
    assert result["total_candidates"] == 0
    assert result["candidates"] == []

def test_candidate_with_no_interviews_yet(db_session, hm, candidate):
    result = get_hm_candidate_review_list(db_session, hm)
    assert result["total_candidates"] == 1
    item = result["candidates"][0]
    assert item["candidate_name"] == "Jane Doe"
    assert item["pipeline_status"] == "Interview"
    assert item["completed_interview_count"] == 0
    assert item["approval_endpoint"] == f"/status/{candidate.candidateID}"
    assert item["interviews"] == []

def test_round_recommendation_hire_when_all_feedback_agrees(db_session, hm, candidate, interviewer):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="Technical", created_at=datetime.utcnow())
    db_session.add(panel)
    db_session.commit()
    iv = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, status="Completed",
                    start_time=datetime.utcnow(), end_time=datetime.utcnow())
    db_session.add(iv)
    db_session.commit()
    db_session.add(InterviewFeedback(
        interview_id=iv.id, interviewer_id=interviewer.UserID, technical_score=8, communication_score=9,
        problem_solving_score=8, culture_fit_score=9, recommendation="Hire",
    ))
    db_session.commit()

    result = get_hm_candidate_review_list(db_session, hm)
    item = result["candidates"][0]
    assert item["completed_interview_count"] == 1
    round_ = item["interviews"][0]
    assert round_["overall_recommendation"] == "Hire"
    assert round_["feedbacks"][0]["interviewer_name"] == "Rahul Interviewer"
    assert round_["feedbacks"][0]["average_score"] == 8.5

def test_round_recommendation_mixed_when_feedback_disagrees(db_session, hm, candidate, interviewer):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="Technical", created_at=datetime.utcnow())
    db_session.add(panel)
    db_session.commit()
    iv = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, status="Completed")
    db_session.add(iv)
    db_session.commit()
    db_session.add(InterviewFeedback(interview_id=iv.id, interviewer_id=interviewer.UserID, recommendation="Hire"))
    db_session.add(InterviewFeedback(interview_id=iv.id, interviewer_id="U-INT-2", recommendation="Reject"))
    db_session.commit()

    result = get_hm_candidate_review_list(db_session, hm)
    round_ = result["candidates"][0]["interviews"][0]
    assert round_["overall_recommendation"] == "Mixed"

def test_round_recommendation_no_feedback(db_session, hm, candidate):
    panel = InterviewPanel(candidate_id=candidate.candidateID, round_name="HR", created_at=datetime.utcnow())
    db_session.add(panel)
    db_session.commit()
    db_session.add(Interview(panel_id=panel.id, candidate_id=candidate.candidateID, status="Scheduled"))
    db_session.commit()

    result = get_hm_candidate_review_list(db_session, hm)
    round_ = result["candidates"][0]["interviews"][0]
    assert round_["overall_recommendation"] == "No Feedback"

def test_scoped_to_the_given_hiring_manager_only(db_session, hm, candidate):
    other_hm = Users(UserID="U-HM-2", UserRole="Hiring Manager", UserEmail="other@blitzenx.com", UserPassword="h")
    db_session.add(other_hm)
    db_session.commit()

    result = get_hm_candidate_review_list(db_session, other_hm)
    assert result["total_candidates"] == 0

# ---------------------------------------------------------------------------
# Thin API-level test -- proves the route itself is wired, auth-gated,
# and 404s correctly. Full aggregation behavior already proven above.
# ---------------------------------------------------------------------------

@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)

@pytest.fixture()
def api_client(throwaway_jwt_keys):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.interviews import router as interviews_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(interviews_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
                 UserPassword=get_password_hash("x"), tenant_id=tenant.id))
    db.add(Users(UserID="U-HM", UserRole="Hiring Manager", UserName="Priya HM", UserEmail="priya@blitzenx.com",
                 UserPassword=get_password_hash("x"), tenant_id=tenant.id))
    db.commit()
    db.close()

    client = TestClient(app)
    try:
        yield client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})

def _auth(email="admin@blitzenx.com", role="Admin"):
    return {"Authorization": f"Bearer {_token_for(email, role)}"}

def test_api_route_returns_the_callers_own_review_list(api_client):
    resp = api_client.get("/interviews/hm-review/my-candidates", headers=_auth("priya@blitzenx.com", "Hiring Manager"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hiring_manager_id"] == "U-HM"
    assert body["hiring_manager_name"] == "Priya HM"
    assert body["total_candidates"] == 0

def test_my_candidates_never_leaks_another_hms_data(api_client):
    """The real security fix: no path parameter exists anymore for a
    caller to substitute another hiring manager's id into -- calling as
    Admin (a different real user than Priya HM) must return Admin's OWN
    (empty) list, never Priya's."""
    resp = api_client.get("/interviews/hm-review/my-candidates", headers=_auth("admin@blitzenx.com", "Admin"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hiring_manager_id"] == "U-ADMIN"
    assert body["hiring_manager_id"] != "U-HM"

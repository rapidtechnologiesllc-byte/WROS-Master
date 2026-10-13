"""Interview rounds decide the candidate's path from interviewer feedback:
any No Hire fails the round (candidate rejected, rehire guard armed), all Hire / Must Hire
passes it, mixed feedback goes to the hiring manager. L2 (management) needs an L1
(technical) pass, and passing L2 is what sends the candidate on for approval."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.tenant import Tenant
from app.models.user import Interview, PanelMember, Users
from app.services.interview_rehire_guard_service import candidate_has_past_no_hire
from app.services.interview_verdict_service import infer_level
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
    with patch("app.services.email_service.EmailService.send_notification"), \
            patch("app.api.v1.endpoints.interviews._notify_feedback_submitted"), \
            patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
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
    users = [Users(UserID=f"U-{_uid()}", UserName=f"Interviewer {i}", UserEmail=f"i{_uid()}@blitzenx.com",
                   UserPassword="x", UserRole="admin", tenant_id=1, role_template_id=role.id,
                   password_reset_required=False) for i in range(2)]
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"c{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Ana", candidateLastName="Ruiz", tenant_id=1,
                          total_experience_months=72)
    db.add_all(users + [candidate])
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Interview"))
    db.commit()
    return users, candidate


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _panel(client, users, candidate, round_name, level=None):
    body = {"candidate_id": candidate.candidateID, "round_name": round_name}
    if level:
        body["level"] = level
    return client.post("/api/v1/interviews/panels/create", headers=_headers(users[0]), json=body)


def _run_round(client, db, users, candidate, panel_id, recommendations):
    """Two interviewers sit the round and each submits feedback; the last one completes it."""
    interview = Interview(panel_id=panel_id, candidate_id=candidate.candidateID, status="Scheduled",
                          start_time=datetime.utcnow() - timedelta(hours=2), end_time=datetime.utcnow() - timedelta(hours=1))
    db.add(interview)
    db.add_all([PanelMember(panel_id=panel_id, interviewer_id=u.UserID) for u in users[:len(recommendations)]])
    db.commit()
    for user, recommendation in zip(users, recommendations):
        response = client.post("/api/v1/interviews/feedback/submit", headers=_headers(user), json={
            "interview_id": interview.id, "interviewer_id": user.UserID, "technical_score": 4,
            "communication_score": 4, "problem_solving_score": 4, "culture_fit_score": 4,
            "comments": "ok", "recommendation": recommendation})
        assert response.status_code == 201, response.text
    db.expire_all()
    return db.query(InterviewRoundVerdict).filter_by(panel_id=panel_id).one()


def _pipeline(db, candidate):
    db.expire_all()
    return db.query(CandidateStatus).filter_by(candidateID=candidate.candidateID).one().piplineStatus


def test_round_levels_are_inferred_from_names():
    assert [infer_level(n) for n in ["HR Screen", "Technical", "L1", "Level 2", "Managerial", "HM round", "Culture"]] == \
        ["SCREEN", "L1", "L1", "L2", "L2", "L2", "OTHER"]


def test_no_hire_fails_the_round_rejects_and_arms_the_rehire_guard(client, db, world):
    users, candidate = world
    panel = _panel(client, users, candidate, "Technical").json()
    assert panel["level"] == "L1" and panel["verdict"] == "PENDING"
    verdict = _run_round(client, db, users, candidate, panel["id"], ["Must Hire", "No Hire"])
    assert verdict.verdict == "FAIL"
    assert _pipeline(db, candidate) == "Rejected"
    assert candidate_has_past_no_hire(db, candidate.candidateID)


def test_l1_then_l2_pass_sends_candidate_for_approval(client, db, world):
    users, candidate = world
    l1 = _panel(client, users, candidate, "Technical").json()
    # L2 can't be scheduled while L1 is undecided
    assert _panel(client, users, candidate, "Managerial").status_code == 400
    assert _run_round(client, db, users, candidate, l1["id"], ["Must Hire", "Hire"]).verdict == "PASS"
    assert _pipeline(db, candidate) == "Interview"  # an L1 pass alone doesn't promote
    l2 = _panel(client, users, candidate, "Managerial")
    assert l2.status_code == 201, l2.text
    assert _run_round(client, db, users, candidate, l2.json()["id"], ["Hire", "Hire"]).verdict == "PASS"
    assert _pipeline(db, candidate) == "Pre-onboarding-Approval"


def test_l2_needs_an_l1_pass_even_as_the_first_round(client, world):
    users, candidate = world
    response = _panel(client, users, candidate, "Final", level="L2")
    assert response.status_code == 400 and "L1" in response.json()["detail"]


def test_mixed_feedback_goes_to_the_hiring_manager(client, db, world):
    users, candidate = world
    panel = _panel(client, users, candidate, "Technical").json()
    assert _run_round(client, db, users, candidate, panel["id"], ["Hire", "Average"]).verdict == "NEEDS_DECISION"
    assert _pipeline(db, candidate) == "Interview"
    decided = client.post(f"/api/v1/interviews/panels/{panel['id']}/verdict", headers=_headers(users[0]),
                          json={"verdict": "PASS", "rationale": "Strong on system design"})
    assert decided.status_code == 200 and decided.json()["source"] == "MANUAL"
    # overturning a decided round needs a reason
    flip = client.post(f"/api/v1/interviews/panels/{panel['id']}/verdict", headers=_headers(users[0]),
                       json={"verdict": "FAIL"})
    assert flip.status_code == 400
    listed = client.get(f"/api/v1/interviews/candidates/{candidate.candidateID}/verdicts", headers=_headers(users[0]))
    assert [(v["level"], v["verdict"]) for v in listed.json()] == [("L1", "PASS")]


def test_round_level_can_be_corrected(client, db, world):
    users, candidate = world
    panel = _panel(client, users, candidate, "Round A").json()
    assert panel["level"] == "OTHER"
    fixed = client.put(f"/api/v1/interviews/panels/{panel['id']}/level", headers=_headers(users[0]), json={"level": "l1"})
    assert fixed.status_code == 200 and fixed.json()["level"] == "L1"
    bad = client.put(f"/api/v1/interviews/panels/{panel['id']}/level", headers=_headers(users[0]), json={"level": "L9"})
    assert bad.status_code == 400


@pytest.mark.parametrize("months", [59, None])
def test_no_interview_under_five_years_experience(client, db, world, months):
    users, candidate = world
    candidate.total_experience_months = months
    db.commit()
    response = _panel(client, users, candidate, "L1 Technical")
    assert response.status_code == 400 and "Cannot schedule an interview" in response.json()["detail"]


def test_five_year_rule_at_every_interview_entry_point(client, db, world):
    from types import SimpleNamespace

    from app.models.interview_rehire_review import InterviewRehireReview
    from app.services.interview_rehire_guard_service import decide_rehire_review
    from app.services.message_handlers.interview_scheduled_handler import InterviewScheduledHandler
    from app.services.submission_service import ExperienceIneligible

    users, candidate = world
    panel = _panel(client, users, candidate, "L1 Technical")
    assert panel.status_code == 201, panel.text
    candidate.total_experience_months = 30  # corrected after the panel existed
    db.commit()
    start = datetime.utcnow() + timedelta(days=1)
    scheduled = client.post("/api/v1/interviews/create", headers=_headers(users[0]), json={
        "panel_id": panel.json()["id"], "candidate_id": candidate.candidateID,
        "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat()})
    assert scheduled.status_code == 400 and "Cannot schedule an interview" in scheduled.json()["detail"]

    review = InterviewRehireReview(candidate_id=candidate.candidateID, round_name="L1", justification="re-try",
                                   status="PENDING_HM_APPROVAL")
    db.add(review)
    db.commit()
    with pytest.raises(ExperienceIneligible):
        decide_rehire_review(db, review.id, "approve", users[0].UserID)
    db.rollback()
    assert db.get(InterviewRehireReview, review.id).status == "PENDING_HM_APPROVAL"

    message = SimpleNamespace(id=str(uuid.uuid4()), payload={"candidate_id": candidate.candidateID, "interview_date": start.isoformat()})
    with pytest.raises(ValueError, match="Cannot schedule an interview"):
        InterviewScheduledHandler.process(message, db)

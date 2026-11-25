"""Two things a browser walk-through of Create Offer and My Tasks found (2026-11-24):

- An offer is approved only by its hiring manager. The wizard sent a blank hiring manager for a
  job without one, and the insert failed with a 500. Now the job's own hiring manager is used,
  and an offer nobody could approve is refused with a clear reason.
- When a round's verdict is worked out from the panel's feedback, nobody was told (the old
  per-feedback notifier read a table and fields that do not exist). Now the interview team hears
  the result once, and mixed feedback asks the hiring manager to decide.
"""
import datetime as dt
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.candidate import CandidateStatus
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.user import Interview, InterviewFeedback, InterviewPanel, PanelMember
from app.services import hiring_pipeline_service as hp
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def world(db):
    admin = factories.user(db, role_template_id=full_access_role(db).id, UserRole="admin")
    manager = factories.user(db, UserName="Hiring Manager")
    interviewer = factories.user(db, UserName="Panel Member")
    db.commit()
    return SimpleNamespace(admin=admin, manager=manager, interviewer=interviewer)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _offer_ready(db, admin):
    candidate = factories.candidate(db, total_experience_months=72)
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Screening"))
    db.commit()
    hp.record_screen_decision(db, candidate.candidateID, "PASS", admin.UserID)
    for level in ("L1", "L2"):
        panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=level)
        db.add(panel)
        db.flush()
        db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                     verdict="PASS", source="MANUAL"))
    db.commit()
    return candidate


def _offer_body(candidate, job, **extra):
    body = {"candidate_id": candidate.candidateID, "job_id": job.jobID, "hiring_manager_id": "",
            "position": "Engineer", "salary": "1200000", "joining_date": "2027-01-15", "offer_expire_date": "2027-01-05"}
    body.update(extra)
    return body


def test_the_offer_takes_the_jobs_hiring_manager_when_none_is_sent(db, world, api):
    candidate = _offer_ready(db, world.admin)
    job = factories.job(db, hiringManagerID=world.manager.UserID)
    db.commit()
    response = api.post(world.admin, "/api/v1/offer-letter/create",
                        json=_offer_body(candidate, job, reporting_manager_id=world.interviewer.UserID))
    assert response.status_code == 200, response.text
    offer = db.query(OfferLetter).filter_by(candidate_id=candidate.candidateID).one()
    assert offer.hiring_manager_id == world.manager.UserID
    assert offer.reporting_manager_id == world.interviewer.UserID


def test_an_offer_nobody_could_approve_is_refused_not_a_500(db, world, api):
    candidate = _offer_ready(db, world.admin)
    job = factories.job(db)  # no hiring manager
    db.commit()
    response = api.post(world.admin, "/api/v1/offer-letter/create", json=_offer_body(candidate, job))
    assert response.status_code == 400
    assert "hiring manager" in response.json()["detail"]
    assert db.query(OfferLetter).filter_by(candidate_id=candidate.candidateID).count() == 0


def _round_with_feedback(db, world, recommendations):
    candidate = factories.candidate(db)
    job = factories.job(db, hiringManagerID=world.manager.UserID)
    panel = InterviewPanel(candidate_id=candidate.candidateID, job_id=job.jobID, round_name="L1")
    db.add(panel)
    db.flush()
    db.add(PanelMember(panel_id=panel.id, interviewer_id=world.interviewer.UserID))
    start = dt.datetime.utcnow() - dt.timedelta(hours=3)
    interview = Interview(panel_id=panel.id, candidate_id=candidate.candidateID, start_time=start,
                          end_time=start + dt.timedelta(hours=1), status="Completed")
    db.add(interview)
    db.flush()
    for recommendation in recommendations:
        db.add(InterviewFeedback(interview_id=interview.id, interviewer_id=world.interviewer.UserID,
                                 recommendation=recommendation))
    db.commit()
    return interview


def _emails(db, interview, actor_id=None):
    from app.api.v1.endpoints.interviews import _record_round_verdict

    sent = []
    with patch("app.services.staff_mail_service.queue_staff_email",
               side_effect=lambda user, **kw: sent.append((user.UserID, kw["subject"])) or True),             patch("app.services.hiring_pipeline_service.notify"):  # the pipeline re-evaluation is queued elsewhere
        _record_round_verdict(db, interview, actor_id)
        _record_round_verdict(db, interview, actor_id)  # recomputing the same verdict tells nobody again
    return sent


def test_a_passed_round_tells_the_interview_team_once(db, world):
    interview = _round_with_feedback(db, world, ["Hire"])
    sent = _emails(db, interview, actor_id=world.interviewer.UserID)
    assert [(u, s.split(":")[0]) for u, s in sent] == [(world.manager.UserID, "Round passed")]  # not the actor


def test_mixed_feedback_asks_the_hiring_manager_to_decide(db, world):
    interview = _round_with_feedback(db, world, ["Hire", "Not sure"])
    sent = _emails(db, interview)
    assert sent == [(world.manager.UserID, sent[0][1])]
    assert sent[0][1].startswith("Your decision")

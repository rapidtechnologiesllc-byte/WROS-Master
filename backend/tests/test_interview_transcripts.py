"""CEO 2026-11-05: "the transcript of the recording is not there, it is no AI based post interview recommendation"."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.interview_log import InterviewLog
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs
from app.services import interview_transcript_service as service
from tests.scope_fixtures import ApiClient, two_bu_world

VTT = """WEBVTT

00:00:01.000 --> 00:00:04.000
<v Avinash Mukundan>Tell me about Guidewire BillingCenter.</v>

00:00:05.000 --> 00:00:09.000
<v Jane Doe>I led BillingCenter programmes for twelve years across three carriers.</v>
"""
JOIN = "https://teams.microsoft.com/meet/123?p=abc"


class Reply:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body


class FakeGraph:
    def __init__(self, refuse=False, transcripts=True):
        self.refuse, self.transcripts, self.patched = refuse, transcripts, []

    def get(self, url, headers=None, timeout=None, params=None):
        if self.refuse and "onlineMeetings" in url:
            return Reply(403, text="No application access policy found")
        if url.endswith("?$select=id"):
            return Reply(body={"id": "user-1"})
        if url.endswith("/onlineMeetings"):
            return Reply(body={"value": [{"id": "meeting-1"}]})
        if url.endswith("/transcripts"):
            return Reply(body={"value": [{"id": "t1"}] if self.transcripts else []})
        return Reply(text=VTT)

    def patch(self, url, headers=None, json=None, timeout=None):
        self.patched.append(json)
        return Reply(200)


@pytest.fixture
def db(test_db_engine, monkeypatch):
    monkeypatch.setattr(service, "_token", lambda: "token")
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
    tenant = world.org_user.tenant_id
    world.candidate = Candidate(tenant_id=tenant, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                                candidateFirstName="Jane", candidateLastName="Doe",
                                candidateEmail=f"j{uuid.uuid4().hex[:6]}@example.com")
    world.job = Jobs(jobTitle="Developer", jobDescription="d", jobSkills="BillingCenter, PolicyCenter", jobExperience="5",
                     jobLocation="Remote", tenant_id=tenant)
    db.add_all([world.candidate, world.job])
    db.flush()
    world.panel = InterviewPanel(candidate_id=world.candidate.candidateID, job_id=world.job.jobID, round_name="L1")
    db.add(world.panel)
    db.flush()
    world.interview = Interview(panel_id=world.panel.id, candidate_id=world.candidate.candidateID, status="Completed",
                                start_time=datetime.utcnow() - timedelta(hours=3), end_time=datetime.utcnow() - timedelta(hours=2),
                                meeting_link=JOIN)
    db.add(world.interview)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _feedback(db, w, recommendation, score=8):
    db.add(InterviewFeedback(interview_id=w.interview.id, interviewer_id=w.org_user.UserID, recommendation=recommendation,
                             technical_score=score, communication_score=score, problem_solving_score=score, culture_fit_score=score))
    db.commit()


def test_teams_vtt_becomes_speaker_lines():
    assert service.vtt_to_text(VTT).splitlines()[1].startswith("Jane Doe: I led BillingCenter")


def test_the_job_keeps_the_transcript_once(db, w):
    first = service.run_interview_transcripts_job(db, http=FakeGraph())
    assert first["fetched"] >= 1
    log = db.get(InterviewLog, w.interview.id)
    assert "BillingCenter" in log.transcript_text and log.meeting_platform == "Teams"
    again = FakeGraph()
    service.run_interview_transcripts_job(db, http=again)
    assert db.get(InterviewLog, w.interview.id).transcript_text == log.transcript_text


def test_a_microsoft_refusal_is_reported_not_hidden(db, w):
    result = service.run_interview_transcripts_job(db, http=FakeGraph(refuse=True))
    assert "access policy" in result["blocked"] and result["fetched"] == 0
    assert db.get(InterviewLog, w.interview.id) is None


def test_upcoming_teams_interviews_get_transcription_on(db, w):
    w.interview.status, w.interview.start_time = "Scheduled", datetime.utcnow() + timedelta(days=1)
    w.interview.end_time = w.interview.start_time + timedelta(hours=1)
    db.commit()
    graph = FakeGraph()
    assert service.run_interview_transcripts_job(db, http=graph)["prepared"] >= 1
    assert graph.patched[0] == {"recordAutomatically": True, "allowTranscription": True}


def test_rules_use_the_panel_and_the_transcript_without_a_key(db, w):
    _feedback(db, w, "Hire", 8)
    service.save_transcript(db, w.interview, service.vtt_to_text(VTT))
    result = service.analysis_for(db, w.interview)
    assert result["source"] == "rules" and result["recommendation"] == "Hire"
    assert result["technical_score"] == 80 and result["confidence_pct"] is None
    assert "Discussed BillingCenter" in result["strengths"]
    assert "PolicyCenter did not come up" in result["concerns"]
    assert "spoke" in result["rationale"]


def test_rules_do_not_invent_a_recommendation_without_the_panel(db, w):
    service.save_transcript(db, w.interview, service.vtt_to_text(VTT))
    assert service.analysis_for(db, w.interview)["recommendation"] is None


def test_a_tied_panel_takes_the_careful_answer(db, w):
    _feedback(db, w, "Hire")
    _feedback(db, w, "Reject", 3)
    result = service.analysis_for(db, w.interview)
    assert result["recommendation"] == "Reject" and "The panel disagreed." in result["concerns"]


def test_a_transcript_can_be_added_to_an_existing_interview(api, db, w):
    added = api.client.post(f"/api/v1/interviews/{w.interview.id}/transcript", headers=ApiClient.headers(w.org_user),
                            data={"transcript_text": "Jane Doe: I know BillingCenter."})
    assert added.status_code == 200, added.text
    shown = api.get(w.org_user, f"/api/v1/interviews/{w.interview.id}/transcript").json()
    assert "BillingCenter" in shown["transcript_text"]
    analysis = api.get(w.org_user, f"/api/v1/flash/interviews/{w.interview.id}/analysis")
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["data"]["source"] == "rules"

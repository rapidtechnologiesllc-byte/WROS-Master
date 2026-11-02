"""Log an interview that already happened (CEO 2026-11-02: "Log interview isnt working as expected, I
pasted the meeting recording but nothing is showing up" -- it only wrote a history note; and the form
"should also ask for Interview Date, Interview Type, Panel Members, Meeting Platform, attach field where
i can upload the word document of the transcript"). The 5-year rule: recorded, and flagged."""
import io
import uuid
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.interview_log import InterviewLog
from app.models.user import Interview, InterviewFeedback, PanelMember
from app.services.interview_log_service import read_docx_text, transcript_meta
from tests.scope_fixtures import ApiClient, two_bu_world

TRANSCRIPT = """Marco Terpstra  BlitzenX-20261030_160921-Meeting Transcript
October 30, 2026, 8:09PM
36m 48s
Avinash Mukundan started transcription
Marco: I have led Guidewire BillingCenter programmes for twelve years."""


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
def w(db):
    world = two_bu_world(db)
    world.candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                                candidateFirstName="Marco", candidateLastName="Terpstra",
                                candidateEmail=f"m{uuid.uuid4().hex[:6]}@example.com")
    db.add(world.candidate)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _docx(text):
    from docx import Document

    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _log(api, w, files=None, **fields):
    data = {"candidate_id": w.candidate.candidateID, "interview_type": "Technical", "meeting_platform": "Teams",
            "recommendation": "Hire", **fields}
    return api.client.post("/api/v1/interviews/log-completed", headers=ApiClient.headers(w.org_user),
                           data=data, files=files)


def test_the_teams_header_gives_date_and_length():
    assert transcript_meta(TRANSCRIPT) == (datetime(2026, 10, 30, 20, 9), 36)


def test_a_word_transcript_is_read():
    assert "BillingCenter programmes" in read_docx_text(_docx(TRANSCRIPT))


def test_a_logged_interview_is_a_completed_interview_with_its_transcript(db, w, api):
    response = _log(api, w, files={"transcript_file": ("marco.docx", _docx(TRANSCRIPT),
                                                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                    summary="Strong BillingCenter lead.", panel_member_ids=f"{w.org_user.UserID},{w.partner_a.UserID}")
    assert response.status_code == 201, response.text
    interview = db.query(Interview).filter_by(id=response.json()["interview_id"]).one()
    assert (interview.status, interview.feedback_status) == ("Completed", "Completed")
    assert interview.start_time == datetime(2026, 10, 30, 20, 9)
    assert (interview.end_time - interview.start_time).seconds == 36 * 60
    assert {m.interviewer_id for m in db.query(PanelMember).filter_by(panel_id=interview.panel_id)} == \
        {w.org_user.UserID, w.partner_a.UserID}
    feedback = db.query(InterviewFeedback).filter_by(interview_id=interview.id).one()
    assert (feedback.recommendation, feedback.comments) == ("Hire", "Strong BillingCenter lead.")
    log = db.query(InterviewLog).filter_by(interview_id=interview.id).one()
    assert log.transcript_file_name == "marco.docx" and "BillingCenter programmes" in log.transcript_text
    assert log.experience_unverified is True  # no verified experience on file: recorded, flagged

    history = api.get(w.org_user, f"/api/v1/interviews/candidate-history/{w.candidate.candidateID}").json()
    assert history["completed_interviews"] == 1
    item = history["interviews"][0]
    assert item["meeting_platform"] == "Teams" and item["has_transcript"] and item["experience_unverified"]
    assert item["feedback_status"] == "Completed"
    transcript = api.get(w.org_user, f"/api/v1/interviews/{interview.id}/transcript").json()
    assert "BillingCenter programmes" in transcript["transcript_text"]


@pytest.mark.parametrize("fields,message", [
    ({"recommendation": "Maybe"}, "recommendation"),
    ({"meeting_platform": "Carrier pigeon"}, "Meeting platform"),
    ({"summary": "ok", "interview_date": "2099-01-01"}, "future"),
    ({"summary": ""}, "summary or the transcript"),
    ({"summary": "no date"}, "interview date"),
])
def test_what_a_log_needs(w, api, fields, message):
    response = _log(api, w, **fields)
    assert response.status_code == 400 and message in response.json()["detail"]


def test_log_options_come_from_the_backend(w, api):
    options = api.get(w.org_user, "/api/v1/interviews/log-options").json()
    assert "Teams" in options["meeting_platforms"] and "Hire" in options["recommendations"]
    assert options["interview_types"]

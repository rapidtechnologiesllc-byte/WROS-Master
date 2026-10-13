"""
S-027/HRMS-0427 -- Resume Upload via WhatsApp/Email.

Real architecture facts under test (see resume_upload_service module
docstring): storage is real SharePoint via DocumentService (mocked
here to avoid a real Graph/network call), BR-01's overwrite-and-archive
is already implemented by DocumentService.save_document_metadata()
itself (not reimplemented), no resume_url column on Candidate (presence
tracked via CandidateDocument.is_latest), qualification continuation
reuses the real S-024 engine.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateInfoForm
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_field_skip import CandidateFieldSkip
from app.models.document import CandidateDocument
from app.models.notification import Notification
from app.models.user import Users

import app.services.document_service as document_service
import app.services.resume_upload_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateInfoForm.__table__,
        CandidateConversation.__table__, ConversationEvent.__table__, CandidateFieldSkip.__table__,
        CandidateDocument.__table__, CandidateAIAssignment.__table__, Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    candidate = Candidate(
        candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Sharma",
    )
    db_session.add_all([owner, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder", escalation_state="none", channel_preference="email")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv


def _fake_sharepoint_upload(self, access_token, candidate_id, document_type, file_content, unique_filename):
    return {"webUrl": f"https://sharepoint.example/{unique_filename}", "id": "sp-file-id-123"}


def test_pdf_resume_stored_successfully(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", _fake_sharepoint_upload)

    result = svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"%PDF-1.4 fake resume bytes", original_filename="priya_resume.pdf", mime_type="application/pdf",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token",
    )

    assert result["outcome"] == "stored"
    doc = db_session.query(CandidateDocument).filter(CandidateDocument.candidate_id == "C-1", CandidateDocument.document_type == "resume").first()
    assert doc is not None
    assert doc.is_latest is True
    assert doc.sharepoint_url.startswith("https://sharepoint.example/")

    uploaded_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESUME_UPLOADED").all()
    assert len(uploaded_events) == 1

    confirmation_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert len(confirmation_events) == 1
    assert "received your resume" in confirmation_events[0].event_data["body"]


def test_docx_resume_via_email_stored_same_as_whatsapp_pdf(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", _fake_sharepoint_upload)

    result = svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"fake docx bytes", original_filename="resume.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        source="EMAIL", graph_token_fn=lambda: "fake-token",
    )
    assert result["outcome"] == "stored"


def test_wrong_file_type_rejected_no_storage(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    called = []
    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", lambda *a, **kw: called.append(1))

    result = svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"fake jpg bytes", original_filename="photo.jpg", mime_type="image/jpeg",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token",
    )

    assert result["outcome"] == "wrong_format"
    assert called == []  # never attempted storage

    wrong_format_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESUME_WRONG_FORMAT").all()
    assert len(wrong_format_events) == 1

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert "PDF or Word" in sent_events[0].event_data["body"]


def test_storage_failure_retries_once_then_alerts_recruiter(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    assignment = CandidateAIAssignment(tenant_id="U-ORG", candidate_id="C-1", ai_agent_name="thunder", assigned_by="U-ORG", is_active=True)
    db_session.add(assignment)
    db_session.commit()

    attempts = []

    def always_fails(self, *a, **kw):
        attempts.append(1)
        raise RuntimeError("SharePoint unreachable")

    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", always_fails)

    result = svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"%PDF-1.4", original_filename="resume.pdf", mime_type="application/pdf",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token",
    )

    assert result["outcome"] == "storage_failed"
    assert len(attempts) == 2  # BR: retry once

    failure_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESUME_STORAGE_FAILED").all()
    assert len(failure_events) == 1

    confirmation_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    assert confirmation_events == []  # BR: do not send confirmation on failure

    notifications = db_session.query(Notification).filter(Notification.recipient_id == "U-ORG").all()
    assert len(notifications) == 1


def test_second_resume_upload_archives_first(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", _fake_sharepoint_upload)

    svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"first resume", original_filename="resume_v1.pdf", mime_type="application/pdf",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token",
    )
    svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"second resume", original_filename="resume_v2.pdf", mime_type="application/pdf",
        source="EMAIL", graph_token_fn=lambda: "fake-token",
    )

    docs = db_session.query(CandidateDocument).filter(CandidateDocument.candidate_id == "C-1", CandidateDocument.document_type == "resume").order_by(CandidateDocument.id.asc()).all()
    assert len(docs) == 2
    assert docs[0].is_latest is False  # BR-01: archived, not deleted
    assert docs[1].is_latest is True
    assert docs[1].version == 2


def test_has_active_resume_reflects_latest_only(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    assert svc.has_active_resume(db_session, "C-1") is False

    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", _fake_sharepoint_upload)
    svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"resume", original_filename="resume.pdf", mime_type="application/pdf",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token",
    )
    assert svc.has_active_resume(db_session, "C-1") is True


def test_qualification_question_appended_when_state_is_qualifying(db_session, seeded, monkeypatch):
    candidate, conv = seeded
    monkeypatch.setattr(document_service.DocumentService, "upload_to_sharepoint", _fake_sharepoint_upload)

    result = svc.handle_resume_document(
        db_session, conv, candidate, "U-ORG",
        file_content=b"resume", original_filename="resume.pdf", mime_type="application/pdf",
        source="WHATSAPP", graph_token_fn=lambda: "fake-token", llm_call=lambda p: "variation",
    )
    assert result["outcome"] == "stored"

    sent_events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").all()
    body = sent_events[0].event_data["body"]
    assert "received your resume" in body
    # candidate is missing every other field, so a qualification question should be appended
    assert len(body) > len(svc._confirmation_message(candidate))

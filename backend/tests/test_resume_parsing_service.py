"""
S-028/HRMS-0428 -- Resume Parsing Engine.

Real architecture facts under test (see resume_parsing_service module
docstring): pypdf/python-docx do REAL text extraction (not mocked --
this test builds an actual PDF and an actual DOCX in-memory and
extracts real text from them). candidates.total_experience_months
(Integer, already existed, already read by the real <5yr hard rule in
submission_service.check_experience_eligibility()) is the real
cascade target -- no total_experience_years/current_employer column on
Candidate. BR-01's overlap-merge is tested against this story's own
worked example (TC-002: 42 months / 3.5 years).

"""
import io
import json
import os
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation, ConversationEvent
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.notification import Notification
from app.models.user import Jobs, Users

import app.services.resume_parsing_service as svc

def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
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
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    db_session.add_all([owner, candidate])
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    return candidate, conv

def _make_real_pdf_bytes(text_lines):
    from pypdf import PdfWriter
    # Build via a minimal reportlab-free approach: pypdf can't author text
    # pages itself, so use pdfminer-free plain approach: write a tiny valid
    # PDF containing the text using the low-level pypdf writer + a simple
    # content stream. This produces a REAL, parseable PDF (not a mock).
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject, ArrayObject, NumberObject

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.pages[0]

    content = "BT /F1 12 Tf 50 700 Td\n"
    for line in text_lines:
        safe = line.replace("(", r"\(").replace(")", r"\)")
        content += f"({safe}) Tj 0 -14 Td\n"
    content += "ET"

    stream_obj = DecodedStreamObject()
    stream_obj.set_data(content.encode("latin-1", errors="replace"))
    stream_ref = writer._add_object(stream_obj)

    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font_dict)
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})

    page[NameObject("/Contents")] = stream_ref
    page[NameObject("/Resources")] = resources

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

def _make_real_docx_bytes(text_lines):
    import docx
    document = docx.Document()
    for line in text_lines:
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()

RESUME_LINES = [
    "Priya Sharma",
    "Senior Software Engineer with extensive backend experience.",
    "Worked at multiple companies building scalable systems.",
    "Email priya@example.com Phone +919876543210",
    "Skilled in Python, SQL, and cloud infrastructure design work.",

def test_extract_text_from_real_pdf():
    pdf_bytes = _make_real_pdf_bytes(RESUME_LINES)
    text = svc.extract_text_from_pdf(pdf_bytes)
    assert "Priya Sharma" in text

def test_extract_text_from_real_docx():
    docx_bytes = _make_real_docx_bytes(RESUME_LINES)
    text = svc.extract_text_from_docx(docx_bytes)
    assert "Priya Sharma" in text

def test_extract_raw_text_too_short_raises():
    docx_bytes = _make_real_docx_bytes(["Hi"])
    with pytest.raises(svc.TextExtractionFailed):
        svc.extract_raw_text(docx_bytes, ".docx")

def test_extract_raw_text_unsupported_extension_raises():
    with pytest.raises(svc.TextExtractionFailed):
        svc.extract_raw_text(b"whatever", ".txt")

# ── BR-01/BR-02: overlap calculation ────────────────────────────────

def test_no_overlap_simple_sum():
    work_history = [
        {"start_date": "2018-01", "end_date": "2019-12"},  # 24 months inclusive
    assert svc.calculate_total_experience_months(work_history) == 24

def test_overlapping_roles_counted_once_tc002():
    """This story's own worked example: Company A Jan2020-Dec2022,
    Company B Jun2021-Jun2023 -> 42 months (3.5 years), never the sum
    (54 months)."""
    work_history = [
        {"employer": "Company A", "start_date": "2020-01", "end_date": "2022-12"},
        {"employer": "Company B", "start_date": "2021-06", "end_date": "2023-06"},
    months = svc.calculate_total_experience_months(work_history)
    assert months == 42
    assert round(months / 12.0, 1) == 3.5

def test_current_role_uses_today_as_end_date():
    work_history = [{"start_date": "2020-01", "end_date": None}]
    months = svc.calculate_total_experience_months(work_history)
    today = date.today()
    expected = (today.year - 2020) * 12 + (today.month - 1) + 1
    assert months == expected

def test_malformed_entry_skipped_not_crashed():
    work_history = [
        {"start_date": "2020-01", "end_date": "2019-01"},  # end before start -- bad data
        {"start_date": "2021-01", "end_date": "2021-12"},  # valid, 12 months
    assert svc.calculate_total_experience_months(work_history) == 12

def test_empty_work_history_returns_zero():
    assert svc.calculate_total_experience_months([]) == 0

# ── parse_resume() integration ──────────────────────────────────────

def _valid_llm_response():
    return json.dumps({
        "full_name": "Priya Sharma", "email": "priya@example.com", "phone": "+919876543210",
        "current_title": "Senior Software Engineer", "current_employer": "Company B",
        "work_history": [
            {"employer": "Company A", "title": "Engineer", "start_date": "2020-01", "end_date": "2022-12", "description": "Backend work"},
            {"employer": "Company B", "title": "Senior Engineer", "start_date": "2021-06", "end_date": "2023-06", "description": "Scaling systems"},
        ],
        "education": [{"institution": "State University", "degree": "B.Tech", "field": "CS", "graduation_year": 2019}],
        "skills": ["Python", "SQL", "AWS"],
        "certifications": [],
        "languages": ["English"],
    })

def test_parse_resume_success_updates_candidate_resume_parsed_and_candidate(db_session, seeded):
    candidate, conv = seeded
    docx_bytes = _make_real_docx_bytes(RESUME_LINES)

    result = svc.parse_resume(
        db_session, candidate, "U-ORG", file_content=docx_bytes, extension=".docx",
        conversation=conv, llm_call=lambda p: _valid_llm_response(),
    )

    assert result["outcome"] == "parsed"
    assert result["total_experience_months"] == 42

    db_session.refresh(candidate)
    assert candidate.total_experience_months == 42
    assert "Python" in candidate.candidateSkills

    parsed = db_session.query(CandidateResumeParsed).filter(CandidateResumeParsed.candidate_id == "C-1").first()
    assert parsed is not None
    assert parsed.current_employer == "Company B"
    assert parsed.total_experience_years == 3.5
    assert len(parsed.work_history) == 2

    events = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "candidate.resume_parsed").all()
    assert len(events) == 1
    assert events[0].event_data["total_experience_months"] == 42
    assert events[0].event_data["skills_count"] == 3

def test_parse_resume_second_parse_updates_existing_row_not_duplicate(db_session, seeded):
    candidate, conv = seeded
    docx_bytes = _make_real_docx_bytes(RESUME_LINES)

    svc.parse_resume(db_session, candidate, "U-ORG", file_content=docx_bytes, extension=".docx", conversation=conv, llm_call=lambda p: _valid_llm_response())
    svc.parse_resume(db_session, candidate, "U-ORG", file_content=docx_bytes, extension=".docx", conversation=conv, llm_call=lambda p: _valid_llm_response())

    rows = db_session.query(CandidateResumeParsed).filter(CandidateResumeParsed.candidate_id == "C-1").all()
    assert len(rows) == 1  # UNIQUE candidate_id -- upserted, not duplicated

def test_parse_resume_text_extraction_failure(db_session, seeded):
    candidate, conv = seeded
    tiny_docx = _make_real_docx_bytes(["Hi"])

    result = svc.parse_resume(db_session, candidate, "U-ORG", file_content=tiny_docx, extension=".docx", conversation=conv)
    assert result["outcome"] == "text_extraction_failed"

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESUME_TEXT_EXTRACTION_FAILED").all()
    assert len(failures) == 1

    db_session.refresh(candidate)
    assert candidate.total_experience_months is None  # profile untouched

def test_parse_resume_llm_failure_retries_once_then_notifies_recruiter(db_session, seeded):
    candidate, conv = seeded
    assignment = CandidateAIAssignment(tenant_id="U-ORG", candidate_id="C-1", ai_agent_name="thunder", assigned_by="U-ORG", is_active=True)
    db_session.add(assignment)
    db_session.commit()

    docx_bytes = _make_real_docx_bytes(RESUME_LINES)
    attempts = []

    def bad_json(prompt):
        attempts.append(1)
        return "not valid json{{{"

    result = svc.parse_resume(db_session, candidate, "U-ORG", file_content=docx_bytes, extension=".docx", conversation=conv, llm_call=bad_json)

    assert result["outcome"] == "parsing_failed"
    assert len(attempts) == 2  # retried once

    failures = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "RESUME_PARSING_FAILED").all()
    assert len(failures) == 1

    db_session.refresh(candidate)
    assert candidate.total_experience_months is None  # BR-03: profile continues without parsed data

    notifications = db_session.query(Notification).filter(Notification.recipient_id == "U-ORG").all()
    assert len(notifications) == 1

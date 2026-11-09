"""Emails staff forward to the HRMS mailbox: poll -> read -> candidate / note / task. Fake Graph + fake LLM."""
import base64
import io
import json
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import func

import pytest

from app.models.activity_timeline import ActivityTimeline
from app.models.candidate import Candidate
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.document import CandidateDocument
from app.models.internal_note import InternalNote
from app.models.mailbox_intake import MailboxIntakeMessage
from app.models.task import Task
from app.models.user import Jobs, Users
from app.services.delivery_errors import DeliveryDeferred
from app.services.message_handlers.candidate_creation_unified_handler import CandidateCreationUnifiedHandler
from app.services.message_handlers.thunder_forwarded_email_handler import ThunderForwardedEmailHandler
from app.services.thunder_mail import forward_classifier
from app.services.thunder_mail.forward_intake_service import CANDIDATE_SOURCE, THUNDER_FORWARD_TASK
from app.services.thunder_mail.mail_poll_service import poll_thunder_mailbox
from tests.hiring_fixtures import full_access_role

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"
MAILBOX = "helpdesk_hrms@blitzenx.com"


def uid():
    return uuid.uuid4().hex[:8]


def docx_bytes(*lines):
    from docx import Document

    document = Document()
    for line in lines:
        document.add_paragraph(line)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def pdf_bytes(text):
    """A one-page PDF with one line of text (enough for pypdf's extractor)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


class FakeMailbox:
    def __init__(self, inbox=None, bodies=None, attachments=None):
        self.inbox = inbox or []
        self.bodies = bodies or {}
        self.attachments = attachments or {}
        self.reads = []

    def list_inbox(self, since, page_cap=10):
        return self.inbox

    def get_message(self, message_id):
        self.reads.append(message_id)
        return {"id": message_id, "body": {"content": self.bodies[message_id]},
                "hasAttachments": bool(self.attachments.get(message_id))}

    def list_attachments(self, message_id):
        return self.attachments.get(message_id, [])

    def get_attachment(self, message_id, attachment_id):
        return next(a for a in self.attachments[message_id] if a["id"] == attachment_id)


def file_attachment(name, content):
    return {"@odata.type": "#microsoft.graph.fileAttachment", "id": f"att-{uid()}", "name": name,
            "size": len(content), "isInline": False, "contentBytes": base64.b64encode(content).decode()}


def graph_msg(sender, subject="Fwd: profile", minutes_ago=1, headers=None, message_id=None):
    return {
        "id": message_id or f"g-{uid()}", "conversationId": f"conv-{uid()}",
        "internetMessageId": f"<{uid()}@mail>", "from": {"emailAddress": {"address": sender}},
        "subject": subject, "uniqueBody": {"content": "see below"},
        "receivedDateTime": (datetime.utcnow() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "internetMessageHeaders": headers or [],
    }


def llm_returning(**data):
    payload = {"kind": "NEW_CANDIDATE", "confidence": 0.9, "candidate": None, "job_reference": None,
               "employee_email": None, "summary": "A resume for a Guidewire developer."}
    payload.update(data)
    return lambda *a: json.dumps(payload)


def llm_down(*a):
    raise RuntimeError("GEMINI_API_KEY not set")


@pytest.fixture(autouse=True)
def _no_llm_retry_wait():
    with patch("app.services.prompt_framework_service.RETRY_DELAY_SECONDS", 0):
        yield


@pytest.fixture
def db(test_db_engine):
    """The code under test commits and rolls back: each transaction is a savepoint in one discarded transaction."""
    from sqlalchemy.orm import Session

    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def staff(db, role=None, **kw):
    role = role or full_access_role(db)
    user = Users(UserID=f"U-{uid()}", UserName=kw.get("name", "Avinash CEO"), UserEmail=f"ceo{uid()}@blitzenx.com",
                 UserPassword="x", UserRole="x", tenant_id=1, role_template_id=role.id)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def ceo(db):
    return staff(db)


@pytest.fixture
def storage():
    """SharePoint configured; uploads recorded instead of sent."""
    uploads = []

    def upload(self, token, candidate_id, document_type, content, filename):
        uploads.append((candidate_id, document_type, filename, content))
        return {"id": f"sp-{uid()}", "webUrl": f"https://sharepoint/{filename}"}

    with patch("app.core.graph_auth.GraphServiceAuth.is_configured", return_value=True), \
         patch("app.core.graph_auth.get_graph_token", return_value="token"), \
         patch("app.services.document_service.SHAREPOINT_SITE_ID", "site"), \
         patch("app.services.document_service.SHAREPOINT_DRIVE_ID", "drive"), \
         patch("app.services.document_service.DocumentService.upload_to_sharepoint", upload):
        yield uploads


def forwarded_body(note, sender_name, sender_email, text):
    return (f"{note}\n\n---------- Forwarded message ---------\nFrom: {sender_name} <{sender_email}>\n"
            f"Date: Thu, 23 Oct 2026\nSubject: My profile\nTo: Avinash\n\n{text}")


def poll(db, inbox):
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        result = poll_thunder_mailbox(db, mailbox=FakeMailbox(inbox))
    return result, [c.kwargs for c in enqueue.call_args_list if c.kwargs["task_name"] == THUNDER_FORWARD_TASK]


def run_handler(db, intake_id, mailbox, llm=None):
    """One queue delivery of the forwarded-email task; returns (result, the tasks it queued)."""
    message = SimpleNamespace(id=f"q-{uid()}", payload={"intake_id": intake_id})
    with patch(ENQUEUE, return_value={"message_id": f"m-{uid()}", "task_id": "x"}) as enqueue:
        result = ThunderForwardedEmailHandler.process(message, db, mailbox=mailbox, llm_call=llm or llm_down)
    return result, [c.kwargs for c in enqueue.call_args_list]


def run_creation(db, queued):
    """The create_candidate queue message the intake queued, processed like the worker does."""
    create = next(q for q in queued if q["task_name"] == "create_candidate")
    message = SimpleNamespace(id=create["task_id"], payload=create["data"], tenant_id=1)
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}):
        result = CandidateCreationUnifiedHandler._do_process(message, db)
        db.commit()  # the status-change event is queued after commit
    return result


def received_forward(db, ceo, body, attachments=(), subject="Fwd: Guidewire developer profile"):
    """Poll the mailbox once with one forward from the CEO; returns (intake row, fake mailbox)."""
    message = graph_msg(ceo.UserEmail, subject=subject)
    mailbox = FakeMailbox([message], {message["id"]: body}, {message["id"]: list(attachments)})
    result, queued = poll(db, [message])
    assert result["forwarded"] == 1 and len(queued) == 1
    row = db.query(MailboxIntakeMessage).filter_by(graph_message_id=message["id"]).one()
    return row, mailbox


RESUME_LINES = ("Priya Raman", "priya.raman@example.com | +91 98765 43210", "Senior Guidewire Developer",
                "Experience", "Acme Insurance Inc", "Guidewire Developer 2019-01 to 2026-09",
                "Skills: Java, Guidewire, SQL")


# ---- the poll: forwards from staff are kept, once -----------------------------------------

def test_poll_keeps_staff_forwards_once_and_ignores_strangers_and_auto_replies(db, ceo):
    forward = graph_msg(ceo.UserEmail.upper())
    auto = graph_msg(ceo.UserEmail, subject="Automatic reply: out of office")
    inbox = [forward, auto, graph_msg("vendor@elsewhere.com"), graph_msg(MAILBOX)]
    first, queued = poll(db, inbox)
    second, queued_again = poll(db, inbox)
    rows = db.query(MailboxIntakeMessage).filter(MailboxIntakeMessage.forwarded_by_user_id == ceo.UserID).all()
    assert first["forwarded"] == 1 and second["forwarded"] == 0 and not queued_again
    assert [r.graph_message_id for r in rows] == [forward["id"]] and rows[0].status == "RECEIVED"
    assert queued[0]["data"]["intake_id"] == rows[0].id and queued[0]["task_id"].startswith("thunder_forward:")


def test_poll_ignores_forwards_when_intake_is_switched_off_and_from_a_terminated_user(db, ceo):
    gone = staff(db)
    gone.terminated_at = datetime.utcnow()
    db.commit()
    with patch("app.core.config.settings.MAILBOX_INTAKE_ENABLED", False):
        off, _ = poll(db, [graph_msg(ceo.UserEmail)])
    on, _ = poll(db, [graph_msg(gone.UserEmail)])
    assert off["forwarded"] == 0 and on["forwarded"] == 0


# ---- end to end: forwarded resume -> candidate + resume + note within one cycle -------------

def test_forwarded_resume_creates_the_candidate_with_resume_and_note(db, ceo, storage):
    resume = file_attachment("Priya_Raman_Resume.docx", docx_bytes(*RESUME_LINES))
    body = forwarded_body("Strong Guidewire profile, please process.", "Priya Raman",
                          "priya.raman@example.com", "Hi, please find my resume attached.")
    row, mailbox = received_forward(db, ceo, body, [resume])
    llm = llm_returning(candidate={
        "first_name": "Priya", "last_name": "Raman", "email": "priya.raman@example.com",
        "phone": "+91 98765 43210", "current_title": "Senior Guidewire Developer", "current_location": None,
        "total_experience_years": 7.5, "skills": ["Java", "Guidewire", "SQL", "Kubernetes"]})

    result, queued = run_handler(db, row.id, mailbox, llm)
    assert result["status"] == "candidate_queued"
    create = next(q for q in queued if q["task_name"] == "create_candidate")
    assert create["data"]["candidate_source"] == CANDIDATE_SOURCE
    assert create["data"]["candidate_skills"] == ["Java", "Guidewire", "SQL"]  # Kubernetes is not in the email
    assert any(q["task_name"] == THUNDER_FORWARD_TASK and q["task_id"].endswith(":attach") for q in queued)

    created = run_creation(db, queued)
    result, _ = run_handler(db, row.id, mailbox, llm)

    candidate = db.query(Candidate).filter_by(candidateID=created["candidate_id"]).one()
    assert (candidate.candidateFirstName, candidate.candidateLastName) == ("Priya", "Raman")
    assert candidate.candidateEmail == "priya.raman@example.com" and candidate.candidateMobile == "+919876543210"
    assert candidate.candidateSource == CANDIDATE_SOURCE and candidate.total_experience_months == 90
    note = db.query(InternalNote).filter_by(candidate_id=candidate.candidateID).one()
    assert "Strong Guidewire profile" in note.content and note.created_by_id == ceo.UserID
    document = db.query(CandidateDocument).filter_by(candidate_id=candidate.candidateID, document_type="resume").one()
    assert document.original_filename == "Priya_Raman_Resume.docx" and len(storage) == 1
    parsed = db.query(CandidateResumeParsed).filter_by(candidate_id=candidate.candidateID).one()
    assert "Guidewire" in parsed.raw_text and parsed.total_experience_months == 90
    db.refresh(row)
    assert (row.status, row.candidate_id, row.note_id, row.document_id) == (
        "PROCESSED", candidate.candidateID, note.id, document.id)
    assert result["status"] == "processed"

    # the same queue message delivered again (or the poll overlapping) never acts twice
    again, queued_again = run_handler(db, row.id, mailbox, llm)
    assert again["status"] == "already_processed" and not queued_again
    assert db.query(InternalNote).filter_by(candidate_id=candidate.candidateID).count() == 1


def test_without_the_llm_the_rules_still_create_the_candidate_from_a_pdf_resume(db, ceo, storage):
    resume = file_attachment("cv.pdf", pdf_bytes("Rahul Verma rahul.verma@example.org +1 415 555 0134"))
    row, mailbox = received_forward(db, ceo, "FYI - candidate for the Duck Creek role", [resume])
    result, queued = run_handler(db, row.id, mailbox, llm_down)
    assert result["status"] == "candidate_queued"
    db.refresh(row)
    assert row.classifier_source == "rule" and row.kind == "NEW_CANDIDATE"
    created = run_creation(db, queued)
    run_handler(db, row.id, mailbox)
    candidate = db.query(Candidate).filter_by(candidateID=created["candidate_id"]).one()
    assert candidate.candidateEmail == "rahul.verma@example.org" and candidate.candidateFirstName == "Rahul"
    assert db.query(InternalNote).filter_by(candidate_id=candidate.candidateID).count() == 1


def test_attach_waits_for_candidate_creation_and_a_failed_creation_becomes_a_task(db, ceo, storage):
    from app.models.channel_queue import ChannelQueueItem

    resume = file_attachment("resume.docx", docx_bytes(*RESUME_LINES))
    row, mailbox = received_forward(db, ceo, "Please add", [resume])
    _, queued = run_handler(db, row.id, mailbox, llm_down)
    db.refresh(row)
    creation = ChannelQueueItem(id=row.creation_message_id, message_id=row.creation_message_id, tenant_id=1,
                                type="create_candidate", channel_type="CANDIDATE_QUEUE", status="PENDING",
                                payload={}, retry_count=0, created_at=datetime.utcnow())
    db.add(creation)
    db.commit()
    with pytest.raises(DeliveryDeferred):
        run_handler(db, row.id, mailbox)
    creation.status, creation.error = "FAILED", "database unavailable"
    db.commit()
    result, _ = run_handler(db, row.id, mailbox)
    task = db.query(Task).filter_by(id=result["task_id"]).one()
    assert result["status"] == "needs_review" and "database unavailable" in task.description
    assert task.assigned_to_user_id == ceo.UserID


def test_a_creation_folded_into_an_identical_queued_one_still_gets_the_resume_and_note(db, ceo, storage):
    from app.models.channel_queue import ChannelQueueItem

    resume = file_attachment("resume.docx", docx_bytes(*RESUME_LINES))
    row, mailbox = received_forward(db, ceo, "Please add", [resume])
    run_handler(db, row.id, mailbox, llm_down)
    db.refresh(row)
    # the queue returned another message (no intake id on it), which created the candidate
    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail="priya.raman@example.com",
                          candidatePassword="h", candidateFirstName="Priya", candidateLastName="Raman")
    db.add_all([candidate, ChannelQueueItem(
        id=row.creation_message_id, message_id=row.creation_message_id, tenant_id=1, type="create_candidate",
        channel_type="CANDIDATE_QUEUE", status="COMPLETED", payload={}, retry_count=0, created_at=datetime.utcnow())])
    db.commit()
    result, _ = run_handler(db, row.id, mailbox)
    assert result["status"] == "processed" and result["candidate_id"] == candidate.candidateID
    assert db.query(InternalNote).filter_by(candidate_id=candidate.candidateID).count() == 1


# ---- an existing candidate is updated, never duplicated ------------------------------------

def test_a_forward_about_an_existing_candidate_adds_the_note_and_fills_only_blank_fields(db, ceo, storage):
    existing = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail="priya.raman@example.com",
                         candidatePassword="h", candidateFirstName="Priya", candidateLastName="R",
                         candidateJobTitle="Lead Developer")
    db.add(existing)
    db.commit()
    resume = file_attachment("Priya_Raman_Resume.docx", docx_bytes(*RESUME_LINES))
    row, mailbox = received_forward(db, ceo, "Updated resume from Priya", [resume])
    result, queued = run_handler(db, row.id, mailbox, llm_down)
    assert result["status"] == "processed" and result["candidate_id"] == existing.candidateID
    assert not any(q["task_name"] == "create_candidate" for q in queued)
    db.refresh(existing)
    assert existing.candidateJobTitle == "Lead Developer"  # recruiter's value kept
    assert existing.candidateMobile == "+919876543210"  # blank filled from the resume
    assert db.query(InternalNote).filter_by(candidate_id=existing.candidateID).count() == 1
    assert db.query(CandidateDocument).filter_by(candidate_id=existing.candidateID).count() == 1


def test_candidate_news_without_a_resume_is_matched_by_phone(db, ceo):
    existing = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"c{uid()}@example.com",
                         candidatePassword="h", candidateFirstName="Sam", candidateLastName="Lee",
                         candidateMobile="+14155550199")
    db.add(existing)
    db.commit()
    row, mailbox = received_forward(db, ceo, "Sam (+1 415 555 0199) can join in 30 days, expects 140k.",
                                    subject="Fwd: Sam availability")
    result, _ = run_handler(db, row.id, mailbox, llm_returning(kind="CANDIDATE_UPDATE", summary="Sam can join in 30 days."))
    assert result["status"] == "processed" and result["candidate_id"] == existing.candidateID
    note = db.query(InternalNote).filter_by(candidate_id=existing.candidateID).one()
    assert "join in 30 days" in note.content


# ---- unclear or not allowed -> a task for the forwarder -----------------------------------

def test_an_email_about_nobody_we_know_is_set_aside_without_a_task(db, ceo):
    row, mailbox = received_forward(db, ceo, "Thoughts?", subject="Fwd: lunch")
    result, _ = run_handler(db, row.id, mailbox, llm_returning(kind="OTHER", confidence=0.4))
    assert result["status"] == "ignored"
    assert db.query(Task).filter(Task.title.like("Forwarded email needs you: Fwd: lunch%")).count() == 0
    db.refresh(row)
    assert row.status == "IGNORED"


def test_a_resume_without_an_email_address_becomes_a_task(db, ceo):
    resume = file_attachment("resume.docx", docx_bytes("Anita Desai", "Guidewire BA, 6 years"))
    row, mailbox = received_forward(db, ceo, "Good BA", [resume])
    result, queued = run_handler(db, row.id, mailbox, llm_down)
    assert result["status"] == "needs_review" and "email address" in result["reason"]
    assert not any(q["task_name"] == "create_candidate" for q in queued)


def test_the_model_cannot_invent_contact_details(db, ceo):
    row, mailbox = received_forward(db, ceo, "Nice profile: Kiran Rao", [])
    llm = llm_returning(candidate={"first_name": "Kiran", "last_name": "Rao", "email": "kiran@made-up.com",
                                   "phone": "+1 212 555 0100"})
    result, queued = run_handler(db, row.id, mailbox, llm)
    db.refresh(row)
    assert row.extracted["candidate"]["email"] is None and row.extracted["candidate"]["phone"] is None
    assert result["status"] == "needs_review" and not any(q["task_name"] == "create_candidate" for q in queued)


def test_a_forwarder_whose_role_cannot_create_candidates_gets_a_task(db):
    from app.models.role_template import RoleTemplate

    full_access_role(db)  # resources exist
    viewer = RoleTemplate(tenant_id=1, name=f"viewer-{uid()}", display_name="Viewer", enabled=True)
    db.add(viewer)
    db.flush()
    user = staff(db, role=viewer)
    resume = file_attachment("resume.docx", docx_bytes(*RESUME_LINES))
    row, mailbox = received_forward(db, user, "Please add", [resume])
    result, queued = run_handler(db, row.id, mailbox, llm_down)
    assert result["status"] == "needs_review" and "cannot create candidates" in result["reason"]
    assert not any(q["task_name"] == "create_candidate" for q in queued)


def test_without_document_storage_the_candidate_and_note_are_saved_and_a_task_asks_for_the_file(db, ceo):
    existing = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail="priya.raman@example.com",
                         candidatePassword="h", candidateFirstName="Priya", candidateLastName="Raman")
    db.add(existing)
    db.commit()
    resume = file_attachment("Priya_Raman_Resume.docx", docx_bytes(*RESUME_LINES))
    row, mailbox = received_forward(db, ceo, "Updated resume", [resume])
    with patch("app.services.document_service.SHAREPOINT_SITE_ID", ""):
        result, _ = run_handler(db, row.id, mailbox, llm_down)
    assert result["status"] == "needs_review" and "SharePoint" in result["reason"]
    assert db.query(InternalNote).filter_by(candidate_id=existing.candidateID).count() == 1
    task = db.query(Task).filter_by(id=result["task_id"]).one()
    assert task.candidate_id == existing.candidateID


# ---- jobs and employees -------------------------------------------------------------------

def test_a_job_requirement_is_noted_on_its_job_or_becomes_a_task(db, ceo):
    job = Jobs(jobID=str(uuid.uuid4()), jobTitle=f"Guidewire PolicyCenter Lead {uid()}", jobDescription="d",
               jobSkills="Guidewire", jobExperience="8", jobLocation="Remote", tenant_id=1)
    db.add(job)
    db.commit()
    row, mailbox = received_forward(db, ceo, f"Client wants 2 more for {job.jobTitle}", subject="Fwd: requirement")
    result, _ = run_handler(db, row.id, mailbox, llm_returning(kind="JOB_REQUIREMENT", job_reference=job.jobTitle,
                                                                 summary="Client needs two more."))
    assert result["status"] == "processed" and result["job_id"] == job.jobID
    entry = db.query(ActivityTimeline).filter_by(entity_type="job", entity_id=job.jobID).one()
    assert "Client needs two more." in entry.description and entry.actor_id == ceo.UserID

    row, mailbox = received_forward(db, ceo, "New req: Duck Creek Architect, 3 positions", subject="Fwd: new req")
    result, _ = run_handler(db, row.id, mailbox, llm_returning(kind="JOB_REQUIREMENT",
                                                                 job_reference="Duck Creek Architect"))
    assert result["status"] == "needs_review" and "Create the job" in result["reason"]


def test_an_employee_email_is_noted_on_the_employee(db, ceo):
    from app.models.employee import Employee

    employee = Employee(tenant_id=1, first_name="Meera", last_name="Iyer", email=f"meera{uid()}@blitzenx.com",
                        joining_date=date(2025, 1, 6))
    db.add(employee)
    db.commit()
    body = forwarded_body("Please note", "Client Manager", "manager@client.com",
                          f"{employee.email} did great work on the release.")
    row, mailbox = received_forward(db, ceo, body, subject="Fwd: kudos")
    result, _ = run_handler(db, row.id, mailbox, llm_returning(kind="EMPLOYEE_NOTE", employee_email=employee.email,
                                                                 summary="Client praises Meera's release work."))
    assert result["status"] == "processed" and result["employee_id"] == employee.id
    entry = db.query(ActivityTimeline).filter_by(entity_type="employee", entity_id=employee.id).one()
    assert "manager@client.com" in entry.description


# ---- reading ------------------------------------------------------------------------------

def test_reading_a_forward_finds_the_original_sender_and_the_forwarders_note(db):
    body = forwarded_body("Looks good, add her.", "Priya Raman", "priya.raman@example.com", "My resume is attached")
    reading = forward_classifier.read_forward(db, 1, "Fwd: profile", body, [], ["ceo@blitzenx.com", MAILBOX],
                                              llm_call=llm_down)
    assert (reading.original_sender_name, reading.original_sender_email) == ("Priya Raman", "priya.raman@example.com")
    assert reading.forwarder_note == "Looks good, add her."
    assert reading.candidate["first_name"] == "Priya" and reading.candidate["email"] == "priya.raman@example.com"


def test_an_email_forwarded_as_an_attachment_is_read(db):
    item = {"@odata.type": "#microsoft.graph.itemAttachment", "id": "a1", "name": "My profile",
            "item": {"subject": "My profile", "from": {"emailAddress": {"name": "Rahul Verma",
                                                                       "address": "rahul.v@example.org"}},
                     "body": {"content": "Hi, I am a Guidewire developer. Call me on +1 415 555 0134."}}}
    reading = forward_classifier.read_forward(db, 1, "Fwd: My profile", "see attached", [item], [MAILBOX],
                                              llm_call=llm_down)
    assert reading.original_sender_email == "rahul.v@example.org" and reading.phones == ["+14155550134"]


def test_an_unreadable_attachment_is_reported_not_hidden(db):
    raw = [file_attachment("resume.doc", b"\xd0\xcf\x11\xe0 legacy word"), file_attachment("big.pdf", b"x")]
    raw[1]["size"] = forward_classifier.RESUME_MAX_BYTES + 1
    reading = forward_classifier.read_forward(db, 1, "Fwd: cv", "cv attached", raw, [MAILBOX], llm_call=llm_down)
    assert reading.resume.name == "resume.doc"
    assert any("resume.doc" in p for p in reading.unreadable_attachments)
    assert any("big.pdf" in p for p in reading.unreadable_attachments)


# ---- fixes found on the way ---------------------------------------------------------------

def test_candidate_activity_entries_show_on_the_candidates_activity_panel(db, ceo):
    """The panel asks for "candidate"; the activity log wrote "Candidate", so nothing showed."""
    from app.services.activity_timeline_service import get_timeline_for_entity
    from app.services.candidate_activity_service import log_resume_uploaded

    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"c{uid()}@example.com",
                          candidatePassword="h", candidateFirstName="Ana", candidateLastName="Silva")
    db.add(candidate)
    db.commit()
    log_resume_uploaded(db, candidate.candidateID, "cv.pdf", 0.1)
    db.commit()
    feed = get_timeline_for_entity(db, "candidate", candidate.candidateID)
    assert [e["action"] for e in feed["entries"]] == ["resume_uploaded"]
    assert get_timeline_for_entity(db, "Candidate", candidate.candidateID)["total"] == 1


def test_existing_timeline_rows_are_lower_cased_once(db):
    from sqlalchemy import text

    from app.core.db_contract import _activity_timeline_entity_types_lowercase, run_data_migrations

    entity_id = f"CAN-{uid()}"
    db.add(ActivityTimeline(entity_type="Candidate", entity_id=entity_id, actor_type="SYSTEM", action="x"))
    db.commit()
    db.execute(text("DELETE FROM app_schema.data_migrations WHERE name = 'activity_timeline_entity_types_lowercase'"))
    ran = run_data_migrations(db, (("activity_timeline_entity_types_lowercase",
                                    _activity_timeline_entity_types_lowercase),))
    assert ran == ["activity_timeline_entity_types_lowercase"]
    assert db.query(ActivityTimeline).filter_by(entity_id=entity_id).one().entity_type == "candidate"


def test_duplicate_check_ignores_email_case_and_phone_formatting(db, ceo):
    from app.services.candidate_service import find_duplicate_candidate

    candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"Mixed.Case{uid()}@Example.com",
                          candidatePassword="h", candidateFirstName="Ana", candidateLastName="Silva",
                          candidateMobile=f"+91 98{uid()[:3].translate(str.maketrans('abcdef', '123456'))}5 43210")
    db.add(candidate)
    db.commit()
    by_email, matched_on = find_duplicate_candidate(db, email=candidate.candidateEmail.upper())
    assert by_email.candidateID == candidate.candidateID and matched_on == "email"
    digits = "+" + "".join(ch for ch in candidate.candidateMobile if ch.isdigit())
    by_phone, matched_on = find_duplicate_candidate(db, mobile=digits)
    assert by_phone.candidateID == candidate.candidateID and matched_on == "phone"
    assert find_duplicate_candidate(db, mobile="12345") == (None, None)


# ---- no model: an email about someone we know is still filed by its addresses ---------------

def test_without_the_llm_a_forward_from_a_known_candidate_goes_on_their_profile(db, ceo):
    existing = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"joss{uid()}@example.com",
                         candidatePassword="h", candidateFirstName="Joss", candidateLastName="S")
    db.add(existing)
    db.commit()
    body = forwarded_body("FYI", "Joss S", existing.candidateEmail, "Would BlitzenX consider an MD title?")
    row, mailbox = received_forward(db, ceo, body, subject="Fwd: Re: Director | Technical Client Partner")
    result, _ = run_handler(db, row.id, mailbox)  # the model is down
    assert result["status"] == "processed" and result["candidate_id"] == existing.candidateID
    assert db.query(Task).filter_by(candidate_id=existing.candidateID, category="MAILBOX_INTAKE").count() == 0


def test_without_the_llm_a_forward_from_a_client_contact_goes_on_the_client(db, ceo):
    from app.models.client import Client, ClientContact, ClientEmail

    client = Client(tenant_id=1, company_name=f"Carrier {uid()}", website=f"carrier{uid()}.com")
    db.add(client)
    db.flush()
    db.add(ClientContact(client_id=client.id, name="Pat", email=f"pat@{client.website}", role_type="PRIMARY"))
    db.commit()
    body = forwarded_body("See below", "Pat", f"pat@{client.website}", "Can we start the inception in December?")
    row, mailbox = received_forward(db, ceo, body, subject="Fwd: inception")
    result, _ = run_handler(db, row.id, mailbox)
    assert result["status"] == "processed" and result["client_ids"] == [client.id]
    logged = db.query(ClientEmail).filter_by(client_id=client.id).one()
    assert logged.direction == "IN" and logged.sent_by_user_id == ceo.UserID


def test_a_reply_about_a_role_from_a_known_candidate_is_filed_on_them_not_left_as_a_job(db, ceo):
    """Job words ('Director | Technical Client Partner') in a known candidate's thread: their profile."""
    existing = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"joss{uid()}@example.com",
                         candidatePassword="h", candidateFirstName="Joss", candidateLastName="S")
    db.add(existing)
    db.commit()
    body = forwarded_body("FYI", "Joss S", existing.candidateEmail,
                          "Thanks for the details on the Director | Technical Client Partner role and job description.")
    row, mailbox = received_forward(db, ceo, body, subject="Fwd: Re: Director | Technical Client Partner | BlitzenX")
    result, _ = run_handler(db, row.id, mailbox)
    assert result["status"] == "processed" and result["candidate_id"] == existing.candidateID


JOBDIVA_ALERT_HTML = """<p>Hello Avinash M,<br>Following is the list of Licenses/Certifications that are already expired
or scheduled to expire:</p><table><tr><td colspan=6>Expiring in 6 months</td></tr>
<tr><td>Candidate</td><td>License/Certification</td><td>State</td><td>Country</td>
<td>License/Certification #</td><td>Expiry Date</td></tr>
<tr><td><a href="#">Aniket Kamalakar Magar</a></td><td>Ace Guidewire</td><td></td><td></td>
<td>Associate Certified Palisades</td><td>30/04/2027</td></tr>
<tr><td>Unknown Person</td><td>Ace Guidewire</td><td></td><td></td><td>X1</td><td>01/02/2027</td></tr></table>"""


def test_a_certification_expiry_alert_is_recorded_on_the_employee_with_a_renewal_task(db, ceo):
    """CEO 2026-11-02: JobDiva's 'List of expiring Licenses and Certifications' for current employees."""
    from app.models.certification import Certification, EmployeeCertification
    from app.models.employee import Employee

    employee = Employee(tenant_id=1, first_name="Aniket", last_name="Magar", email=f"aniket{uid()}@blitzenx.com",
                        joining_date=date(2025, 1, 6))
    db.add(employee)
    db.commit()
    body = "Hello Avinash M,\nFollowing is the list of Licenses/Certifications that are already expired or scheduled to expire:"
    row, mailbox = received_forward(db, ceo, body, subject="FW: List of expiring Licenses and Certifications")
    mailbox.get_message_html = lambda message_id: JOBDIVA_ALERT_HTML
    result, _ = run_handler(db, row.id, mailbox)
    assert result["status"] == "processed" and result["unmatched"] == ["Unknown Person"]
    record = db.query(EmployeeCertification).filter_by(employee_id=employee.id).one()
    cert = db.query(Certification).filter_by(id=record.certification_id).one()
    assert cert.cert_name == "Ace Guidewire" and record.cert_number == "Associate Certified Palisades"
    assert record.expires_date == datetime(2027, 4, 30) and record.status == "Active"
    renew = db.query(Task).filter(Task.title.like("Renew Ace Guidewire for Aniket Magar%")).one()
    assert renew.due_date == datetime(2027, 4, 30) - timedelta(days=60) and renew.link == f"/employees/{employee.id}"
    assert db.query(Task).filter(Task.title.like("Certification alert: 1 person%")).count() == 1


# ---- a Teams meeting set up with a candidate (CEO 2026-11-03: "a meeting was setup but the system didnt
# create a candidate and thunder didnt autonomously start working on mapping the interview") ----------

class MeetingMailbox(FakeMailbox):
    """A meeting request the CEO sent to the candidate and a partner, the helpdesk copied."""

    def __init__(self, inbox, bodies, attachments, to, meeting):
        super().__init__(inbox, bodies, attachments)
        self.to, self.meeting = to, meeting

    def get_message(self, message_id):
        return {**super().get_message(message_id), "toRecipients": self.to}

    def get_meeting(self, message_id):
        return self.meeting


def test_a_meeting_with_a_candidate_creates_the_candidate_and_the_scheduled_interview(db, ceo, storage):
    from app.models.user import Interview, PanelMember

    troy = staff(db, name="Troy Towsley")
    # the PDF's text layer splits the address ("shivaprasadadluri03 | @gmail.com") and opens with "Email:"
    resume = file_attachment("ShivaPrasadAdluri-Digital_Core_ACE_Certified.pdf",
                             pdf_bytes("Email: shivaprasadadluri03 | @gmail.com ShivaPrasad Adluri Ph: 216-212-9887"))
    body = ("Hello Shiva, Scheduling time to discuss with my partner Troy Towsley regarding the roles we discussed.\n"
            "I am ShivaPrasad Adluri, Sr Guidewire Developer.\n"
            "Microsoft Teams meeting Join: https://teams.microsoft.com/meet/473154335567838?p=wlJF8b2PGU")
    row, plain = received_forward(db, ceo, body, [resume], subject="ShivaPrasad Adluri | Troy Towsley")
    to = [{"emailAddress": {"name": "Shiva Adluri", "address": "shivaprasadadluri03@gmail.com"}},
          {"emailAddress": {"name": "Troy Towsley", "address": troy.UserEmail}}]
    mailbox = MeetingMailbox(plain.inbox, plain.bodies, plain.attachments, to,
                             {"start": "2026-11-04T18:30:00.0000000", "end": "2026-11-04T19:00:00.0000000",
                              "location": "Microsoft Teams Meeting", "type": "meetingRequest"})

    result, queued = run_handler(db, row.id, mailbox)  # no model: rules only
    assert result["status"] == "candidate_queued", result
    create = next(q for q in queued if q["task_name"] == "create_candidate")["data"]
    assert "shivaprasadadluri03@gmail.com" in json.dumps(create).lower()  # from the To line and the rejoined resume
    created = run_creation(db, queued)
    result, queued = run_handler(db, row.id, mailbox)
    assert result["status"] == "processed", result
    candidate = db.query(Candidate).filter_by(candidateID=created["candidate_id"]).one()
    assert (candidate.candidateFirstName, candidate.candidateLastName) == ("ShivaPrasad", "Adluri")
    interview = db.query(Interview).filter_by(candidate_id=candidate.candidateID).one()
    assert (interview.status, interview.start_time) == ("Scheduled", datetime(2026, 11, 4, 18, 30))
    assert interview.meeting_link.startswith("https://teams.microsoft.com/meet/")
    assert {m.interviewer_id for m in db.query(PanelMember).filter_by(panel_id=interview.panel_id)} == \
        {ceo.UserID, troy.UserID}
    assert any(q["task_name"] == "interview_scheduled" for q in queued)  # Thunder and the pipeline follow
    # the same meeting read again records nothing new
    db.query(MailboxIntakeMessage).filter_by(id=row.id).update({"status": "CANDIDATE_QUEUED"})
    db.commit()
    run_handler(db, row.id, mailbox)
    assert db.query(Interview).filter_by(candidate_id=candidate.candidateID).count() == 1


# ---- reaching out (CEO 2026-11-09: "Tried reaching you" to one outside person, HRMS copied, made no candidate) ----

OUTREACH_BODY = ("Hello Apeksha,\n\nHope you are doing well, tried reaching you regarding a potential opportunity. "
                 "Let me know a good time for us to connect and discuss the opportunity in detail.\n\nThanks\nAvinash")


def _outreach(db, ceo, address, body=OUTREACH_BODY, name=None):
    row, plain = received_forward(db, ceo, body, subject="Tried Reaching you")
    to = [{"emailAddress": {"name": name or address, "address": address}}]
    return row, MeetingMailbox(plain.inbox, plain.bodies, plain.attachments, to, None)


def test_an_email_to_one_outside_person_creates_them_as_a_candidate(db, ceo):
    row, mailbox = _outreach(db, ceo, "apeksha.suvarna@gmail.com")
    result, queued = run_handler(db, row.id, mailbox)  # no model: rules only, like production
    assert result["status"] == "candidate_queued", result
    created = run_creation(db, queued)
    candidate = db.query(Candidate).filter_by(candidateID=created["candidate_id"]).one()
    assert (candidate.candidateFirstName, candidate.candidateLastName) == ("Apeksha", "Suvarna")
    assert candidate.candidateEmail == "apeksha.suvarna@gmail.com"


def test_the_recipients_display_name_is_used_when_it_has_both_names(db, ceo):
    row, mailbox = _outreach(db, ceo, "apeksha.s123@gmail.com", name="Apeksha Suvarna")
    result, queued = run_handler(db, row.id, mailbox)
    assert result["status"] == "candidate_queued", result
    created = run_creation(db, queued)
    candidate = db.query(Candidate).filter_by(candidateID=created["candidate_id"]).one()
    assert (candidate.candidateFirstName, candidate.candidateLastName) == ("Apeksha", "Suvarna")


def test_an_address_without_a_last_name_asks_the_sender(db, ceo):
    row, mailbox = _outreach(db, ceo, "apeksha1990@gmail.com")
    result, _ = run_handler(db, row.id, mailbox)
    assert result["status"] == "needs_review" and "last name" in result["reason"]


def test_an_email_to_an_employee_is_not_a_new_candidate(db, ceo):
    from datetime import date as day

    from app.models.employee import Employee

    db.add(Employee(tenant_id=1, first_name="Apeksha", last_name="S", email=f"e{uid()}@blitzenx.com",
                    personal_email="apeksha.suvarna@gmail.com", joining_date=day(2026, 1, 1), status="ACTIVE"))
    db.commit()
    row, mailbox = _outreach(db, ceo, "apeksha.suvarna@gmail.com")
    result, queued = run_handler(db, row.id, mailbox)
    assert not any(q["task_name"] == "create_candidate" for q in queued)
    db.refresh(row)
    assert row.kind == "EMPLOYEE_NOTE"


@pytest.mark.parametrize("address,greeting,expected", [
    ("apeksha.suvarna@gmail.com", "Apeksha", ("Apeksha", "Suvarna")),
    ("jane_doe@x.com", None, ("Jane", "Doe")),
    ("jane.m.doe@x.com", "jane", ("Jane", "Doe")),
    ("apeksha.suvarna@gmail.com", "Priya", (None, None)),  # the greeting names someone else
    ("apeksha1990@gmail.com", None, (None, None)),
    ("a.suvarna@gmail.com", None, (None, None)),  # an initial is not a first name
])
def test_a_name_from_an_address(address, greeting, expected):
    from app.services.thunder_mail.forward_classifier import name_from_address

    assert name_from_address(address, greeting) == expected


# ---- set-aside emails looked at again (CEO 2026-11-09: Apeksha was added by hand after her email was set aside) ----

class OnceQueue:
    """The queue's deterministic task id is its primary key: the same key is queued once."""

    def __init__(self):
        self.ids = []

    def __call__(self, task_name, task_id, data, tenant_id, delay_seconds=0):
        if task_id in self.ids:
            return False
        self.ids.append(task_id)
        return True


def _set_aside(db, ceo, address):
    row, mailbox = _outreach(db, ceo, address, body="Thoughts on this?", name="Someone")
    with patch("app.services.thunder_mail.forward_intake_service._outreach_to_a_new_person", return_value=False):
        run_handler(db, row.id, mailbox)  # as before the outreach rule: set aside
    db.refresh(row)
    assert row.status == "IGNORED"
    return row, mailbox


def test_a_set_aside_email_is_filed_once_its_person_is_added(db, ceo):
    from app.services.thunder_mail.forward_intake_service import recheck_set_aside

    row, mailbox = _set_aside(db, ceo, "apeksha.suvarna@gmail.com")
    queue = OnceQueue()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", queue):
        assert recheck_set_aside(db)["refiled"] == 0  # still nobody we know
        candidate = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Apeksha", candidateLastName="Suvarna",
                              candidateEmail="apeksha.suvarna@gmail.com", tenant_id=1, candidatePassword="x")
        db.add(candidate)  # added by hand
        db.commit()
        assert recheck_set_aside(db)["refiled"] == 1
        assert queue.ids == [f"thunder_forward:{row.id}:recheck"]
        result, _ = run_handler(db, row.id, mailbox)  # the queued re-read files it on her profile
        assert result["status"] in ("processed", "candidate_queued"), result
        db.refresh(row)
        assert row.candidate_id == candidate.candidateID
        assert recheck_set_aside(db)["refiled"] == 0  # filed: never again
    assert db.query(Candidate).filter(func.lower(Candidate.candidateEmail) == "apeksha.suvarna@gmail.com").count() == 1


def test_an_email_older_than_the_window_is_left_alone(db, ceo):
    from app.services.thunder_mail.forward_intake_service import RECHECK_WINDOW, recheck_set_aside

    row, _ = _set_aside(db, ceo, "late.person@gmail.com")
    db.query(MailboxIntakeMessage).filter_by(id=row.id).update(
        {"received_at": datetime.utcnow() - RECHECK_WINDOW - timedelta(days=1)})
    db.add(Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Late", candidateLastName="Person",
                     candidateEmail="late.person@gmail.com", tenant_id=1, candidatePassword="x"))
    db.commit()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", OnceQueue()):
        assert recheck_set_aside(db)["refiled"] == 0


def test_a_set_aside_email_queued_once_is_not_queued_again(db, ceo):
    from app.services.thunder_mail.forward_intake_service import recheck_set_aside

    row, _ = _set_aside(db, ceo, "twice.checked@gmail.com")
    db.add(Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Twice", candidateLastName="Checked",
                     candidateEmail="twice.checked@gmail.com", tenant_id=1, candidatePassword="x"))
    db.commit()
    queue = OnceQueue()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", queue):
        assert recheck_set_aside(db)["refiled"] == 1
        db.query(MailboxIntakeMessage).filter_by(id=row.id).update({"status": "IGNORED"})  # say its filing failed
        db.commit()
        assert recheck_set_aside(db)["refiled"] == 0
    db.refresh(row)
    assert row.status == "IGNORED" and len(queue.ids) == 1

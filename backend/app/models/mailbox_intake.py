"""An email a staff member forwarded to the HRMS mailbox (settings.THUNDER_MAILBOX).

One row per Graph message (unique per mailbox), so a message is never acted on
twice, however often the poll overlaps. app.services.thunder_mail.forward_intake_service
moves it RECEIVED -> CANDIDATE_QUEUED (a new candidate is being created) ->
PROCESSED, or to NEEDS_REVIEW (a task was opened for a person).
"""
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.models.base import Base

INTAKE_STATUSES = ("RECEIVED", "CANDIDATE_QUEUED", "PROCESSED", "NEEDS_REVIEW")
INTAKE_KINDS = ("NEW_CANDIDATE", "CANDIDATE_UPDATE", "JOB_REQUIREMENT", "EMPLOYEE_NOTE", "OTHER")


class MailboxIntakeMessage(Base):
    __tablename__ = "mailbox_intake_messages"
    __table_args__ = (UniqueConstraint("mailbox", "graph_message_id", name="uq_mailbox_intake_graph_id"),)

    id = Column(String(36), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    mailbox = Column(String(320), nullable=False)
    graph_message_id = Column(String(512), nullable=False)
    internet_message_id = Column(String(998), nullable=True)
    from_address = Column(String(320), nullable=False)
    forwarded_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False, index=True)
    subject = Column(String(998), nullable=True)
    received_at = Column(DateTime, nullable=True)

    status = Column(String(20), nullable=False, default="RECEIVED", index=True)
    kind = Column(String(20), nullable=True)
    classifier_source = Column(String(16), nullable=True)  # llm / rule
    confidence = Column(Float, nullable=True)
    # What was read from the email: the forwarder's text, the original sender, the candidate's
    # details, the resume attachment's id/name and parsed text (JSON-serializable only)
    extracted = Column(JSON, nullable=True)

    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=True, index=True)
    job_id = Column(String(512), nullable=True)
    employee_id = Column(String(512), nullable=True)
    creation_message_id = Column(String(512), nullable=True)  # the queued create_candidate message
    note_id = Column(Integer, nullable=True)  # internal_notes.id (candidate) or activity_timeline.id
    document_id = Column(Integer, nullable=True)  # candidate_documents.id of the attached resume
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    review_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)

"""A reply the system drafted to a candidate's email, waiting for a person's approval (CEO 2026-11-02:
"the system has to process these emails on its own and get related user approval").

One open draft per candidate: a newer reply supersedes the older draft. Approving queues the email
through Thunder (step REPLY-<id>, threaded under the candidate's email); discarding closes it.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

REPLY_DRAFT_STATUSES = ("DRAFT", "APPROVED", "SENT", "DISCARDED")


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    # the candidate's email this answers (the reply is threaded under it)
    in_message_id = Column(String(36), ForeignKey("thunder_email_messages.id"), nullable=False)
    intent = Column(String(32), nullable=True)
    subject = Column(String(998), nullable=False)
    body_html = Column(Text, nullable=False)
    composed_by = Column(String(16), nullable=False)  # "claude" / "rules"
    status = Column(String(16), nullable=False, default="DRAFT", index=True)  # REPLY_DRAFT_STATUSES
    note = Column(String(512), nullable=True)
    decided_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    thunder_message_id = Column(String(36), ForeignKey("thunder_email_messages.id"), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

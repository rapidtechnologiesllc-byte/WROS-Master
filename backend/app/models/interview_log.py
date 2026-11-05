"""An interview that already happened, logged after the fact (CEO 2026-11-02: "Log interview isnt
working as expected, I pasted the meeting recording but nothing is showing up" / "should also ask for
Interview Date, Interview Type, Panel Members, Meeting Platform, attach field where i can upload the
word document of the transcript").

The interview itself is an ordinary Interview (status Completed) on its own panel, with the logging
interviewer's InterviewFeedback; this row keeps what a logged interview has beside that: how it was
held, its transcript (pasted or read from a Word document) and the summary, and whether the
candidate's 5+ years were unverified when it was logged (it is recorded anyway -- it happened -- and
the existing experience gates still stop an offer or a client submission until it is verified).
"""
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

MEETING_PLATFORMS = ("Teams", "Zoom", "Google Meet", "Phone", "In person", "Other")


class InterviewLog(Base):
    __tablename__ = "interview_logs"

    interview_id = Column(Integer, ForeignKey("interviews.id"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    meeting_platform = Column(String(32), nullable=False)
    transcript_text = Column(Text, nullable=True)
    transcript_file_name = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    # Claude's suggested recommendation from the transcript; the interviewer's pick is the record
    suggested_recommendation = Column(String(20), nullable=True)
    summary_by = Column(String(16), nullable=True)  # "interviewer" / "claude"
    analysis = Column(JSON, nullable=True)  # Claude's scores and recommendation (interview_transcript_service)
    experience_unverified = Column(Boolean, nullable=False, default=False, server_default="false")
    experience_note = Column(String(512), nullable=True)
    logged_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

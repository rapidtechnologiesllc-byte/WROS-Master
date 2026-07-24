"""
S-028/HRMS-0428 -- Resume Parsing Engine.

candidate_resume_parsed: a genuinely new table (not reusable via
ConversationEvent, unlike most stories this round) -- structured
resume data (work history, education, skills, certifications) is
substantial, queryable, and needs its own JSON columns; there is no
existing structure this fits into.

Integer-autoincrement PK + String(50) UserID-as-tenant_id convention,
matching every other real table added this round, not the spec's UUID
assumption.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func

from app.models.base import Base

PARSER_VERSION = "1.0"


class CandidateResumeParsed(Base):
    __tablename__ = "candidate_resume_parsed"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    raw_text = Column(Text, nullable=True)
    full_name = Column(String(200), nullable=True)
    email = Column(String(300), nullable=True)
    phone = Column(String(50), nullable=True)
    current_title = Column(String(200), nullable=True)
    current_employer = Column(String(200), nullable=True)

    work_history = Column(JSON, nullable=True)
    education = Column(JSON, nullable=True)
    skills = Column(JSON, nullable=True)
    certifications = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)

    total_experience_months = Column(Integer, nullable=True)
    total_experience_years = Column(Float, nullable=True)

    parsed_at = Column(DateTime(timezone=False), server_default=func.now())
    parser_version = Column(String(20), nullable=False, server_default=PARSER_VERSION)

"""
Career Site Models - Public job listings and applications

This module provides models for the public career site (port 3001):
- CareerJob: Public job listings (synced from internal opportunities)
- CareerApplication: External candidate applications
- CareerResumeAnalysis: Thunder AI resume analysis against JD
- CareerClarification: AI-generated clarification questions

No authentication required (public candidates). Separate from internal WROS.
"""
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean, JSON, ForeignKey, func, Float
from app.models.base import Base
import uuid


def _new_uuid() -> str:
    return str(uuid.uuid4())


class CareerJob(Base):
    """Public job listing (visible to external candidates on career site)"""
    __tablename__ = "career_jobs"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, nullable=True, index=True)  # Career site is public, but track tenant

    # Link to internal opportunity/demand
    opportunity_id = Column(String(36), nullable=True, index=True)  # From WROS opportunities table
    demand_id = Column(String(36), nullable=True, index=True)      # From WROS demands table

    # Job details
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    skills_required = Column(JSON, nullable=True)  # List of skills {skill, years_required, level}
    experience_years_required = Column(Integer, nullable=True)
    location = Column(String(200), nullable=True)
    salary_range_min_usd_cents = Column(Integer, nullable=True)
    salary_range_max_usd_cents = Column(Integer, nullable=True)

    # Status
    is_published = Column(Boolean, default=True, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)


class CareerApplication(Base):
    """External candidate application to a job"""
    __tablename__ = "career_applications"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # Job reference
    career_job_id = Column(String(36), ForeignKey("career_jobs.id"), nullable=False, index=True)

    # Candidate info (no internal candidate record yet)
    candidate_email = Column(String(300), nullable=False, index=True)
    candidate_name = Column(String(200), nullable=True)
    candidate_phone = Column(String(50), nullable=True)

    # Resume
    resume_file_path = Column(String(500), nullable=True)
    resume_text = Column(Text, nullable=True)  # Extracted text for analysis
    resume_uploaded_at = Column(DateTime, nullable=True)

    # Application status
    status = Column(String(50), default="PENDING", index=True)  # PENDING, UNDER_REVIEW, CLARIFICATION_NEEDED, APPROVED, REJECTED

    # Resume analysis results
    overall_fit_score = Column(Float, nullable=True)  # 0-100 from Thunder analysis

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CareerResumeAnalysis(Base):
    """Thunder AI analysis of resume vs job description"""
    __tablename__ = "career_resume_analysis"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # References
    career_application_id = Column(String(36), ForeignKey("career_applications.id"), nullable=False, index=True)
    career_job_id = Column(String(36), ForeignKey("career_jobs.id"), nullable=False, index=True)

    # Analysis results
    overall_fit_score = Column(Float, nullable=True)  # 0-100
    skills_matched = Column(JSON, nullable=True)  # [{"skill": "Java", "required_years": 5, "has_years": 2, "match": false}]
    experience_gap = Column(JSON, nullable=True)  # {"required": 5, "has": 2, "gap": 3}

    # AI-generated assessment
    ai_assessment = Column(Text, nullable=True)  # Raw Thunder assessment
    gaps_identified = Column(JSON, nullable=True)  # List of gaps
    has_critical_gaps = Column(Boolean, default=False)  # True if gaps that need clarification

    # Tags for recruiter review
    tags = Column(JSON, default=list)  # ["needs_clarification", "overqualified", "meets_requirements", etc]

    analyzed_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())


class CareerConversation(Base):
    """Relationship-building conversation responses (pre-resume stage)"""
    __tablename__ = "career_conversations"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # References
    career_application_id = Column(String(36), ForeignKey("career_applications.id"), nullable=True, index=True)
    candidate_email = Column(String(300), nullable=False, index=True)

    # Conversation data
    question_index = Column(Integer, nullable=False)  # 0-4 for 5 questions
    question_text = Column(Text, nullable=False)
    candidate_response = Column(Text, nullable=True)

    # Metadata
    conversation_summary = Column(JSON, nullable=True)  # All responses {0: "answer", 1: "answer", ...}
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CareerClarification(Base):
    """AI-generated clarification questions for gaps in resume vs JD"""
    __tablename__ = "career_clarifications"

    id = Column(String(36), primary_key=True, default=_new_uuid)

    # References
    career_application_id = Column(String(36), ForeignKey("career_applications.id"), nullable=False, index=True)
    career_resume_analysis_id = Column(String(36), ForeignKey("career_resume_analysis.id"), nullable=False, index=True)

    # Clarification details
    gap_type = Column(String(100), nullable=False)  # "experience", "skill", "certification", etc
    gap_description = Column(Text, nullable=True)  # "JD requires 5 years Java, resume shows 2 years"

    ai_question = Column(Text, nullable=False)  # The actual question for candidate
    suggested_answers = Column(JSON, nullable=True)  # Suggested responses for candidate to choose from

    # Candidate response
    candidate_response = Column(Text, nullable=True)
    response_received_at = Column(DateTime, nullable=True)

    # Assessment
    response_assessment = Column(Text, nullable=True)  # Thunder's evaluation of the response
    satisfies_gap = Column(Boolean, nullable=True)  # Does response address the gap?

    status = Column(String(50), default="PENDING", index=True)  # PENDING, ANSWERED, ASSESSED

    created_at = Column(DateTime, server_default=func.now())
    answered_at = Column(DateTime, nullable=True)
    assessed_at = Column(DateTime, nullable=True)

"""Job metadata for SLM learning (app.services.slm_job_metadata_service).

Declared here, in app.models, so that importing app.models registers the table with Base.metadata
and every Base.metadata.create_all (startup's db_contract, the test suite's schema) creates it.
It used to live in the service module, where only an explicit import in db_contract registered it.

job_id has no foreign key: the row is written when the job is queued, before job_created_flash
creates the Jobs row."""
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func

from app.models.base import Base


class SLMJobMetadata(Base):
    """Track job metadata for ML learning."""
    __tablename__ = "slm_job_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(50), nullable=False, unique=True, index=True)
    job_title = Column(String(255), nullable=False)
    job_description = Column(Text, nullable=True)
    business_unit_id = Column(Integer, nullable=True, index=True)
    department = Column(String(100), nullable=True)

    # Skills and requirements
    required_skills = Column(JSON, nullable=True)  # Array of skill names
    min_experience_months = Column(Integer, nullable=True)
    max_experience_months = Column(Integer, nullable=True)

    # Hiring outcomes (updated when candidates complete the hiring journey)
    candidates_submitted = Column(Integer, default=0)  # Total submitted
    candidates_interviewed = Column(Integer, default=0)  # Passed interview
    candidates_offered = Column(Integer, default=0)  # Received offer
    candidates_hired = Column(Integer, default=0)  # Accepted offer

    # Success metrics
    time_to_hire_avg = Column(Integer, nullable=True)  # Days
    offer_acceptance_rate = Column(Float, nullable=True)  # 0-1
    interview_to_offer_rate = Column(Float, nullable=True)  # 0-1

    # Metadata
    created_by = Column(String(50), nullable=True)  # User who created job
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Quality metrics for Thunder's learning
    match_quality_score = Column(Float, nullable=True)  # 0-100, computed from outcomes
    total_candidates_matched = Column(Integer, default=0)  # By Thunder AI
    total_candidates_hired = Column(Integer, default=0)  # From matches, final outcome

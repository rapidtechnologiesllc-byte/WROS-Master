"""
import logging
SLM Job Metadata Service

Stores job metadata for continuous improvement of Thunder's job-matching ML model.

When jobs are created/updated, this service captures:
- Job title
- Job description
- Business unit
- Department
- Skills required
- Experience requirements
- Salary range
- Hiring outcomes (for feedback loop)

This improves Thunder's ability to match candidates to jobs over time.

Usage:
    from app.services.slm_job_metadata_service import store_job_metadata

    store_job_metadata(
        job_id="job-123",
        job_title="Senior Engineer",
        job_description="...",
        business_unit_id=1,
        created_by="user-123"
    )
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Float, JSON, func, Text
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.base import Base

logger = logging.getLogger(__name__)

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

class SLMJobMetadataService:
    """Service for storing and retrieving job metadata."""

    @staticmethod
    def store_job_metadata(
        db: Session,
        job_id: str,
        job_title: str,
        job_description: Optional[str] = None,
        business_unit_id: Optional[int] = None,
        department: Optional[str] = None,
        required_skills: Optional[list] = None,
        min_experience_months: Optional[int] = None,
        max_experience_months: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> bool:
        """
        Store job metadata for ML learning.

        Args:
            db: Database session
            job_id: Job ID
            job_title: Job title
            job_description: Full job description
            business_unit_id: BU ID (for BU-specific patterns)
            department: Department name
            required_skills: List of required skills
            min_experience_months: Minimum experience required
            max_experience_months: Maximum experience level
            created_by: User ID who created the job

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if job metadata already exists
            existing = db.query(SLMJobMetadata).filter(
                SLMJobMetadata.job_id == job_id
            ).first()

            if existing:
                # Update existing
                existing.job_title = job_title
                if job_description:
                    existing.job_description = job_description
                if business_unit_id:
                    existing.business_unit_id = business_unit_id
                if department:
                    existing.department = department
                if required_skills:
                    existing.required_skills = required_skills
                if min_experience_months:
                    existing.min_experience_months = min_experience_months
                if max_experience_months:
                    existing.max_experience_months = max_experience_months
                existing.updated_at = datetime.utcnow()

                logger.info(f"Updated job metadata: {job_id} ({job_title})")
            else:
                # Create new
                job_metadata = SLMJobMetadata(
                    job_id=job_id,
                    job_title=job_title,
                    job_description=job_description,
                    business_unit_id=business_unit_id,
                    department=department,
                    required_skills=required_skills,
                    min_experience_months=min_experience_months,
                    max_experience_months=max_experience_months,
                    created_by=created_by,
                    created_at=datetime.utcnow(),
                )
                db.add(job_metadata)

                logger.info(f"Stored job metadata: {job_id} ({job_title})")

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to store job metadata: {str(e)}", exc_info=True)
            db.rollback()
            raise ValueError(f"Failed to store job metadata: {str(e)}")

    @staticmethod
    def record_hiring_outcome(
        db: Session,
        job_id: str,
        candidate_submitted: bool = False,
        candidate_interviewed: bool = False,
        candidate_offered: bool = False,
        candidate_hired: bool = False,
    ) -> bool:
        """
        Update hiring outcomes for a job.

        Called when candidates progress through the hiring pipeline.

        Args:
            db: Database session
            job_id: Job ID
            candidate_submitted: Whether a candidate was submitted
            candidate_interviewed: Whether a candidate passed interview
            candidate_offered: Whether a candidate received offer
            candidate_hired: Whether a candidate accepted offer

        Returns:
            True if successful
        """
        try:
            job_metadata = db.query(SLMJobMetadata).filter(
                SLMJobMetadata.job_id == job_id
            ).first()

            if not job_metadata:
                logger.warning(f"Job metadata not found: {job_id}")
                return False

            if candidate_submitted:
                job_metadata.candidates_submitted += 1
            if candidate_interviewed:
                job_metadata.candidates_interviewed += 1
            if candidate_offered:
                job_metadata.candidates_offered += 1
            if candidate_hired:
                job_metadata.candidates_hired += 1

            # Calculate rates
            if job_metadata.candidates_submitted > 0:
                job_metadata.interview_to_offer_rate = (
                    job_metadata.candidates_offered / job_metadata.candidates_interviewed
                    if job_metadata.candidates_interviewed > 0 else 0
                )

            if job_metadata.candidates_offered > 0:
                job_metadata.offer_acceptance_rate = (
                    job_metadata.candidates_hired / job_metadata.candidates_offered
                )

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to record hiring outcome: {str(e)}", exc_info=True)
            db.rollback()
            raise ValueError(f"Failed to record outcome: {str(e)}")

    @staticmethod
    def get_job_metadata(db: Session, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job metadata (no confidential salary information)."""
        try:
            job_metadata = db.query(SLMJobMetadata).filter(
                SLMJobMetadata.job_id == job_id
            ).first()

            if not job_metadata:
                return None

            return {
                "job_id": job_metadata.job_id,
                "job_title": job_metadata.job_title,
                "business_unit_id": job_metadata.business_unit_id,
                "department": job_metadata.department,
                "required_skills": job_metadata.required_skills,
                "min_experience_months": job_metadata.min_experience_months,
                "max_experience_months": job_metadata.max_experience_months,
                "candidates_submitted": job_metadata.candidates_submitted,
                "candidates_interviewed": job_metadata.candidates_interviewed,
                "candidates_offered": job_metadata.candidates_offered,
                "candidates_hired": job_metadata.candidates_hired,
                "interview_to_offer_rate": job_metadata.interview_to_offer_rate,
                "offer_acceptance_rate": job_metadata.offer_acceptance_rate,
            }

        except Exception as e:
            logger.error(f"Failed to get job metadata: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to get job metadata: {str(e)}")

    @staticmethod
    def get_top_performing_jobs(
        db: Session,
        business_unit_id: Optional[int] = None,
        limit: int = 10
    ) -> list:
        """
        Get top performing jobs by hire rate.

        Useful for Thunder to learn which job types have best match rates.
        """
        try:
            query = db.query(SLMJobMetadata).filter(
                SLMJobMetadata.candidates_hired > 0
            )

            if business_unit_id:
                query = query.filter(SLMJobMetadata.business_unit_id == business_unit_id)

            # Sort by hire rate (descending)
            jobs = query.order_by(
                SLMJobMetadata.candidates_hired.desc()
            ).limit(limit).all()

            return [
                {
                    "job_id": job.job_id,
                    "job_title": job.job_title,
                    "candidates_hired": job.candidates_hired,
                    "candidates_submitted": job.candidates_submitted,
                    "offer_acceptance_rate": job.offer_acceptance_rate,
                }
                for job in jobs
            ]

        except Exception as e:
            logger.error(f"Failed to get top jobs: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to get top jobs: {str(e)}")

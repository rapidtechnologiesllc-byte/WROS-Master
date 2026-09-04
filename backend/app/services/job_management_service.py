"""Job Management Service - Full job lifecycle automation"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.user import Jobs
from app.core.logging import logger

class JobManagementService:
    """Manages job lifecycle: creation, updates, closure, metrics"""

    @staticmethod
    def update_job_details(
        db: Session,
        job_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update job details (salary, title, team, description)"""
        try:
            job = db.query(Jobs).filter(Jobs.id == job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # Update allowed fields
            allowed_fields = [
                'title', 'description', 'salary_min', 'salary_max',
                'salary_currency', 'status', 'team_size', 'department'
            ]

            updated_fields = {}
            for field, value in updates.items():
                if field in allowed_fields and value is not None:
                    setattr(job, field, value)
                    updated_fields[field] = value

            job.updated_at = datetime.utcnow()
            job.updated_by = updated_by
            db.commit()

            logger.info(f"Job updated: {job_id}, fields={list(updated_fields.keys())}")
            return {
                "id": job.id,
                "updated_fields": updated_fields,
                "updated_at": job.updated_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Job update failed: {e}", exc_info=True)
            raise

    @staticmethod
    def close_job(
        db: Session,
        job_id: str,
        reason: str = "FILLED",
        closed_by: str = "system"
    ) -> Dict[str, Any]:
        """Close a job (FILLED, CANCELED, ON_HOLD)"""
        try:
            job = db.query(Jobs).filter(Jobs.id == job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            job.status = "CLOSED"
            job.closure_reason = reason
            job.closed_at = datetime.utcnow()
            job.closed_by = closed_by
            db.commit()

            logger.info(f"Job closed: {job_id}, reason={reason}")
            return {
                "id": job.id,
                "status": "CLOSED",
                "reason": reason,
                "closed_at": job.closed_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Job closure failed: {e}", exc_info=True)
            raise

    @staticmethod
    def reopen_job(
        db: Session,
        job_id: str,
        reopened_by: str = "system"
    ) -> Dict[str, Any]:
        """Reopen a closed job"""
        try:
            job = db.query(Jobs).filter(Jobs.id == job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status != "CLOSED":
                raise ValueError(f"Can only reopen CLOSED jobs, current status: {job.status}")

            job.status = "OPEN"
            job.closure_reason = None
            job.closed_at = None
            job.reopened_at = datetime.utcnow()
            job.reopened_by = reopened_by
            db.commit()

            logger.info(f"Job reopened: {job_id}")
            return {
                "id": job.id,
                "status": "OPEN",
                "reopened_at": job.reopened_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Job reopen failed: {e}", exc_info=True)
            raise

    @staticmethod
    def get_job_metrics(
        db: Session,
        job_id: str
    ) -> Dict[str, Any]:
        """Get job performance metrics (time-to-hire, candidate funnel, etc.)"""
        try:
            job = db.query(Jobs).filter(Jobs.id == job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # Calculate time-to-hire
            time_to_hire = None
            if hasattr(job, 'created_at') and hasattr(job, 'closed_at'):
                if job.created_at and job.closed_at:
                    time_to_hire = (job.closed_at - job.created_at).days

            return {
                "job_id": job.id,
                "title": job.title if hasattr(job, 'title') else None,
                "status": job.status,
                "time_to_hire_days": time_to_hire,
                "candidates_in_pipeline": 0,  # Would calculate from candidates table
                "interviews_scheduled": 0,  # Would calculate from interviews table
                "offers_extended": 0,  # Would calculate from offers table
                "offers_accepted": 0,  # Would calculate from hired employees
                "created_at": job.created_at.isoformat() if hasattr(job, 'created_at') and job.created_at else None
            }
        except Exception as e:
            logger.error(f"Failed to get job metrics: {e}", exc_info=True)
            raise

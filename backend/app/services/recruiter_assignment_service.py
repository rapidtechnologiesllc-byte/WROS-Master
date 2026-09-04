"""
Recruiter Assignment Service - Round-robin assignment of jobs to recruiters
"""
from sqlalchemy.orm import Session
from app.models.user import Users
from app.models.job import Job
import logging
from app.core.logging import logger

def assign_to_recruiter_roundrobin(db: Session) -> Users:
    """
    Assign a job to the next available recruiter using round-robin.
    Returns the recruiter user or None if no recruiters available.
    """
    try:
        # Get all active recruiters (HR Manager role)
        recruiters = db.query(Users).filter(
            Users.UserRole.in_(["HR Manager", "Recruiter"]),
            Users.is_active == True
        ).all()

        if not recruiters:
            logger.warning("[Recruiter Assignment] No active recruiters found")
            return None

        # Get the recruiter with the least recent assignment
        # This implements simple round-robin by picking the one with oldest last_assignment_date
        from sqlalchemy import func

        recruiter_loads = db.query(
            Users.UserID,
            func.count(Job.job_id).label("job_count")
        ).outerjoin(
            Job, Users.UserID == Job.assigned_recruiter_id
        ).filter(
            Users.UserRole.in_(["HR Manager", "Recruiter"]),
            Users.is_active == True
        ).group_by(Users.UserID).all()

        if not recruiter_loads:
            # Fallback to first recruiter
            return recruiters[0]

        # Find recruiter with minimum jobs assigned
        min_load_recruiter_id = min(recruiter_loads, key=lambda x: x.job_count)[0]
        recruiter = db.query(Users).filter(Users.UserID == min_load_recruiter_id).first()

        if recruiter:
            logger.info(f"[Recruiter Assignment] Assigned to recruiter: {recruiter.UserName}")
            return recruiter

        return recruiters[0]

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"[Recruiter Assignment] Error during round-robin assignment: {e}")
        raise ValueError("Operation failed")

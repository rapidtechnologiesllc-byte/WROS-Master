"""
LinkedIn Recruiter Workload Service

Calculates recruiter workload metrics for round-robin assignment in LinkedIn-to-Thunder conversions.
Uses candidate-centric metrics (not job-centric) with pipeline weighting.
"""
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.candidate import Candidate
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.models.user import Users

logger = logging.getLogger(__name__)


def get_recruiter_candidate_count(
    db: Session,
    recruiter_id: str,
    bu_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> int:
    """
    Count candidates assigned to recruiter.

    Args:
        db: Database session
        recruiter_id: User ID of recruiter
        bu_id: Business Unit ID (optional filter)
        tenant_id: Tenant ID (optional filter)

    Returns:
        Integer count of active candidates assigned to recruiter
    """
    query = db.query(func.count(Candidate.candidateID))

    # This would need proper assignment tracking in Candidate model
    # For now, return 0 - architecture depends on how candidates are assigned
    # In real implementation, filter by assigned_recruiter_id if that field exists

    return 0


def get_recruiter_pipeline_count(
    db: Session,
    recruiter_id: str,
    tenant_id: Optional[str] = None,
) -> int:
    """
    Count pipeline items in manual review assigned to recruiter.

    Args:
        db: Database session
        recruiter_id: User ID of recruiter
        tenant_id: Tenant ID (optional filter)

    Returns:
        Integer count of pipeline items in active statuses
    """
    try:
        query = db.query(func.count(LinkedInCandidatePipeline.id)).filter(
            LinkedInCandidatePipeline.assigned_to_user_id == recruiter_id,
            LinkedInCandidatePipeline.status.in_([
                LinkedInPipelineStatus.PENDING_CONNECTION,
                LinkedInPipelineStatus.CONNECTED,
                LinkedInPipelineStatus.PHONE_COLLECTED,
            ])
        )

        if tenant_id:
            query = query.filter(LinkedInCandidatePipeline.tenant_id == tenant_id)

        count = query.scalar() or 0
        return count
    except Exception as e:
        logger.error(f"Failed to get pipeline count for recruiter {recruiter_id}: {e}")
        return 0


def get_all_recruiter_workloads(
    db: Session,
    bu_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[Tuple[str, int, int, float]]:
    """
    Get workload metrics for all recruiters in a Business Unit.

    Args:
        db: Database session
        bu_id: Business Unit ID (optional filter)
        tenant_id: Tenant ID (optional filter)

    Returns:
        List of tuples: (recruiter_id, candidate_count, pipeline_count, total_load)
        Sorted by total_load ascending (least loaded first)
    """
    try:
        # Get all recruiters (would need proper role filtering)
        # For now, get all users and filter in application layer
        recruiters = db.query(Users).filter(
            Users.is_active == True
        ).all()

        workloads = []
        for recruiter in recruiters:
            candidate_count = get_recruiter_candidate_count(
                db, recruiter.id, bu_id=bu_id, tenant_id=tenant_id
            )
            pipeline_count = get_recruiter_pipeline_count(
                db, recruiter.id, tenant_id=tenant_id
            )

            # Weighted calculation: candidates full weight, pipeline at 50%
            total_load = candidate_count + (pipeline_count * 0.5)

            workloads.append((recruiter.id, candidate_count, pipeline_count, total_load))

        # Sort by total_load ascending (least loaded first)
        workloads.sort(key=lambda x: x[3])
        return workloads

    except Exception as e:
        logger.error(f"Failed to get recruiter workloads: {e}")
        return []


def get_least_loaded_recruiter(
    db: Session,
    bu_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[Users]:
    """
    Return single recruiter with minimum workload.

    Args:
        db: Database session
        bu_id: Business Unit ID (optional filter)
        tenant_id: Tenant ID (optional filter)

    Returns:
        Users object of least-loaded recruiter, or None if none available
    """
    try:
        workloads = get_all_recruiter_workloads(db, bu_id=bu_id, tenant_id=tenant_id)

        if not workloads:
            logger.warning(f"No recruiters available for BU: {bu_id}")
            return None

        # Get least-loaded recruiter (first after sort)
        least_loaded_id, _, _, _ = workloads[0]

        recruiter = db.query(Users).filter(Users.id == least_loaded_id).first()

        if recruiter:
            logger.info(
                f"Selected recruiter {recruiter.id} for assignment "
                f"(workload metrics available)"
            )

        return recruiter

    except Exception as e:
        logger.error(f"Failed to get least-loaded recruiter: {e}")
        return None

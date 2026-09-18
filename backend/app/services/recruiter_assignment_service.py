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


class RecruiterAssignmentServiceForCandidates:
    """
    Weighted work-average recruiter assignment for candidates.

    Weight formula: (candidates_handled / days_active)
    - Newer recruiters: fewer days_active = higher weight = AVOID
    - Older recruiters with few candidates: lowest weight = ASSIGN FIRST
    - Ensures even distribution, prevents burnout

    CRITICAL: Idempotent - if called twice for same candidate,
    second call returns same recruiter (checks candidate.assigned_recruiter_id first).
    """

    RECRUITER_UNAVAILABLE_ERROR = "No available recruiters (all terminated)"

    @staticmethod
    def assign_recruiter_to_candidate(
        candidate_id: str,
        tenant_id: int,
        db: Session,
        force_reassign: bool = False
    ) -> dict:
        """
        Auto-assign a recruiter to a candidate based on weighted work average.

        Args:
            candidate_id: Candidate to assign recruiter to
            tenant_id: Tenant context
            db: Database session
            force_reassign: If True, ignore existing assignment (breaks idempotency)

        Returns:
            {
                'recruiter_id': str,
                'recruiter_name': str,
                'recruiter_email': str,
                'is_new_assignment': bool,
                'weight': float,
                'candidates_handled': int,
                'days_active': int
            }

        Raises:
            ValueError: Candidate not found
            RuntimeError: No available recruiters (retryable)
        """
        from app.models.candidate import Candidate
        from datetime import datetime

        try:
            # Guard 1: Validate candidate exists
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
                Candidate.tenant_id == tenant_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # Guard 2: Idempotency check
            if candidate.assigned_recruiter_id and not force_reassign:
                recruiter = db.query(Users).filter(
                    Users.UserID == candidate.assigned_recruiter_id
                ).first()
                if recruiter:
                    logger.info(
                        f"[CandidateRecruiterAssignment] Candidate {candidate_id} already assigned to "
                        f"{recruiter.UserID} (idempotent)"
                    )
                    return {
                        'recruiter_id': recruiter.UserID,
                        'recruiter_name': recruiter.UserName,
                        'recruiter_email': recruiter.UserEmail,
                        'is_new_assignment': False,
                        'weight': None,
                        'candidates_handled': None,
                        'days_active': None
                    }

            # Guard 3: Find all active recruiters
            recruiters = db.query(Users).filter(
                Users.tenant_id == tenant_id,
                Users.UserRole.ilike('%Recruiter%'),
                Users.terminated_at.is_(None),
            ).all()

            if not recruiters:
                logger.error(f"[CandidateRecruiterAssignment] No recruiters in tenant {tenant_id}")
                raise RuntimeError(RecruiterAssignmentServiceForCandidates.RECRUITER_UNAVAILABLE_ERROR)

            # Calculate weight for each recruiter
            recruiter_weights = {}
            for recruiter in recruiters:
                candidates_count = db.query(Candidate).filter(
                    Candidate.assigned_recruiter_id == recruiter.UserID,
                    Candidate.tenant_id == tenant_id
                ).count()

                days_active = max(
                    (datetime.utcnow() - recruiter.CreatedAt).days,
                    1
                )

                weight = candidates_count / days_active
                recruiter_weights[recruiter.UserID] = {
                    'recruiter': recruiter,
                    'weight': weight,
                    'candidates_handled': candidates_count,
                    'days_active': days_active
                }

            # Find recruiter with lowest weight
            selected_recruiter_id = min(
                recruiter_weights.keys(),
                key=lambda uid: recruiter_weights[uid]['weight']
            )
            selected_data = recruiter_weights[selected_recruiter_id]
            selected_recruiter = selected_data['recruiter']

            # Assign recruiter
            candidate.assigned_recruiter_id = selected_recruiter_id
            candidate.assigned_recruiter_changed_at = datetime.utcnow()
            candidate.assigned_recruiter_changed_by = "THUNDER_AUTO_ASSIGN"

            db.add(candidate)
            db.commit()

            logger.info(
                f"[CandidateRecruiterAssignment] Assigned {selected_recruiter_id} to {candidate_id} "
                f"(weight={selected_data['weight']:.2f})"
            )

            return {
                'recruiter_id': selected_recruiter_id,
                'recruiter_name': selected_recruiter.UserName,
                'recruiter_email': selected_recruiter.UserEmail,
                'is_new_assignment': True,
                'weight': selected_data['weight'],
                'candidates_handled': selected_data['candidates_handled'],
                'days_active': selected_data['days_active']
            }

        except ValueError:
            raise
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"[CandidateRecruiterAssignment] Error: {e}", exc_info=True)
            raise RuntimeError(f"Recruiter assignment failed: {e}")

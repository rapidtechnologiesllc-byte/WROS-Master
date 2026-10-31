"""
Recruiter Assignment Service - Round-robin assignment of jobs to recruiters
"""
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import Jobs, Users

logger = logging.getLogger(__name__)

CLOSED_JOB_STATUSES = ("closed", "filled", "cancelled", "inactive", "deleted")


def active_recruiters(db: Session, tenant_id) -> list:
    """The recruiter pool, by templates and permissions only (never the legacy UserRole text):
    active people in the Recruitment function (a template's specialization or their
    department) who may edit candidates (Manage Role set U add-on U overrides). HR Managers
    are in HR, not Recruitment, so they are never in the pool."""
    from app.core import authority

    return [u for u in db.query(Users).filter(
        Users.tenant_id == tenant_id,
        Users.terminated_at.is_(None),
    ).order_by(Users.CreatedAt).all()
        if authority.in_function(db, u, "Recruitment") and authority.has_permission(db, u, "candidates.edit")]


def assign_to_recruiter_roundrobin(db: Session, tenant_id) -> Optional[Users]:
    """Return the tenant's recruiter with the fewest open jobs (None if there are no recruiters)."""
    if tenant_id is None:
        raise ValueError("tenant_id is required to pick a recruiter")
    recruiters = active_recruiters(db, tenant_id)
    if not recruiters:
        logger.warning(f"[Recruiter Assignment] No active recruiters in tenant {tenant_id}")
        return None
    loads = dict(
        db.query(Jobs.recuriterID, func.count(Jobs.jobID))
        .filter(Jobs.recuriterID.in_([r.UserID for r in recruiters]),
                func.lower(func.coalesce(Jobs.jobStatus, "")).notin_(CLOSED_JOB_STATUSES))
        .group_by(Jobs.recuriterID)
        .all()
    )
    recruiter = min(recruiters, key=lambda r: loads.get(r.UserID, 0))  # ties: earliest created
    logger.info(f"[Recruiter Assignment] Picked {recruiter.UserName or recruiter.UserEmail} "
                f"({loads.get(recruiter.UserID, 0)} open jobs)")
    return recruiter


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

            # Guard 3: the recruiter pool (role template only, never UserRole text)
            recruiters = active_recruiters(db, tenant_id)

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
            from app.services.action_emails.candidates import notify_recruiter_assigned

            notify_recruiter_assigned(db, candidate, actor_id=None)

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

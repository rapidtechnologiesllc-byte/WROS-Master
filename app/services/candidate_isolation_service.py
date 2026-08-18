"""Candidate Isolation Service - Enforces BU-based candidate visibility and locking.

ZERO-HARDCODING: All visibility rules determined by database-driven role_templates
and BU assignments. No hardcoded visibility rules.

Isolation Rules:
- Unassociated candidate (submission_bu_id = NULL): visible to all HR users (any BU)
- Associated candidate (submission_bu_id != NULL): locked to that BU permanently
  - Visible ONLY to users in that BU (via role_templates + BU assignment)
  - Cannot be moved to another BU
  - Cannot be unassigned

This prevents candidates from being seen across BU boundaries once they're
submitted to a specific business unit.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.services.rbac_service import RBACService
from app.services.organization_service import OrganizationService


class CandidateIsolationService:
    """Manages candidate BU isolation and visibility enforcement."""

    @staticmethod
    def submit_candidate_to_bu(
        db: Session,
        candidate_id: str,
        bu_id: str,
        submitted_by_user_id: str,
        tenant_id: int = 1
    ) -> Candidate:
        """Submit a candidate to a specific business unit.

        Once submitted, candidate is LOCKED to that BU. This is immutable.

        Args:
            db: Database session
            candidate_id: Candidate ID
            bu_id: Business Unit ID to submit to
            submitted_by_user_id: User submitting the candidate
            tenant_id: Tenant ID

        Returns:
            Updated Candidate object

        Raises:
            ValueError: If candidate already submitted to a different BU
            ValueError: If user not authorized to submit to this BU
        """
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        # Check if candidate already submitted (immutable)
        if candidate.submission_bu_id is not None and candidate.submission_bu_id != bu_id:
            raise ValueError(
                f"Candidate already submitted to BU {candidate.submission_bu_id}. "
                f"Cannot reassign to different BU."
            )

        # Verify submitter has permission to submit to this BU
        submitter = db.query(Users).filter(Users.UserID == submitted_by_user_id).first()
        if not submitter:
            raise ValueError(f"Submitting user {submitted_by_user_id} not found")

        # Check if user has BU management permission and access to this BU
        if not RBACService.has_permission(db, submitted_by_user_id, "business-units", "edit"):
            raise ValueError(f"User {submitted_by_user_id} not authorized to submit candidates")

        # Check if user has access to this BU
        user_bus = OrganizationService.get_user_accessible_business_units(
            submitted_by_user_id, db, tenant_id
        )
        if bu_id not in user_bus and not RBACService.is_super_user(db, submitted_by_user_id, tenant_id):
            raise ValueError(f"User cannot submit to BU {bu_id} (not accessible)")

        # Lock candidate to BU
        candidate.submission_bu_id = bu_id
        candidate.associated_bu_id = bu_id
        candidate.submission_timestamp = datetime.utcnow()

        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        return candidate

    @staticmethod
    def can_view_candidate(
        db: Session,
        user_id: str,
        candidate_id: str,
        tenant_id: int = 1
    ) -> bool:
        """Check if user can view a candidate.

        Visibility rules:
        - Admin.manage: Can see all candidates (any BU)
        - Unassociated candidate: Visible to any HR user
        - Associated candidate: Visible only to users in that BU

        Args:
            db: Database session
            user_id: User ID
            candidate_id: Candidate ID
            tenant_id: Tenant ID

        Returns:
            True if user can view candidate, False otherwise
        """
        # Super admin sees all candidates
        if RBACService.is_super_admin(user_id, db, tenant_id):
            return True

        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            return False

        # Unassociated candidate (no BU assignment yet)
        if candidate.associated_bu_id is None:
            # Visible to any user with recruitment/HR permissions
            return RBACService.has_any_permission(
                user_id,
                ["recruitment.manage", "employee.manage", "recruitment.view"],
                db,
                tenant_id
            )

        # Associated candidate (locked to a BU)
        # User must be in the same BU as the candidate
        user_bus = OrganizationService.get_user_accessible_business_units(
            user_id, db, tenant_id
        )

        return candidate.associated_bu_id in user_bus

    @staticmethod
    def get_candidates_for_user(
        db: Session,
        user_id: str,
        tenant_id: int = 1
    ) -> List[Candidate]:
        """Get all candidates visible to the user.

        Returns:
        - All candidates if user is super admin
        - All unassociated candidates + candidates in user's BU if user is HR/recruitment
        - Empty list if user has no visibility permissions

        Args:
            db: Database session
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            List of visible Candidate objects
        """
        # Super admin sees all
        if RBACService.is_super_admin(user_id, db, tenant_id):
            return db.query(Candidate).filter(
                Candidate.tenant_id == tenant_id
            ).all()

        # Check if user has HR/recruitment permissions
        has_hr_perms = RBACService.has_any_permission(
            user_id,
            ["recruitment.manage", "employee.manage", "recruitment.view"],
            db,
            tenant_id
        )

        if not has_hr_perms:
            return []

        # Get user's accessible BUs
        user_bus = OrganizationService.get_user_accessible_business_units(
            user_id, db, tenant_id
        )

        # Get candidates:
        # 1. All unassociated candidates (visible to any HR)
        # 2. Associated candidates in user's BU
        from sqlalchemy import or_

        candidates = db.query(Candidate).filter(
            or_(
                Candidate.associated_bu_id.is_(None),  # Unassociated
                Candidate.associated_bu_id.in_(user_bus)  # In user's BU
            ),
            Candidate.tenant_id == tenant_id
        ).all()

        return candidates

    @staticmethod
    def get_candidate_isolation_status(
        db: Session,
        candidate_id: str,
        tenant_id: int = 1
    ) -> dict:
        """Get isolation status of a candidate.

        Returns:
            {
                "is_associated": bool,  # True if locked to a BU
                "bu_id": str or None,   # BU ID if associated
                "bu_name": str or None, # BU name if associated
                "submitted_at": datetime or None,
                "is_locked": bool  # True if can't be moved
            }
        """
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            return None

        bu = None
        if candidate.associated_bu_id:
            bu = db.query(BusinessUnit).filter(
                BusinessUnit.id == candidate.associated_bu_id
            ).first()

        return {
            "is_associated": candidate.associated_bu_id is not None,
            "bu_id": candidate.associated_bu_id,
            "bu_name": bu.bu_name if bu else None,
            "submitted_at": candidate.submission_timestamp,
            "is_locked": candidate.submission_bu_id is not None
        }

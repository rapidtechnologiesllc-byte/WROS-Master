import logging
"""Candidate query helpers with isolation enforcement.

Provides query functions that automatically apply candidate isolation rules
based on user's permissions and BU assignments.

Usage in endpoints:
    from app.services.candidate_query_helpers import get_candidates_for_user

    candidates = get_candidates_for_user(db, current_user.UserID, current_user.tenant_id)
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.candidate import Candidate
from app.models.user import Users
from app.services.organization_service import OrganizationService
from app.services.candidate_isolation_service import CandidateIsolationService
from app.services.permission_helper import PermissionHelper


def get_candidates_for_user(
    db: Session,
    user_id: str,
    tenant_id: int = 1,
    job_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Candidate]:
    """Get all candidates visible to user with isolation enforcement.

    Returns candidates based on:
    - User's permissions (admin sees all, HR sees their BU)
    - User's BU assignment
    - Candidate isolation status (unassociated vs associated to BU)

    Filters:
    - job_id: Optional, filter by specific job
    - status: Optional, filter by candidate status

    Args:
        db: Database session
        user_id: User ID
        tenant_id: Tenant ID
        job_id: Optional job filter
        status: Optional status filter

    Returns:
        List of Candidate objects visible to user
    """
    base_query = db.query(Candidate).filter(Candidate.tenant_id == tenant_id)

    # Apply isolation rules
    if PermissionHelper.is_super_admin(user_id, db, tenant_id):
        # Super admin sees all candidates
        pass
    elif PermissionHelper.has_any_permission(user_id, ["recruitment.manage", "employee.manage", "recruitment.view"], db, tenant_id):
        # HR/Recruiter sees:
        # 1. All unassociated candidates
        # 2. Candidates associated to their BU(s)
        user_bus = OrganizationService.get_user_accessible_business_units(user_id, db, tenant_id)

        base_query = base_query.filter(
            or_(
                Candidate.associated_bu_id.is_(None),  # Unassociated
                Candidate.associated_bu_id.in_(user_bus) if user_bus else False  # In their BU
            )
        )
    else:
        # No visibility for regular employees
        return []

    # Apply optional filters
    if job_id:
        base_query = base_query.filter(Candidate.job_id == job_id)

    if status:
        base_query = base_query.filter(Candidate.status == status)

    return base_query.all()


def get_candidate_by_id(
    db: Session,
    candidate_id: str,
    user_id: str,
    tenant_id: int = 1,
) -> Optional[Candidate]:
    """Get a candidate by ID with visibility check.

    Returns the candidate only if user can view it (isolation enforced).

    Args:
        db: Database session
        candidate_id: Candidate ID
        user_id: User ID
        tenant_id: Tenant ID

    Returns:
        Candidate object if visible, None otherwise
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == candidate_id,
        Candidate.tenant_id == tenant_id
    ).first()

    if not candidate:
        return None

    # Check visibility using isolation service
    if CandidateIsolationService.can_view_candidate(db, user_id, candidate_id, tenant_id):
        return candidate

    return None


def count_candidates_for_user(
    db: Session,
    user_id: str,
    tenant_id: int = 1,
    status: Optional[str] = None,
) -> int:
    """Count candidates visible to user with isolation enforcement.

    Args:
        db: Database session
        user_id: User ID
        tenant_id: Tenant ID
        status: Optional status filter

    Returns:
        Count of visible candidates
    """
    candidates = get_candidates_for_user(db, user_id, tenant_id, status=status)
    return len(candidates)


def get_candidates_by_bu(
    db: Session,
    user_id: str,
    bu_id: str,
    tenant_id: int = 1,
) -> List[Candidate]:
    """Get all candidates in a specific BU, with permission check.

    User must have BU management or HR permissions to see BU candidates.

    Args:
        db: Database session
        user_id: User ID
        bu_id: Business Unit ID
        tenant_id: Tenant ID

    Returns:
        List of Candidate objects in the BU
    """
    # Check permission to view BU data
    if not PermissionHelper.has_any_permission(user_id, ["admin.manage", "business_unit.manage", "employee.manage"], db, tenant_id):
        return []

    # For non-admin users, verify they have access to this BU
    if not PermissionHelper.is_super_admin(user_id, db, tenant_id):
        user_bus = OrganizationService.get_user_accessible_business_units(user_id, db, tenant_id)
        if bu_id not in user_bus:
            return []

    return db.query(Candidate).filter(
        Candidate.associated_bu_id == bu_id,
        Candidate.tenant_id == tenant_id
    ).all()


def submit_candidates_to_bu(
    db: Session,
    candidate_ids: List[str],
    bu_id: str,
    submitted_by_user_id: str,
    tenant_id: int = 1,
) -> dict:
    """Submit multiple candidates to a BU (locks them to that BU).

    Args:
        db: Database session
        candidate_ids: List of candidate IDs to submit
        bu_id: Business Unit ID
        submitted_by_user_id: User ID of submitter
        tenant_id: Tenant ID

    Returns:
        {
            "success": int,      # Number of candidates successfully submitted
            "failed": int,       # Number of candidates that failed
            "errors": List[str]  # Error messages for failures
        }
    """
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }

    for candidate_id in candidate_ids:
        try:
            CandidateIsolationService.submit_candidate_to_bu(
                db, candidate_id, bu_id, submitted_by_user_id, tenant_id
            )
            results["success"] += 1
        except ValueError as e:
            results["failed"] += 1
            results["errors"].append(f"Candidate {candidate_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            results["failed"] += 1
            results["errors"].append(f"Candidate {candidate_id}: Unexpected error: {str(e)}")

            return results

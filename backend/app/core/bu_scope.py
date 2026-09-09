"""
HR-Manager/BU-restricted visibility gap fix, 2026-08-05. Avinash's own
words: "HR Manager wasn't able to see candidates so everything an hr
can see... should be what a hr manager is able to see kind of all
interviews, all feedbacks if they are tagged to that department."

Real finding, checked against actual code before building anything
new: a correct, tested BU-ownership mechanism already exists
(app.models.candidate_ownership.CandidateOwnership, populated by
POST /jobs/{id}/assign-candidate/{candidate_id} via
candidate_pool_service.set_bu_owned()) and a real, correctly-scoped
endpoint (GET /onboarding/hr/candidates-by-my-bu) already reads it --
but grep confirms that endpoint is never called by any frontend
screen. The gap isn't a missing mechanism, it's that the DEFAULT
candidate list (get_all_candidates, the one CandidateSearch.js
actually calls) and every interview/feedback endpoint apply no BU
scoping at all, regardless of the caller's role.

This module makes bu_restricted enforcement automatic and reusable
across those call sites, reusing the EXACT same CandidateOwnership /
"Org Pool visible to everyone" rule get_candidates_by_my_bu already
implements correctly -- not a second, divergent BU rule. Deliberately
a set of plain helper functions (mirroring app.core.tenant_context's
get_tenant_scoped_query, not its global with_loader_criteria
mechanism) -- the real surface here is a handful of specific
candidate/interview/feedback list endpoints, not the ~180-call-site
scale that justified a global session-level filter for tenant scoping.
"""
import logging
from typing import Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_ORG
from app.models.user import Users
from app.core.visibility import should_bypass_bu_filter, get_user_bu_id

logger = logging.getLogger(__name__)


def is_bu_restricted(db: Session, user: Users) -> bool:
    """
    Check if user should have BU-restricted visibility.

    Uses visibility.py to determine if user is org-level:
    - Org-level users (via role_template.org_level_access) see ALL candidates (not restricted)
    - Regular users (BU-scoped) see only their BU's candidates (restricted)
    """
    # If user should bypass BU filter (org-level), they are NOT restricted
    if should_bypass_bu_filter(user):
        return False

    # If user has a BU assigned, they ARE restricted to that BU
    return get_user_bu_id(user) is not None

def apply_bu_scope_to_candidate_query(db: Session, query: Query, current_user: Users) -> Query:
    """
    Narrows an existing Candidate query to Org Pool candidates plus
    whatever the caller's own Business Unit owns.

    For org-level users (CEO, Super User, etc. with org_level_access=True):
    - Returns unmodified query (see all candidates)

    For BU-scoped users (Recruiters, Hiring Managers, etc.):
    - Filters to Org Pool candidates + their own BU's assigned candidates
    - Fail closed: if no BU assigned, see only org-wide pool

    This uses visibility.py to determine org-level status, so the rule is:
    - role_template.org_level_access=True → org-level (no filtering)
    - role_template.org_level_access=False → BU-scoped (filter by business_unit_id)
    """
    # Check if user should bypass BU filtering (org-level user)
    if should_bypass_bu_filter(current_user):
        # Org-level user: return unmodified query, they see everything
        logger.debug(f"BU scoping bypassed for org-level user: {current_user.UserEmail}")
        return query

    # BU-scoped user: apply filtering
    user_bu_id = get_user_bu_id(current_user)

    # Join with CandidateOwnership to determine BU ownership
    query = query.outerjoin(CandidateOwnership, CandidateOwnership.candidateID == Candidate.candidateID)

    # Define org pool visibility: candidates not yet assigned to a BU, or explicitly in org pool
    org_pool_visible = or_(
        CandidateOwnership.id.is_(None),  # never assigned a BU-owning job -- Org Pool by default
        CandidateOwnership.pool_status == POOL_ORG,
    )

    if user_bu_id is None:
        # Fail closed: a BU-scoped user with no BU assigned sees only the org-wide pool
        logger.debug(f"BU-scoped user {current_user.UserEmail} has no BU assigned, filtering to org pool only")
        return query.filter(org_pool_visible)

    # BU-scoped user with assigned BU: see org pool + their own BU's candidates
    logger.debug(f"Applying BU scope for user {current_user.UserEmail} to BU {user_bu_id}")
    return query.filter(or_(org_pool_visible, CandidateOwnership.owned_by_bu_id == user_bu_id))

def get_bu_scoped_candidate_ids(db: Session, current_user: Users) -> Optional[Set[str]]:
    """Returns the set of candidate IDs visible to current_user under
    BU scoping, or None if the caller is global-access (no
    restriction -- callers should treat None as "don't filter", not as
    an empty set). Used by interview/feedback endpoints that query a
    different base table and need to filter by candidate_id membership
    rather than joining Candidate directly."""
    if not is_bu_restricted(db, current_user):
        return None
    query = apply_bu_scope_to_candidate_query(db, db.query(Candidate.candidateID), current_user)
    return {row[0] for row in query.all()}

def get_candidate_by_id_with_bu_scope(db: Session, candidate_id: str, current_user: Users) -> Optional[Candidate]:
    """
    Safely fetch a candidate by ID, respecting BU scoping ONLY if the
    candidate has been submitted to a job (has CandidateOwnership).

    Newly created candidates live in the Org Pool (no CandidateOwnership)
    and should be visible to ALL HR users regardless of Business Unit.
    BU scoping only applies AFTER a candidate is submitted to a job.

    Args:
        db: Database session
        candidate_id: The candidate ID to fetch
        current_user: The requesting user

    Returns:
        The Candidate if found and visible to the user, None otherwise
    """
    try:
        # Fetch the candidate without scoping first. If it doesn't exist, return None.
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            return None

        # Check if candidate has been submitted to a job (has CandidateOwnership).
        # If not, it's in Org Pool and should be visible to all HR users.
        ownership = db.query(CandidateOwnership).filter(
            CandidateOwnership.candidateID == candidate_id
        ).first()

        if not ownership:
            # No job submission yet -- in Org Pool, visible to all HR users
            return candidate

        # Has been submitted to a job. Apply BU scoping.
        candidate_scoped = apply_bu_scope_to_candidate_query(
            db, db.query(Candidate).filter(Candidate.candidateID == candidate_id), current_user=current_user,
        ).first()
        return candidate_scoped
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[BU-Scope] Error fetching candidate {candidate_id}: {e}", exc_info=True)
        raise ValueError("Operation failed")

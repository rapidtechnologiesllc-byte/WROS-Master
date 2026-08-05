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
from typing import Optional, Set

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.candidate import Candidate
from app.models.candidate_ownership import CandidateOwnership, POOL_ORG
from app.models.user import Users
from app.services.rbac_service import RBACService


def is_bu_restricted(db: Session, user: Users) -> bool:
    return RBACService.has_attribute(db, user.UserID, "bu_restricted", expected=True)


def apply_bu_scope_to_candidate_query(db: Session, query: Query, current_user: Users) -> Query:
    """Narrows an existing Candidate query to Org Pool candidates plus
    whatever the caller's own Business Unit owns. A no-op for
    global-access roles (Super User, Partner, HR Operations -- whoever
    isn't bu_restricted per the RBAC seed)."""
    if not is_bu_restricted(db, current_user):
        return query

    query = query.outerjoin(CandidateOwnership, CandidateOwnership.candidateID == Candidate.candidateID)
    org_pool_visible = or_(
        CandidateOwnership.id.is_(None),  # never assigned a BU-owning job -- Org Pool by default
        CandidateOwnership.pool_status == POOL_ORG,
    )
    if current_user.business_unit_id is None:
        # Fail closed: a bu_restricted user with no BU assigned sees
        # only the org-wide pool, never another BU's owned candidates.
        return query.filter(org_pool_visible)
    return query.filter(or_(org_pool_visible, CandidateOwnership.owned_by_bu_id == current_user.business_unit_id))


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

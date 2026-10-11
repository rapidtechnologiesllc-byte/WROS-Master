"""
Revenue Visibility Engine (EPIC-02) / Workforce Planning (EPIC-03)
access gate. Avinash's explicit 2026-08-05 access spec: "Epic 2,3 is
only visible to ceo, partner (only for their BU); BU head (Only for
their BU); finance & HR manager (no actual p&l)." Refined the same
day: "a partner has it's own clients and the work is done in their BU
only... any business he generates should go only to that BU" -- BU
ownership is a real, client-level fact (Client.business_unit_id), not
a role-attribute abstraction.

Deliberately a SEPARATE scoping mechanism from app.core.bu_scope's
general bu_restricted RBAC attribute -- Partner is global_access=True /
bu_restricted=False at the role-attribute level (added earlier for the
Desire Intelligence edit gate), but is BU-scoped specifically for these
revenue/planning screens. The same role can be globally-visible for
one feature and BU-scoped for another; a single role-level boolean
can't express that, so this feature gets its own scoping here rather
than overloading bu_restricted's meaning.

"CEO" has no distinct RBAC role in this codebase -- Super User is the
highest-privilege real role and is treated as the CEO-equivalent here.
"""
from typing import Optional

from sqlalchemy.orm import Query, Session

from app.models.client import Client
from app.models.user import Users

def is_revenue_bu_scoped(db: Session, user: Users) -> bool:
    """BU leaders (role template hierarchy level) see revenue for their own BU only;
    org-level and super-user roles see it org-wide (app.core.authority)."""
    from app.core import authority

    return authority.is_revenue_bu_scoped(db, user)

def can_view_pnl(db: Session, user: Users) -> bool:
    """P&L needs the revenue view permission on the user's role template."""
    from app.core import authority

    return authority.has_permission(db, user, "revenue.view")

def apply_revenue_bu_scope_to_client_query(db: Session, query: Query, current_user: Users) -> Query:
    """Narrows a Client query to clients with no BU assigned yet
    (visible to everyone, same Org-Pool-until-claimed posture as
    CandidateOwnership) plus whatever the caller's own Business Unit
    owns. A no-op for every role except Partner/BU Head."""
    if not is_revenue_bu_scoped(db, current_user):
        return query
    if current_user.business_unit_id is None:
        return query.filter(Client.business_unit_id.is_(None))
    return query.filter(
        (Client.business_unit_id.is_(None)) | (Client.business_unit_id == current_user.business_unit_id)
    )

def get_revenue_scoped_client_ids(db: Session, current_user: Users) -> Optional[set]:
    """Returns the set of client IDs visible to current_user under
    revenue BU scoping, or None if unrestricted (org-wide). Used by
    Opportunity/Demand/dashboard queries that need to filter by
    client_id membership rather than joining Client directly."""
    if not is_revenue_bu_scoped(db, current_user):
        return None
    query = apply_revenue_bu_scope_to_client_query(db, db.query(Client.id), current_user)
    return {row[0] for row in query.all()}

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
from app.services.rbac_service import RBACService

# Only these two roles are BU-scoped for revenue/planning screens --
# everyone else with revenue.view (Super User/CEO, Finance, HR Manager)
# sees org-wide, per Avinash's exact spec.
REVENUE_BU_SCOPED_ROLES = {"Partner", "BU Head"}


def get_user_role_name(db: Session, user: Users) -> Optional[str]:
    role = RBACService.get_user_role(db, user.UserID)
    return role.name if role else None


def is_revenue_bu_scoped(db: Session, user: Users) -> bool:
    return get_user_role_name(db, user) in REVENUE_BU_SCOPED_ROLES


def can_view_pnl(db: Session, user: Users) -> bool:
    """revenue.view_pnl -- Super User, Partner, BU Head, Finance. NOT
    HR Manager, per Avinash's explicit "no actual p&l" instruction."""
    return RBACService.has_permission(db, user.UserID, "revenue.view_pnl")


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

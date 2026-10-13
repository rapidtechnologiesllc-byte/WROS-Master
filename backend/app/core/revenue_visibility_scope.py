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

Org-level roles (role template org_level_access) see everything; scoping is decided by
app.core.authority and app.core.visibility, never by a role name.
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
    """Narrows a Client query to the clients the caller may see (app.core.data_scope: the BUs
    they partner, head or belong to, plus clients with no BU yet). A no-op for org-level roles."""
    from app.core.data_scope import bu_filter

    return query.filter(bu_filter(db, current_user, Client.business_unit_id))


def get_revenue_scoped_client_ids(db: Session, current_user: Users) -> Optional[set]:
    """The client ids whose revenue current_user may see, or None if unrestricted (org-level).
    Money is strict: a client with no business unit yet counts for the org only, not for
    every partner (unlike the client list, where unassigned prospects stay visible)."""
    from app.core.data_scope import bu_filter

    if not is_revenue_bu_scoped(db, current_user):
        return None
    query = db.query(Client.id).filter(bu_filter(db, current_user, Client.business_unit_id, unassigned_visible=False))
    return {row[0] for row in query.all()}

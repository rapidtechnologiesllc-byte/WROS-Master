"""Who leads which business unit, and where (CEO 2026-10-12).

- Partner: one per business unit (BusinessUnit.partner_user_id), for every company the
  BU operates in. E.g. Troy is partner of AXION in BX-US and BX-IN.
- BU head: one per business unit per company (BusinessUnitLocationHead). E.g. Troy runs
  AXION in BX-US, Hemant runs AXION in BX-IN. A person may head several BUs, the same BU
  in several companies, and may also be a partner.

Scope is the single answer to "what may this leader see": a mapping
business_unit_id -> None (the whole BU, every company) or a set of company ids. Org-level
roles (role template) are not scoped at all and get None from leadership_scope.
"""
import logging
from typing import Dict, FrozenSet, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit, BusinessUnitCompany, BusinessUnitLocationHead
from app.models.user import Users

logger = logging.getLogger(__name__)

Scope = Dict[int, Optional[FrozenSet[str]]]  # bu_id -> None (whole BU) | company ids


def location_heads(db: Session, business_unit_id: int) -> Dict[str, BusinessUnitLocationHead]:
    """company_id -> head row, for one business unit."""
    rows = db.query(BusinessUnitLocationHead).filter(
        BusinessUnitLocationHead.business_unit_id == business_unit_id).all()
    return {row.company_id: row for row in rows}


def head_user_id(db: Session, business_unit_id: Optional[int], company_id: Optional[str]) -> Optional[str]:
    """The head of a BU in one company, or None when either is unknown or nobody is set."""
    if business_unit_id is None or company_id is None:
        return None
    row = db.query(BusinessUnitLocationHead.head_user_id).filter(
        BusinessUnitLocationHead.business_unit_id == business_unit_id,
        BusinessUnitLocationHead.company_id == company_id).first()
    return row[0] if row else None


def leadership_scope(db: Session, user: Users) -> Scope:
    """What this user leads: BUs they partner (whole BU) and BU x company they head."""
    scope: Dict[int, Optional[set]] = {}
    for (bu_id,) in db.query(BusinessUnit.id).filter(BusinessUnit.partner_user_id == user.UserID):
        scope[bu_id] = None
    for bu_id, company_id in db.query(BusinessUnitLocationHead.business_unit_id, BusinessUnitLocationHead.company_id) \
            .filter(BusinessUnitLocationHead.head_user_id == user.UserID):
        if bu_id in scope and scope[bu_id] is None:
            continue  # already sees the whole BU as its partner
        scope.setdefault(bu_id, set()).add(company_id)
    return {bu_id: (None if companies is None else frozenset(companies)) for bu_id, companies in scope.items()}


def in_scope(scope: Optional[Scope], business_unit_id: Optional[int], company_id: Optional[str]) -> bool:
    """Whether a record attributed to (BU, company) is inside the scope. None = unscoped (org)."""
    if scope is None:
        return True
    if business_unit_id not in scope:
        return False
    companies = scope[business_unit_id]
    return companies is None or company_id in companies


def set_location_heads(db: Session, bu: BusinessUnit, tenant_id: int, heads: Dict[str, str],
                       validate_head) -> None:
    """Apply {company_id: user_id or ""} for one BU: "" removes that company's head.
    A head can only be set for a company the BU operates in. validate_head(user_id) returns
    the Users row or raises (the role-level rule lives with the caller's API)."""
    operates_in = {c for (c,) in db.query(BusinessUnitCompany.company_id)
                   .filter(BusinessUnitCompany.business_unit_id == bu.id)}
    unknown = set(heads) - operates_in
    if unknown:
        raise ValueError(f"{bu.display_name or bu.name} does not operate in company {sorted(unknown)}; "
                         "add the company to the business unit first")
    current = location_heads(db, bu.id)
    for company_id, user_id in heads.items():
        row = current.get(company_id)
        if not user_id:
            if row is not None:
                db.delete(row)
            continue
        head = validate_head(user_id)
        if row is None:
            db.add(BusinessUnitLocationHead(tenant_id=tenant_id, business_unit_id=bu.id, company_id=company_id,
                                            head_user_id=head.UserID))
        else:
            row.head_user_id = head.UserID
    db.flush()


def drop_heads_outside(db: Session, business_unit_id: int, company_ids: Iterable[str]) -> int:
    """A BU that stops operating in a company has no head there any more."""
    keep = set(company_ids)
    removed = 0
    for company_id, row in location_heads(db, business_unit_id).items():
        if company_id not in keep:
            db.delete(row)
            removed += 1
    return removed


def carry_over_single_heads(db: Session) -> int:
    """One-time move from the old single BusinessUnit.manager_id: that person becomes the
    head in each company the BU operates in where no head is set yet, and manager_id is
    cleared so it is never read again. A BU with no companies keeps manager_id (there is
    no company to put the head in) and is logged so it can be fixed on the BU screen."""
    moved = 0
    for bu in db.query(BusinessUnit).filter(BusinessUnit.manager_id.isnot(None)).all():
        companies = [c for (c,) in db.query(BusinessUnitCompany.company_id)
                     .filter(BusinessUnitCompany.business_unit_id == bu.id)]
        if not companies:
            logger.warning(f"[BU heads] BU {bu.id} ({bu.name}) has a head but no company; "
                           "set its companies and per-company heads on the Business Units screen")
            continue
        existing = location_heads(db, bu.id)
        for company_id in companies:
            if company_id not in existing:
                db.add(BusinessUnitLocationHead(tenant_id=bu.tenant_id, business_unit_id=bu.id,
                                                company_id=company_id, head_user_id=bu.manager_id))
                moved += 1
        bu.manager_id = None
    db.commit()
    return moved


def head_for_client(db: Session, business_unit_id: Optional[int], client_id: Optional[str]) -> Optional[str]:
    """The BU head who owns work for a client: the head of the BU in the client's
    contracting company. Without a client company, a BU that operates in exactly one
    company uses that company's head; otherwise None (never a guess between locations)."""
    from app.models.client import Client

    if business_unit_id is None:
        return None
    company_id = None
    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
        company_id = client.contracting_company_id if client else None
    if company_id is None:
        companies = [c for (c,) in db.query(BusinessUnitCompany.company_id)
                     .filter(BusinessUnitCompany.business_unit_id == business_unit_id)]
        company_id = companies[0] if len(companies) == 1 else None
    return head_user_id(db, business_unit_id, company_id)

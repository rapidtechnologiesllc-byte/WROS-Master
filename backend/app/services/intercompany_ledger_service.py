"""EPIC-16 -- Intercompany Ledger. See app.models.intercompany_ledger
for why this is manual-entry, not auto-derived. Entries reference companies by id (never by
name): the P&L by company and the goal tree attribute them through from/to_company_id."""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.intercompany_ledger import IntercompanySettlement
from app.models.location import Location

logger = logging.getLogger(__name__)

class IntercompanySettlementError(Exception):
    pass

def _company(db: Session, company_id: str, tenant_id: Optional[int]) -> Location:
    query = db.query(Location).filter(Location.id == company_id)
    if tenant_id is not None:
        query = query.filter(Location.tenant_id == tenant_id)
    company = query.first()
    if company is None:
        raise IntercompanySettlementError(f"Company {company_id!r} does not exist.")
    return company

def record_intercompany_settlement(
    db: Session, *, from_company_id: str, to_company_id: str, amount_usd_cents: int, settlement_date, reason: str,
    created_by: str, tenant_id: Optional[int] = None, business_unit_id: Optional[int] = None,
) -> IntercompanySettlement:
    if amount_usd_cents <= 0:
        raise IntercompanySettlementError("amount_usd_cents must be positive.")
    if not from_company_id or not to_company_id:
        raise IntercompanySettlementError("Both companies are required.")
    if from_company_id == to_company_id:
        raise IntercompanySettlementError("The two companies must differ.")
    payer, receiver = _company(db, from_company_id, tenant_id), _company(db, to_company_id, tenant_id)
    settlement = IntercompanySettlement(
        tenant_id=tenant_id, from_company_id=payer.id, to_company_id=receiver.id,
        from_entity=payer.name, to_entity=receiver.name,
        amount_usd_cents=amount_usd_cents, settlement_date=settlement_date, reason=reason, created_by=created_by,
        business_unit_id=business_unit_id,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement

def get_company_net_position(db: Session, *, company_id: str, tenant_id: Optional[int] = None) -> int:
    """Positive = this company has received more than it's sent (owed
    money out), negative = it owes the other side(s)."""
    _company(db, company_id, tenant_id)
    query = db.query(IntercompanySettlement).filter(
        (IntercompanySettlement.to_company_id == company_id) | (IntercompanySettlement.from_company_id == company_id))
    if tenant_id is not None:
        query = query.filter(IntercompanySettlement.tenant_id == tenant_id)
    net = 0
    for s in query.all():
        if s.to_company_id == company_id:
            net += s.amount_usd_cents
        if s.from_company_id == company_id:
            net -= s.amount_usd_cents
    return net

def link_settlement_companies(db: Session, settlement: IntercompanySettlement, *, from_company_id: str,
                              to_company_id: str) -> IntercompanySettlement:
    """Link an old entry whose free-text name matched no company. Only unlinked entries: a linked
    entry is part of the books and is never re-pointed."""
    if settlement.from_company_id and settlement.to_company_id:
        raise IntercompanySettlementError(f"Settlement {settlement.id} is already linked to its companies.")
    if from_company_id == to_company_id:
        raise IntercompanySettlementError("The two companies must differ.")
    payer = _company(db, from_company_id, settlement.tenant_id)
    receiver = _company(db, to_company_id, settlement.tenant_id)
    settlement.from_company_id, settlement.to_company_id = payer.id, receiver.id
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    logger.info(f"[Intercompany] settlement {settlement.id} linked {payer.id} -> {receiver.id}")
    return settlement

def list_settlements(db: Session, *, tenant_id: Optional[int] = None) -> List[IntercompanySettlement]:
    query = db.query(IntercompanySettlement)
    if tenant_id is not None:
        query = query.filter(IntercompanySettlement.tenant_id == tenant_id)
    return query.order_by(IntercompanySettlement.settlement_date.desc()).all()

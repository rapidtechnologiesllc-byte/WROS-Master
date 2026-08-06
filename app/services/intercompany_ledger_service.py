"""EPIC-16 -- Intercompany Ledger. See app.models.intercompany_ledger
for why this is manual-entry, not auto-derived."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.intercompany_ledger import IntercompanySettlement


class IntercompanySettlementError(Exception):
    pass


def record_intercompany_settlement(
    db: Session, *, from_entity: str, to_entity: str, amount_usd_cents: int, settlement_date, reason: str,
    created_by: str, tenant_id: Optional[int] = None,
) -> IntercompanySettlement:
    if amount_usd_cents <= 0:
        raise IntercompanySettlementError("amount_usd_cents must be positive.")
    if from_entity == to_entity:
        raise IntercompanySettlementError("from_entity and to_entity must differ.")
    settlement = IntercompanySettlement(
        tenant_id=tenant_id, from_entity=from_entity, to_entity=to_entity,
        amount_usd_cents=amount_usd_cents, settlement_date=settlement_date, reason=reason, created_by=created_by,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def get_entity_net_position(db: Session, *, entity: str, tenant_id: Optional[int] = None) -> int:
    """Positive = this entity has received more than it's sent (owed
    money out), negative = it owes the other side(s)."""
    query = db.query(IntercompanySettlement)
    if tenant_id is not None:
        query = query.filter(IntercompanySettlement.tenant_id == tenant_id)
    net = 0
    for s in query.all():
        if s.to_entity == entity:
            net += s.amount_usd_cents
        if s.from_entity == entity:
            net -= s.amount_usd_cents
    return net


def list_settlements(db: Session, *, tenant_id: Optional[int] = None) -> List[IntercompanySettlement]:
    query = db.query(IntercompanySettlement)
    if tenant_id is not None:
        query = query.filter(IntercompanySettlement.tenant_id == tenant_id)
    return query.order_by(IntercompanySettlement.settlement_date.desc()).all()

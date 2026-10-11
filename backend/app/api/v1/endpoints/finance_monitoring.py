"""
Finance Monitoring Endpoints - Real-time P&L Tracking

Provides real-time profitability monitoring with:
- Partner consolidated P&L (all their BUs)
- BU-specific P&L (single location)
- 7-day margin forecasting
- 25% profit floor monitoring
- Cost anomaly detection

Access Control:
- Partner: sees their BUs only
- BU Head: sees their BU only
- CEO: sees all BUs/partners
- Finance role: sees all
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from app.core.dependencies import get_current_user, require_resource_permission
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.services.finance_agent import FinanceAgent, partner_bu_ids
from app.core.database import get_db

router = APIRouter(prefix="/finance", tags=["finance"])
logger = logging.getLogger(__name__)

def get_user_business_units(user_id: str, tenant_id: int, db: Session) -> List[int]:
    """Get all BUs user has access to"""
    # org-level roles (role template flag) see every BU
    from app.core import authority

    user = db.query(Users).filter(Users.UserID == user_id).first()
    if authority.is_org_level(db, user):
        bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()
        return [bu.id for bu in bus]

    # BUs the user owns (partner) or runs (head), plus their own BU
    bu_ids = partner_bu_ids(db, user_id) + [row[0] for row in db.query(BusinessUnit.id).filter(
        BusinessUnit.manager_id == user_id).all()]
    if user and user.business_unit_id and user.business_unit_id not in bu_ids:
        bu_ids.append(user.business_unit_id)
    return bu_ids

def check_bu_access(user_id: str, bu_id: int, tenant_id: int, db: Session) -> bool:
    """Verify user has access to this BU"""
    user = db.query(Users).filter(Users.UserID == user_id).first()

    from app.core import authority

    if authority.is_org_level(db, user):
        return True

    # User must have this BU assigned
    allowed_bus = get_user_business_units(user_id, tenant_id, db)
    return bu_id in allowed_bus


@router.get(
    "/health-check",
    dependencies=[Depends(require_resource_permission("forecasts", "view"))]
)
async def hourly_profitability_check(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Hourly profitability health check

    Only CEO and Finance can access
    Returns all partners below 25% net profit floor
    """

    from app.core import authority

    if not (authority.is_finance_leader(db, current_user) or authority.is_ceo(db, current_user)):
        raise HTTPException(status_code=403, detail="Only Finance (Senior Manager or above) and the CEO can access this")

    results = FinanceAgent.hourly_partner_check(db, current_user.tenant_id)

    return {
        "check_time": datetime.utcnow().isoformat(),
        "partners_monitored": len(results),
        "critical_alerts": [r for r in results if r.get("status") == "ESCALATION_TRIGGERED"],
        "results": results
    }

"""
import logging
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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.core.dependencies import get_db, get_current_user, require_resource_permission
from app.models.user import Users
from app.models.business_unit import BusinessUnit
from app.services.finance_agent import FinanceAgent
from app.core.database import get_db

router = APIRouter(prefix="/finance", tags=["finance"])


def get_user_business_units(user_id: str, tenant_id: int, db: Session) -> List[str]:
    """Get all BUs user has access to"""
    from app.models.bu_access import BUAccess

    # Check if user is CEO - they see all BUs
    user = db.query(Users).filter(Users.UserID == user_id).first()
    if user and user.UserRole == "CEO":
        bus = db.query(BusinessUnit).filter(BusinessUnit.tenant_id == tenant_id).all()
        return [bu.id for bu in bus]

    # Otherwise get assigned BUs from user_roles or primary BU
    if user and user.business_unit_id:
        return [user.business_unit_id]
    return []


def check_bu_access(user_id: str, bu_id: str, tenant_id: int, db: Session) -> bool:
    """Verify user has access to this BU"""
    user = db.query(Users).filter(Users.UserID == user_id).first()

    # CEO can access all
    if user and user.UserRole == "CEO":
        return True

    # User must have this BU assigned
    allowed_bus = get_user_business_units(user_id, tenant_id, db)
    return bu_id in allowed_bus


@router.get(
    "/dashboard",
    dependencies=[Depends(require_resource_permission("dashboard", "view"))]
)
async def get_finance_dashboard(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Real-time finance dashboard for logged-in user

    Response filtered by user's role and assigned BUs:
    - Partner: sees all their BUs consolidated + breakdown
    - BU Head: sees their single BU only
    - CEO: sees all partners/BUs
    - Finance: sees all
    """

    try:
        if current_user.UserRole == "CEO":
            # CEO sees all partners' P&Ls
            partners = db.query(Users).filter(
                Users.UserRole == "Partner",
                Users.tenant_id == current_user.tenant_id
            ).all()

            return {
                "role": "CEO",
                "view": "company_wide",
                "partners": [
                    {
                        "partner_id": p.UserID,
                        "partner_name": p.UserName,
                        "pl": FinanceAgent.calculate_real_time_partner_pl(
                            db, current_user.tenant_id, p.UserID, annual_goal_usd=5000000
                        )
                    }
                    for p in partners
                ],
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }

        elif current_user.UserRole == "Partner":
            # Partner sees all their BUs consolidated
            bus = get_user_business_units(current_user.UserID, current_user.tenant_id, db)

            return {
                "role": "Partner",
                "partner_id": current_user.UserID,
                "partner_name": current_user.UserName,
                "view": "consolidated_bu",
                "pl": FinanceAgent.calculate_real_time_partner_pl(
                    db, current_user.tenant_id, current_user.UserID, annual_goal_usd=5000000
                ),
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }

        elif current_user.UserRole == "BU_HEAD" or current_user.business_unit_id:
            # BU Head sees only their BU
            bu_id = current_user.business_unit_id
            if not check_bu_access(current_user.UserID, bu_id, current_user.tenant_id, db):
                raise HTTPException(status_code=403, detail="Access denied to this BU")

            return {
                "role": "BU_HEAD",
                "bu_id": bu_id,
                "view": "single_bu",
                "pl": FinanceAgent.calculate_real_time_partner_pl(
                    db, current_user.tenant_id, bu_id, annual_goal_usd=500000  # Per-BU target
                ),
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }

        else:
            raise HTTPException(status_code=403, detail="No finance dashboard access for your role")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Finance calculation error: {str(e)}")


@router.get(
    "/partner/{partner_id}/consolidation",
    dependencies=[Depends(require_resource_permission("partner", "view"))]
)
async def get_partner_consolidated_pl(
    partner_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Partner's consolidated P&L across all their BUs

    Returns:
    - Individual BU P&Ls
    - Consolidated totals
    - Annual goal tracking
    - Health status
    """

    # Access control: partner viewing self OR CEO viewing any
    if current_user.UserRole != "CEO" and current_user.UserID != partner_id:
        raise HTTPException(status_code=403, detail="Can only view your own P&L")

    return FinanceAgent.calculate_real_time_partner_pl(
        db, current_user.tenant_id, partner_id, annual_goal_usd=5000000
    )


@router.get(
    "/bu/{bu_id}/metrics",
    dependencies=[Depends(require_resource_permission("bu", "view"))]
)
async def get_bu_pl(
    bu_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Single BU's P&L metrics

    Returns:
    - Revenue
    - COGS
    - Gross profit
    - Operating expenses
    - Net profit
    - Health status
    """

    # Access control: BU Head viewing own BU OR CEO viewing any
    if not check_bu_access(current_user.UserID, bu_id, current_user.tenant_id, db):
        raise HTTPException(status_code=403, detail="Access denied to this BU")

    return FinanceAgent.calculate_real_time_partner_pl(
        db, current_user.tenant_id, bu_id, annual_goal_usd=500000
    )


@router.get(
    "/forecast/{partner_id}",
    dependencies=[Depends(require_resource_permission("forecast", "view"))]
)
async def forecast_partner_margin(
    partner_id: str,
    days: int = 7,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    7-day profitability forecast

    Predicts if partner will fall below 25% margin floor
    """

    # Access control
    if current_user.UserRole != "CEO" and current_user.UserID != partner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return FinanceAgent.forecast_margin_risk(
        db, current_user.tenant_id, partner_id, days_ahead=days
    )


@router.get(
    "/anomalies/{partner_id}",
    dependencies=[Depends(require_resource_permission("anomalie", "view"))]
)
async def detect_cost_anomalies(
    partner_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Detect unusual spending patterns

    Flags:
    - Large invoices (>$10K)
    - Rapid cost increases
    - Contractor spend spikes
    """

    # Access control
    if current_user.UserRole != "CEO" and current_user.UserID != partner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    anomalies = FinanceAgent.detect_cost_anomalies(
        db, current_user.tenant_id, partner_id
    )

    return {
        "partner_id": partner_id,
        "anomalies": anomalies,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


@router.get(
    "/health-check",
    dependencies=[Depends(require_resource_permission("health-check", "view"))]
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

    if current_user.UserRole not in ["CEO", "Finance"]:
        raise HTTPException(status_code=403, detail="Only CEO and Finance can access this endpoint")

    results = FinanceAgent.hourly_partner_check(db, current_user.tenant_id)

    return {
        "check_time": __import__('datetime').datetime.utcnow().isoformat(),
        "partners_monitored": len(results),
        "critical_alerts": [r for r in results if r.get("status") == "ESCALATION_TRIGGERED"],
        "results": results
    }

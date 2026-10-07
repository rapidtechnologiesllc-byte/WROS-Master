"""
import logging
Goals Management Endpoints - CEO Strategic Goals with Auto-Cascade

CEO sets strategic goals. System automatically cascades to all departments.
Example: CEO sets "150 consultants" → Workforce Ops auto-gets 150/year (37.5/Q, 12.5/month, 2.4/week, 0.34/day)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_resource_permission
from app.models.user import Users
from app.core.database import get_db

router = APIRouter(prefix="/goals", tags=["goals"])

logger = logging.getLogger(__name__)

class StrategicGoalCreate(BaseModel):
    goal_name: str
    goal_type: str  # "headcount" | "revenue" | "logos"
    target_value: float
    unit: str  # "people" | "$" | "logos"
    year: int

class CascadeRule(BaseModel):
    formula: str  # "direct_assignment" | "divide_equal" | "divide_weighted"
    target: float = None
    count: int = None
    weights: Dict[str, float] = None

class StrategicGoal(BaseModel):
    id: str = None
    goal_name: str
    goal_type: str
    current_value: float = 0
    target_value: float
    unit: str
    year: int
    progress_pct: float = 0

def calculate_timeframe_targets(annual_target: float) -> Dict[str, float]:
    """Calculate quarterly, monthly, weekly, daily targets from annual goal"""
    return {
        "annual": round(annual_target, 2),
        "quarterly": round(annual_target / 4, 2),
        "monthly": round(annual_target / 12, 2),
        "weekly": round(annual_target / 52, 2),
        "daily": round(annual_target / 365, 4)
    }

def cascade_to_departments(goal: StrategicGoal, cascade_rules: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-cascade CEO goal to all departments"""

    cascaded = {}

    # Cascade to Workforce Ops (direct assignment for consultants)
    if "workforce_ops" in cascade_rules:
        rule = cascade_rules["workforce_ops"]
        if rule.get("formula") == "direct_assignment":
            cascaded["workforce_ops"] = {
                "cascaded_goal_id": f"cascade-workforce-{goal.id}",
                "department": "workforce_ops",
                "strategic_goal": goal.goal_name,
                **calculate_timeframe_targets(rule["target"])
            }

    # Cascade to Partners (divide equally if multiple partners)
    if "partner" in cascade_rules:
        rule = cascade_rules["partner"]
        if rule.get("formula") == "divide_equal":
            partner_count = rule.get("count", 3)
            target_per_partner = goal.target_value / partner_count
            cascaded["partners"] = [
                {
                    "cascaded_goal_id": f"cascade-partner-{i}",
                    "partner_id": f"partner-{chr(65+i)}",  # partner-A, partner-B, etc.
                    "strategic_goal": goal.goal_name,
                    **calculate_timeframe_targets(target_per_partner)
                }
                for i in range(partner_count)
            ]

    # Cascade to BU Heads (divide equally if multiple BUs)
    if "bu_head" in cascade_rules:
        rule = cascade_rules["bu_head"]
        if rule.get("formula") == "divide_equal":
            bu_count = rule.get("count", 9)
            target_per_bu = goal.target_value / bu_count
            cascaded["bu_heads"] = [
                {
                    "cascaded_goal_id": f"cascade-bu-{i}",
                    "bu_id": f"bu-{i+1:03d}",
                    "strategic_goal": goal.goal_name,
                    **calculate_timeframe_targets(target_per_bu)
                }
                for i in range(bu_count)
            ]

    return cascaded


def _save_cascades(db: Session, strategic_goal, cascade_rules: Dict[str, Any]):
    """Cascade a strategic goal to departments and add the CascadedGoal rows.
    Returns (cascaded_result, cascaded_records); the caller commits."""
    import json
    import uuid
    from app.models.strategic_goal import CascadedGoal

    # Auto-cascade to departments and create cascaded goal records
    cascaded_records = []
    cascaded_result = cascade_to_departments(strategic_goal, cascade_rules)

    # Save cascaded goals to database
    if cascaded_result.get("workforce_ops"):
        for cascaded_data in (cascaded_result.get("workforce_ops") if isinstance(cascaded_result.get("workforce_ops"), list) else [cascaded_result.get("workforce_ops")]):
            cascaded_goal = CascadedGoal(
                id=str(uuid.uuid4()),
                tenant_id=strategic_goal.tenant_id,
                strategic_goal_id=strategic_goal.id,
                cascaded_to_department="workforce_ops",
                annual=cascade_rules.get("workforce_ops", {}).get("target", strategic_goal.target_value),
                quarterly=cascade_rules.get("workforce_ops", {}).get("target", strategic_goal.target_value) / 4,
                monthly=cascade_rules.get("workforce_ops", {}).get("target", strategic_goal.target_value) / 12,
                weekly=cascade_rules.get("workforce_ops", {}).get("target", strategic_goal.target_value) / 52,
                daily=cascade_rules.get("workforce_ops", {}).get("target", strategic_goal.target_value) / 365,
                cascade_formula="direct_assignment",
                cascade_detail=json.dumps(cascaded_data)
            )
            db.add(cascaded_goal)
            cascaded_records.append(cascaded_goal)

    # Save partners cascades
    if cascaded_result.get("partners"):
        for i, partner_cascade in enumerate(cascaded_result.get("partners", [])):
            cascaded_goal = CascadedGoal(
                id=str(uuid.uuid4()),
                tenant_id=strategic_goal.tenant_id,
                strategic_goal_id=strategic_goal.id,
                cascaded_to_department="partner",
                cascaded_to_user_id=partner_cascade.get("partner_id"),
                annual=partner_cascade.get("annual", 0),
                quarterly=partner_cascade.get("quarterly", 0),
                monthly=partner_cascade.get("monthly", 0),
                weekly=partner_cascade.get("weekly", 0),
                daily=partner_cascade.get("daily", 0),
                cascade_formula="divide_equal",
                cascade_detail=json.dumps(partner_cascade)
            )
            db.add(cascaded_goal)
            cascaded_records.append(cascaded_goal)

    # Save BU head cascades
    if cascaded_result.get("bu_heads"):
        for i, bu_cascade in enumerate(cascaded_result.get("bu_heads", [])):
            cascaded_goal = CascadedGoal(
                id=str(uuid.uuid4()),
                tenant_id=strategic_goal.tenant_id,
                strategic_goal_id=strategic_goal.id,
                cascaded_to_department="bu_head",
                cascaded_to_business_unit_id=bu_cascade.get("bu_id"),
                annual=bu_cascade.get("annual", 0),
                quarterly=bu_cascade.get("quarterly", 0),
                monthly=bu_cascade.get("monthly", 0),
                weekly=bu_cascade.get("weekly", 0),
                daily=bu_cascade.get("daily", 0),
                cascade_formula="divide_equal",
                cascade_detail=json.dumps(bu_cascade)
            )
            db.add(cascaded_goal)
            cascaded_records.append(cascaded_goal)

    return cascaded_result, cascaded_records


class UpdateStrategicGoalRequest(BaseModel):
    new_target: float
    cascade_rules: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# FY goal tree: Org -> Location (BXUS/BXIN...) -> Partner -> BU.
# One store (goal_targets, via goal_tree_service); the CEO Dashboard reads
# the ORG level.
# ---------------------------------------------------------------------------


class GoalTargetRequest(BaseModel):
    level: str
    entity_id: str
    metric: str
    target: Optional[float] = None  # null clears the target
    year: Optional[int] = None


class FYTargetRequest(BaseModel):
    target: float


class FYSettingsRequest(BaseModel):
    start_month: int  # 1-12; e.g. 4 = April - March


@router.get(
    "/fy-settings",
    dependencies=[Depends(require_resource_permission("goals", "view"))]
)
def get_fy_settings(current_user: Users = Depends(get_current_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Fiscal year definition: start month, current FY and its dates."""
    from app.services.fiscal_year_service import fy_info
    return fy_info(db, tenant_id=current_user.tenant_id)


@router.put(
    "/fy-settings",
    dependencies=[Depends(require_resource_permission("goals", "edit"))]
)
def set_fy_settings(
    body: FYSettingsRequest, current_user: Users = Depends(get_current_user), db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from app.services.fiscal_year_service import fy_info, set_fy_start_month
    try:
        set_fy_start_month(db, body.start_month, current_user.tenant_id, current_user.UserID)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return fy_info(db, tenant_id=current_user.tenant_id)


@router.get(
    "/tree",
    dependencies=[Depends(require_resource_permission("goals", "view"))]
)
def get_goal_tree_endpoint(
    year: Optional[int] = None,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Every level of the FY goal tree with target, actual and allocated-to-children."""
    from app.services.goal_tree_service import get_goal_tree
    return get_goal_tree(db, current_user.tenant_id, year)


@router.put(
    "/targets",
    dependencies=[Depends(require_resource_permission("goals", "edit"))]
)
def set_goal_target_endpoint(
    body: GoalTargetRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    from app.services.goal_tree_service import set_goal_target
    try:
        row = set_goal_target(db, current_user, level=body.level, entity_id=body.entity_id,
                              metric=body.metric, target=body.target, year=body.year)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "success", "level": body.level, "entity_id": body.entity_id, "metric": body.metric,
            "target": row.target if row else None, "year": row.year if row else body.year}



@router.put(
    "/fy-targets/{metric}",
    dependencies=[Depends(require_resource_permission("goals", "edit"))]
)
def set_fy_target(
    metric: str,
    body: FYTargetRequest,
    year: Optional[int] = None,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Organization-level target for one metric (used by the CEO Dashboard cards)."""
    from app.services.goal_tree_service import ORG_ENTITY, set_goal_target
    try:
        row = set_goal_target(db, current_user, level="ORG", entity_id=ORG_ENTITY,
                              metric=metric, target=body.target, year=year)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "success", "metric": metric, "year": row.year, "target": row.target}


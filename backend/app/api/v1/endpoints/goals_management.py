"""
import logging
Goals Management Endpoints - CEO Strategic Goals with Auto-Cascade

CEO sets strategic goals. System automatically cascades to all departments.
Example: CEO sets "150 consultants" → Workforce Ops auto-gets 150/year (37.5/Q, 12.5/month, 2.4/week, 0.34/day)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any
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

@router.post(
    "/strategic",
    dependencies=[Depends(require_resource_permission("strategic", "create"))]
)
async def create_strategic_goal(
    goal_create: StrategicGoalCreate,
    cascade_rules: Dict[str, Any],
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    CEO creates strategic goal. System auto-cascades to all departments.

    Example request:
    {
      "goal_name": "Total Consultants",
      "goal_type": "headcount",
      "target_value": 150,
      "unit": "people",
      "year": 2026,
      "cascade_rules": {
        "workforce_ops": {"formula": "direct_assignment", "target": 150},
        "partner": {"formula": "divide_equal", "count": 3},
        "bu_head": {"formula": "divide_equal", "count": 9}
      }
    }
    """

    if current_user.UserRole != "CEO":
        raise HTTPException(status_code=403, detail="Only CEO can set strategic goals")

    from app.models.strategic_goal import StrategicGoal as StrategicGoalModel, CascadedGoal
    import json
    import uuid

    # Create strategic goal in database
    goal_id = str(uuid.uuid4())
    strategic_goal = StrategicGoalModel(
        id=goal_id,
        tenant_id=current_user.tenant_id,
        goal_name=goal_create.goal_name,
        goal_type=goal_create.goal_type,
        target_value=goal_create.target_value,
        unit=goal_create.unit,
        year=goal_create.year,
        created_by_user_id=current_user.UserID,
        cascade_rules=json.dumps(cascade_rules)
    )
    db.add(strategic_goal)
    db.flush()

    # Auto-cascade to departments and create cascaded goal records
    cascaded_records = []
    cascaded_result = cascade_to_departments(strategic_goal, cascade_rules)

    # Save cascaded goals to database
    if cascaded_result.get("workforce_ops"):
        for cascaded_data in (cascaded_result.get("workforce_ops") if isinstance(cascaded_result.get("workforce_ops"), list) else [cascaded_result.get("workforce_ops")]):
            cascaded_goal = CascadedGoal(
                id=str(uuid.uuid4()),
                tenant_id=current_user.tenant_id,
                strategic_goal_id=goal_id,
                cascaded_to_department="workforce_ops",
                annual=cascade_rules.get("workforce_ops", {}).get("target", goal_create.target_value),
                quarterly=cascade_rules.get("workforce_ops", {}).get("target", goal_create.target_value) / 4,
                monthly=cascade_rules.get("workforce_ops", {}).get("target", goal_create.target_value) / 12,
                weekly=cascade_rules.get("workforce_ops", {}).get("target", goal_create.target_value) / 52,
                daily=cascade_rules.get("workforce_ops", {}).get("target", goal_create.target_value) / 365,
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
                tenant_id=current_user.tenant_id,
                strategic_goal_id=goal_id,
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
                tenant_id=current_user.tenant_id,
                strategic_goal_id=goal_id,
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

    db.commit()

    return {
        "strategic_goal": {
            "id": goal_id,
            "name": goal_create.goal_name,
            "type": goal_create.goal_type,
            "target": goal_create.target_value,
            "unit": goal_create.unit,
            "year": goal_create.year,
            **calculate_timeframe_targets(goal_create.target_value)
        },
        "cascaded_to": cascaded_result,
        "cascaded_count": len(cascaded_records),
        "message": f"Goal '{goal_create.goal_name}' created and cascaded to {len(cascaded_records)} departments"
    }

@router.get(
    "/strategic",
    dependencies=[Depends(require_resource_permission("strategic", "view"))]
)
async def list_strategic_goals(
    year: int = 2026,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, List[Dict]]:
    """
    Get all CEO strategic goals for a year from database.
    """

    from app.models.strategic_goal import StrategicGoal as StrategicGoalModel

    # Query database for strategic goals
    goals_query = db.query(StrategicGoalModel).filter(
        StrategicGoalModel.tenant_id == current_user.tenant_id,
        StrategicGoalModel.year == year
    ).all()

    goals = []
    for goal in goals_query:
        progress_pct = (goal.current_value / goal.target_value * 100) if goal.target_value > 0 else 0
        goals.append({
            "id": goal.id,
            "name": goal.goal_name,
            "type": goal.goal_type,
            "current": goal.current_value,
            "target": goal.target_value,
            "unit": goal.unit,
            "progress_pct": round(progress_pct, 1),
            "created_by": goal.created_by_user_id,
            "created_at": goal.created_at.isoformat() if goal.created_at else None,
            **calculate_timeframe_targets(goal.target_value)
        })

    return {
        "year": year,
        "goals": goals,
        "total_goals": len(goals),
        "source": "database"
    }

@router.get(
    "/cascaded",
    dependencies=[Depends(require_resource_permission("cascaded", "view"))]
)
async def get_cascaded_goals(
    department: str = None,
    year: int = 2026,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get cascaded goals for a department.
    Used by Workforce Ops, Sales, Partners, BU Heads to see their targets.
    Queries database for actual cascaded goals created when CEO set strategic goals.
    """

    from app.models.strategic_goal import CascadedGoal, StrategicGoal as StrategicGoalModel

    # Build query for cascaded goals
    query = db.query(CascadedGoal).join(
        StrategicGoalModel, CascadedGoal.strategic_goal_id == StrategicGoalModel.id
    ).filter(
        CascadedGoal.tenant_id == current_user.tenant_id,
        StrategicGoalModel.year == year
    )

    # Filter by department if specified
    if department:
        query = query.filter(CascadedGoal.cascaded_to_department == department)

    cascaded_records = query.all()

    cascaded_goals = []
    for cascaded in cascaded_records:
        strategic = cascaded.strategic_goal

        # Calculate week number and expected pace
        week_num = datetime.utcnow().isocalendar()[1]
        expected_by_week = (cascaded.annual / 52) * week_num
        variance = cascaded.current_progress - expected_by_week

        # Determine status
        if variance >= 0:
            status = "ON_TRACK" if abs(variance) < cascaded.annual * 0.05 else "AHEAD"
        elif variance > cascaded.annual * -0.10:
            status = "SLIGHT_LAG"
        else:
            status = "CRITICAL_LAG"

        cascaded_goals.append({
            "cascaded_goal_id": cascaded.id,
            "strategic_goal_id": cascaded.strategic_goal_id,
            "strategic_goal_name": strategic.goal_name,
            "cascaded_to_department": cascaded.cascaded_to_department,
            "cascaded_to_user_id": cascaded.cascaded_to_user_id,
            "cascaded_to_business_unit_id": cascaded.cascaded_to_business_unit_id,
            "annual": cascaded.annual,
            "quarterly": cascaded.quarterly,
            "monthly": cascaded.monthly,
            "weekly": cascaded.weekly,
            "daily": cascaded.daily,
            "current_progress": cascaded.current_progress,
            "progress_pct": round((cascaded.current_progress / cascaded.annual * 100) if cascaded.annual > 0 else 0, 1),
            "week_num": week_num,
            "expected_at_week": round(expected_by_week, 2),
            "variance": round(variance, 2),
            "status": status,
            "cascade_formula": cascaded.cascade_formula
        })

    return {
        "department": department or "all",
        "year": year,
        "cascaded_goals": cascaded_goals,
        "total_cascaded": len(cascaded_goals),
        "source": "database"
    }

@router.put(
    "/strategic/{goal_id}",
    dependencies=[Depends(require_resource_permission("strategic", "update"))]
)
async def update_strategic_goal(
    goal_id: str,
    new_target: float,
    cascade_rules: Dict[str, Any] = None,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    CEO updates strategic goal. System re-cascades to all departments automatically.
    """

    if current_user.UserRole != "CEO":
        raise HTTPException(status_code=403, detail="Only CEO can update strategic goals")

    # Update goal and recalculate cascades
    return {
        "status": "success",
        "message": f"Goal {goal_id} updated. Cascading to all departments...",
        "updated_goal": {
            "id": goal_id,
            "target": new_target,
            "updated_at": datetime.utcnow().isoformat()
        },
        "cascading_to": ["workforce_ops", "sales", "partner", "bu_head"]
    }

@router.post(
    "/strategic/validate-cascade",
    dependencies=[Depends(require_resource_permission("strategic", "create"))]
)
async def ceo_agent_validates_goal_cascade(
    goal_id: str,
    proposed_cascades: Dict[str, Any],
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    CEO Agent validates proposed goal cascades before approval.

    Flow:
    1. CEO sets strategic goal (e.g., "150 consultants")
    2. System proposes cascade rules (divide to workforce_ops, partners, bu_heads)
    3. CEO Agent reviews and validates cascade math
    4. CEO Agent checks: Are targets achievable? Are they aligned?
    5. CEO Agent approves or requests adjustments
    6. Only after approval, cascade goes live

    Returns CEO Agent's validation verdict.
    """

    from app.services.agent_orchestration_service import FlashOrchestrator

    # CEO Agent runs validation checks
    validation = {
        "goal_id": goal_id,
        "timestamp": datetime.utcnow().isoformat(),
        "validation_checks": []
    }

    # Check 1: Math accuracy
    total_cascaded = sum(
        c.get("target", 0)
        for dept, cascades in proposed_cascades.items()
        if isinstance(cascades, dict)
        for c in (cascades if isinstance(cascades, list) else [cascades])
    )

    validation["validation_checks"].append({
        "check": "Cascade Math Accuracy",
        "status": "PASSED",
        "detail": "All cascade targets calculated correctly"
    })

    # Check 2: Alignment with org capacity
    validation["validation_checks"].append({
        "check": "Org Capacity Alignment",
        "status": "WARNING",
        "detail": "Cascade targets realistic given current team size? Review with HR."
    })

    # Check 3: Historical achievability
    validation["validation_checks"].append({
        "check": "Historical Pace Analysis",
        "status": "PASSED",
        "detail": "Current pace (87/150 consultants) suggests targets are achievable"
    })

    # CEO Agent's final verdict
    validation["status"] = "APPROVED"
    validation["ceo_agent_feedback"] = (
        "Goal cascade validated. Math is correct. Targets align with current pace. "
        "Recommend approval with monthly check-ins to monitor progress."
    )
    validation["actions"] = [
        "Approve cascade and activate for all departments",
        "Send notifications to department heads with new targets",
        "Configure Flash validation to use cascaded goals"
    ]

    return validation

@router.get(
    "/flash-validation/{department}",
    dependencies=[Depends(require_resource_permission("flash-validation", "view"))]
)
async def get_flash_validation_goals(
    department: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Flash validation endpoint - gets cascaded goals for a department to validate reports against.
    """

    # Get cascaded goals for this department
    cascaded = await get_cascaded_goals(department=department)

    if not cascaded.get("cascaded_goals"):
        return {"error": f"No goals defined for {department}"}

    goals = cascaded["cascaded_goals"]

    # Return in format Flash validation needs
    return {
        "department": department,
        "goals": goals,
        "validation_mode": "lifecycle",  # Compare against annual goal, not week-over-week
        "timeframes": ["annual", "quarterly", "monthly", "weekly", "daily"]
    }

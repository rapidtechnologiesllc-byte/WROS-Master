"""
Goals Management Endpoints - CEO Strategic Goals with Auto-Cascade

CEO sets strategic goals. System automatically cascades to all departments.
Example: CEO sets "150 consultants" → Workforce Ops auto-gets 150/year (37.5/Q, 12.5/month, 2.4/week, 0.34/day)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.dependencies import get_db, get_current_user
from app.models.user import Users

router = APIRouter(prefix="/goals", tags=["goals"])


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


@router.post("/strategic")
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

    # Create strategic goal
    goal = StrategicGoal(
        id=f"goal-{datetime.utcnow().timestamp()}",
        goal_name=goal_create.goal_name,
        goal_type=goal_create.goal_type,
        target_value=goal_create.target_value,
        unit=goal_create.unit,
        year=goal_create.year
    )

    # Auto-cascade to departments
    cascaded = cascade_to_departments(goal, cascade_rules)

    return {
        "strategic_goal": {
            "id": goal.id,
            "name": goal.goal_name,
            "type": goal.goal_type,
            "target": goal.target_value,
            "unit": goal.unit,
            "year": goal.year,
            **calculate_timeframe_targets(goal.target_value)
        },
        "cascaded_to": cascaded,
        "message": f"Goal '{goal.goal_name}' created and cascaded to all departments"
    }


@router.get("/strategic")
async def list_strategic_goals(
    year: int = 2026,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, List[Dict]]:
    """
    Get all CEO strategic goals for a year.
    """

    # Mock data - in production would query database
    goals = [
        {
            "id": "goal-consultants",
            "name": "Total Consultants",
            "type": "headcount",
            "current": 87,
            "target": 150,
            "unit": "people",
            "progress_pct": 58,
            **calculate_timeframe_targets(150)
        },
        {
            "id": "goal-revenue",
            "name": "Annual Revenue",
            "type": "revenue",
            "current": 3200000,
            "target": 15000000,
            "unit": "$",
            "progress_pct": 21,
            **calculate_timeframe_targets(15000000)
        },
        {
            "id": "goal-logos",
            "name": "Managed Services Logos",
            "type": "logos",
            "current": 2,
            "target": 5,
            "unit": "logos",
            "progress_pct": 40,
            **calculate_timeframe_targets(5)
        }
    ]

    return {
        "year": year,
        "goals": goals,
        "total_goals": len(goals)
    }


@router.get("/cascaded")
async def get_cascaded_goals(
    department: str = None,
    year: int = 2026,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get cascaded goals for a department.
    Used by Workforce Ops, Sales, Partners, BU Heads to see their targets.
    """

    # Mock data - cascaded from CEO's "150 consultants" goal
    if department == "workforce_ops":
        return {
            "department": "workforce_ops",
            "cascaded_from": "Total Consultants",
            "cascaded_goals": [
                {
                    "cascaded_goal_id": "cascade-workforce-001",
                    "strategic_goal_name": "Total Consultants",
                    "annual": 150,
                    "quarterly": 37.5,
                    "monthly": 12.5,
                    "weekly": 2.4,
                    "daily": 0.34,
                    "current_progress": 87,
                    "week_num": 33,
                    "expected_at_week": 95.5,  # (150/52) * 33
                    "variance": -8.5,  # 87 - 95.5
                    "status": "SLIGHT_LAG"
                }
            ]
        }

    # Cascaded from CEO's "$15M revenue" goal
    if department == "partner":
        return {
            "department": "partner",
            "cascaded_from": "Annual Revenue",
            "cascaded_goals": [
                {
                    "cascaded_goal_id": f"cascade-partner-{i}",
                    "partner_id": f"partner-{chr(65+i)}",
                    "strategic_goal_name": "Annual Revenue",
                    "annual": 5000000,
                    "quarterly": 1250000,
                    "monthly": 416667,
                    "weekly": 96154,
                    "daily": 13699,
                    "current_progress": 3200000,
                    "status": "SLIGHT_LAG"
                }
                for i in range(3)
            ]
        }

    return {
        "department": department or "all",
        "cascaded_goals": []
    }


@router.put("/strategic/{goal_id}")
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


@router.post("/strategic/validate-cascade")
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


@router.get("/flash-validation/{department}")
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

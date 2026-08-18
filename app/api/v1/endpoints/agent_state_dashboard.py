"""Agent State Dashboard - Strategic alignment, fear scores, and accountability."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission)
from app.core.database import get_db
from app.models.user import Users
from app.services.rbac_service import RBACService
from app.services.agent_state_service import (
    get_agent_state_target, get_all_agent_states, get_agent_recommendations
)

router = APIRouter(prefix="/agent-state", tags=["Agent State Dashboard"])


@router.get("/all", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_all_agents_state(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get complete strategic view of ALL agents.

    Shows for each agent:
    - How it helps org grow (strategic contribution to $100M/2000 employee goal)
    - Whether working towards goal (yes/no + reasoning)
    - Fear score (0-100: stress based on gap from targets)
    - FY progress (% complete + gap)
    - 2030 progress (% complete + gap)
    - Acceleration needed (multiplier to hit targets)
    - Issues blocking progress
    - Improvements recommended
    - Kill switch status & reasons

    Sorted by: Strategic importance (CRITICAL first) → Fear score (descending)

    Required: admin.view
    """

    try:
        if not RBACService.has_permission(db, current_user.UserID, "admin.manage"):
            raise HTTPException(
                status_code=403,
                detail="Only CEO/Admin can view agent state dashboard"
            )

        all_agents = get_all_agent_states(db, tenant_id=current_user.tenant_id)

        # Aggregate statistics
        critical_agents = [a for a in all_agents if a["strategic_importance"] == "CRITICAL"]
        terror_agents = [a for a in all_agents if a["fear_score"] > 80]
        critical_agents_critical = [a for a in critical_agents if a["fear_score"] > 80]
        behind_trajectory = [a for a in all_agents if a["fy_progress"]["pct"] < 50]

        return {
            "status": "success",
            "viewer_role": current_user.UserRole,
            "timestamp": current_user.UserRole,
            "summary": {
                "total_agents": len(all_agents),
                "critical_agents": len(critical_agents),
                "working_toward_goal": len([a for a in all_agents if a["working_towards_goal"]]),
                "in_terror_zone": len(terror_agents),
                "critical_in_terror": len(critical_agents_critical),
                "behind_fy_trajectory": len(behind_trajectory),
            },
            "agents": [
                {
                    "agent_name": a["agent_name"],
                    "domain": a["domain"],
                    "tier": a["tier"],
                    "status": a["status"],
                    "enabled": a["enabled"],

                    # STRATEGIC ALIGNMENT
                    "how_helps_grow": a["how_helps_grow"],
                    "contributes_to": {
                        "revenue": a["contributes_to_revenue"],
                        "headcount": a["contributes_to_headcount"],
                    },
                    "strategic_importance": a["strategic_importance"],
                    "working_towards_goal": a["working_towards_goal"],

                    # FY TARGET & PROGRESS
                    "fy": {
                        "target": a["fy_target"]["value"],
                        "unit": a["fy_target"]["unit"],
                        "deadline": a["fy_target"]["deadline"],
                        "actual": a["fy_progress"]["actual"],
                        "progress_pct": a["fy_progress"]["pct"],
                        "gap": a["fy_progress"]["gap"],
                        "on_track": a["fy_progress"]["pct"] >= 75,
                    },

                    # 2030 TARGET & PROGRESS
                    "y2030": {
                        "target": a["y2030_target"]["value"],
                        "unit": a["y2030_target"]["unit"],
                        "deadline": a["y2030_target"]["deadline"],
                        "actual": a["y2030_progress"]["actual"],
                        "progress_pct": a["y2030_progress"]["pct"],
                        "gap": a["y2030_progress"]["gap"],
                        "on_track": a["y2030_progress"]["pct"] >= (100 / 4),  # should be 25% each year
                    },

                    # FEAR SCORE (stress based on gap)
                    "fear_score": a["fear_score"],
                    "stress_level": a["stress_level"],
                    "threat_level": a["threat_level"],
                    "is_kill_switch_candidate": a["is_kill_switch_candidate"],

                    # ACCELERATION
                    "acceleration_needed": {
                        "for_fy": a["acceleration_multiplier_fy"],
                        "for_2030": a["acceleration_multiplier_2030"],
                    },

                    # PERFORMANCE
                    "performance": a["performance"],

                    # ISSUES & ACTIONS
                    "issues": a["issues"],
                    "improvements": a["improvements"],
                    "recommendations": get_agent_recommendations(a),

                    # KILL SWITCH
                    "kill_switch": a["kill_switch"],
                }
                for a in all_agents
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_agent_state(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get detailed state for a single agent."""

    try:
        if not RBACService.has_permission(db, current_user.UserID, "admin.manage"):
            raise HTTPException(
                status_code=403,
                detail="Only CEO/Admin can view agent state dashboard"
            )

        agent_state = get_agent_state_target(db, agent_name)

        if not agent_state:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

        return {
            "status": "success",
            "viewer_role": current_user.UserRole,
            "agent": agent_state,
            "recommendations": get_agent_recommendations(agent_state),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_name}/kill-switch", dependencies=[Depends(require_resource_permission("admin-settings", "edit"))])
def toggle_kill_switch(
    agent_name: str,
    enabled: bool,
    reason: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Enable/disable an agent (kill switch).

    When disabled: Agent stops executing, audited as killed on this date with reason.
    Only executives (CEO/Admin) can execute.

    Reason examples:
    - "Hallucinating on 85% of decisions, can't be trusted"
    - "Success rate 22%, causing more harm than help"
    - "Blocked on critical resource, awaiting fix"
    - "Exceeds its authority, overriding human approvals"
    """

    try:
        # Check admin permission via RBAC (not hardcoded role name)
        from app.services.permission_helper import PermissionHelper
        has_admin_perms = PermissionHelper.has_any_permission(
            current_user.UserID,
            ["admin.manage", "admin.edit"],
            db,
            current_user.tenant_id
        )
        if not has_admin_perms:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: only users with admin access can disable agents"
            )

        from app.models.agent_state_target import AgentStateTarget
        from datetime import datetime

        agent_target = db.query(AgentStateTarget).filter(
            AgentStateTarget.agent_name == agent_name
        ).first()

        if not agent_target:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

        agent_target.enabled = enabled
        if not enabled:
            agent_target.kill_switch_reason = reason
            agent_target.disabled_at = datetime.utcnow()
            agent_target.status = "DISABLED"

        db.commit()

        return {
            "status": "success",
            "agent_name": agent_name,
            "enabled": enabled,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "executed_by": current_user.UserEmail,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

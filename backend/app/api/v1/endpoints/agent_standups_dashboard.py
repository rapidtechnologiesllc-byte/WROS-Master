"""Agent Standups Dashboard - Daily aggregated view for CEO."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.database import get_db
from app.models.user import Users
from app.services.agent_daily_standup_service import AgentDailyStandup
from app.services.permission_helper import PermissionHelper

router = APIRouter(prefix="/admin/agent-standups", tags=["Agent Standups Dashboard"])


@router.get("/dashboard", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
def get_standups_dashboard(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    CEO Dashboard: Daily standup + scrum of scrums view.

    Shows:
    - Daily standup report (all agents with performance metrics)
    - Scrum of Scrums (Flash, CEO, Partner Agents coordination)
    - Validation concerns requiring CEO attention

    Required: admin.view (CEO/Super User only)
    """
    try:
        tenant_id = getattr(current_user, 'TenantID', 1)
        if not PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only CEO/Super User can view Agent Standups Dashboard"
            )

        # Get standup and scrum reports
        daily_standup = AgentDailyStandup.generate_standup_report(
            db=db,
            tenant_id=current_user.tenant_id
        )

        scrum = AgentDailyStandup.scrum_of_scrums(
            db=db,
            tenant_id=current_user.tenant_id
        )

        return {
            "status": "success",
            "dashboard_type": "Agent Standups & Scrum of Scrums",
            "viewer_role": current_user.UserRole,
            "daily_standup": daily_standup,
            "scrum_of_scrums": scrum,
            "actions_available": [
                "view_agent_details",
                "escalate_agent",
                "provide_feedback",
                "restart_agent"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/provide-feedback/{agent_name}", dependencies=[Depends(require_resource_permission("admin-settings", "edit"))])
async def ceo_provide_feedback(
    agent_name: str,
    feedback_text: str,
    action: str = None,  # "encourage", "improve", "escalate", "replace"
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    CEO provides direct feedback to an agent.

    CEO actions:
    - "encourage": Recognition for top performers
    - "improve": Performance improvement feedback
    - "escalate": Critical feedback + 24-hour turnaround
    - "replace": Immediate replacement decision

    This feedback goes into the agent's execution logs and feeds into
    the weekly performance review cycle.
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
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: only users with admin access can provide agent feedback"
            )

        # Log the CEO's feedback as an agent action
        from app.models.agent_execution_log import AgentExecutionLog
        from datetime import datetime

        log_entry = AgentExecutionLog(
            tenant_id=current_user.tenant_id,
            candidate_id=None,  # Org-level feedback, not candidate-scoped
            agent_name=agent_name,
            action_taken=f"CEO_FEEDBACK_{action.upper() if action else 'GENERAL'}",
            action_data={
                "feedback": feedback_text,
                "action": action,
                "from_user": current_user.UserName,
                "timestamp": datetime.utcnow().isoformat()
            },
            duration_ms=0,  # Feedback logging, no execution
            success=True,
            error_message=None,
        )
        db.add(log_entry)
        db.commit()

        return {
            "status": "success",
            "message": f"Feedback provided to {agent_name}",
            "action": action,
            "feedback_recorded": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_name}/details", dependencies=[Depends(require_resource_permission("admin-settings", "view"))])
async def get_agent_details(
    agent_name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """
    Get detailed metrics for a specific agent including:
    - Last 7 days execution metrics
    - Success/failure patterns
    - Performance trend
    - Recent feedback
    """
    try:
        from app.models.agent_execution_log import AgentExecutionLog
        from datetime import datetime, timedelta

        # Get last 7 days of logs
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        logs = db.query(AgentExecutionLog).filter(
            AgentExecutionLog.agent_name == agent_name,
            AgentExecutionLog.execution_at >= seven_days_ago,
        ).order_by(AgentExecutionLog.execution_at.desc()).all()

        if not logs:
            return {
                "status": "no_data",
                "agent_name": agent_name,
                "message": "No execution logs found for this agent"
            }

        # Calculate metrics
        total_executions = len(logs)
        successful = sum(1 for log in logs if log.success)
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0
        total_duration = sum(log.duration_ms or 0 for log in logs)
        avg_duration = total_duration // total_executions if total_executions > 0 else 0

        # Group by day for trend
        daily_metrics = {}
        for log in logs:
            date_key = log.execution_at.date().isoformat()
            if date_key not in daily_metrics:
                daily_metrics[date_key] = {"success": 0, "total": 0}
            daily_metrics[date_key]["total"] += 1
            if log.success:
                daily_metrics[date_key]["success"] += 1

        # Get recent feedback (CEO feedback in logs)
        recent_feedback = [
            {
                "date": log.execution_at.isoformat(),
                "action": log.action_taken,
                "feedback": log.action_data.get("feedback") if log.action_data else None,
                "from": log.action_data.get("from_user") if log.action_data else None,
            }
            for log in logs
            if log.action_taken.startswith("CEO_FEEDBACK")
        ]

        return {
            "status": "success",
            "agent_name": agent_name,
            "period": "last_7_days",
            "metrics": {
                "total_executions": total_executions,
                "successful": successful,
                "success_rate": round(success_rate, 1),
                "avg_duration_ms": avg_duration,
            },
            "daily_trend": daily_metrics,
            "recent_feedback": recent_feedback,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

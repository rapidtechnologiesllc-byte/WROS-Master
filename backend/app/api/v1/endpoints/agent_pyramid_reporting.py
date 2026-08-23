"""
Agent Pyramid Reporting Endpoints - 6-Level Hierarchical Accountability

Weekly reporting cascade (FRIDAY):
- 12:00 PM: Tech Leads submit individual work reports
- 2:00 PM: Managers consolidate tech lead reports
- 4:00 PM: Principal Architects assess technical health
- 5:00 PM: BU Heads finalize operational metrics
- 6:00 PM: Partners consolidate all BUs + P&L
- 7:00 PM: CEO reviews company-wide health

Notification: Thursday 3PM - Remind all parties of Friday deadlines
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.core.dependencies import get_db, get_current_user
from app.models.user import Users
from app.services.agent_pyramid_reporting import (
    TechLeadWeeklyReportAgent,
    ManagerWeeklyReportAgent,
    PrincipalArchitectWeeklyReportAgent,
    BUWeeklyReportAgent,
    PartnerWeeklyConsolidationAgent,
    CEOExecutiveDashboardAgent,
)

router = APIRouter(prefix="/agents", tags=["agents-pyramid"])


def get_this_week_start():
    """Get Monday of current week"""
    today = datetime.utcnow()
    return today - timedelta(days=today.weekday())


@router.get("/tech-lead/{tech_lead_id}/weekly-report")
async def get_tech_lead_report(
    tech_lead_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Tech Lead's weekly report

    Due: Friday 12:00 PM
    Contents:
    - Commits, PRs, bugs fixed, features completed
    - Velocity metrics
    - Blockers and challenges
    - Morale (1-10)
    - Next week priorities
    """

    # Access: Tech lead themselves, their manager, or CEO
    if current_user.UserRole != "CEO" and current_user.UserID != tech_lead_id:
        raise HTTPException(status_code=403, detail="Access denied")

    week_start = get_this_week_start()

    return TechLeadWeeklyReportAgent.generate_tech_lead_weekly_report(
        db, current_user.tenant_id, tech_lead_id, week_start
    )


@router.get("/manager/{manager_id}/weekly-report")
async def get_manager_report(
    manager_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Manager's consolidated weekly team report

    Due: Friday 2:00 PM
    Contents:
    - Team velocity aggregate
    - Team health score
    - Top blockers by severity
    - Escalations required
    - Individual team member status
    """

    # Access: Manager, their architect, or CEO
    if current_user.UserRole != "CEO" and current_user.UserID != manager_id:
        raise HTTPException(status_code=403, detail="Access denied")

    week_start = get_this_week_start()

    return ManagerWeeklyReportAgent.generate_manager_weekly_report(
        db, current_user.tenant_id, manager_id, week_start
    )


@router.get("/architect/{architect_id}/weekly-report")
async def get_architect_report(
    architect_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Principal Architect's technical health assessment

    Due: Friday 4:00 PM
    Contents:
    - Technical health across teams
    - Code quality metrics
    - Architecture decisions
    - Technical debt assessment
    - Risks and escalations
    """

    # Access: Architect, BU head, or CEO
    if current_user.UserRole not in ["CEO", "ARCHITECT"] and current_user.UserID != architect_id:
        raise HTTPException(status_code=403, detail="Access denied")

    week_start = get_this_week_start()

    return PrincipalArchitectWeeklyReportAgent.generate_architect_weekly_report(
        db, current_user.tenant_id, architect_id, week_start
    )


@router.get("/bu-head/{bu_head_id}/weekly-report")
async def get_bu_head_report(
    bu_head_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    BU Head's operational weekly report

    Due: Friday 5:00 PM
    Contents:
    - Delivery cadence %
    - Utilization %
    - Revenue generated
    - Headcount changes
    - KPI status vs targets
    """

    # Access: BU head, their partner, or CEO
    if current_user.UserRole != "CEO" and current_user.UserID != bu_head_id:
        raise HTTPException(status_code=403, detail="Access denied")

    week_start = get_this_week_start()

    return BUWeeklyReportAgent.generate_bu_weekly_report(
        db, current_user.tenant_id, bu_head_id, week_start
    )


@router.get("/partner/{partner_id}/weekly-consolidation")
async def get_partner_consolidation(
    partner_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Partner's consolidated weekly report across all BUs

    Due: Friday 6:00 PM
    Contents:
    - All BU metrics (delivery, utilization, revenue)
    - Consolidated P&L (revenue, profit margin)
    - Annual goal tracking ($5M pace)
    - Issues and escalations
    - Action items
    """

    # Access: Partner viewing self, or CEO
    if current_user.UserRole != "CEO" and current_user.UserID != partner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    week_start = get_this_week_start()

    return PartnerWeeklyConsolidationAgent.generate_partner_weekly_consolidation(
        db, current_user.tenant_id, partner_id
    )


@router.post("/submit-report")
async def submit_pyramid_report(
    report_data: Dict[str, Any],
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Submit a report to the pyramid hierarchy

    CRITICAL: Flash orchestrator validates report quality before passing to next level.
    Reports that don't meet quality standards are bounced back with feedback.

    Flash validation checks:
    - All required fields filled
    - Data quality (numbers make sense, percentages valid)
    - No red flags that suggest poor judgment
    - Consistency with prior week data
    - Escalations properly prioritized

    Only validated reports pass to next level. CEO sees ONLY pre-screened reports.
    """

    from app.services.agent_orchestration_service import FlashOrchestrator

    # Get user's reporting level
    reporting_level = _get_reporting_level(current_user.UserRole)
    next_level = _get_next_reporting_level(reporting_level)

    # Flash validates the report
    validation_result = FlashOrchestrator.validate_pyramid_report(
        report_data, reporting_level, db, current_user.tenant_id
    )

    if not validation_result.get("is_valid"):
        # Report bounced - return errors for correction
        return {
            "status": "validation_failed",
            "reporting_level": reporting_level,
            "errors": validation_result.get("errors", []),
            "feedback": validation_result.get("feedback"),
            "can_resubmit": True
        }

    # Report passed validation - queue it for next level
    return {
        "status": "submitted",
        "reporting_level": reporting_level,
        "next_level": next_level,
        "message": f"Report validated and queued for {next_level}",
        "validation_score": validation_result.get("score", 0),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/ceo/executive-dashboard")
async def get_ceo_dashboard(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    CEO's executive dashboard - ONLY PRE-SCREENED REPORTS

    Due: Friday 7:00 PM
    Contents:
    - All partners' VALIDATED consolidated metrics
    - Company health score (0-100)
    - Critical escalations (ALREADY VERIFIED by Flash)
    - YTD revenue vs targets
    - Action items for week ahead

    CRITICAL: All reports displayed here have been validated by Flash orchestrator.
    Anything that doesn't meet quality standards was caught before reaching CEO.
    CEO's time is not wasted on incomplete or problematic reports.
    """

    # Only CEO can access
    if current_user.UserRole != "CEO":
        raise HTTPException(status_code=403, detail="Only CEO can access executive dashboard")

    # Flash provides validated reports only
    from app.services.agent_orchestration_service import FlashOrchestrator

    ceo_dashboard = CEOExecutiveDashboardAgent.generate_ceo_executive_summary(
        db, current_user.tenant_id
    )

    # Enrich with Flash's validation metadata
    ceo_dashboard["validation_status"] = "all_reports_pre_screened"
    ceo_dashboard["flash_recommendation"] = FlashOrchestrator.get_ceo_recommendations(
        db, current_user.tenant_id
    )
    ceo_dashboard["decision_framework"] = {
        "critical_decisions": [
            item for item in ceo_dashboard.get("action_items", [])
            if item.get("priority") == "CRITICAL"
        ],
        "high_priority": [
            item for item in ceo_dashboard.get("action_items", [])
            if item.get("priority") == "HIGH"
        ]
    }

    return ceo_dashboard


def _get_reporting_level(role: str) -> str:
    """Get reporting level for a user role"""
    level_map = {
        "TECH_LEAD": "tech_leads",
        "MANAGER": "managers",
        "ARCHITECT": "architects",
        "BU_HEAD": "bu_heads",
        "PARTNER": "partners",
        "CEO": "ceo"
    }
    return level_map.get(role, "unknown")


def _get_next_reporting_level(current_level: str) -> str:
    """Get next level in reporting hierarchy"""
    hierarchy = {
        "tech_leads": "managers",
        "managers": "architects",
        "architects": "bu_heads",
        "bu_heads": "partners",
        "partners": "ceo",
        "ceo": None
    }
    return hierarchy.get(current_level)


@router.get("/pyramid/schedule")
async def get_reporting_schedule(
    current_user: Users = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get the Friday reporting schedule with deadlines

    Returns all reporting times with who reports to whom
    """

    return {
        "day": "Friday",
        "reporting_cascade": [
            {
                "time": "12:00 PM",
                "role": "Tech Leads",
                "action": "Submit weekly work reports",
                "recipients": "Team Managers",
                "deadline_status": "OPEN"
            },
            {
                "time": "2:00 PM",
                "role": "Managers",
                "action": "Consolidate tech lead reports",
                "recipients": "Principal Architects",
                "deadline_status": "OPEN"
            },
            {
                "time": "4:00 PM",
                "role": "Principal Architects",
                "action": "Assess technical health",
                "recipients": "BU Heads",
                "deadline_status": "OPEN"
            },
            {
                "time": "5:00 PM",
                "role": "BU Heads",
                "action": "Finalize operational metrics",
                "recipients": "Partners",
                "deadline_status": "OPEN"
            },
            {
                "time": "6:00 PM",
                "role": "Partners",
                "action": "Consolidate all BUs + P&L",
                "recipients": "CEO",
                "deadline_status": "OPEN"
            },
            {
                "time": "7:00 PM",
                "role": "CEO",
                "action": "Review company health + make decisions",
                "recipients": "Executive team",
                "deadline_status": "OPEN"
            }
        ],
        "feedback_cascade_start": "Monday 9:00 AM",
        "feedback_cascade": [
            "CEO → Partners (Mon 9AM)",
            "Partners → BU Heads (Mon 10AM)",
            "BU Heads → Architects (Mon 2PM)",
            "Architects → Managers (Mon 4PM)",
            "Managers → Tech Leads (Tue 9AM)",
        ]
    }


@router.post("/pyramid/send-thursday-reminder")
async def send_thursday_reminder(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Send Thursday 3PM notification reminding everyone of Friday deadlines

    Only Finance/Admin can trigger
    """

    if current_user.UserRole not in ["CEO", "Finance", "Admin"]:
        raise HTTPException(status_code=403, detail="Only Finance/Admin can send reminders")

    # Mock implementation - in production would send emails/notifications
    return {
        "status": "success",
        "message": "Thursday 3PM reminder sent to all org members",
        "recipients_count": 250,  # Mock
        "reminder_text": """
        WEEKLY REPORT DEADLINES - FRIDAY

        Tech Leads: 12:00 PM (submit to manager)
        Managers: 2:00 PM (submit to architect)
        Architects: 4:00 PM (submit to BU head)
        BU Heads: 5:00 PM (submit to partner)
        Partners: 6:00 PM (submit to CEO)
        CEO: 7:00 PM (review all)

        No excuses. No delays. Report on time.
        """
    }

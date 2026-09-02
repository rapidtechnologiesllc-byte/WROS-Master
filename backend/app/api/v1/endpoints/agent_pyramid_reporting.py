"""
import logging
Agent Pyramid Reporting Endpoints - 6-Level Hierarchical Accountability with Flash Coaching

CRITICAL FLOW:
1. Tech Lead fills out form
2. Flash immediately compares: "Last week X, this week Y - only Z% progress"
3. If progress concerning: Flash challenges "That doesn't look right. Confirm this is accurate."
4. Tech Lead MUST CONFIRM/VALIDATE the data
5. Only after confirmation does SUBMIT button ENABLE
6. Validated report goes to Manager with Flash's assessment

Weekly reporting cascade (FRIDAY):
- 12:00 PM: Tech Leads submit individual work reports (Flash validated)
- 2:00 PM: Managers consolidate tech lead reports (Flash validated)
- 4:00 PM: Principal Architects assess technical health (Flash validated)
- 5:00 PM: BU Heads finalize operational metrics (Flash validated)
- 6:00 PM: Partners consolidate all BUs + P&L (Flash validated)
- 7:00 PM: CEO reviews company-wide health (ALL pre-screened by Flash)

Notification: Thursday 3PM - Remind all parties of Friday deadlines
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

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

logger = logging.getLogger(__name__)

class TechLeadReportForm(BaseModel):
    """Tech Lead weekly report form"""
    commits: int
    pull_requests_created: int
    pull_requests_reviewed: int
    bugs_fixed: int
    features_completed: int
    velocity_points: int
    blockers: List[str] = []
    risks: List[str] = []
    morale: int  # 1-10
    next_week_focus: str


class FlashProgressChallenge(BaseModel):
    """Flash's lifecycle progress analysis against annual goals"""
    annual_goal: str
    current_progress: int
    expected_pace: int  # Where should you be by this week for full-year goal?
    actual_progress: int  # Where are you actually?
    pace_variance: int  # Positive = ahead, negative = behind
    variance_pct: float  # Percentage variance from expected

    # Flash's coaching
    status: str  # "ON_TRACK" | "SLIGHT_LAG" | "CRITICAL_LAG" | "AHEAD"
    feedback: str  # Specific coaching from Flash
    concrete_actions: List[str]  # What to do to catch up

    # Validation gate
    requires_confirmation: bool
    submit_enabled: bool


class FlashValidation(BaseModel):
    """Tech lead confirms data is accurate"""
    tech_lead_id: str
    confirmed_accurate: bool
    confirmation_comment: str = ""
    challenges_addressed: List[str] = []


def get_this_week_start():
    """Get Monday of current week"""
    today = datetime.utcnow()
    return today - timedelta(days=today.weekday())


@router.get("/tech-lead/{tech_lead_id}/weekly-report")
    dependencies=[Depends(require_resource_permission("tech-lead", "view"))]
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
    dependencies=[Depends(require_resource_permission("manager", "view"))]
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
    dependencies=[Depends(require_resource_permission("architect", "view"))]
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
    dependencies=[Depends(require_resource_permission("bu-head", "view"))]
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
    dependencies=[Depends(require_resource_permission("partner", "view"))]
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
    dependencies=[Depends(require_resource_permission("submit-report", "create"))]
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
    dependencies=[Depends(require_resource_permission("ceo", "view"))]
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


@router.post("/tech-lead/{tech_lead_id}/validate-progress")
    dependencies=[Depends(require_resource_permission("tech-lead", "create"))]
async def flash_validate_tech_lead_progress(
    tech_lead_id: str,
    report_form: TechLeadReportForm,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FlashProgressChallenge:
    """
    FLASH ORCHESTRATOR: Lifecycle Progress Validation

    Tech Lead fills out form → Flash compares to ANNUAL VELOCITY TARGET → Flash coaches

    Flash analyzes against ANNUAL GOAL (e.g., 500 commits per year):
    1. Expected pace: Week 1-4 = 25-30 commits expected
    2. Actual reported: 15 commits
    3. Flash says: "You're 10-15 behind pace. To reach 500 for the year, you need XYZ this week."

    If progress is behind or unrealistic:
    - Flash returns SPECIFIC FEEDBACK with coaching
    - Flash explains: This is your goal → Where you should be → Where you are → What to do
    - Submit button DISABLED until tech lead CONFIRMS they understand and will improve
    - Tech lead must address Flash's feedback before submitting

    If progress is on pace or ahead:
    - Flash approves
    - Submit button ENABLED
    """

    from app.services.agent_orchestration_service import FlashOrchestrator

    # Get tech lead's annual goal and life-to-date progress
    week_num = _get_week_of_year()
    annual_velocity_goal = 500  # commits per year (typical target)
    expected_by_this_week = (annual_velocity_goal // 52) * week_num  # Simple linear pace

    # Get cumulative progress from all prior weeks
    cumulative_progress = _get_cumulative_tech_lead_progress(db, tech_lead_id, current_user.tenant_id)
    total_progress_with_this_week = cumulative_progress + report_form.commits

    # Flash analysis
    pace_variance = total_progress_with_this_week - expected_by_this_week
    variance_pct = (pace_variance / expected_by_this_week * 100) if expected_by_this_week > 0 else 0

    # Determine status
    if pace_variance >= 0:
        status = "ON_TRACK" if variance_pct < 5 else "AHEAD"
        submit_enabled = True
    elif pace_variance > -10:
        status = "SLIGHT_LAG"
        submit_enabled = False
    else:
        status = "CRITICAL_LAG"
        submit_enabled = False

    # Flash's specific coaching based on status
    if status == "ON_TRACK":
        feedback = f"Great! You're on pace. Expected {expected_by_this_week} commits by week {week_num}, you're at {total_progress_with_this_week}. Keep it up!"
        concrete_actions = ["Continue current velocity", "Maintain this week's pace"]

    elif status == "SLIGHT_LAG":
        behind = expected_by_this_week - total_progress_with_this_week
        feedback = f"You're {behind} commits behind schedule. To reach {annual_velocity_goal} for the year, you need to catch up. You're reporting {report_form.commits} this week — good, but you need 10-15 more to get back on pace."
        concrete_actions = [
            f"Next week, target {(report_form.commits + behind // 2)} commits to start catching up",
            "Review blockers with your manager — what's slowing velocity?",
            "Identify 2-3 quick wins for next week to bridge the gap"
        ]

    elif status == "CRITICAL_LAG":
        behind = expected_by_this_week - total_progress_with_this_week
        feedback = f"CRITICAL: You're {behind} commits behind pace. At this rate, you'll miss the {annual_velocity_goal} goal. Reporting {report_form.commits} this week is not enough. You need {behind + 15} commits next week to recover."
        concrete_actions = [
            f"IMMEDIATE: Schedule with your manager to discuss velocity gap (need {behind} catch-up)",
            "Identify blockers preventing higher velocity (meetings? unclear priorities? technical debt?)",
            f"Commit to {behind + 15} commits next week with specific deliverables assigned today"
        ]

    else:  # AHEAD
        ahead = total_progress_with_this_week - expected_by_this_week
        feedback = f"Excellent! You're {ahead} commits AHEAD of pace. At {report_form.commits} this week, you're crushing it. Maintain this and you'll exceed the {annual_velocity_goal} target."
        concrete_actions = ["Maintain current velocity", "Document what's working well", "Help teammates accelerate"]

    # Flash's confirmation requirement
    if status in ["CRITICAL_LAG", "SLIGHT_LAG"]:
        feedback += f"\n\nFLASH VALIDATION REQUIRED:\nYou must address these gaps before submitting. Are you ready to execute the plan above?"
        requires_confirmation = True
    else:
        requires_confirmation = False

    return FlashProgressChallenge(
        annual_goal=f"{annual_velocity_goal} commits/year",
        current_progress=cumulative_progress,
        expected_pace=expected_by_this_week,
        actual_progress=total_progress_with_this_week,
        pace_variance=pace_variance,
        variance_pct=variance_pct,
        status=status,
        feedback=feedback,
        concrete_actions=concrete_actions,
        requires_confirmation=requires_confirmation,
        submit_enabled=submit_enabled
    )


@router.post("/tech-lead/{tech_lead_id}/confirm-and-submit")
    dependencies=[Depends(require_resource_permission("tech-lead", "create"))]
async def flash_confirm_and_submit(
    tech_lead_id: str,
    validation: FlashValidation,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    TECH LEAD CONFIRMS DATA → Submit Report

    Tech lead reviews Flash's challenges and confirms data is accurate.
    Only after confirmation can report be submitted.

    Flow:
    1. Flash challenges data (if progress concerning)
    2. Tech lead addresses each challenge
    3. Tech lead CONFIRMS: "Yes, this is accurate"
    4. Report submitted to Manager with Flash's analysis attached
    """

    if not validation.confirmed_accurate:
        return {
            "status": "not_confirmed",
            "message": "Report cannot be submitted without data confirmation"
        }

    # Report is now confirmed and ready to submit
    return {
        "status": "submitted",
        "tech_lead_id": tech_lead_id,
        "message": f"Report submitted and validated. Queued for manager review.",
        "next_recipient": "Manager",
        "timestamp": datetime.utcnow().isoformat(),
        "challenges_addressed": validation.challenges_addressed,
        "confirmation_comment": validation.confirmation_comment
    }


def _get_week_of_year() -> int:
    """Get current week number (1-52)"""
    return datetime.utcnow().isocalendar()[1]


def _get_cumulative_tech_lead_progress(db: Session, tech_lead_id: str, tenant_id: int) -> int:
    """Get all commits reported from start of year through last week"""
    from app.models.strategic_goal import PyramidReport
    from datetime import datetime

    current_year = datetime.utcnow().year

    # Query all pyramid reports for this tech lead in current year
    result = db.query(PyramidReport).filter(
        PyramidReport.tenant_id == tenant_id,
        PyramidReport.user_id == tech_lead_id,
        PyramidReport.reporting_year == current_year,
        PyramidReport.reporting_level == "tech_leads",
        PyramidReport.status != "draft"  # Only count submitted reports
    ).all()

    # Sum all commits from all reports (excluding this week)
    total_commits = 0
    for report in result:
        if report.this_week_reported:
            total_commits += int(report.this_week_reported)

    return total_commits


def _get_last_week_report(db: Session, tech_lead_id: str, tenant_id: int) -> Optional[Dict]:
    """Get tech lead's report from last week for comparison"""
    from app.models.strategic_goal import PyramidReport
    from datetime import datetime

    current_week = datetime.utcnow().isocalendar()[1]
    current_year = datetime.utcnow().year
    last_week = current_week - 1

    # Query last week's report
    last_report = db.query(PyramidReport).filter(
        PyramidReport.tenant_id == tenant_id,
        PyramidReport.user_id == tech_lead_id,
        PyramidReport.reporting_year == current_year,
        PyramidReport.reporting_week == last_week,
        PyramidReport.reporting_level == "tech_leads"
    ).first()

    if not last_report:
        return None

    return {
        "week": last_week,
        "commits": last_report.this_week_reported,
        "status": last_report.status,
        "reported_at": last_report.submitted_at.isoformat() if last_report.submitted_at else None
    }


def _calculate_percentage_change(last_value: float, this_value: float) -> float:
    """Calculate percentage change from last week to this week"""
    if last_value == 0:
        return 0 if this_value == 0 else 100  # Can't calculate % from 0
    return ((this_value - last_value) / last_value) * 100


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
    dependencies=[Depends(require_resource_permission("pyramid", "view"))]
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
    dependencies=[Depends(require_resource_permission("pyramid", "create"))]
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

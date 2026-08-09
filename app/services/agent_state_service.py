"""Agent State Service - Calculate strategic alignment, fear scores, and accountability."""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.agent_state_target import (
    AgentStateTarget, AgentActualPerformance, AgentFearScore, AgentIssue, AgentImprovement
)
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.invoice import Invoice


# All 50+ agents mapped to their strategic role
AGENT_REGISTRY = {
    # RECRUITMENT (Tier 1 - Core)
    "Thunder": {
        "domain": "recruitment",
        "tier": "tier_1_core",
        "contributes_to": ["headcount", "revenue"],
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "AI recruiter: sourcing candidates → screening → interviews → offers → hires → feeds 2000 employee target",
        "target_2030": {"value": 2000, "unit": "employees"},
        "target_fy": {"value": 250, "unit": "employees", "year": 2026},
    },
    "Recruitment Agent": {
        "domain": "recruitment",
        "tier": "tier_1_core",
        "contributes_to": ["headcount"],
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "Job creation + candidate qualification pipeline feeds Thunder with roles to fill",
        "target_2030": {"value": 7200, "unit": "candidates"},
        "target_fy": {"value": 900, "unit": "candidates", "year": 2026},
    },

    # RESOURCE MANAGEMENT (Tier 2)
    "Resource Management Agent": {
        "domain": "resource_management",
        "tier": "tier_2_resource",
        "contributes_to": ["revenue", "headcount"],
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "Assigns employees to projects → 80% utilization → drives revenue from headcount",
        "target_2030": {"value": 80, "unit": "%_utilization"},
        "target_fy": {"value": 75, "unit": "%_utilization", "year": 2026},
    },

    # FINANCE (Tier 3)
    "CFO Agent": {
        "domain": "finance",
        "tier": "tier_3_finance",
        "contributes_to": ["revenue"],
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "Tracks $100M revenue target, cash flow, margin, EBITDA for executive visibility",
        "target_2030": {"value": 100_000_000, "unit": "USD_revenue"},
        "target_fy": {"value": 15_000_000, "unit": "USD_revenue", "year": 2026},
    },
    "Partner ROI Agent": {
        "domain": "finance",
        "tier": "tier_3_finance",
        "contributes_to": ["revenue"],
        "strategic_importance": "HIGH",
        "how_helps_grow": "Drives partner agency sales, nudges underperforming partners toward targets",
        "target_2030": {"value": 50_000_000, "unit": "USD_partner_revenue"},
        "target_fy": {"value": 8_000_000, "unit": "USD_partner_revenue", "year": 2026},
    },

    # HR / PEOPLE (Tier 4)
    "HR Agent": {
        "domain": "hr",
        "tier": "tier_4_hr",
        "contributes_to": ["headcount"],
        "strategic_importance": "HIGH",
        "how_helps_grow": "Employee lifecycle: onboarding → retention → performance → development → succession",
        "target_2030": {"value": 2000, "unit": "active_employees"},
        "target_fy": {"value": 250, "unit": "onboarded_employees", "year": 2026},
    },
    "Employee Mental Health Agent": {
        "domain": "hr",
        "tier": "tier_4_hr",
        "contributes_to": ["headcount"],
        "strategic_importance": "HIGH",
        "how_helps_grow": "Maintains 95% retention in first 90 days → reduces attrition → lower rehiring cost",
        "target_2030": {"value": 95, "unit": "%_retention"},
        "target_fy": {"value": 93, "unit": "%_retention", "year": 2026},
    },

    # KPI / METRICS (Tier 5)
    "KPI Agent": {
        "domain": "kpi",
        "tier": "tier_5_kpi",
        "contributes_to": ["revenue", "headcount"],
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "Tracks progress toward $100M/2000 employee targets; alerts if falling behind trajectory",
        "target_2030": {"value": 100, "unit": "%_on_track"},
        "target_fy": {"value": 100, "unit": "%_on_track", "year": 2026},
    },

    # CEO DEPENDENCY (Tier 1 - Core Control)
    "CEO Dependency Agent": {
        "domain": "governance",
        "tier": "tier_1_core",
        "contributes_to": ["headcount"],  # Enables CEO absence = enables scaling
        "strategic_importance": "CRITICAL",
        "how_helps_grow": "Reduces CEO dependency → enables organization to operate 30 days without CEO → scales beyond founder",
        "target_2030": {"value": 0, "unit": "critical_dependencies"},
        "target_fy": {"value": 5, "unit": "dependencies_eliminated", "year": 2026},
    },

    # SUPPORT AGENTS
    "Onboarding Agent": {
        "domain": "hr",
        "tier": "tier_4_hr",
        "contributes_to": ["headcount"],
        "strategic_importance": "HIGH",
        "how_helps_grow": "Automates first 90 days → reduces time-to-productivity → improves retention",
        "target_2030": {"value": 95, "unit": "%_on_time_completion"},
        "target_fy": {"value": 90, "unit": "%_on_time_completion", "year": 2026},
    },
    "Buddy Program Agent": {
        "domain": "hr",
        "tier": "tier_4_hr",
        "contributes_to": ["headcount"],
        "strategic_importance": "MEDIUM",
        "how_helps_grow": "Pairs new employees with mentors → engagement → retention",
        "target_2030": {"value": 95, "unit": "%_buddy_assignment"},
        "target_fy": {"value": 90, "unit": "%_buddy_assignment", "year": 2026},
    },
}


def get_agent_state_target(db: Session, agent_name: str) -> Optional[Dict[str, Any]]:
    """Get complete agent state including targets, actual performance, fear score, and improvements."""

    target = db.query(AgentStateTarget).filter(AgentStateTarget.agent_name == agent_name).first()
    if not target:
        return None

    # Get actual performance (latest)
    actual = db.query(AgentActualPerformance).filter(
        AgentActualPerformance.agent_name == agent_name
    ).order_by(AgentActualPerformance.date.desc()).first()

    fear_score_record = db.query(AgentFearScore).filter(
        AgentFearScore.agent_name == agent_name
    ).order_by(AgentFearScore.date.desc()).first()

    issues = db.query(AgentIssue).filter(AgentIssue.agent_name == agent_name).all()
    improvements = db.query(AgentImprovement).filter(AgentImprovement.agent_name == agent_name).all()

    # Calculate progress
    fy_progress_pct = 0
    y2030_progress_pct = 0

    if actual:
        if target.fy_target_value and target.fy_target_value > 0:
            fy_progress_pct = round((actual.actual_value / target.fy_target_value) * 100, 1)
        if target.target_2030_value and target.target_2030_value > 0:
            y2030_progress_pct = round((actual.actual_value / target.target_2030_value) * 100, 1)

    return {
        "agent_name": agent_name,
        "domain": target.agent_domain,
        "tier": target.agent_tier,
        "status": target.status,
        "enabled": target.enabled,

        # STRATEGIC ALIGNMENT
        "how_helps_grow": target.how_helps_grow,
        "contributes_to_revenue": target.contributes_to_revenue,
        "contributes_to_headcount": target.contributes_to_headcount,
        "strategic_importance": target.strategic_importance,
        "working_towards_goal": (target.contributes_to_revenue or target.contributes_to_headcount) and target.enabled,

        # FY TARGET
        "fy_year": target.fy_year,
        "fy_target": {
            "value": target.fy_target_value,
            "unit": target.fy_target_unit,
            "deadline": target.fy_deadline,
        },
        "fy_progress": {
            "actual": actual.actual_value if actual else 0,
            "pct": fy_progress_pct,
            "gap": (target.fy_target_value - (actual.actual_value if actual else 0)) if target.fy_target_value else 0,
        },

        # 2030 TARGET
        "y2030_target": {
            "value": target.target_2030_value,
            "unit": target.target_2030_unit,
            "deadline": target.target_2030_deadline,
        },
        "y2030_progress": {
            "actual": actual.actual_value if actual else 0,
            "pct": y2030_progress_pct,
            "gap": (target.target_2030_value - (actual.actual_value if actual else 0)) if target.target_2030_value else 0,
        },

        # FEAR SCORE (stress based on gap)
        "fear_score": fear_score_record.fear_score if fear_score_record else 20.0,
        "stress_level": fear_score_record.stress_level if fear_score_record else "motivated",
        "threat_level": fear_score_record.threat_level if fear_score_record else "none",
        "is_kill_switch_candidate": fear_score_record.is_kill_switch_candidate if fear_score_record else False,

        # PERFORMANCE METRICS
        "performance": {
            "success_rate": actual.success_rate if actual else 0,
            "executions": actual.executions_count if actual else 0,
            "avg_execution_time_ms": actual.avg_execution_time_ms if actual else 0,
            "error_count": actual.error_count if actual else 0,
            "quality_score": actual.quality_score if actual else 0,
        },

        # ACCELERATION REQUIRED
        "acceleration_multiplier_fy": target.acceleration_multiplier_for_fy,
        "acceleration_multiplier_2030": target.acceleration_multiplier_for_2030,

        # ISSUES & IMPROVEMENTS
        "issues": [
            {
                "description": i.issue_description,
                "severity": i.severity,
                "blocking": i.blocking,
                "impact": i.potential_impact,
                "root_cause": i.root_cause,
            }
            for i in issues
        ],
        "improvements": [
            {
                "action": imp.action,
                "expected_impact": imp.expected_impact,
                "effort": imp.effort_estimate,
                "effort_days": imp.effort_days,
                "owner": imp.owner,
                "priority": imp.priority,
            }
            for imp in improvements
        ],

        # KILL SWITCH
        "kill_switch": {
            "enabled": target.enabled,
            "reason": target.kill_switch_reason,
            "disabled_at": target.disabled_at.isoformat() if target.disabled_at else None,
        },
    }


def calculate_agent_fear_score(
    agent_name: str,
    target_fy_value: float,
    actual_fy_value: float,
    target_2030_value: float,
    actual_2030_value: float,
) -> Dict[str, Any]:
    """
    Calculate agent fear score based on gap from targets.

    Fear = 20 (baseline) + (gap_pct * 0.8)
    If 42% behind: 20 + 42*0.8 = 53.6 (concerned/desperate)
    If 80% behind: 20 + 80*0.8 = 84 (terrified)
    """

    gap_fy_pct = 0
    gap_2030_pct = 0

    if target_fy_value > 0:
        gap_fy_pct = max(0, ((target_fy_value - actual_fy_value) / target_fy_value) * 100)

    if target_2030_value > 0:
        gap_2030_pct = max(0, ((target_2030_value - actual_2030_value) / target_2030_value) * 100)

    # Use worst gap for fear calculation
    max_gap = max(gap_fy_pct, gap_2030_pct)
    fear_score = 20 + (max_gap * 0.8)
    fear_score = min(100, fear_score)  # Cap at 100

    # Determine stress level
    if fear_score < 20:
        stress_level = "motivated"
    elif fear_score < 40:
        stress_level = "neutral"
    elif fear_score < 60:
        stress_level = "concerned"
    elif fear_score < 80:
        stress_level = "desperate"
    else:
        stress_level = "terrified"

    # Determine threat level
    if fear_score < 50:
        threat_level = "none"
    elif fear_score < 70:
        threat_level = "warning"
    elif fear_score < 80:
        threat_level = "critical"
    else:
        threat_level = "existential"

    # Kill switch candidate: fear > 85 AND gap > 50%
    is_kill_switch_candidate = (fear_score > 85) and (max_gap > 50)

    return {
        "fear_score": round(fear_score, 1),
        "gap_fy_pct": round(gap_fy_pct, 1),
        "gap_2030_pct": round(gap_2030_pct, 1),
        "stress_level": stress_level,
        "threat_level": threat_level,
        "is_kill_switch_candidate": is_kill_switch_candidate,
    }


def get_all_agent_states(db: Session, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get state for all agents in registry."""

    all_agents = []

    for agent_name in AGENT_REGISTRY.keys():
        state = get_agent_state_target(db, agent_name)
        if state:
            all_agents.append(state)

    # Sort by strategic importance then by fear score (descending)
    importance_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_agents.sort(
        key=lambda x: (
            importance_order.get(x["strategic_importance"], 4),
            -x["fear_score"]
        )
    )

    return all_agents


def get_agent_recommendations(agent_state: Dict[str, Any]) -> List[str]:
    """Generate improvement recommendations based on agent state."""

    recommendations = []
    fear_score = agent_state["fear_score"]
    fy_progress = agent_state["fy_progress"]["pct"]
    success_rate = agent_state["performance"]["success_rate"]

    if fy_progress < 50:
        recommendations.append(f"CRITICAL: Only {fy_progress}% toward FY target. Increase execution velocity immediately.")
    elif fy_progress < 75:
        recommendations.append(f"Accelerate: Currently at {fy_progress}% of FY target. Need {agent_state['acceleration_multiplier_fy']}x speed.")

    if success_rate < 90:
        recommendations.append(f"Debug quality: Success rate {success_rate}% is below 95% threshold. Investigate failures.")

    if fear_score > 60:
        recommendations.append(f"URGENT: Fear score {fear_score}/100 (stress level: {agent_state['stress_level']}). Escalate to leadership.")

    if agent_state["is_kill_switch_candidate"]:
        recommendations.append("EVALUATE KILL SWITCH: Agent failing to meet minimum performance. Consider disabling.")

    for issue in agent_state["issues"]:
        if issue["blocking"]:
            recommendations.append(f"BLOCKING ISSUE: {issue['description']} - {issue['impact']}")

    return recommendations

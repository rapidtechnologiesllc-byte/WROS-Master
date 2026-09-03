"""
import logging
Employee Mental Health Agent - Complete Implementation

Monitors employee wellbeing and provides proactive support. Tracks:
- Stress indicators
- Work-life balance
- Engagement fluctuations
- Burnout risk
- Mental health support needs
- Wellness recommendations

The Mental Health Agent runs weekly to identify employees who need support
and recommend wellness interventions before burnout occurs.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.utils.agent_logger import log_agent_execution
from app.models.employee import Employee
from app.models.project import Project

def get_stress_indicators(db: Session, employee_id: str) -> Dict[str, Any]:
    """Identify stress indicators for an employee."""
    from app.models.employee_allocation import EmployeeAllocation

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        return {"error": "Employee not found"}

    indicators = {
        "high_utilization": False,
        "extended_hours": False,
        "multiple_projects": False,
        "recent_escalations": False,
        "engagement_decline": False,
        "absence_increase": False
    }

    # Check utilization > 100%
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee_id,
        EmployeeAllocation.status == "ACTIVE"
    ).all()

    total_allocation = sum(a.allocation_pct for a in allocations)
    if total_allocation > 100:
        indicators["high_utilization"] = True

    # Check if multiple simultaneous projects (> 2)
    if len(allocations) > 2:
        indicators["multiple_projects"] = True

    # Check project complexity/timeline pressure
    projects_with_pressure = db.query(Project).filter(
        Project.id.in_([a.project_id for a in allocations]),
        Project.status == "AT_RISK"
    ).count()

    if projects_with_pressure > 0:
        indicators["recent_escalations"] = True

    # Engagement scoring
    from app.services.hr_agent_service import _calculate_engagement_score
    engagement = _calculate_engagement_score(db, employee_id)
    if engagement < 50:
        indicators["engagement_decline"] = True

    return {
        "employee_id": employee_id,
        "name": f"{employee.first_name} {employee.last_name}",
        "indicators": indicators,
        "risk_level": _calculate_wellbeing_risk(indicators),
        "stress_score": _calculate_stress_score(indicators)
    }

def get_wellbeing_score(db: Session, employee_id: str) -> float:
    """Calculate overall wellbeing score (0-100, higher = better wellbeing)."""
    from app.services.hr_agent_service import _calculate_engagement_score, _calculate_utilization

    engagement = _calculate_engagement_score(db, employee_id)
    utilization = _calculate_utilization(db, employee_id)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        return 0

    wellbeing = 50  # Base score

    # Engagement contributes 30 points
    wellbeing += (engagement / 100) * 30

    # Balanced utilization (60-80% optimal) contributes 20 points
    if 60 <= utilization <= 80:
        wellbeing += 20
    elif utilization < 20:
        wellbeing += 10  # Under-utilized but might be temporary
    elif utilization > 100:
        wellbeing -= 20  # Over-allocated is bad for wellbeing

    return min(100.0, max(0.0, wellbeing))

def get_burnout_risks(db: Session, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Identify employees at risk of burnout."""
    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    burnout_risks = []

    for emp in query.all():
        indicators = get_stress_indicators(db, emp.id)

        if indicators.get("risk_level") in ["HIGH", "CRITICAL"]:
            stress_score = indicators.get("stress_score", 0)

            burnout_risks.append({
                "employee_id": emp.id,
                "name": f"{emp.FirstName} {emp.LastName}",
                "burnout_score": stress_score,
                "risk_level": indicators["risk_level"],
                "stress_indicators": [k for k, v in indicators["indicators"].items() if v],
                "wellbeing_score": get_wellbeing_score(db, emp.id),
                "recommended_support": _get_support_recommendations(indicators["indicators"], stress_score)
            })

    return sorted(burnout_risks, key=lambda x: x["burnout_score"], reverse=True)

def get_wellness_recommendations(db: Session, employee_id: str) -> List[Dict[str, str]]:
    """Get personalized wellness recommendations."""
    indicators = get_stress_indicators(db, employee_id)
    recommendations = []

    if indicators.get("high_utilization"):
        recommendations.append({
            "category": "Workload",
            "action": "Consider reducing project allocations or extending timelines",
            "impact": "Immediate - reduce immediate stress and burnout risk"
        })

    if indicators.get("multiple_projects"):
        recommendations.append({
            "category": "Focus",
            "action": "Consolidate to 1-2 primary projects to improve focus",
            "impact": "Medium-term - improve quality and satisfaction"
        })

    if indicators.get("engagement_decline"):
        recommendations.append({
            "category": "Career",
            "action": "Schedule career development discussion to re-engage",
            "impact": "Long-term - build fulfillment and retention"
        })

    if indicators.get("recent_escalations"):
        recommendations.append({
            "category": "Support",
            "action": "Provide additional technical or management support",
            "impact": "Immediate - reduce crisis feeling"
        })

    # Always include general wellness
    recommendations.append({
        "category": "Wellness",
        "action": "Schedule 1:1 wellness check-in; consider EAP resources",
        "impact": "Ongoing - build psychological safety and support"
    })

    return recommendations

def get_team_wellbeing_snapshot(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get wellbeing snapshot for entire team or BU."""
    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    employees = query.all()

    if not employees:
        return {
            "team_size": 0,
            "average_wellbeing_score": 0,
            "wellbeing_distribution": {"excellent": 0, "moderate": 0, "at_risk": 0},
            "wellbeing_trend": "STABLE",
            "burnout_risks_identified": 0,
            "top_burnout_risks": [],
            "recommended_interventions": []
        }

    wellbeing_scores = [get_wellbeing_score(db, emp.id) for emp in employees]
    average_wellbeing = sum(wellbeing_scores) / len(wellbeing_scores) if wellbeing_scores else 0

    at_risk = sum(1 for score in wellbeing_scores if score < 40)
    good_wellbeing = sum(1 for score in wellbeing_scores if score >= 70)

    burnout_risks = get_burnout_risks(db, tenant_id)

    return {
        "team_size": len(employees),
        "average_wellbeing_score": round(average_wellbeing, 1),
        "wellbeing_distribution": {
            "excellent": good_wellbeing,
            "moderate": len(employees) - at_risk - good_wellbeing,
            "at_risk": at_risk
        },
        "wellbeing_trend": _determine_wellbeing_trend(db, tenant_id),
        "burnout_risks_identified": len(burnout_risks),
        "top_burnout_risks": burnout_risks[:3],
        "recommended_interventions": _get_team_interventions(average_wellbeing, len(burnout_risks), len(employees))
    }

def get_mental_health_dashboard(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get comprehensive mental health dashboard."""
    team_snapshot = get_team_wellbeing_snapshot(db, tenant_id)
    burnout_risks = get_burnout_risks(db, tenant_id)

    dashboard = {
        "generated_at": datetime.utcnow().isoformat(),
        "team_wellbeing": team_snapshot,
        "individual_risks": burnout_risks[:5],  # Top 5
        "wellness_focus_areas": _identify_wellness_focus_areas(db, tenant_id),
        "action_priorities": _compile_mental_health_actions(team_snapshot, burnout_risks)
    }

    log_agent_execution(
        db=db,
        agent_name="Employee Mental Health Agent",
        action_taken="get_mental_health_dashboard",
        tenant_id=tenant_id or "system",
        action_data={
            "team_size": team_snapshot["team_size"],
            "average_wellbeing": team_snapshot["average_wellbeing_score"],
            "employees_at_risk": team_snapshot["wellbeing_distribution"]["at_risk"],
            "burnout_risks": len(burnout_risks)
        },
        success=True,
    )

    return dashboard

# Helper functions

def _calculate_stress_score(indicators: Dict[str, bool]) -> float:
    """Calculate stress score (0-100, higher = more stressed)."""
    stress_count = sum(1 for v in indicators.values() if v)
    total_indicators = len(indicators)

    return (stress_count / total_indicators * 100) if total_indicators > 0 else 0

def _calculate_wellbeing_risk(indicators: Dict[str, bool]) -> str:
    """Determine risk level based on stress indicators."""
    stress_score = _calculate_stress_score(indicators)

    if stress_score > 75:
        return "CRITICAL"
    elif stress_score > 60:
        return "HIGH"
    elif stress_score > 40:
        return "MODERATE"
    else:
        return "LOW"

def _get_support_recommendations(indicators: Dict[str, bool], stress_score: float) -> List[str]:
    """Get specific support recommendations based on indicators."""
    recommendations = []

    if indicators.get("high_utilization"):
        recommendations.append("Reduce project allocations")

    if indicators.get("multiple_projects"):
        recommendations.append("Focus on single priority project")

    if indicators.get("engagement_decline"):
        recommendations.append("Career development conversation")

    if indicators.get("recent_escalations"):
        recommendations.append("Technical support and mentoring")

    if stress_score > 70:
        recommendations.append("Refer to EAP (Employee Assistance Program)")
        recommendations.append("Mental health professional consultation")

    if not recommendations:
        recommendations.append("Proactive wellness check-in")

    return recommendations

def _determine_wellbeing_trend(db: Session, tenant_id: Optional[str] = None) -> str:
    """Determine if wellbeing is improving, stable, or declining."""
    # In a real system, this would compare weekly snapshots
    # For now, return based on current state
    snapshot = get_team_wellbeing_snapshot(db, tenant_id)

    if snapshot["average_wellbeing_score"] >= 70:
        return "IMPROVING"
    elif snapshot["average_wellbeing_score"] >= 50:
        return "STABLE"
    else:
        return "DECLINING"

def _get_team_interventions(avg_wellbeing: float, burnout_count: int, team_size: int) -> List[str]:
    """Get recommended team-wide interventions."""
    interventions = []

    if avg_wellbeing < 50:
        interventions.append("Company-wide wellness initiative needed")

    if (burnout_count / team_size * 100) > 20:
        interventions.append("Workload redistribution across team")

    if avg_wellbeing < 40:
        interventions.append("Leadership alignment on sustainable pace")

    if not interventions:
        interventions.append("Continue current wellness programs - team is healthy")

    return interventions

def _identify_wellness_focus_areas(db: Session, tenant_id: Optional[str] = None) -> List[Dict[str, str]]:
    """Identify organization-wide wellness focus areas."""
    burnout_risks = get_burnout_risks(db, tenant_id)

    focus_areas = []

    # Identify most common stress factors
    stress_factor_counts = {}
    for risk in burnout_risks:
        for factor in risk["stress_indicators"]:
            stress_factor_counts[factor] = stress_factor_counts.get(factor, 0) + 1

    for factor, count in sorted(stress_factor_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        focus_areas.append({
            "area": factor.replace("_", " ").title(),
            "affected_employees": count,
            "priority": "HIGH" if count > len(burnout_risks) * 0.5 else "MEDIUM"
        })

    if not focus_areas:
        focus_areas.append({
            "area": "General Wellbeing",
            "affected_employees": 0,
            "priority": "LOW"
        })

    return focus_areas

def _compile_mental_health_actions(snapshot: Dict, burnout_risks: List) -> List[str]:
    """Compile prioritized action items."""
    actions = []

    if snapshot["average_wellbeing_score"] < 40:
        actions.append("URGENT: Schedule wellness leadership meeting to address team burnout crisis")

    if len(burnout_risks) > 5:
        actions.append(f"HIGH PRIORITY: Initiate support conversations with {len(burnout_risks)} at-risk employees")

    if snapshot["wellbeing_distribution"]["at_risk"] > len(snapshot["team_size"]) * 0.2:
        actions.append("Review and redistribute workloads across team")

    if "declining" in snapshot.get("wellbeing_trend", "").lower():
        actions.append("Investigate root causes of wellbeing decline - conduct team survey")

    if not actions:
        actions.append("Continue monitoring - current wellbeing metrics are healthy")

    return actions

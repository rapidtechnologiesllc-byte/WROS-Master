"""
import logging
HR Agent Service - Complete Implementation

Centralized HR operations and employee tracking. Manages:
- Employee status and lifecycle
- KPI assignment and tracking
- Performance reviews
- Development plans
- Attrition monitoring
- Engagement scores
- Compensation management

The HR Agent runs daily to track employee health metrics
and escalate issues requiring HR attention.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.utils.agent_logger import log_agent_execution
from app.models.employee import Employee
from app.models.user import Users
from app.models.project import Project

def get_employee_status_summary(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get summary of all employees by status."""
    query = db.query(Employee)
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    total = query.count()
    active = query.filter(Employee.status == "ACTIVE").count()
    training = query.filter(Employee.status == "TRAINING").count()
    onboarding = query.filter(Employee.status == "ONBOARDING").count()
    inactive = query.filter(Employee.status == "INACTIVE").count()
    departed = query.filter(Employee.status == "DEPARTED").count()

    return {
        "total_employees": total,
        "active": active,
        "in_training": training,
        "onboarding": onboarding,
        "inactive": inactive,
        "departed": departed,
        "active_pct": round((active / total * 100), 1) if total > 0 else 0
    }

def get_employee_kpis(db: Session, employee_id: str) -> Dict[str, Any]:
    """Get KPI tracking for a specific employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        return {"error": "Employee not found"}

    # Get current project allocation
    current_allocation = None
    from app.models.employee_allocation import EmployeeAllocation
    alloc = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee_id,
        EmployeeAllocation.status == "ACTIVE"
    ).first()

    if alloc:
        current_allocation = {
            "project_id": alloc.project_id,
            "status": alloc.status,
            "billable": alloc.billable,
            "allocation_pct": alloc.allocation_pct
        }

    return {
        "employee_id": employee_id,
        "name": f"{employee.first_name} {employee.last_name}",
        "status": employee.status,
        "role": employee.designation if hasattr(employee, 'designation') else None,
        "business_unit": employee.business_unit_id,
        "start_date": employee.joining_date.isoformat() if hasattr(employee, 'joining_date') and employee.joining_date else None,
        "current_allocation": current_allocation,
        "utilization_pct": _calculate_utilization(db, employee_id),
        "engagement_score": _calculate_engagement_score(db, employee_id),
        "performance_rating": None  # Performance rating not available in current schema
    }

def get_attrition_risks(db: Session, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Identify employees at risk of attrition based on engagement and tenure."""
    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    risks = []
    for emp in query.all():
        risk_score = _calculate_attrition_risk(db, emp.EmployeeID)

        if risk_score > 60:  # High risk
            risks.append({
                "employee_id": emp.EmployeeID,
                "name": f"{emp.FirstName} {emp.LastName}",
                "risk_score": risk_score,
                "risk_level": "HIGH" if risk_score > 75 else "MEDIUM",
                "factors": _get_attrition_factors(db, emp.EmployeeID),
                "recommended_actions": _get_retention_actions(risk_score)
            })

    return sorted(risks, key=lambda x: x["risk_score"], reverse=True)

def get_development_needs(db: Session, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Identify employees ready for development or promotion."""
    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    development_candidates = []
    for emp in query.all():
        readiness_score = _calculate_readiness_score(db, emp.EmployeeID)

        if readiness_score > 70:
            development_candidates.append({
                "employee_id": emp.EmployeeID,
                "name": f"{emp.FirstName} {emp.LastName}",
                "readiness_score": readiness_score,
                "current_role": emp.Role,
                "next_role_candidates": _suggest_next_roles(emp.Role),
                "development_plan": _get_development_plan(emp.Role, readiness_score)
            })

    return sorted(development_candidates, key=lambda x: x["readiness_score"], reverse=True)

def get_engagement_metrics(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get org-wide engagement metrics."""
    query = db.query(Employee).filter(Employee.status == "ACTIVE")
    if tenant_id:
        query = query.filter(Employee.tenant_id == tenant_id)

    employees = query.all()
    if not employees:
        return {
            "average_engagement_score": 0,
            "engagement_distribution": {"high": 0, "medium": 0, "low": 0},
            "total_active_employees": 0,
            "high_engagement_pct": 0,
            "at_risk_pct": 0
        }

    engagement_scores = [_calculate_engagement_score(db, emp.id) for emp in employees]
    avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0

    high_engagement = sum(1 for score in engagement_scores if score > 70)
    at_risk = sum(1 for score in engagement_scores if score < 40)

    return {
        "average_engagement_score": round(avg_engagement, 1),
        "engagement_distribution": {
            "high": high_engagement,
            "medium": len(engagement_scores) - high_engagement - at_risk,
            "low": at_risk
        },
        "total_active_employees": len(employees),
        "high_engagement_pct": round((high_engagement / len(employees) * 100), 1) if employees else 0,
        "at_risk_pct": round((at_risk / len(employees) * 100), 1) if employees else 0
    }

def get_hr_dashboard(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get comprehensive HR dashboard with all metrics."""
    status_summary = get_employee_status_summary(db, tenant_id)
    engagement = get_engagement_metrics(db, tenant_id)
    attrition_risks = get_attrition_risks(db, tenant_id)
    development_needs = get_development_needs(db, tenant_id)

    dashboard = {
        "generated_at": datetime.utcnow().isoformat(),
        "status": status_summary,
        "engagement": engagement,
        "attrition_risks": attrition_risks[:5],  # Top 5
        "development_opportunities": development_needs[:5],  # Top 5
        "action_items": _compile_action_items(status_summary, engagement, attrition_risks, development_needs)
    }

    log_agent_execution(
        db=db,
        agent_name="HR Agent",
        action_taken="get_hr_dashboard",
        tenant_id=tenant_id or "system",
        action_data={
            "total_employees": status_summary["total_employees"],
            "active_employees": status_summary["active"],
            "average_engagement": engagement["average_engagement_score"],
            "attrition_risks_count": len(attrition_risks)
        },
        success=True,
    )

    return dashboard

# Helper functions

def _calculate_utilization(db: Session, employee_id: str) -> float:
    """Calculate employee utilization percentage."""

    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee_id,
        EmployeeAllocation.status == "ACTIVE"
    ).all()

    if not allocations:
        return 0.0

    total_allocation = sum(alloc.allocation_pct for alloc in allocations)
    return min(100.0, total_allocation)

def _calculate_engagement_score(db: Session, employee_id: str) -> float:
    """Calculate engagement score (0-100) based on various factors."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        return 0

    score = 50  # Base score

    # Utilization contributes 30 points
    utilization = _calculate_utilization(db, employee_id)
    score += (utilization / 100) * 30

    # Tenure contributes 20 points
    if employee.StartDate:
        months_employed = (datetime.utcnow() - employee.StartDate).days / 30
        if months_employed < 3:
            score -= 10  # New hires need onboarding
        elif months_employed > 12:
            score += 10  # Long tenure is positive

    return min(100.0, max(0.0, score))

def _calculate_attrition_risk(db: Session, employee_id: str) -> float:
    """Calculate attrition risk score (0-100, higher = more at-risk)."""
    engagement = _calculate_engagement_score(db, employee_id)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not engagement:
        return 100  # No engagement data = high risk

    # Inverse of engagement = risk
    risk = 100 - engagement

    # Penalize if no allocation (benched/idle)
    if _calculate_utilization(db, employee_id) < 20:
        risk += 20

    return min(100.0, risk)

def _calculate_readiness_score(db: Session, employee_id: str) -> float:
    """Calculate readiness for promotion/development (0-100)."""
    engagement = _calculate_engagement_score(db, employee_id)
    utilization = _calculate_utilization(db, employee_id)

    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        return 0

    readiness = 0

    # High engagement = ready (40 points)
    if engagement > 70:
        readiness += 40

    # High utilization = ready (30 points)
    if utilization > 80:
        readiness += 30

    # Tenure 1+ year = ready (20 points)
    if employee.StartDate:
        months = (datetime.utcnow() - employee.StartDate).days / 30
        if months > 12:
            readiness += 20

    # Performance rating if exists (10 points)
    if hasattr(employee, 'PerformanceRating') and employee.PerformanceRating and employee.PerformanceRating >= 4:
        readiness += 10

    return min(100.0, readiness)

def _get_attrition_factors(db: Session, employee_id: str) -> List[str]:
    """Get specific factors contributing to attrition risk."""
    factors = []

    engagement = _calculate_engagement_score(db, employee_id)
    if engagement < 40:
        factors.append("Low engagement")

    utilization = _calculate_utilization(db, employee_id)
    if utilization < 20:
        factors.append("Low utilization (possible bench time)")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee and employee.StartDate:
        months = (datetime.utcnow() - employee.StartDate).days / 30
        if 6 < months < 18:
            factors.append("Early-career stage (common departure window)")

    return factors

def _get_retention_actions(risk_score: float) -> List[str]:
    """Get recommended retention actions."""
    actions = []

    if risk_score > 75:
        actions.append("Schedule urgent retention discussion with manager")
        actions.append("Review compensation and benefits")
        actions.append("Identify career development opportunity")
    elif risk_score > 60:
        actions.append("Schedule 1:1 check-in to understand concerns")
        actions.append("Discuss career goals and development path")
        actions.append("Consider project allocation change")

    return actions

def _suggest_next_roles(current_role: str) -> List[str]:
    """Suggest next career roles based on current role."""
    role_progression = {
        "Junior Developer": ["Senior Developer", "Tech Lead"],
        "Senior Developer": ["Tech Lead", "Engineering Manager"],
        "Tech Lead": ["Engineering Manager", "Principal Engineer"],
        "Associate": ["Consultant", "Senior Consultant"],
        "Consultant": ["Senior Consultant", "Principal"],
        "Manager": ["Senior Manager", "Director"],
    }

    return role_progression.get(current_role, ["Senior " + current_role])

def _get_development_plan(current_role: str, readiness_score: float) -> Dict[str, Any]:
    """Get personalized development plan."""
    next_roles = _suggest_next_roles(current_role)

    return {
        "focus_areas": ["Leadership", "Technical depth", "Client skills"],
        "timeline_months": 6 if readiness_score > 80 else 12,
        "suggested_next_roles": next_roles,
        "development_activities": ["Mentorship", "Stretch assignments", "Training"]
    }

def _compile_action_items(status: Dict, engagement: Dict, risks: List, development: List) -> List[str]:
    """Compile prioritized action items for HR focus."""
    actions = []

    if status["active_pct"] < 85:
        actions.append(f"Address non-active employees: {status['departed']} departed, {status['inactive']} inactive")

    if engagement["at_risk_pct"] > 10:
        actions.append(f"{int(engagement['at_risk_pct'])}% of employees at engagement risk - initiate wellness programs")

    if len(risks) > 3:
        actions.append(f"{len(risks)} employees identified for retention focus - begin intervention conversations")

    if len(development) > 5:
        actions.append(f"{len(development)} high-readiness employees available for advancement - create promotion pipeline")

    return actions

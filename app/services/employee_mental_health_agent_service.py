"""
Employee Mental Health Agent Service

Monitors employee wellbeing and provides support resources:
- Wellness check-ins
- Stress and burnout indicators
- Work-life balance monitoring
- Mental health resource availability
- Peer support and mentorship matching
- Confidential reporting and escalation

The Employee Mental Health Agent works with HR Agent to create a
psychologically safe workplace where employees feel supported.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.agent_logging import log_agent_execution
from app.models.employees import Employees


class EmployeeMentalHealthAgent:
    """Employee wellbeing monitoring and support."""

    # Wellness indicators based on data patterns
    BURNOUT_INDICATORS = {
        "excessive_overtime": {
            "threshold": 60,  # hours per week
            "weight": 0.3,
            "description": "Working >60 hours per week"
        },
        "high_project_churn": {
            "threshold": 4,  # projects in 3 months
            "weight": 0.25,
            "description": "Moved between 4+ projects in 3 months"
        },
        "extended_bench": {
            "threshold": 30,  # days without assignment
            "weight": 0.2,
            "description": "On bench >30 days (may indicate lost confidence)"
        },
        "salary_below_market": {
            "threshold": 0.85,  # 85% of market rate
            "weight": 0.15,
            "description": "Compensation below market (may indicate undervaluation)"
        },
        "early_tenure": {
            "threshold": 180,  # days
            "weight": 0.1,
            "description": "Early tenure (<6 months) - critical adjustment period"
        }
    }

    @staticmethod
    @log_agent_execution("Employee Mental Health Agent", "assess_employee_wellness")
    async def assess_employee_wellness(
        tenant_id: str,
        employee_id: Optional[str],
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Assess single employee's mental health and wellbeing.

        Returns burnout score (0-100), indicators, and recommended actions.
        """
        try:
            if not employee_id:
                # If no employee specified, scan all
                return await EmployeeMentalHealthAgent.scan_all_employees(
                    tenant_id=tenant_id, db=db, **kwargs
                )

            emp = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.EmployeeID == employee_id,
                Employees.OnBoardingStatus == "Joined"
            ).first()

            if not emp:
                return {
                    "status": "not_found",
                    "message": f"Employee {employee_id} not found or not joined"
                }

            burnout_score = 0
            indicators = []
            recommendations = []

            # Check for early tenure stress
            if emp.JoinedOn:
                days_employed = (datetime.utcnow() - emp.JoinedOn).days
                if days_employed < 180:
                    indicator_weight = EmployeeMentalHealthAgent.BURNOUT_INDICATORS["early_tenure"]["weight"]
                    burnout_score += (1 - days_employed / 180) * 100 * indicator_weight
                    indicators.append({
                        "type": "early_tenure",
                        "severity": "info",
                        "message": f"Early employment phase ({days_employed} days). Offer onboarding support and mentorship.",
                    })
                    recommendations.append({
                        "action": "check_buddy_program",
                        "priority": "high",
                        "message": "Ensure buddy program active and supportive"
                    })
                    recommendations.append({
                        "action": "schedule_30d_checkin",
                        "priority": "high",
                        "message": "Schedule manager 1:1 to address any concerns"
                    })

            # Check for bench time (no active allocation)
            # Note: When allocations table is finalized, check for gaps
            # For now, use a placeholder
            # if not emp.active_allocation:
            #     days_on_bench = ...
            #     if days_on_bench > 30:
            #         indicator_weight = BURNOUT_INDICATORS["extended_bench"]["weight"]
            #         burnout_score += min(days_on_bench / 90, 1) * 100 * indicator_weight
            #         indicators.append({...})
            #         recommendations.append({...})

            # Overall burnout assessment
            if burnout_score >= 70:
                wellness_status = "at_risk"
            elif burnout_score >= 40:
                wellness_status = "concerning"
            else:
                wellness_status = "healthy"

            return {
                "status": "success",
                "employee_id": employee_id,
                "employee_name": emp.EmployeeName,
                "assessment_date": datetime.utcnow().isoformat(),
                "wellness_status": wellness_status,
                "burnout_score": round(burnout_score, 1),
                "indicators": indicators,
                "recommendations": recommendations,
                "resources": [
                    {
                        "name": "Employee Assistance Program (EAP)",
                        "description": "Confidential counseling and mental health support",
                        "access": "Call 1-800-XXX-XXXX or through HR portal"
                    },
                    {
                        "name": "Flexible Work Arrangements",
                        "description": "Discuss with manager for work-from-home or flexible hours",
                        "access": "Contact HR Manager"
                    },
                    {
                        "name": "Peer Mentorship",
                        "description": "Connect with experienced colleagues for guidance",
                        "access": "Request through HR Agent"
                    }
                ]
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("Employee Mental Health Agent", "scan_all_employees")
    async def scan_all_employees(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Scan all employees for mental health indicators.
        Returns aggregate report + at-risk employee list.
        """
        try:
            # Get all active employees
            all_employees = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined"
            ).all()

            at_risk_employees = []
            early_tenure_count = 0

            for emp in all_employees:
                risk_indicators = []

                # Check early tenure
                if emp.JoinedOn:
                    days_employed = (datetime.utcnow() - emp.JoinedOn).days
                    if days_employed < 180:
                        early_tenure_count += 1
                        risk_indicators.append("early_tenure")

                if risk_indicators:
                    at_risk_employees.append({
                        "employee_id": emp.EmployeeID,
                        "name": emp.EmployeeName,
                        "risk_indicators": risk_indicators,
                        "recommendation": "Schedule wellness check-in"
                    })

            return {
                "status": "success",
                "scan_date": datetime.utcnow().isoformat(),
                "total_employees": len(all_employees),
                "at_risk_count": len(at_risk_employees),
                "early_tenure_employees": early_tenure_count,
                "at_risk_employees": at_risk_employees,
                "aggregate_insights": {
                    "overall_wellness": "healthy" if len(at_risk_employees) / max(len(all_employees), 1) < 0.15 else "concerning",
                    "priority_actions": [
                        f"Check in with {len(at_risk_employees)} at-risk employees",
                        f"Verify {early_tenure_count} early-tenure employees have buddy support",
                        "Schedule monthly wellness pulse survey"
                    ]
                }
            }

        except Exception as e:
            raise

    @staticmethod
    async def send_wellness_checkin(
        tenant_id: str,
        employee_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Send wellness check-in survey to employee."""
        try:
            # In production, this would integrate with email/portal system
            return {
                "status": "scheduled",
                "employee_id": employee_id,
                "message": "Wellness check-in survey scheduled to send",
                "survey_questions": [
                    "How are you feeling about your current role?",
                    "Are you getting adequate support from your manager and team?",
                    "Do you have a good work-life balance?",
                    "Are there any challenges you'd like to discuss?",
                    "Rate your overall job satisfaction (1-10)"
                ],
                "deadline": (datetime.utcnow() + timedelta(days=7)).isoformat()
            }

        except Exception as e:
            raise

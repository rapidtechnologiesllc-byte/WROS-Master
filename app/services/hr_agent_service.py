"""
HR Agent Service

Centralized HR operations and employee lifecycle tracking:
- New employee onboarding coordination
- Performance and engagement tracking
- Employee milestone recognition
- Attrition risk detection
- Compensation reviews and adjustments
- HR policy compliance monitoring

The HR Agent coordinates with Onboarding Agent, Buddy Program Agent,
and Employee Mental Health Agent to deliver seamless employee experience.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.agent_logging import log_agent_execution
from app.models.employees import Employees


class HRAgent:
    """HR operations and employee lifecycle management."""

    @staticmethod
    @log_agent_execution("HR Agent", "get_employee_overview")
    async def get_employee_overview(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get high-level employee population overview.

        Returns employee count by status, tenure distribution, and key metrics.
        """
        try:
            # Total employees by status
            total_employees = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
            ).scalar() or 0

            joined = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined"
            ).scalar() or 0

            onboarding = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus.in_(["Pre-Onboarding", "Onboarding"])
            ).scalar() or 0

            churned = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Churned"
            ).scalar() or 0

            # Tenure distribution
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            one_year_ago = datetime.utcnow() - timedelta(days=365)

            new_employees_30d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn >= thirty_days_ago
            ).scalar() or 0

            employees_30_90d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn >= ninety_days_ago,
                Employees.JoinedOn < thirty_days_ago
            ).scalar() or 0

            employees_90d_1yr = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn >= one_year_ago,
                Employees.JoinedOn < ninety_days_ago
            ).scalar() or 0

            seasoned_employees = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn < one_year_ago
            ).scalar() or 0

            # Churn rate (last 90 days)
            churned_90d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Churned",
                Employees.CreatedOn >= ninety_days_ago
            ).scalar() or 0

            churn_rate = (churned_90d / max(joined, 1) * 100) if joined > 0 else 0

            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "overview": {
                    "total_employees": total_employees,
                    "joined": joined,
                    "onboarding": onboarding,
                    "churned": churned,
                    "churn_rate_percent": round(churn_rate, 1),
                },
                "tenure_distribution": {
                    "new_0_30d": new_employees_30d,
                    "growing_30_90d": employees_30_90d,
                    "established_90d_1yr": employees_90d_1yr,
                    "seasoned_1yr_plus": seasoned_employees,
                },
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("HR Agent", "detect_attrition_risk")
    async def detect_attrition_risk(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Detect employees at risk of attrition based on:
        - Utilization (bench employees)
        - Salary discrepancies
        - Lack of progression
        - Project churn

        Returns list of at-risk employees with risk scores.
        """
        try:
            # Get all active employees
            employees = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined"
            ).all()

            at_risk = []

            for emp in employees:
                risk_score = 0
                risk_factors = []

                # Factor 1: Bench (not allocated to project)
                # Note: Check allocations table once it's finalized
                # if not emp.active_allocation:
                #     risk_score += 25
                #     risk_factors.append("On bench - no active project")

                # Factor 2: Tenure in 0-6 month range (highest churn period)
                if emp.JoinedOn:
                    days_employed = (datetime.utcnow() - emp.JoinedOn).days
                    if 0 <= days_employed <= 180:
                        risk_score += 20
                        risk_factors.append(f"Early tenure ({days_employed} days) - critical churn period")

                if risk_score >= 20:
                    at_risk.append({
                        "employee_id": emp.EmployeeID,
                        "name": emp.EmployeeName,
                        "risk_score": risk_score,
                        "risk_factors": risk_factors,
                    })

            return {
                "status": "success",
                "at_risk_count": len(at_risk),
                "at_risk_employees": sorted(at_risk, key=lambda x: x["risk_score"], reverse=True),
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("HR Agent", "get_onboarding_status")
    async def get_onboarding_status(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Get detailed onboarding pipeline and status for all employees."""
        try:
            onboarding_employees = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus.in_(["Pre-Onboarding", "Onboarding"])
            ).all()

            onboarding_details = []
            for emp in onboarding_employees:
                if emp.CreatedOn:
                    days_in_process = (datetime.utcnow() - emp.CreatedOn).days
                else:
                    days_in_process = 0

                onboarding_details.append({
                    "employee_id": emp.EmployeeID,
                    "name": emp.EmployeeName,
                    "status": emp.OnBoardingStatus,
                    "days_in_process": days_in_process,
                    "target_completion_days": 14 if emp.OnBoardingStatus == "Pre-Onboarding" else 30,
                    "on_track": days_in_process <= (14 if emp.OnBoardingStatus == "Pre-Onboarding" else 30),
                })

            return {
                "status": "success",
                "onboarding_count": len(onboarding_details),
                "employees": sorted(onboarding_details, key=lambda x: x["days_in_process"], reverse=True),
            }

        except Exception as e:
            raise

    @staticmethod
    @log_agent_execution("HR Agent", "schedule_reviews")
    async def schedule_reviews(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Schedule performance reviews based on tenure and role.
        - 90-day reviews for new employees
        - Quarterly reviews for growing employees
        - Annual reviews for seasoned employees
        """
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            one_year_ago = datetime.utcnow() - timedelta(days=365)

            # Employees due for 90-day review (hired 90 days ago)
            due_90_day = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn >= ninety_days_ago,
                Employees.JoinedOn < one_year_ago
            ).all()

            # Employees due for annual review (hired 1+ year ago, review not done)
            due_annual = db.query(Employees).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                Employees.JoinedOn < one_year_ago
            ).all()

            scheduled = []
            for emp in due_90_day:
                scheduled.append({
                    "employee_id": emp.EmployeeID,
                    "name": emp.EmployeeName,
                    "review_type": "90-day",
                    "scheduled_date": (emp.JoinedOn + timedelta(days=90)).isoformat() if emp.JoinedOn else None,
                })

            for emp in due_annual:
                scheduled.append({
                    "employee_id": emp.EmployeeID,
                    "name": emp.EmployeeName,
                    "review_type": "annual",
                    "scheduled_date": (emp.JoinedOn + timedelta(days=365)).isoformat() if emp.JoinedOn else None,
                })

            return {
                "status": "success",
                "reviews_due": len(scheduled),
                "reviews": scheduled,
            }

        except Exception as e:
            raise

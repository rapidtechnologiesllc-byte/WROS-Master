"""
KPI Agent Service

Tracks company-wide KPIs and forecasts progress to strategic goals:
- 2000 employees by 2030
- $100M annual revenue by 2030

The KPI Agent runs daily at midnight IST, analyzes current state,
forecasts trajectory, and escalates to CEO Agent if off-track.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.agent_logging import log_agent_execution
from app.models.employees import Employees
from app.models.invoices import Invoices
from app.models.candidates import Candidates
from app.models.jobs import Jobs


class KPIAgent:
    """Company-wide KPI tracking and forecasting agent."""

    # Strategic targets for 2030
    TARGET_EMPLOYEES_2030 = 2000
    TARGET_REVENUE_2030 = 100_000_000  # $100M in USD cents
    TARGET_YEAR = 2030

    @staticmethod
    @log_agent_execution("KPI Agent", "calculate_daily_kpis")
    async def calculate_daily_kpis(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate current state and forecast for all strategic KPIs.

        Returns:
          {
            "date": "2026-08-08",
            "metrics": {
              "employees": {
                "current": 42,
                "target_2030": 2000,
                "monthly_growth_rate": 3.2,  # percent
                "projected_2030": 1850,
                "on_track": false,
              },
              "revenue": {
                "current_month_usd": 156000.50,
                "current_month_rate_annual": 1872000,
                "annual_revenue_ytd": 987500,
                "target_2030": 100000000,
                "monthly_growth_rate": 8.5,
                "projected_2030": 87500000,
                "on_track": false,
              },
              "recruiting": {
                "open_positions": 18,
                "candidates_in_pipeline": 147,
                "avg_time_to_hire_days": 22,
                "placements_this_month": 3,
                "placements_monthly_avg": 2.1,
              },
              "utilization": {
                "billable_utilization": 78.5,
                "bench_count": 4,
                "bench_percentage": 8.7,
              },
            },
            "alerts": [
              {"severity": "warning", "message": "Employee growth at 1.2%/month, need 4.8% to hit 2030 target"},
              {"severity": "warning", "message": "Revenue growth at 6.1%/month, need 7.2% to hit 2030 target"},
            ],
            "status": "forecasting_off_track"
          }
        """
        try:
            # Get current timestamp
            today = datetime.utcnow().date()
            year_2030 = 2030

            # ====== EMPLOYEE METRICS ======
            current_employees = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined"
            ).scalar() or 0

            # Calculate 7-day and 30-day hiring rate
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            employees_7d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.CreatedOn >= seven_days_ago,
            ).scalar() or 0

            employees_30d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.CreatedOn >= thirty_days_ago,
            ).scalar() or 0

            # Monthly growth rate (extrapolate from 7d to 30d)
            monthly_employee_growth_rate = (employees_30d / 30.0 * max(current_employees, 1) * 100) if current_employees > 0 else 0

            # Forecast to 2030
            years_to_2030 = year_2030 - datetime.utcnow().year
            if monthly_employee_growth_rate > 0:
                # Compound growth
                monthly_factor = 1 + (monthly_employee_growth_rate / 100)
                projected_employees_2030 = current_employees * (monthly_factor ** (years_to_2030 * 12))
            else:
                projected_employees_2030 = current_employees

            employee_on_track = projected_employees_2030 >= KPIAgent.TARGET_EMPLOYEES_2030 * 0.8  # 80% target

            # ====== REVENUE METRICS ======
            current_month = datetime.utcnow()
            month_start = current_month.replace(day=1)
            next_month = (month_start + timedelta(days=32)).replace(day=1)

            # Current month revenue (from invoices marked as paid)
            current_month_revenue_cents = db.query(func.sum(Invoices.InvoiceTotal)).filter(
                Invoices.tenant_id == tenant_id,
                Invoices.InvoiceDate >= month_start,
                Invoices.InvoiceDate < next_month,
                Invoices.Status == "Paid"
            ).scalar() or 0

            # YTD revenue
            ytd_start = current_month.replace(month=1, day=1)
            ytd_revenue_cents = db.query(func.sum(Invoices.InvoiceTotal)).filter(
                Invoices.tenant_id == tenant_id,
                Invoices.InvoiceDate >= ytd_start,
                Invoices.Status == "Paid"
            ).scalar() or 0

            # Monthly growth rate
            if ytd_revenue_cents > 0:
                current_month_revenue_usd = current_month_revenue_cents / 100
                monthly_growth_rate = (current_month_revenue_usd / (ytd_revenue_cents / 100)) * 100
            else:
                current_month_revenue_usd = 0
                monthly_growth_rate = 0

            # Annualized revenue
            days_into_year = (current_month - ytd_start).days
            if days_into_year > 0:
                annualized_revenue_cents = int(ytd_revenue_cents * (365 / days_into_year))
            else:
                annualized_revenue_cents = 0

            # Forecast to 2030
            if monthly_growth_rate > 0:
                monthly_factor = 1 + (monthly_growth_rate / 100)
                projected_revenue_2030_cents = annualized_revenue_cents * (monthly_factor ** (years_to_2030 * 12))
            else:
                projected_revenue_2030_cents = annualized_revenue_cents

            revenue_on_track = projected_revenue_2030_cents >= KPIAgent.TARGET_REVENUE_2030 * 0.8  # 80% target

            # ====== RECRUITING METRICS ======
            open_positions = db.query(func.count(Jobs.JobID)).filter(
                Jobs.tenant_id == tenant_id,
                Jobs.JobStatus == "Open"
            ).scalar() or 0

            candidates_in_pipeline = db.query(func.count(Candidates.CandidateID)).filter(
                Candidates.tenant_id == tenant_id,
                Candidates.CandidateStatus.in_(["Intake", "Screening", "Interview", "Offer"]),
            ).scalar() or 0

            placements_30d = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.CreatedOn >= thirty_days_ago,
            ).scalar() or 0

            avg_placements_monthly = placements_30d / (30.0 / 30.0)  # 30d extrapolation

            # ====== UTILIZATION METRICS ======
            # Billable utilization: (employees with active assignments) / total employees
            billable_count = db.query(func.count(Employees.EmployeeID)).filter(
                Employees.tenant_id == tenant_id,
                Employees.OnBoardingStatus == "Joined",
                # Note: check for active allocations if that table exists
            ).scalar() or 1

            billable_utilization = (billable_count / max(current_employees, 1) * 100) if current_employees > 0 else 0
            bench_count = current_employees - billable_count
            bench_percentage = (bench_count / max(current_employees, 1) * 100) if current_employees > 0 else 0

            # ====== ALERTS ======
            alerts = []

            # Employee growth alert
            required_employee_growth_rate = (
                (KPIAgent.TARGET_EMPLOYEES_2030 / max(current_employees, 1)) ** (1 / (years_to_2030 * 12)) - 1
            ) * 100
            if monthly_employee_growth_rate < required_employee_growth_rate:
                alerts.append({
                    "severity": "warning",
                    "message": f"Employee growth at {monthly_employee_growth_rate:.1f}%/month, "
                               f"need {required_employee_growth_rate:.1f}% to hit 2030 target of {KPIAgent.TARGET_EMPLOYEES_2030}"
                })

            # Revenue growth alert
            if annualized_revenue_cents > 0:
                required_revenue_growth_rate = (
                    (KPIAgent.TARGET_REVENUE_2030 / annualized_revenue_cents) ** (1 / years_to_2030) - 1
                ) * 100
                if monthly_growth_rate < required_revenue_growth_rate:
                    alerts.append({
                        "severity": "warning",
                        "message": f"Revenue growth at {monthly_growth_rate:.1f}%/month, "
                                   f"need {required_revenue_growth_rate:.1f}% to hit 2030 target"
                    })

            # Utilization alert
            if billable_utilization < 75:
                alerts.append({
                    "severity": "info",
                    "message": f"Billable utilization at {billable_utilization:.1f}%, "
                               f"bench has {bench_count} employees"
                })

            # Determine overall status
            status = "on_track" if (employee_on_track and revenue_on_track) else "forecasting_off_track"
            if len(alerts) > 1:
                status = "needs_action"

            return {
                "date": today.isoformat(),
                "metrics": {
                    "employees": {
                        "current": current_employees,
                        "target_2030": KPIAgent.TARGET_EMPLOYEES_2030,
                        "monthly_growth_rate": round(monthly_employee_growth_rate, 2),
                        "projected_2030": int(projected_employees_2030),
                        "on_track": employee_on_track,
                    },
                    "revenue": {
                        "current_month_usd": round(current_month_revenue_usd, 2),
                        "current_month_rate_annual_usd": round(current_month_revenue_usd * 12, 2),
                        "annual_revenue_ytd_usd": round(ytd_revenue_cents / 100, 2),
                        "annualized_revenue_usd": round(annualized_revenue_cents / 100, 2),
                        "target_2030_usd": KPIAgent.TARGET_REVENUE_2030 / 100,
                        "monthly_growth_rate": round(monthly_growth_rate, 2),
                        "projected_2030_usd": round(projected_revenue_2030_cents / 100, 2),
                        "on_track": revenue_on_track,
                    },
                    "recruiting": {
                        "open_positions": open_positions,
                        "candidates_in_pipeline": candidates_in_pipeline,
                        "placements_this_month": placements_30d,
                        "placements_monthly_avg": round(avg_placements_monthly, 1),
                    },
                    "utilization": {
                        "billable_utilization_percent": round(billable_utilization, 1),
                        "bench_count": bench_count,
                        "bench_percentage": round(bench_percentage, 1),
                    },
                },
                "alerts": alerts,
                "status": status,
                "forecasted_2030": {
                    "employees": int(projected_employees_2030),
                    "revenue_usd": round(projected_revenue_2030_cents / 100, 2),
                }
            }

        except Exception as e:
            raise

    @staticmethod
    async def get_kpi_dashboard(
        tenant_id: str,
        db: Session,
        **kwargs
    ) -> Dict[str, Any]:
        """Get formatted KPI dashboard for CEO/executive viewing."""
        kpis = await KPIAgent.calculate_daily_kpis(tenant_id=tenant_id, db=db)

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "data": kpis
        }

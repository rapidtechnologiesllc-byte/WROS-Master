"""BU Head dashboard: real figures for one business unit, across every company it operates
in (visibility is by business unit, never by location -- CEO 2026-10-12).

Definitions match the goal tree and plan-vs-actual views so the screens never disagree:
- team: employees of the BU who are working (not PRE_JOINING / EXITED), by their
  employer company (Employee.company_id)
- utilized: of those, people with an ACTIVE allocation
- revenue MTD: earned revenue (revenue_chain_service.earned_revenue, the P&L's income line:
  billed or approved work by timesheet week) of the BU's clients from the 1st to today
- bench cost per day: loaded payroll (CostBook) of working bench employees
"""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.services.ceo_fy_progress_service import WORKING_STATUSES_EXCLUDED

logger = logging.getLogger(__name__)

LIVE_PROJECT_STATUSES = ("ACTIVE",)


def _working(bu_id: int):
    return and_(Employee.bu_id == bu_id, Employee.status.notin_(WORKING_STATUSES_EXCLUDED))


def _clients(bu_id: int):
    return Client.business_unit_id == bu_id


class BUHeadDashboardService:
    """Aggregates real data for the BU Head dashboard."""

    @staticmethod
    def get_bu_dashboard_data(db: Session, bu_id: int, today: Optional[date] = None) -> dict:
        from app.services.revenue_chain_service import CostBook, earned_revenue

        bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if not bu:
            return {}
        today = today or date.today()

        from app.services.bench_service import headcount_snapshot

        team = db.query(Employee).filter(_working(bu_id)).all()
        # the bench rule shared by every surface (bench_service): billable, joined, no ACTIVE allocation
        snapshot = headcount_snapshot(db, bu_ids={bu_id}, today=today)
        bench = snapshot["bench"]

        costs = CostBook(db)
        bench_daily = [costs.period(e, today, today) for e in bench]
        bench_cost_known = all(c is not None for c in bench_daily)
        bench_cost_daily = sum(c for c in bench_daily if c is not None)

        revenue_mtd = earned_revenue(db, start=today.replace(day=1), end=today, business_unit_ids={bu_id})

        active_projects = db.query(func.count(Project.id)).join(Client, Project.client_id == Client.id).filter(
            _clients(bu_id), Project.status.in_(LIVE_PROJECT_STATUSES),
        ).scalar() or 0

        allocations_by_project = db.query(
            Project.name,
            func.count(func.distinct(EmployeeAllocation.employee_id)),
            func.round(func.avg(EmployeeAllocation.utilization_pct), 1),
        ).join(EmployeeAllocation, Project.id == EmployeeAllocation.project_id).join(
            Client, Project.client_id == Client.id
        ).filter(
            _clients(bu_id), EmployeeAllocation.status == "ACTIVE",
        ).group_by(Project.id, Project.name).all()

        team_count, billable_count, utilized = len(team), len(snapshot["billable"]), len(snapshot["allocated"])
        return {
            "bu_name": bu.name,
            "team_size": {
                "total": team_count,
                "billable": billable_count,
                "non_billable": len(snapshot["non_billable"]),
                "utilized": utilized,
                "bench": len(bench),
                # of billable people: internal staff are never "unutilized"
                "utilization_percent": round(utilized / billable_count * 100, 1) if billable_count else 0,
            },
            "revenue": {
                "mtd_usd": int(revenue_mtd // 100),
                "arn_usd": int(revenue_mtd * 12 // 100),  # simple run rate: MTD x 12
                "bench_cost_daily_usd": int(bench_cost_daily // 100),
                # False when a bench employee has no salary or cost-rate config (never counted as 0)
                "bench_cost_complete": bench_cost_known,
            },
            "delivery": {
                "active_projects": active_projects,
                "project_allocations": [
                    {"name": name, "employees": count or 0, "total_utilization": float(avg or 0)}
                    for name, count, avg in allocations_by_project
                ],
            },
        }

    @staticmethod
    def get_team_details(db: Session, bu_id: int) -> list:
        """Working team members of the BU with their current allocation."""
        rows = db.query(
            Employee.id,
            Employee.first_name,
            Employee.last_name,
            Employee.current_title,
            Employee.billing_rate_usd_cents,
            EmployeeAllocation.utilization_pct,
            Project.name.label("project_name"),
        ).outerjoin(
            EmployeeAllocation,
            and_(EmployeeAllocation.employee_id == Employee.id, EmployeeAllocation.status == "ACTIVE"),
        ).outerjoin(Project, Project.id == EmployeeAllocation.project_id).filter(
            _working(bu_id)
        ).all()

        return [
            {
                "id": r[0],
                "name": f"{r[1]} {r[2]}",
                "title": r[3],
                "billable_rate": int((r[4] or 0) // 100),  # cents -> dollars
                "utilization": r[5] or 0,
                "current_project": r[6] or "Bench",
            }
            for r in rows
        ]

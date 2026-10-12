"""BU Head dashboard: real figures for one business unit, across every company it operates
in (visibility is by business unit, never by location -- CEO 2026-10-12).

Definitions match the goal tree and plan-vs-actual views so the screens never disagree:
- team: employees of the BU who are working (not PRE_JOINING / EXITED), by their
  employer company (Employee.company_id)
- utilized: of those, people with an ACTIVE allocation
- revenue MTD: approved / sent / paid invoices this month for the BU's clients, by the
  client's contracting company
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
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.services.ceo_fy_progress_service import WORKING_STATUSES_EXCLUDED

logger = logging.getLogger(__name__)

REVENUE_STATUSES = ("APPROVED", "SENT", "PAID")
LIVE_PROJECT_STATUSES = ("ACTIVE",)


def _working(bu_id: int):
    return and_(Employee.bu_id == bu_id, Employee.status.notin_(WORKING_STATUSES_EXCLUDED))


def _clients(bu_id: int):
    return Client.business_unit_id == bu_id


class BUHeadDashboardService:
    """Aggregates real data for the BU Head dashboard."""

    @staticmethod
    def get_bu_dashboard_data(db: Session, bu_id: int, today: Optional[date] = None) -> dict:
        from app.services.revenue_chain_service import CostBook

        bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if not bu:
            return {}
        today = today or date.today()

        team = db.query(Employee).filter(_working(bu_id)).all()
        allocated_ids = {
            employee_id for (employee_id,) in db.query(EmployeeAllocation.employee_id).filter(
                EmployeeAllocation.status == "ACTIVE",
                EmployeeAllocation.employee_id.in_([e.id for e in team] or [""]),
            )
        }
        bench = [e for e in team if e.id not in allocated_ids]

        costs = CostBook(db)
        bench_daily = [costs.period(e, today, today) for e in bench]
        bench_cost_known = all(c is not None for c in bench_daily)
        bench_cost_daily = sum(c for c in bench_daily if c is not None)

        revenue_mtd = db.query(func.sum(InvoiceLineItem.amount_usd_cents)).join(
            Invoice, Invoice.id == InvoiceLineItem.invoice_id
        ).join(Client, Client.id == Invoice.client_id).filter(
            _clients(bu_id),
            Invoice.status.in_(REVENUE_STATUSES),
            Invoice.billing_period_start >= today.replace(day=1),
        ).scalar() or 0

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

        team_count, utilized = len(team), len(team) - len(bench)
        return {
            "bu_name": bu.name,
            "team_size": {
                "total": team_count,
                "utilized": utilized,
                "bench": len(bench),
                "utilization_percent": round(utilized / team_count * 100, 1) if team_count else 0,
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

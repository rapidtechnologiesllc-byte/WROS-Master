"""BU Head Dashboard Service - Real data aggregation for Business Unit leadership."""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.project import Project
from app.models.rbac import BusinessUnit
from datetime import datetime, timedelta


class BUHeadDashboardService:
    """Aggregates real data for BU Head dashboard visibility."""

    @staticmethod
    def get_bu_dashboard_data(db: Session, bu_id: int) -> dict:
        """
        Get comprehensive BU dashboard data:
        - Team size and utilization
        - Revenue (billed hours × rate)
        - Active projects
        - Allocation distribution
        - Bench time and costs
        """

        # Get BU info
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if not bu:
            return {}

        # Team metrics: active employees in this BU
        team_count = db.query(func.count(Employee.id)).filter(
            Employee.bu_id == bu_id,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        # Utilization: distinct employees with active allocations
        utilized = db.query(func.count(func.distinct(EmployeeAllocation.employee_id))).filter(
            EmployeeAllocation.status == "ACTIVE"
        ).scalar() or 0

        # Bench: active employees with no active allocation
        bench_count = team_count - utilized

        # Revenue MTD: sum of (hours × rate_usd_cents) from invoice line items
        # Group by invoices and their billing period
        from sqlalchemy import text
        mtd_start = datetime.utcnow().replace(day=1).date()

        revenue_mtd = db.query(func.sum(InvoiceLineItem.amount_usd_cents)).join(
            Invoice, Invoice.id == InvoiceLineItem.invoice_id
        ).filter(
            Invoice.business_unit_id == bu_id,
            Invoice.billing_period_start >= mtd_start
        ).scalar() or 0

        # Annual run rate (simple: MTD × 12)
        revenue_arn = revenue_mtd * 12

        # Active projects in this BU (join with Client to get business_unit_id)
        from app.models.client import Client
        active_projects = db.query(func.count(Project.id)).join(
            Client, Project.client_id == Client.id
        ).filter(
            Client.business_unit_id == bu_id,
            Project.status.in_(["ACTIVE", "IN_PROGRESS"])
        ).scalar() or 0

        # Bench cost daily: sum of (billing_rate_usd_cents / 8 / 100 for cents to dollars)
        bench_cost_daily = db.query(func.sum(Employee.billing_rate_usd_cents / 8 / 100)).filter(
            Employee.bu_id == bu_id,
            Employee.status == "ACTIVE",
            Employee.billing_classification == "BENCH"
        ).scalar() or 0

        # Allocation breakdown by project (join with Client for BU filtering)
        allocations_by_project = db.query(
            Project.name,
            func.count(func.distinct(EmployeeAllocation.employee_id)).label("emp_count"),
            func.round(func.avg(EmployeeAllocation.utilization_pct), 1).label("avg_utilization")
        ).join(
            EmployeeAllocation, Project.id == EmployeeAllocation.project_id
        ).join(
            Client, Project.client_id == Client.id
        ).filter(
            Client.business_unit_id == bu_id,
            EmployeeAllocation.status == "ACTIVE"
        ).group_by(Project.id, Project.name).all()

        projects_summary = [
            {
                "name": p[0],
                "employees": p[1] or 0,
                "total_utilization": p[2] or 0
            }
            for p in allocations_by_project
        ]

        return {
            "bu_name": bu.name,
            "team_size": {
                "total": team_count,
                "utilized": utilized,
                "bench": bench_count,
                "utilization_percent": round((utilized / team_count * 100) if team_count > 0 else 0, 1)
            },
            "revenue": {
                "mtd_usd": int(revenue_mtd / 100) if revenue_mtd else 0,
                "arn_usd": int(revenue_arn / 100) if revenue_arn else 0,
                "bench_cost_daily_usd": int(bench_cost_daily * 100) if bench_cost_daily else 0
            },
            "delivery": {
                "active_projects": active_projects,
                "project_allocations": projects_summary
            }
        }

    @staticmethod
    def get_team_details(db: Session, bu_id: int) -> list:
        """Get detailed team member info with current allocation."""

        # Employees with their current allocation (if any)
        employees = db.query(
            Employee.id,
            Employee.first_name,
            Employee.last_name,
            Employee.current_title,
            Employee.billing_rate_usd_cents,
            EmployeeAllocation.utilization_pct,
            Project.name.label("project_name")
        ).outerjoin(
            EmployeeAllocation,
            and_(
                EmployeeAllocation.employee_id == Employee.id,
                EmployeeAllocation.status == "ACTIVE"
            )
        ).outerjoin(
            Project,
            Project.id == EmployeeAllocation.project_id
        ).filter(
            Employee.bu_id == bu_id,
            Employee.status == "ACTIVE"
        ).all()

        return [
            {
                "id": e[0],
                "name": f"{e[1]} {e[2]}",
                "title": e[3],
                "billable_rate": int((e[4] or 0) / 100),  # convert cents to dollars
                "utilization": e[5] or 0,
                "current_project": e[6] or "Bench"
            }
            for e in employees
        ]

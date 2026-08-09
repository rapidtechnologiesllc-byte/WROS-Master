"""
KPI Agent Service - Complete Implementation

Tracks company-wide KPIs and forecasts progress to strategic goals:
- 2,000 employees by 2030
- $100M annual revenue by 2030
- Monthly 2× growth rate

The KPI Agent runs daily at midnight, analyzes current state,
forecasts trajectory, and escalates to CEO Agent if off-track.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.utils.agent_logger import log_agent_execution
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.candidate import Candidate
from app.models.project import Project


def get_current_headcount(db: Session) -> int:
    """Get current active employee count."""
    return db.query(func.count(Employee.id)).filter(
        Employee.status == "ACTIVE"
    ).scalar() or 0


def get_ytd_revenue(db: Session, year: Optional[int] = None) -> int:
    """Get YTD revenue in USD cents."""
    if not year:
        year = datetime.utcnow().year

    fy_start = datetime(year, 1, 1)
    fy_end = datetime(year, 12, 31)

    return db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.created_at >= fy_start,
        Invoice.created_at <= fy_end,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"])
    ).scalar() or 0


def get_monthly_growth_rate(db: Session, months_back: int = 3) -> float:
    """Calculate average monthly employee growth rate (percent)."""
    headcounts = []

    for i in range(months_back, 0, -1):
        target_date = datetime.utcnow() - timedelta(days=30 * i)
        count = db.query(func.count(Employee.id)).filter(
            Employee.created_at <= target_date,
            Employee.status == "ACTIVE"
        ).scalar() or 0
        headcounts.append(count)

    if len(headcounts) < 2 or headcounts[0] == 0:
        return 0.0

    total_growth = sum(
        ((headcounts[i] - headcounts[i-1]) / headcounts[i-1] * 100)
        for i in range(1, len(headcounts))
    )

    return total_growth / (len(headcounts) - 1)


def forecast_2030_headcount(current: int, monthly_growth_rate: float) -> int:
    """Forecast headcount at 2030 based on current growth rate."""
    months_remaining = (
        (datetime(2030, 12, 31) - datetime.utcnow()).days // 30
    )

    projected = current * ((1 + monthly_growth_rate / 100) ** months_remaining)
    return int(projected)


def forecast_2030_revenue(ytd_revenue: int, current_year: int) -> int:
    """Forecast annual revenue at 2030 based on current trajectory."""
    if current_year == 2026:
        year_progress_pct = (datetime.utcnow() - datetime(2026, 1, 1)).days / 365 * 100
        if year_progress_pct == 0:
            return 0

        annual_run_rate = int(ytd_revenue / (year_progress_pct / 100))

        # Simple forecast: assume 2× YoY growth
        years_to_2030 = 2030 - current_year
        projected = annual_run_rate * (2 ** years_to_2030)
        return projected

    return 0


def get_metrics_by_tier(db: Session) -> Dict[str, Any]:
    """Get KPI breakdown by BU (AXION, PRISM)."""
    from app.models.business_unit import BusinessUnit

    tiers = {}
    for bu in db.query(BusinessUnit).all():
        bu_employees = db.query(func.count(Employee.id)).filter(
            Employee.business_unit_id == bu.id,
            Employee.status == "ACTIVE"
        ).scalar() or 0

        bu_revenue = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
            Invoice.business_unit_id == bu.id,
            Invoice.status.in_(["APPROVED", "SENT", "PAID"])
        ).scalar() or 0

        tiers[bu.name or f"BU_{bu.id}"] = {
            "headcount": bu_employees,
            "revenue_usd_cents": bu_revenue,
            "revenue_usd": bu_revenue / 100 if bu_revenue else 0
        }

    return tiers


def calculate_daily_kpis(db: Session, tenant_id: str = "system") -> Dict[str, Any]:
    """
    Calculate current state and forecast for all strategic KPIs.

    Returns comprehensive KPI snapshot with current metrics and 2030 forecasts.
    """
    today = datetime.utcnow()
    current_employees = get_current_headcount(db)
    ytd_revenue = get_ytd_revenue(db)
    monthly_growth = get_monthly_growth_rate(db)

    projected_employees_2030 = forecast_2030_headcount(current_employees, monthly_growth)
    projected_revenue_2030 = forecast_2030_revenue(ytd_revenue, today.year)

    # Calculate pace vs target
    days_elapsed = (today - datetime(today.year, 1, 1)).days
    days_in_year = 365
    year_progress_pct = (days_elapsed / days_in_year) * 100

    # Revenue pace
    annual_run_rate = int(ytd_revenue / (year_progress_pct / 100)) if year_progress_pct > 0 else 0
    revenue_target_2026 = 5_000_000_00  # $5M
    revenue_pace_pct = (annual_run_rate / revenue_target_2026 * 100) if revenue_target_2026 > 0 else 0

    # Headcount pace (2030: 2000 employees, so 2026 interim target ~150)
    headcount_target_2026 = 150
    headcount_pace_pct = (current_employees / headcount_target_2026 * 100) if headcount_target_2026 > 0 else 0

    result = {
        "date": today.isoformat(),
        "year": today.year,
        "year_progress_pct": round(year_progress_pct, 1),
        "metrics": {
            "employees": {
                "current": current_employees,
                "target_2026": 150,
                "target_2030": 2000,
                "monthly_growth_rate": round(monthly_growth, 2),
                "projected_2030": projected_employees_2030,
                "pace_vs_2026_target_pct": round(headcount_pace_pct, 1),
                "status": "ON_TRACK" if headcount_pace_pct >= year_progress_pct * 0.9 else "BEHIND"
            },
            "revenue": {
                "ytd_usd": ytd_revenue / 100 if ytd_revenue else 0,
                "ytd_usd_cents": ytd_revenue,
                "annual_run_rate_usd": annual_run_rate / 100 if annual_run_rate else 0,
                "annual_run_rate_usd_cents": annual_run_rate,
                "target_2026_usd": 5_000_000,
                "target_2030_usd": 100_000_000,
                "projected_2030_usd": projected_revenue_2030 / 100 if projected_revenue_2030 else 0,
                "projected_2030_usd_cents": projected_revenue_2030,
                "pace_vs_2026_target_pct": round(revenue_pace_pct, 1),
                "status": "ON_TRACK" if revenue_pace_pct >= year_progress_pct * 0.9 else "BEHIND"
            }
        },
        "by_tier": get_metrics_by_tier(db),
        "health_score": _calculate_health_score(headcount_pace_pct, revenue_pace_pct)
    }

    log_agent_execution(
        db=db,
        agent_name="KPI Agent",
        action_taken="calculate_daily_kpis",
        tenant_id=tenant_id,
        action_data={
            "current_employees": current_employees,
            "ytd_revenue_usd_cents": ytd_revenue,
            "monthly_growth_rate": monthly_growth,
            "health_score": result["health_score"]
        },
        success=True,
    )

    return result


def _calculate_health_score(headcount_pace: float, revenue_pace: float) -> int:
    """Calculate overall organizational health score (0-100)."""
    avg_pace = (headcount_pace + revenue_pace) / 2
    if avg_pace >= 100:
        return 100
    elif avg_pace >= 90:
        return 85
    elif avg_pace >= 75:
        return 70
    elif avg_pace >= 50:
        return 55
    else:
        return 40


def get_kpi_alerts(db: Session) -> List[Dict[str, Any]]:
    """Generate alerts for KPIs that are off-track."""
    kpis = calculate_daily_kpis(db)
    alerts = []

    # Employee growth alert
    if kpis["metrics"]["employees"]["status"] == "BEHIND":
        alerts.append({
            "severity": "HIGH",
            "metric": "Employee Growth",
            "message": f"Headcount pace at {kpis['metrics']['employees']['pace_vs_2026_target_pct']:.1f}% vs {kpis['year_progress_pct']:.1f}% FY progress",
            "recommendation": "Accelerate hiring pipeline"
        })

    # Revenue alert
    if kpis["metrics"]["revenue"]["status"] == "BEHIND":
        alerts.append({
            "severity": "HIGH",
            "metric": "Revenue Growth",
            "message": f"Revenue pace at {kpis['metrics']['revenue']['pace_vs_2026_target_pct']:.1f}% vs {kpis['year_progress_pct']:.1f}% FY progress",
            "recommendation": "Accelerate sales pipeline and close rates"
        })

    log_agent_execution(
        db=db,
        agent_name="KPI Agent",
        action_taken="get_kpi_alerts",
        tenant_id="system",
        action_data={"alert_count": len(alerts)},
        success=True,
    )

    return alerts

"""
import logging
PRIORITY 2: Revenue Autonomous Scanning Service.

Background job (runs daily) that proactively scans all active allocations
for revenue leakage, eliminating the need for manual project UUID entry.

Workflow:
1. Get all active projects
2. For each project, scan the current billing period for revenue leakage
3. Store results in RevenueLeakageFlag table
4. API endpoint returns cached results (no manual UUID needed)
5. Manual UUID form remains as "re-scan this specific project" secondary action
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.revenue_leakage import RevenueLeakageFlag
from app.services.revenue_leakage_service import (
    scan_project_revenue_leakage,
    DEFAULT_LEAKAGE_GRACE_DAYS,
)


def _get_current_billing_period(date_within_period: date) -> tuple:
    """
    Returns the billing period (period_start, period_end) for the month
    containing the given date. Standard calendar months.
    """
    period_start = date_within_period.replace(day=1)

    # Find last day of month
    if period_start.month == 12:
        period_end = date(period_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        period_end = date(period_start.year, period_start.month + 1, 1) - timedelta(days=1)

    return period_start, period_end


def run_daily_revenue_scan_job(db: Session) -> Dict:
    """
    Daily background job: scan all active projects for revenue leakage.

    Returns: dict with scan results:
    {
        "scanned_projects": int,
        "flags_created": int,
        "flags_updated": int,
        "leakage_detected": int,  # Active flags (no reason logged)
        "errors": list,
        "timestamp": datetime,
    }
    """
    logger.info("[RevenueScan] Daily scan job starting...")

    scanned = 0
    created = 0
    updated = 0
    leakage_count = 0
    errors = []

    # Get today's date to determine current billing period
    today = date.today()
    period_start, period_end = _get_current_billing_period(today)

    try:
        # Get all active projects
        active_projects = db.query(Project).filter(
            Project.status == "ACTIVE"
        ).all()

        if not active_projects:
            logger.info("[RevenueScan] No active projects found")
            return {
                "scanned_projects": 0,
                "flags_created": 0,
                "flags_updated": 0,
                "leakage_detected": 0,
                "errors": [],
                "timestamp": datetime.utcnow(),
            }

        logger.info(f"[RevenueScan] Scanning {len(active_projects)} active projects for period {period_start} to {period_end}")

        # Scan each project
        for project in active_projects:
            try:
                scanned += 1

                # Scan for leakage in current period
                flag = scan_project_revenue_leakage(
                    db,
                    project,
                    period_start=period_start,
                    period_end=period_end,
                    grace_days=DEFAULT_LEAKAGE_GRACE_DAYS,
                    now=datetime.utcnow(),
                )

                if flag:
                    # Check if this is a new flag or an update
                    existing = db.query(RevenueLeakageFlag).filter(
                        RevenueLeakageFlag.project_id == project.id,
                        RevenueLeakageFlag.period_start == period_start,
                        RevenueLeakageFlag.period_end == period_end,
                    ).first()

                    if existing and existing.id == flag.id:
                        updated += 1
                    else:
                        created += 1

                    # Count active leakage (no reason logged)
                    if not flag.partial_billing_reason:
                        leakage_count += 1

                    logger.debug(
                        f"[RevenueScan] Project {project.id}: "
                        f"{flag.approved_hours}h approved, {flag.invoiced_hours}h invoiced, "
                        f"{flag.unbilled_hours}h unbilled"
                    )

            except Exception as exc:
                logger.error(f"Error: {str(exc)}", exc_info=True)
                error_msg = f"Project {project.id}: {str(exc)}"
                errors.append(error_msg)
                logger.warning(f"[RevenueScan] {error_msg}")

        # Commit all changes
                db.commit()

        logger.info(
            f"[RevenueScan] Daily scan complete: "
            f"{scanned} projects scanned, {created} new flags, {updated} updated, "
            f"{leakage_count} active leakage issues"
        )

        return {
            "scanned_projects": scanned,
            "flags_created": created,
            "flags_updated": updated,
            "leakage_detected": leakage_count,
            "errors": errors,
            "timestamp": datetime.utcnow(),
        }

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[RevenueScan] Daily scan job failed: {exc}")
        return {
            "scanned_projects": scanned,
            "flags_created": created,
            "flags_updated": updated,
            "leakage_detected": leakage_count,
            "errors": [str(exc)],
            "timestamp": datetime.utcnow(),
        }


def get_recent_scan_results(db: Session, *, tenant_id: Optional[int] = None, limit: int = 50) -> List[Dict]:
    """
    Get recent revenue leakage scan results (cached from background job).

    Returns list of active leakage flags sorted by most recent first.
    """
    query = db.query(RevenueLeakageFlag).filter(
        RevenueLeakageFlag.partial_billing_reason.is_(None)  # Only active flags
    )

    if tenant_id is not None:
        query = query.filter(RevenueLeakageFlag.tenant_id == tenant_id)

    flags = query.order_by(RevenueLeakageFlag.detected_at.desc()).limit(limit).all()

    return [
        {
            "id": f.id,
            "project_id": f.project_id,
            "period_start": f.period_start.isoformat(),
            "period_end": f.period_end.isoformat(),
            "approved_hours": float(f.approved_hours),
            "invoiced_hours": float(f.invoiced_hours),
            "unbilled_hours": float(f.unbilled_hours),
            "detected_at": f.detected_at.isoformat() if f.detected_at else None,
        }
        for f in flags
    ]


def get_scan_statistics(db: Session, *, tenant_id: Optional[int] = None) -> Dict:
    """
    Get statistics about revenue leakage across all scanned projects.
    """
    query = db.query(RevenueLeakageFlag).filter(
        RevenueLeakageFlag.partial_billing_reason.is_(None)  # Only active flags
    )

    if tenant_id is not None:
        query = query.filter(RevenueLeakageFlag.tenant_id == tenant_id)

    flags = query.all()

    if not flags:
        return {
            "total_flags": 0,
            "total_unbilled_hours": 0.0,
            "total_unbilled_value_usd_cents": 0,
            "affected_projects": 0,
        }

    total_unbilled = sum(float(f.unbilled_hours) for f in flags)
    affected_projects = len(set(f.project_id for f in flags))

    # Estimate value: 50/hr (rough staffing cost)
    # This is advisory — actual value depends on client rates
    estimated_value_usd_cents = int(total_unbilled * 50 * 100)

    return {
        "total_flags": len(flags),
        "total_unbilled_hours": total_unbilled,
        "total_unbilled_value_usd_cents": estimated_value_usd_cents,
        "affected_projects": affected_projects,
    }

"""CEO FY Progress Dashboard — org-wide progress tracking against annual targets.

Targets are the ORG level of the FY goal tree (goal_targets, see
goal_tree_service), set on the Goals screen or from the CEO Dashboard's
metric cards. A metric with no target shows as NOT_SET -- there are no
built-in default targets.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.opportunity import CLOSED_STAGES, Opportunity
from app.services.pnl_service import get_org_pnl_summary
import logging

logger = logging.getLogger(__name__)

# The FY metrics the CEO sets targets for: key -> (label, unit, description)
FY_METRICS = {
    "headcount": ("Headcount", "people", "Employees who have joined and not exited"),
    "revenue": ("Revenue", "USD", "Approved/sent/paid invoices this FY"),
    "new_logos": ("New logos", "clients", "Clients added this FY that are active"),
    "engagement": ("Pipeline engagement", "score", "Open opportunities per active client x 100"),
    "retention": ("Retention", "%", "Employees retained this FY (joined, not exited)"),
    "utilization": ("Utilization", "%", "Invoiced hours vs available hours (2,080/yr per head)"),
    "margin": ("Margin", "%", "Org-wide margin this month"),
}
WORKING_STATUSES_EXCLUDED = ("PRE_JOINING", "EXITED")


def get_fy_targets(db: Session, fy_year: Optional[int] = None, tenant_id: Optional[int] = None) -> dict:
    """{metric_key: {"target": float|None}} -- the ORG-level rows of the goal tree."""
    from app.models.strategic_goal import GoalTarget

    fy_year = fy_year or datetime.utcnow().year
    query = db.query(GoalTarget).filter(
        GoalTarget.year == fy_year, GoalTarget.level == "ORG", GoalTarget.metric.in_(list(FY_METRICS)),
    )
    if tenant_id is not None:
        query = query.filter(GoalTarget.tenant_id == tenant_id)
    found = {row.metric: row.target for row in query.all()}
    return {key: {"target": found.get(key)} for key in FY_METRICS}


def _metric(key: str, current, target, fy_progress_pct: float, *, higher_is_better_absolute: bool = False) -> dict:
    """Uniform metric record. Cumulative metrics (headcount, revenue, logos)
    are judged against the share of the year elapsed; rate metrics
    (retention, utilization, margin, engagement) against the full target."""
    label, unit, detail = FY_METRICS[key]
    if not target:
        return {"key": key, "label": label, "unit": unit, "detail": detail, "current": current,
                "target": None, "progress_pct": None, "status": "NOT_SET"}
    progress = current / target * 100
    expected = 100 if higher_is_better_absolute else fy_progress_pct
    status = "ON_TRACK" if progress >= expected * 0.9 else "BEHIND"
    return {"key": key, "label": label, "unit": unit, "detail": detail, "current": current,
            "target": target, "progress_pct": round(progress, 1), "status": status}


def get_fy_progress(db: Session, fy_year: Optional[int] = None, tenant_id: Optional[int] = None) -> dict:
    """Actual FY progress against the CEO's targets."""
    fy_year = fy_year or datetime.utcnow().year
    targets = get_fy_targets(db, fy_year, tenant_id)

    # Fiscal year = calendar year
    fy_start = datetime(fy_year, 1, 1)
    fy_end = datetime(fy_year, 12, 31)
    today = min(datetime.utcnow(), datetime(fy_year, 12, 31, 23, 59))
    total_fy_days = (fy_end - fy_start).days
    days_elapsed = max(1, (today - fy_start).days)
    fy_progress_pct = min(100, days_elapsed / total_fy_days * 100)

    headcount = db.query(func.count(Employee.id)).filter(
        Employee.status.notin_(WORKING_STATUSES_EXCLUDED)
    ).scalar() or 0

    revenue_cents = db.query(func.sum(Invoice.total_usd_cents)).filter(
        Invoice.created_at >= fy_start, Invoice.created_at <= today,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"]),
    ).scalar() or 0
    revenue_usd = revenue_cents / 100

    new_logos = db.query(func.count(Client.id)).filter(
        Client.status == "ACTIVE", Client.created_at >= fy_start, Client.created_at <= today,
    ).scalar() or 0

    open_opportunities = db.query(func.count(Opportunity.id)).filter(
        Opportunity.stage.notin_(CLOSED_STAGES)
    ).scalar() or 0
    active_clients = db.query(func.count(Client.id)).filter(Client.status == "ACTIVE").scalar() or 0
    engagement = (open_opportunities / active_clients * 100) if active_clients else 0

    # Retention: of everyone employed at some point this FY, the share not exited
    exited_this_fy = db.query(func.count(Employee.id)).filter(
        Employee.status == "EXITED", Employee.updated_at >= fy_start,
    ).scalar() or 0
    retention = (headcount / (headcount + exited_this_fy) * 100) if (headcount + exited_this_fy) else 0

    billable_hours = float(db.query(func.sum(InvoiceLineItem.hours)).join(
        Invoice, Invoice.id == InvoiceLineItem.invoice_id
    ).filter(Invoice.created_at >= fy_start, Invoice.created_at <= today).scalar() or 0)
    available_hours = headcount * 2080 * (fy_progress_pct / 100)
    utilization = (billable_hours / available_hours * 100) if available_hours else 0

    pnl = get_org_pnl_summary(db, year=today.year, month=today.month)
    margin = (pnl.get("margin_pct") or 0) if pnl else 0

    t = {k: v["target"] for k, v in targets.items()}
    metrics = [
        _metric("headcount", headcount, t["headcount"], fy_progress_pct),
        _metric("revenue", round(revenue_usd, 2), t["revenue"], fy_progress_pct),
        _metric("new_logos", new_logos, t["new_logos"], fy_progress_pct),
        _metric("engagement", round(engagement, 1), t["engagement"], fy_progress_pct, higher_is_better_absolute=True),
        _metric("retention", round(retention, 1), t["retention"], fy_progress_pct, higher_is_better_absolute=True),
        _metric("utilization", round(utilization, 1), t["utilization"], fy_progress_pct, higher_is_better_absolute=True),
        _metric("margin", round(margin, 1), t["margin"], fy_progress_pct, higher_is_better_absolute=True),
    ]
    by_key = {m["key"]: m for m in metrics}

    return {
        "fy_year": fy_year,
        "fy_progress_pct": round(fy_progress_pct, 1),
        "days_elapsed": days_elapsed,
        "total_fy_days": total_fy_days,
        "metrics": metrics,
        "targets_set": sum(1 for m in metrics if m["status"] != "NOT_SET"),
        # Per-metric shapes kept for existing screens (target fields are None when not set)
        "headcount": {**by_key["headcount"]},
        "revenue": {**by_key["revenue"], "current_usd": revenue_usd, "current_usd_cents": revenue_cents,
                    "target_usd": t["revenue"], "target_usd_cents": int(t["revenue"] * 100) if t["revenue"] else None},
        "new_logos": {**by_key["new_logos"]},
        "engagement": {**by_key["engagement"], "current_score": by_key["engagement"]["current"], "target_score": t["engagement"]},
        "retention": {**by_key["retention"], "current_pct": by_key["retention"]["current"], "target_pct": t["retention"]},
        "utilization": {**by_key["utilization"], "current_pct": by_key["utilization"]["current"], "target_pct": t["utilization"]},
        "margin": {**by_key["margin"], "current_pct": by_key["margin"]["current"], "target_pct": t["margin"]},
    }


def _fmt(metric: dict) -> str:
    unit, cur, tgt = metric["unit"], metric["current"], metric["target"]
    if unit == "USD":
        cur_s = f"${cur / 1e6:,.2f}M"
        tgt_s = f"${tgt / 1e6:,.2f}M" if tgt else None
    elif unit == "%":
        cur_s, tgt_s = f"{cur:.1f}%", (f"{tgt:g}%" if tgt else None)
    else:
        cur_s, tgt_s = f"{cur:g}", (f"{tgt:g}" if tgt else None)
    return f"{cur_s} (target: {tgt_s})" if tgt_s else f"{cur_s} (target not set)"


def get_fy_executive_summary(db: Session, tenant_id: Optional[int] = None) -> dict:
    """High-level FY progress summary for CEO presentation."""
    progress = get_fy_progress(db, tenant_id=tenant_id)
    metrics = progress["metrics"]
    with_targets = [m for m in metrics if m["status"] != "NOT_SET"]
    on_track = sum(1 for m in with_targets if m["status"] == "ON_TRACK")
    behind = len(with_targets) - on_track

    return {
        "fy_year": progress["fy_year"],
        "fy_progress_pct": progress["fy_progress_pct"],
        "overall_health_pct": round(on_track / len(with_targets) * 100, 1) if with_targets else None,
        "on_track_count": on_track,
        "behind_count": behind,
        "targets_set": len(with_targets),
        "metrics_total": len(metrics),
        "key_metrics": {m["label"]: _fmt(m) for m in metrics},
        "headline": _get_headline(progress),
        "priorities": _get_ceo_priorities(progress),
    }

def _get_headline(progress: dict) -> str:
    """Generate executive summary headline."""
    if progress["targets_set"] == 0:
        return "No FY targets set yet -- set them on the CEO Goals screen"
    if progress["fy_progress_pct"] < 25:
        return "Early stage FY — establishing momentum"
    elif progress["fy_progress_pct"] < 50:
        return "Mid-year checkpoint — tracking to plan"
    elif progress["fy_progress_pct"] < 75:
        return "Q3 push — accelerating finish"
    else:
        return "Final sprint — delivering FY targets"

def _get_ceo_priorities(progress: dict) -> list:
    """Top priorities for CEO focus based on progress."""
    priorities = []

    if progress["revenue"]["status"] == "BEHIND":
        priorities.append({
            "rank": 1,
            "metric": "Revenue",
            "gap": f"{progress['fy_progress_pct'] - progress['revenue']['progress_pct']:.0f} pts behind plan",
            "action": "Accelerate sales cycles and client expansion"
        })

    if progress["utilization"]["status"] == "BEHIND":
        priorities.append({
            "rank": len(priorities) + 1,
            "metric": "Utilization",
            "gap": f"{100 - progress['utilization']['progress_pct']:.0f}% below target",
            "action": "Increase billable allocations and delivery velocity"
        })

    if progress["headcount"]["status"] == "BEHIND":
        gap = progress["headcount"]["target"] - progress["headcount"]["current"]
        priorities.append({
            "rank": len(priorities) + 1,
            "metric": "Headcount",
            "gap": f"{gap:g} openings to fill",
            "action": "Accelerate hiring and onboarding"
        })

    unset = [m["label"] for m in progress["metrics"] if m["status"] == "NOT_SET"]
    if unset:
        priorities.append({
            "rank": len(priorities) + 1,
            "metric": "FY targets",
            "gap": f"{len(unset)} target(s) not set: {', '.join(unset)}",
            "action": "Set them on the CEO Goals screen"
        })

    if not priorities:
        priorities.append({
            "rank": 1,
            "metric": "Growth",
            "gap": "On track",
            "action": "Focus on new logos and market expansion"
        })

    return priorities

def get_slm_insights(db: Session) -> dict:
    """Get Smart Learning Model insights for CEO dashboard.

    Returns resume parsing accuracy, model readiness, and recommendations.
    """
    try:
        from app.services.slm_feedback_engine import SLMFeedbackEngine
        from app.services.slm_job_metadata_service import SLMJobMetadata

        # Get SLM accuracy stats
        stats = SLMFeedbackEngine.get_feedback_stats(db, days=30)

        # Get top performing jobs by hire rate
        top_jobs = db.query(SLMJobMetadata).filter(
            SLMJobMetadata.candidates_hired > 0
        ).order_by(SLMJobMetadata.candidates_hired.desc()).limit(5).all()

        top_jobs_list = [
            {
                "job_title": job.job_title,
                "candidates_hired": job.candidates_hired,
                "hire_success_rate": round(job.candidates_hired / max(1, job.candidates_submitted) * 100, 1) if job.candidates_submitted > 0 else 0
            }
            for job in top_jobs
        ]

        return {
            "status": "active",
            "resume_parsing_accuracy_pct": round(100 * (1 - stats.get("correction_rate", 0) / 100), 1),
            "total_feedback_this_month": stats.get("total_feedback", 0),
            "corrections_this_month": stats.get("corrections", 0),
            "model_ready_to_retrain": stats.get("ready_to_retrain", False),
            "low_confidence_fields": [field for field, acc in stats.get("low_confidence_fields", [])],
            "recommendation": stats.get("recommendation", "No action needed"),
            "top_performing_jobs": top_jobs_list
        }
    except Exception as e:
        logger.error(f"Failed to get SLM insights: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch SLM insights: {str(e)}"
        }

def get_fy_executive_dashboard(db: Session) -> dict:
    """Get complete CEO executive dashboard with SLM insights."""
    progress = get_fy_progress(db)
    slm_insights = get_slm_insights(db)
    summary = get_fy_executive_summary(db)

    return {
        **summary,
        "slm_insights": slm_insights
    }

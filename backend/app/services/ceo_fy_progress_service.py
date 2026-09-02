"""CEO FY Progress Dashboard — org-wide progress tracking against annual targets."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import Users
from app.models.employee import Employee
from app.models.candidate import Candidate
from app.models.client import Client
from app.models.opportunity import Opportunity
from app.models.invoice import Invoice
from app.services.pnl_service import get_org_pnl_summary
from app.utils.agent_logger import log_agent_execution
import logging
from app.core.logging import logger


def get_fy_targets(db: Session) -> dict:
    """Get the FY targets (hardcoded baseline, can be made configurable later)."""
    # Based on BlitzenX goals: 75 → 150 → 300 → 500 → 1,000 → 2,000 employees
    # Avinash's ambition: reach 2000-person scale
    return {
        "fy_year": 2026,  # Adjust based on current fiscal year
        "headcount_target": 150,  # Next scale gate
        "revenue_target_usd": 5000000,  # $5M annual target
        "new_logos_target": 20,
        "average_engagement_score": 85,
        "retention_target_pct": 95,
        "utilization_target_pct": 85,
        "margin_target_pct": 20
    }


def get_fy_progress(db: Session, fy_year: int = 2026) -> dict:
    """
    Get actual FY progress against targets.

    Returns headcount, revenue, clients, engagement, retention, utilization, margin progress.
    """
    targets = get_fy_targets(db)

    # FY 2026: assume calendar year for simplicity (Jan 1 - Dec 31, 2026)
    fy_start = datetime(fy_year, 1, 1)
    fy_end = datetime(fy_year, 12, 31)
    today = datetime.utcnow()

    # Calculate progress percentage (days elapsed in FY)
    total_fy_days = (fy_end - fy_start).days
    days_elapsed = max(1, (today - fy_start).days)
    fy_progress_pct = min(100, (days_elapsed / total_fy_days) * 100)

    # 1. Headcount: active employees (ACTIVE status, not archived)
    total_headcount = db.query(func.count(Employee.EmployeeID)).filter(
        Employee.EmployeeStatus == "ACTIVE"
    ).scalar() or 0

    headcount_target = targets["headcount_target"]
    headcount_pct = (total_headcount / headcount_target * 100) if headcount_target > 0 else 0

    # 2. Revenue: total invoiced YTD
    ytd_revenue = db.query(func.sum(Invoice.total_amount_usd_cents)).filter(
        Invoice.created_at >= fy_start,
        Invoice.created_at <= today,
        Invoice.status.in_(["APPROVED", "SENT", "PAID"])
    ).scalar() or 0

    revenue_target = targets["revenue_target_usd"] * 100
    revenue_pct = (ytd_revenue / revenue_target * 100) if revenue_target > 0 else 0

    # 3. New Logos: clients added YTD (status=ACTIVE)
    new_clients_ytd = db.query(func.count(Client.id)).filter(
        Client.status == "ACTIVE",
        Client.created_at >= fy_start,
        Client.created_at <= today
    ).scalar() or 0

    logos_target = targets["new_logos_target"]
    logos_pct = (new_clients_ytd / logos_target * 100) if logos_target > 0 else 0

    # 4. Engagement Score: proxy = (active opportunities / active clients) * 100
    active_opportunities = db.query(func.count(Opportunity.id)).filter(
        Opportunity.stage.in_(["PROSPECTING", "DISCOVERY", "PROPOSAL", "NEGOTIATION"]),
        Opportunity.created_at >= fy_start
    ).scalar() or 0

    active_clients = db.query(func.count(Client.id)).filter(
        Client.status == "ACTIVE",
        Client.created_at <= today
    ).scalar() or 1  # Avoid divide by zero

    engagement_score = (active_opportunities / active_clients * 100) if active_clients > 0 else 0
    engagement_target = targets["average_engagement_score"]
    engagement_pct = (engagement_score / engagement_target * 100) if engagement_target > 0 else 0

    # 5. Retention: (current headcount / peak headcount this year) * 100
    # For now, assume no departures = 100% retention (real attrition tracking not implemented)
    retention_pct = 100

    # 6. Utilization: billable hours / available hours
    billable_hours_ytd = db.query(func.sum(Invoice.billable_hours)).filter(
        Invoice.created_at >= fy_start,
        Invoice.created_at <= today
    ).scalar() or 0

    available_hours = total_headcount * 2080 if total_headcount > 0 else 1  # 40h/week * 52 weeks
    utilization_pct = (billable_hours_ytd / available_hours * 100) if available_hours > 0 else 0
    utilization_target = targets["utilization_target_pct"]
    utilization_progress_pct = (utilization_pct / utilization_target * 100) if utilization_target > 0 else 0

    # 7. Margin: org-wide this FY
    current_month = today.strftime("%Y-%m")
    pnl = get_org_pnl_summary(db, current_month)
    margin_pct = pnl.get("margin_pct", 0) if pnl else 0
    margin_target = targets["margin_target_pct"]
    margin_progress_pct = (margin_pct / margin_target * 100) if margin_target > 0 else 0

    return {
        "fy_year": fy_year,
        "fy_progress_pct": round(fy_progress_pct, 1),
        "days_elapsed": days_elapsed,
        "total_fy_days": total_fy_days,

        # Headcount
        "headcount": {
            "current": total_headcount,
            "target": headcount_target,
            "progress_pct": round(headcount_pct, 1),
            "status": "ON_TRACK" if headcount_pct >= fy_progress_pct * 0.9 else "BEHIND"
        },

        # Revenue
        "revenue": {
            "current_usd": ytd_revenue / 100 if ytd_revenue else 0,
            "current_usd_cents": ytd_revenue,
            "target_usd": targets["revenue_target_usd"],
            "target_usd_cents": revenue_target,
            "progress_pct": round(revenue_pct, 1),
            "status": "ON_TRACK" if revenue_pct >= fy_progress_pct * 0.9 else "BEHIND"
        },

        # New Logos
        "new_logos": {
            "current": new_clients_ytd,
            "target": logos_target,
            "progress_pct": round(logos_pct, 1),
            "status": "ON_TRACK" if logos_pct >= fy_progress_pct * 0.9 else "BEHIND"
        },

        # Engagement
        "engagement": {
            "current_score": round(engagement_score, 1),
            "target_score": engagement_target,
            "progress_pct": round(engagement_pct, 1),
            "status": "ON_TRACK" if engagement_pct >= fy_progress_pct * 0.9 else "BEHIND"
        },

        # Retention
        "retention": {
            "current_pct": round(retention_pct, 1),
            "target_pct": targets["retention_target_pct"],
            "progress_pct": round((retention_pct / targets["retention_target_pct"] * 100), 1),
            "status": "ON_TRACK"
        },

        # Utilization
        "utilization": {
            "current_pct": round(utilization_pct, 1),
            "target_pct": utilization_target,
            "progress_pct": round(utilization_progress_pct, 1),
            "status": "ON_TRACK" if utilization_progress_pct >= fy_progress_pct * 0.9 else "BEHIND"
        },

        # Margin
        "margin": {
            "current_pct": round(margin_pct, 1),
            "target_pct": margin_target,
            "progress_pct": round(margin_progress_pct, 1),
            "status": "ON_TRACK" if margin_progress_pct >= fy_progress_pct * 0.9 else "BEHIND"
        }
    }

    result_dict = {
        "fy_year": fy_year,
        "headcount_progress": total_headcount,
        "revenue_progress_usd_cents": ytd_revenue,
        "margin_pct": margin_pct,
        "fy_progress_pct": fy_progress_pct
    }

    log_agent_execution(
        db=db,
        agent_name="CEO/FY Progress Agent",
        action_taken="get_fy_progress",
        tenant_id="system",
        action_data=result_dict,
        success=True,
    )


def get_fy_executive_summary(db: Session) -> dict:
    """High-level FY progress summary for CEO presentation."""
    progress = get_fy_progress(db)
    targets = get_fy_targets(db)

    # Count on-track vs behind metrics
    metrics = [
        progress["headcount"],
        progress["revenue"],
        progress["new_logos"],
        progress["engagement"],
        progress["retention"],
        progress["utilization"],
        progress["margin"]
    ]

    on_track = sum(1 for m in metrics if m["status"] == "ON_TRACK")
    behind = len(metrics) - on_track

    # Calculate overall health (simple: on_track / total)
    overall_health_pct = (on_track / len(metrics) * 100) if metrics else 0

    return {
        "fy_year": progress["fy_year"],
        "fy_progress_pct": progress["fy_progress_pct"],
        "overall_health_pct": round(overall_health_pct, 1),
        "on_track_count": on_track,
        "behind_count": behind,
        "key_metrics": {
            "headcount": f"{progress['headcount']['current']}/{targets['headcount_target']}",
            "revenue": f"${progress['revenue']['current_usd']:,.0f}M (target: ${targets['revenue_target_usd']/1e6:.1f}M)",
            "new_logos": f"{progress['new_logos']['current']} (target: {targets['new_logos_target']})",
            "margin": f"{progress['margin']['current_pct']:.1f}% (target: {targets['margin_target_pct']}%)"
        },
        "headline": _get_headline(progress),
        "priorities": _get_ceo_priorities(progress)
    }


def _get_headline(progress: dict) -> str:
    """Generate executive summary headline."""
    if progress["fy_progress_pct"] < 25:
        return "Early stage FY — establishing momentum"
    elif progress["fy_progress_pct"] < 50:
        return "Mid-year checkpoint — tracking to plan"
    elif progress["fy_progress_pct"] < 75:
        return "Q3 push — accelerating finish"
    else:
        return "Final sprint — delivering FY targets"


def _get_ceo_priorities(progress: dict) -> list:
    """Extract top 3 priorities for CEO focus based on progress."""
    priorities = []

    # If revenue behind, that's priority #1
    if progress["revenue"]["status"] == "BEHIND":
        gap_pct = 100 - progress["revenue"]["progress_pct"]
        priorities.append({
            "rank": 1,
            "metric": "Revenue",
            "gap": f"{gap_pct:.0f}% behind plan",
            "action": "Accelerate sales cycles and client expansion"
        })

    # If utilization behind, that's high priority
    if progress["utilization"]["status"] == "BEHIND":
        gap_pct = 100 - progress["utilization"]["progress_pct"]
        priorities.append({
            "rank": len(priorities) + 1,
            "metric": "Utilization",
            "gap": f"{gap_pct:.0f}% below target",
            "action": "Increase billable allocations and delivery velocity"
        })

    # If headcount behind, that's important for scaling
    if progress["headcount"]["status"] == "BEHIND":
        gap = progress["headcount"]["target"] - progress["headcount"]["current"]
        priorities.append({
            "rank": len(priorities) + 1,
            "metric": "Headcount",
            "gap": f"{gap} openings to fill",
            "action": "Accelerate hiring and onboarding"
        })

    # If no major issues, focus on growth
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
    except Exception as e:        logger.error(f"Failed to get SLM insights: {str(e)}", exc_info=True)
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

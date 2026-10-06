"""Admin Weekly Recap -- what the agents and the pipeline did in one week.

Built only from recorded data: agent runs (agent_execution_log), agent
maturity (agent_maturity_levels), the org-health alert counts, and
opportunities opened/won/lost in the week. Replaces a screen that showed
hardcoded sample numbers.
"""
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.agent_execution_log import AgentExecutionLog
from app.models.agent_maturity import AgentMaturityLevel
from app.models.employee import Employee
from app.models.opportunity import Opportunity

# An agent below this success rate for the week is shown as degraded
DEGRADED_BELOW_SUCCESS_PCT = 90
WON_STAGES = ("CONTRACT", "ACTIVE")


def _week_bounds(weeks_back: int):
    """Monday 00:00 .. next Monday 00:00 (UTC), weeks_back weeks ago."""
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks_back)
    start = datetime.combine(monday, datetime.min.time())
    return start, start + timedelta(days=7)


def _agent_health(db: Session, start: datetime, end: datetime) -> list:
    rows = db.query(
        AgentExecutionLog.agent_name,
        func.count(AgentExecutionLog.id),
        func.sum(case((AgentExecutionLog.success.is_(False), 1), else_=0)),
        func.max(AgentExecutionLog.execution_at),
    ).filter(
        AgentExecutionLog.execution_at >= start, AgentExecutionLog.execution_at < end
    ).group_by(AgentExecutionLog.agent_name).all()

    maturity = {
        name: level for name, level in db.query(
            AgentMaturityLevel.agent_name, AgentMaturityLevel.maturity_level
        ).filter(AgentMaturityLevel.is_retired.is_(False)).all()
    }

    agents = []
    for name, runs, failures, last_run in rows:
        failures = int(failures or 0)
        success_rate = round((runs - failures) / runs * 100, 1) if runs else None
        agents.append({
            "name": name,
            "runs": runs,
            "failures": failures,
            "success_rate": success_rate,
            "maturity": maturity.get(name),
            "status": "degraded" if success_rate is not None and success_rate < DEGRADED_BELOW_SUCCESS_PCT else "operational",
            "last_run": last_run.isoformat() if last_run else None,
        })
    return sorted(agents, key=lambda a: (a["status"] != "degraded", a["name"]))


def _pipeline_by_owner(db: Session, start: datetime, end: datetime) -> list:
    def per_owner(*filters):
        return dict(
            (owner, (count, int(value or 0)))
            for owner, count, value in db.query(
                Opportunity.owner_employee_id, func.count(Opportunity.id), func.sum(Opportunity.revenue_value_usd_cents)
            ).filter(*filters).group_by(Opportunity.owner_employee_id).all()
        )

    opened = per_owner(Opportunity.created_at >= start, Opportunity.created_at < end)
    won = per_owner(Opportunity.stage.in_(WON_STAGES), Opportunity.updated_at >= start, Opportunity.updated_at < end)
    lost = per_owner(Opportunity.stage == "LOST", Opportunity.updated_at >= start, Opportunity.updated_at < end)

    owner_ids = set(opened) | set(won) | set(lost)
    names = {
        e.id: " ".join(filter(None, [e.first_name, e.last_name]))
        for e in db.query(Employee).filter(Employee.id.in_([o for o in owner_ids if o])).all()
    }
    rows = []
    for owner in owner_ids:
        rows.append({
            "owner": names.get(owner, "Unassigned"),
            "opened": opened.get(owner, (0, 0))[0],
            "opened_value_usd_cents": opened.get(owner, (0, 0))[1],
            "won": won.get(owner, (0, 0))[0],
            "won_value_usd_cents": won.get(owner, (0, 0))[1],
            "lost": lost.get(owner, (0, 0))[0],
        })
    return sorted(rows, key=lambda r: -r["won_value_usd_cents"])


def get_weekly_recap(db: Session, weeks_back: int = 0) -> dict:
    from app.services.org_health_service import get_org_health_snapshot

    start, end = _week_bounds(weeks_back)
    agents = _agent_health(db, start, end)
    health = get_org_health_snapshot(db)
    queue = health["recruiting"]["intervention_queue"]

    return {
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(days=1)).date().isoformat(),
        "agents": agents,
        "agents_reporting": len(agents),
        "agents_operational": sum(1 for a in agents if a["status"] == "operational"),
        "agents_degraded": sum(1 for a in agents if a["status"] == "degraded"),
        "alerts": {
            "intervention_critical": queue.get("critical", 0),
            "intervention_high": queue.get("high", 0),
            "active_sla_breaches": health["recruiting"]["active_sla_breaches"],
            "escalated_overdue_tasks": health["workforce"]["overdue_tasks"],
            "open_capacity_alerts": health["workforce"]["open_capacity_alerts"],
        },
        "pipeline": _pipeline_by_owner(db, start, end),
    }

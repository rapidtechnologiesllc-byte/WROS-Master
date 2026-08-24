"""
Executive Signal & Culture Agent -- org-health rollup.

Real correction, 2026-08-04 (see app.models.executive_signal's module
docstring): the original design assumed aggregating "Client Health"
and "Project Health" scores already built elsewhere in the platform.
Neither exists -- confirmed via grep before writing this (HRMS-1107
Project Health Monitoring is explicitly NOT built per
app.models.project's own docstring; no client-health score exists
anywhere). This aggregates what's REALLY there instead: recruiting
risk/intervention queue, SLA breaches, revenue leakage, bench aging,
and the new Task system's own overdue/capacity signals -- a real
"watches everything, surfaces what needs attention" view, not
fabricated scores. Read-only by design -- this agent watches, it does
not act on any of it.

Tenant scoping: candidate-engagement-side signals (SLA breaches,
intervention queue) use the real per-owner "tenant_id resolves to a
UserID" convention (resolve_default_tenant_id()); revenue/bench-side
signals use the separate Integer Tenant.id convention with
tenant_id=None (returns NULL-tenant rows, the common case in a
single-org deployment) -- this codebase's own pre-existing tenant-
model inconsistency, not invented here, just aggregated across both
conventions honestly rather than silently picking one.
"""
from typing import Dict

from sqlalchemy.orm import Session


def get_org_health_snapshot(db: Session) -> Dict:
    from app.services.ai_conversation_service import resolve_default_tenant_id
    from app.services.intervention_queue_service import get_queue_summary
    from app.services.resource_management_service import check_bench_aging_alerts
    from app.services.revenue_leakage_service import get_active_leakage_flags
    from app.services.sla_monitoring_service import get_active_breaches
    from app.services.task_assignment_service import OPEN_STATUSES
    from app.models.task import Task, TaskCapacityAlert

    engagement_tenant_id = resolve_default_tenant_id(db)

    intervention_summary = get_queue_summary(db, engagement_tenant_id) if engagement_tenant_id else {}
    sla_breaches = get_active_breaches(db, engagement_tenant_id) if engagement_tenant_id else []
    leakage_flags = get_active_leakage_flags(db, tenant_id=None)
    bench_aging_alerts = check_bench_aging_alerts(db, tenant_id=None)

    overdue_tasks = db.query(Task).filter(Task.status.in_(OPEN_STATUSES), Task.is_escalated.is_(True)).count()
    open_capacity_alerts = db.query(TaskCapacityAlert).filter(TaskCapacityAlert.is_resolved.is_(False)).count()

    return {
        "recruiting": {
            "intervention_queue": intervention_summary,
            "active_sla_breaches": len(sla_breaches),
        },
        "revenue": {
            "active_leakage_flags": len(leakage_flags),
        },
        "workforce": {
            "bench_aging_alerts": bench_aging_alerts,
            "overdue_tasks": overdue_tasks,
            "open_capacity_alerts": open_capacity_alerts,
        },
        "note": (
            "Client Health and Project Health scores don't exist yet in this codebase "
            "(HRMS-1107 not built) -- this snapshot aggregates real existing signals only, "
            "not fabricated health scores."
        ),
    }

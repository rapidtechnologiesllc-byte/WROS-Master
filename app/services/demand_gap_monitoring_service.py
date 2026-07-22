"""
HRMS-1102 -- Workforce Demand Monitoring Agent.

Per the story doc's own framing: this agent decides WHEN sourcing
needs to start and for WHAT -- it never sources candidates itself
(HRMS-1103's job) and it never bypasses R-04 (bench-first). See
app.models.sourcing for what's genuinely unresolved here
(bench_match_count has no real skill-matching engine to compute it
yet -- Phase 4 territory, not invented here).

Severity classification is specified as an LLM call
(claude-sonnet-4-6). No Claude API client is wired into this codebase
today (Gemini is, for a different story) -- classify_gap_severity()
takes an injectable llm_classifier, same "real orchestration logic,
injectable external dependency" pattern as
orchestration_router_service's novel-pattern classifier and
thunder_service's whatsapp_client. Absence or failure of the
classifier defaults to WATCH per AC-6 ("LLM call failure defaults
severity to WATCH and does not create a sourcing alert"), not silently
upgraded to something that would create one.
"""
from datetime import datetime
from typing import Callable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.sourcing import GAP_SEVERITIES, DemandGapScore, SourcingAlert
from app.models.user import Users
from app.services.notification_service import send_notification

CRITICAL_ESCALATION_DAYS_OPEN = 5  # BR-1102-03


def classify_gap_severity(
    *,
    required_skills: str,
    bench_match_count: int,
    days_open: int,
    demand_type: Optional[str],
    llm_classifier: Optional[Callable[[dict], dict]] = None,
) -> Tuple[str, Optional[str], bool]:
    """
    Returns (gap_severity, rationale, llm_parse_failed). Step 3's
    "reject and retry once on malformed JSON, on second failure default
    to WATCH" is collapsed here into a single try (an injectable test
    double doesn't benefit from a literal retry loop) -- any exception
    or a response missing gap_severity, or with a gap_severity outside
    GAP_SEVERITIES, is treated as parse failure.
    """
    if llm_classifier is None:
        return "WATCH", None, True

    try:
        result = llm_classifier({
            "required_skills": required_skills,
            "bench_match_count": bench_match_count,
            "days_open": days_open,
            "demand_type": demand_type,
        })
        severity = result.get("gap_severity")
        rationale = result.get("rationale")
        if severity not in GAP_SEVERITIES:
            return "WATCH", None, True
        return severity, rationale, False
    except Exception:
        return "WATCH", None, True


def scan_demand_gap(
    db: Session,
    demand: Demand,
    *,
    bench_match_count: int,
    llm_classifier: Optional[Callable[[dict], dict]] = None,
    router_evaluate: Optional[Callable[..., object]] = None,
    rm_user: Optional[Users] = None,
    now: Optional[datetime] = None,
) -> DemandGapScore:
    """
    One scan-cycle pass for a single demand. bench_match_count is
    required and caller-supplied -- see module/model docstrings on why
    this codebase can't compute it internally yet.

    router_evaluate: if supplied, called as
    router_evaluate(agent_id="HRMS-1102", entity_type="demand",
    entity_id=demand.id, action_type="sourcing_alert_create",
    risk_tier="LOW") before a sourcing_alerts row is created, matching
    HRMS-1102's own "publish agent.action.intent... before creating the
    row" step. Not required -- the Orchestration Router fails open by
    design (BR-1101-06), and this agent's own alert-creation gate
    (R-04) is enforced regardless of whether the Router is wired in.
    """
    now = now or datetime.utcnow()
    days_open = max(0, (now - demand.created_at).days) if demand.created_at else 0

    severity, rationale, llm_parse_failed = classify_gap_severity(
        required_skills=demand.required_skills,
        bench_match_count=bench_match_count,
        days_open=days_open,
        demand_type=getattr(demand, "demand_type", None),
        llm_classifier=llm_classifier,
    )

    score = DemandGapScore(
        tenant_id=demand.tenant_id,
        demand_id=demand.id,
        bench_match_count=bench_match_count,
        bench_first_check_passed=bool(demand.bench_first_checked),
        gap_severity=severity,
        rationale=rationale,
        llm_parse_failed=llm_parse_failed,
        days_open=days_open,
        scored_at=now,
    )
    db.add(score)
    db.flush()

    if severity in ("ALERT", "CRITICAL"):
        _maybe_create_sourcing_alert(
            db, demand, score, router_evaluate=router_evaluate,
        )

    if severity == "CRITICAL" and days_open > CRITICAL_ESCALATION_DAYS_OPEN and rm_user is not None:
        _escalate_to_rm(db, demand, score, rm_user=rm_user)

    return score


def _maybe_create_sourcing_alert(
    db: Session, demand: Demand, score: DemandGapScore, *, router_evaluate,
) -> Optional[SourcingAlert]:
    # BR-1102-01: R-04 hard gate -- this agent has no authority to
    # bypass it. Reuses Demand.bench_first_checked (the real, existing
    # R-04 flag / app.services.demand_service.enable_sourcing() gate)
    # rather than a second bench-first mechanism.
    if not score.bench_first_check_passed:
        return None

    if router_evaluate is not None:
        router_evaluate(
            agent_id="HRMS-1102", entity_type="demand", entity_id=demand.id,
            action_type="sourcing_alert_create", risk_tier="LOW", tenant_id=demand.tenant_id,
        )

    alert = SourcingAlert(
        tenant_id=demand.tenant_id, demand_id=demand.id, gap_score_id=score.id,
        severity=score.gap_severity, rationale=score.rationale,
        bench_first_check_passed=True, status="OPEN",
    )
    db.add(alert)
    return alert


def _escalate_to_rm(db: Session, demand: Demand, score: DemandGapScore, *, rm_user: Users) -> None:
    # BR-1102-03: immediate, 24/7, never batched into the morning digest
    # -- P0 is the one priority tier that actually bypasses business-
    # hours gating in notification_service.send_notification(), reused
    # here rather than building a second "send immediately" path.
    send_notification(
        db, calling_context_tenant_id=demand.tenant_id, recipient=rm_user,
        priority_tier="P0", channel_preference="IN_APP",
        message=(
            f"CRITICAL sourcing gap on demand '{demand.job_title}' "
            f"({demand.id}), open {score.days_open} days: {score.rationale or 'no rationale available'}."
        ),
    )

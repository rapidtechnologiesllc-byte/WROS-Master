"""
HRMS-1103 -- LinkedIn Sourcing Agent Loop (Phase 3 Workstream 1 /
import logging
Recruit), EPIC-11.

Consumes OPEN sourcing_alerts (HRMS-1102's output), generates a Boolean
search query, executes it, deduplicates results, and stages the clean
candidate list for HRMS-1104's outreach agent. Per BR-1103-01, this
agent NEVER calls createCandidateSafe()'s CREATE path -- only its
dedup-check sub-function
(app.services.candidate_service.find_duplicate_candidate(), already
real and tested for R-07) -- reused here, not reimplemented. The
promotion path below (BR-1103-02) is the one exception: it's the
explicit human action, not this agent acting on its own.

Two genuinely unresolved external dependencies, injectable rather than
faked (same pattern as HRMS-1102's bench_match_count, thunder_service's
whatsapp_client, and the Router's llm_classifier):
  - EPIC-P9 Boolean Search Engine (query execution against LinkedIn
    Recruiter API) -- doesn't exist in this codebase.
  - LLM query generation (claude-sonnet-4-6) and HRMS-0429's canonical
    skill synonym library -- no Claude client is wired into this
    codebase (Gemini is, for ai_conversation_service's different
    story), and HRMS-0429 doesn't exist either.

This codebase's dedup is exact-match only (email/phone/LinkedIn URL),
per R-07's own "no fuzzy/AI-based name matching" note elsewhere -- so
dedup_status here is binary in practice: NEW or CONFIRMED_DUPLICATE.
POSSIBLE_DUPLICATE is modeled (matches the doc's enum) but never
produced by this implementation; it's reserved for a future fuzzy-
matching capability this codebase doesn't have.
"""
import json
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.demand import Demand
from app.models.sourcing import SourcingAlert, SourcingSearchRun, StagedCandidate
from app.models.user import Users
from app.services.candidate_service import create_candidate_safe, find_duplicate_candidate
from app.services.notification_service import send_notification

CONSECUTIVE_SEARCH_FAILURES_BEFORE_ESCALATION = 2  # AC-6

logger = logging.getLogger(__name__)

class StagedCandidateAlreadyPromoted(Exception):
    """BR-1103-02: a staged_candidates row can only be promoted once."""


def claim_alert(db: Session, alert_id: str) -> Optional[SourcingAlert]:
    """
    BR-1103-03: atomic OPEN->PROCESSING claim, preventing two workers
    from double-sourcing the same demand. Uses a conditional UPDATE
    (WHERE status='OPEN') rather than SELECT FOR UPDATE -- SQLite (this
    codebase's test database) doesn't support row-level locking the
    same way SQL Server does, but the conditional-UPDATE-and-check-
    rowcount pattern is portable across both and gives the identical
    atomicity guarantee: two callers racing this statement can never
    both see rowcount=1.
    """
    updated = (
        db.query(SourcingAlert)
        .filter(SourcingAlert.id == alert_id, SourcingAlert.status == "OPEN")
        .update({"status": "PROCESSING"}, synchronize_session=False)
    )
    if updated == 0:
        return None
    db.flush()
    return db.query(SourcingAlert).filter(SourcingAlert.id == alert_id).first()


def _generate_query(demand: Demand, *, llm_query_generator):
    """Returns (boolean_query, alt_queries_json, rationale, estimated_volume, generation_failed)."""
    if llm_query_generator is None:
        return None, None, None, None, True
    try:
        result = llm_query_generator({
            "required_skills": demand.required_skills,
            "demand_type": getattr(demand, "demand_type", None),
        })
        query = result.get("boolean_query")
        if not query:
            return None, None, None, None, True
        return (
            query,
            json.dumps(result.get("alt_queries") or []),
            result.get("search_rationale"),
            result.get("estimated_result_volume"),
            False,
        )
    except Exception:
        return None, None, None, None, True


def process_sourcing_alert(
    db: Session,
    alert: SourcingAlert,
    demand: Demand,
    *,
    llm_query_generator: Optional[Callable[[dict], dict]] = None,
    search_executor: Optional[Callable[[str], List[dict]]] = None,
    router_evaluate: Optional[Callable[..., object]] = None,
    rm_user: Optional[Users] = None,
    manual_query_override: Optional[str] = None,
    now: Optional[datetime] = None,
) -> SourcingSearchRun:
    """
    One processing attempt against an already-claimed (status=
    PROCESSING) alert. Callers must call claim_alert() first -- this
    function doesn't claim it itself, so the atomic-claim step stays
    independently testable/inspectable rather than buried inside one
    monolithic call.

    manual_query_override: per the UI spec, a recruiter-supplied string
    takes precedence over LLM generation entirely for this run.
    """
    now = now or datetime.utcnow()
    run = SourcingSearchRun(
        tenant_id=alert.tenant_id, sourcing_alert_id=alert.id,
        manual_query_override=manual_query_override, status="RUNNING",
    )
    db.add(run)
    db.flush()

    query = manual_query_override
    if query is None:
        query, alt_queries, rationale, estimated_volume, generation_failed = _generate_query(
            demand, llm_query_generator=llm_query_generator,
        )
        run.alt_queries = alt_queries
        run.search_rationale = rationale
        run.estimated_result_volume = estimated_volume
        if generation_failed:
            # Integration table: LLM failure -> mark search run FAILED,
            # re-queue alert as OPEN (distinct from the search-execution
            # failure path below, which counts toward RM escalation).
            run.status = "FAILED"
            alert.status = "OPEN"
            db.add(run)
            db.add(alert)
            return run

    run.boolean_query = query
    db.add(run)

    results = None
    if search_executor is not None:
        try:
            results = search_executor(query)
        except Exception:
            results = None

    if results is None:
        alert.consecutive_search_failures = (alert.consecutive_search_failures or 0) + 1
        run.status = "FAILED"
        if (
            alert.consecutive_search_failures >= CONSECUTIVE_SEARCH_FAILURES_BEFORE_ESCALATION
            and rm_user is not None
        ):
            # AC-6 -- doc doesn't specify a priority tier for this one
            # (unlike HRMS-1102's explicit "24/7, not batched" P0 case);
            # P1 (business-hours gated, standard escalation) is the
            # closest documented tier for a non-immediate RM alert.
            send_notification(
                db, calling_context_tenant_id=alert.tenant_id, recipient=rm_user,
                priority_tier="P1", channel_preference="IN_APP",
                message=(
                    f"Boolean Search Engine failed {alert.consecutive_search_failures} consecutive "
                    f"times sourcing demand '{demand.job_title}' ({demand.id})."
                ),
            )
        db.add(alert)
        db.add(run)
        return run

    alert.consecutive_search_failures = 0

    staged_count = 0
    for result in results:
        # BR-1103-01/AC-4: the dedup-check sub-function only -- never
        # create_candidate_safe()'s CREATE path. A CONFIRMED_DUPLICATE
        # is excluded from staged_candidates entirely, not staged-then-
        # marked; nothing to promote if it's already a real candidate.
        existing, _matched_on = find_duplicate_candidate(
            db, email=result.get("email"), mobile=result.get("mobile"),
            linkedin_url=result.get("linkedin_profile_url"),
        )
        if existing is not None:
            continue

        db.add(StagedCandidate(
            tenant_id=alert.tenant_id, search_run_id=run.id,
            linkedin_profile_url=result.get("linkedin_profile_url"),
            email=result.get("email"), mobile=result.get("mobile"),
            full_name=result.get("full_name"),
            raw_profile_data=json.dumps(result),
            dedup_status="NEW", status="PENDING_REVIEW",
        ))
        staged_count += 1

    run.staged_candidate_count = staged_count
    run.status = "COMPLETE"
    run.completed_at = now
    db.add(run)

    if router_evaluate is not None:
        router_evaluate(
            agent_id="HRMS-1103", entity_type="staged_candidate_batch", entity_id=run.id,
            action_type="stage_candidates", risk_tier="LOW", tenant_id=alert.tenant_id,
        )

    alert.status = "SOURCED"
    alert.sourced_at = now
    db.add(alert)

    return run


def promote_staged_candidate(
    db: Session,
    staged: StagedCandidate,
    *,
    promoted_by: str,
    consent_given: bool = True,
    **candidate_fields,
) -> Candidate:
    """
    BR-1103-02: the ONLY path from a staged_candidates row to a real
    candidates row -- a recruiter's explicit "Promote" action, never
    this agent acting alone. Calls create_candidate_safe() (R-07's one
    CREATE path) and captures consent, per the story's own "including
    consent capture" wording -- recorded against the whatsapp_outreach
    consent type, matching thunder_service's send-gate.
    """
    if staged.status == "PROMOTED":
        raise StagedCandidateAlreadyPromoted(
            f"Staged candidate {staged.id} was already promoted to {staged.promoted_to_candidate_id}."
        )

    candidate = create_candidate_safe(
        db, email=staged.email, mobile=staged.mobile,
        linkedin_url=staged.linkedin_profile_url,
        candidateSource="linkedin_sourcing_agent",
        **candidate_fields,
    )
    db.add(ConsentRecord(
        subject_type="candidate", subject_id=candidate.candidateID,
        consent_type="whatsapp_outreach", consent_given=consent_given,
        captured_by=promoted_by,
    ))

    staged.status = "PROMOTED"
    staged.promoted_to_candidate_id = candidate.candidateID
    staged.promoted_by = promoted_by
    staged.promoted_at = datetime.utcnow()
    db.add(staged)

    return candidate

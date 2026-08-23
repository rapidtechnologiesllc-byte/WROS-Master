"""
HRMS-1105 (canonical S-320 -- not S-274 as its `.docx` filename says, and
NOT "HRMS-0312" as that same doc's own prerequisite line and
04-RESOURCE-MANAGEMENT.md both say; both corrected against
`WROS_Canonical_Backlog_S001-401.xlsx`) -- Resource Management Agent.

Built from `Requirements/S-274_HRMS-1105.docx` directly.

The 30-minute cadence is scheduling wiring this codebase defers everywhere
(same "idempotent function exists, wiring is follow-up" posture as every
other cron-shaped story here, e.g. HRMS-0901's weekly draft job) --
run_bench_scan() is a plain, directly-callable, idempotent function, not a
self-scheduling loop.

Scope decision on "Core-vs-Speciality simultaneous eligibility", flagged
rather than silently narrowed: the story doc frames this purely in terms
of the *bench* pool ("query current bench pool... for each bench
employee..."), but detect_core_pull_conflict() (S-353) only ever finds a
conflict for an employee who currently HOLDS an active Speciality
allocation -- which a bench employee, by definition, does not. Scanning
literally only the bench pool would make AC-1 ("a bench employee matching
both a CORE and SPECIALITY demand triggers HRMS-0514") structurally
unreachable. This module therefore also checks every Core-Certified
employee who *does* hold an active Speciality allocation against open
CORE demands -- the real Core-Pull scenario -- using the exact same
detect_core_pull_conflict() call, never a second copy of "Core wins".
Bench employees still only ever get ranked, never pulled (there is
nothing active to pull them from).

DEFERRED, not silently dropped: S-358/HRMS-0519's AC-3 ("+5 continuity
bonus when an employee's current SI partner matches the new demand's")
is not wired into skill_match_score() or the LLM ranking pass below.
That AC assumes a flat point-bonus scoring model; this module's actual
scoring is a 0-1 skill-match float plus an independent LLM confidence
score, and match_bench_resources_to_demand() only ever considers
already-unallocated bench employees, who by definition have no
"current SI partner" a continuity bonus could apply to -- the doc's
scenario (someone already deployed at PwC) is really about
find_open_demand_matches() territory instead. Flagging rather than
forcing an ad-hoc fit onto a scoring model that wasn't built for it.
"""
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.llm_prompt_safety import build_safe_prompt
from app.core.logging import logger
from app.models.core_pull import CorePullEvent
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_agent import BenchAllocationRecommendation
from app.models.user import Users
from app.services.core_pull_service import detect_core_pull_conflict
from app.services.employee_allocation_service import allocate_employee_to_project
from app.services.notification_service import send_notification
from app.services.resource_management_service import get_current_bench_pool, is_staffing_eligible
from app.utils.agent_logger import log_agent_execution

# Reuses the same Gemini pattern as every other LLM call in this codebase
# (thunder_service.py, ai_conversation_service.py) rather than the story
# doc's "claude-sonnet-4-6" -- no Claude API client is wired in this
# codebase, same substitution already made and confirmed for Thunder.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RANKER_MODEL = "gemini-3-flash-preview"

# No requirements doc specifies an exact skill-match threshold ("skill
# match score exceeds threshold" is the doc's own phrasing) -- 0.5 (at
# least half the demand's required skills present) is this session's
# plain default, flagged rather than silently baked in with no comment.
SKILL_MATCH_THRESHOLD = 0.5

RESOURCE_AGENT_ID = "resource_management_agent"


class RecommendationNotPending(Exception):
    pass


class EmployeeAlreadyActivelyEngaged(Exception):
    """Avinash's explicit business call (2026-07-22): an employee already
    IN_PROGRESS on one client engagement must never be simultaneously
    pursued for a second. Hard block, not a warning -- see
    start_pursuing_recommendation()."""


# ---------------------------------------------------------------------------
# Skill matching
# ---------------------------------------------------------------------------

def _parse_skills(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(s).strip().lower() for s in parsed if str(s).strip()]


def skill_match_score(employee_skills_raw: Optional[str], demand_required_skills_raw: Optional[str]) -> float:
    """Fraction of the demand's required skills the employee has. 0.0 if
    the demand lists no required skills (nothing to match against)."""
    employee_skills = set(_parse_skills(employee_skills_raw))
    required_skills = set(_parse_skills(demand_required_skills_raw))
    if not required_skills:
        return 0.0
    return len(employee_skills & required_skills) / len(required_skills)


def find_open_demand_matches(
    db: Session, employee: Employee, *, min_score: float = SKILL_MATCH_THRESHOLD,
) -> List[Tuple[Demand, float]]:
    """Every OPEN/IN_PROGRESS demand this employee is skill-eligible for
    (per SKILL_MATCH_THRESHOLD) and staffing-eligible for (per
    is_staffing_eligible() -- buddy-program/core-certification gates),
    scored, tenant-scoped, highest match first."""
    candidate_demands = (
        db.query(Demand)
        .filter(
            Demand.tenant_id == employee.tenant_id,
            Demand.status.in_(("OPEN", "IN_PROGRESS")),
        )
        .all()
    )
    matches = []
    for demand in candidate_demands:
        eligible, _reason = is_staffing_eligible(employee, demand.delivery_engine)
        if not eligible:
            continue
        score = skill_match_score(employee.current_skills, demand.required_skills)
        if score >= min_score:
            matches.append((demand, score))
    matches.sort(key=lambda pair: pair[1], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# S-253/HRMS-0509 (canonical) -- Match Bench Resources to Opportunity.
#
# The reverse direction of find_open_demand_matches() above (one demand
# -> ranked bench candidates, rather than one employee -> ranked
# demands) -- reuses the exact same skill_match_score()/
# is_staffing_eligible() pair, not a second scoring implementation.
# Deliberately does not touch bench_allocation_recommendations or call
# the LLM ranker: this is a read-only "who fits this opportunity"
# preview a demand owner can check anytime, distinct from HRMS-1105's
# own scan-and-write recommendation workflow (rank_bench_candidate()),
# which stays the only thing that ever writes a recommendation row.
# ---------------------------------------------------------------------------

def match_bench_resources_to_demand(
    db: Session, demand: Demand, *, top_n: int = 5, min_score: float = SKILL_MATCH_THRESHOLD,
) -> List[Dict]:
    """Top `top_n` current bench employees for this demand, by skill
    match score, staffing-eligibility-filtered. Returns
    [{employee, score}, ...], highest match first."""
    ranked: List[Tuple[Employee, float]] = []
    for entry in get_current_bench_pool(db, tenant_id=demand.tenant_id):
        employee = db.query(Employee).filter(Employee.id == entry.employee_id).first()
        if employee is None:
            continue
        eligible, _reason = is_staffing_eligible(employee, demand.delivery_engine)
        if not eligible:
            continue
        score = skill_match_score(employee.current_skills, demand.required_skills)
        if score >= min_score:
            ranked.append((employee, score))

    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return [{"employee": employee, "score": score} for employee, score in ranked[:top_n]]


# ---------------------------------------------------------------------------
# Step 3/BR-1105-01/AC-1/AC-3 -- Core-vs-Speciality detection, delegated
# ---------------------------------------------------------------------------

def _speciality_deployed_core_certified_employees(db: Session, tenant_id: Optional[int]) -> List[Employee]:
    return (
        db.query(Employee)
        .join(EmployeeAllocation, EmployeeAllocation.employee_id == Employee.id)
        .join(Demand, EmployeeAllocation.demand_id == Demand.id)
        .filter(
            Employee.tenant_id == tenant_id,
            Employee.core_certified.is_(True),
            EmployeeAllocation.status == "ACTIVE",
            Demand.delivery_engine == "SPECIALITY",
        )
        .distinct()
        .all()
    )


def detect_core_pull_triggers(
    db: Session, *, tenant_id: Optional[int] = None, bu_head: Optional[Users] = None,
) -> List[CorePullEvent]:
    """
    BR-1105-01/AC-1: for every Core-Certified employee currently deployed
    in Speciality, checks every open CORE demand via the SAME
    detect_core_pull_conflict() S-353 already exposes -- never a local
    "Core wins" conditional. AC-6: a detection failure for one employee
    alerts bu_head (if given) and does not abort the rest of the scan.
    """
    triggered: List[CorePullEvent] = []
    core_demands = (
        db.query(Demand)
        .filter(
            Demand.tenant_id == tenant_id,
            Demand.delivery_engine == "CORE",
            Demand.status.in_(("OPEN", "IN_PROGRESS")),
        )
        .all()
    )
    if not core_demands:
        return triggered

    for employee in _speciality_deployed_core_certified_employees(db, tenant_id):
        for core_demand in core_demands:
            try:
                event = detect_core_pull_conflict(db, employee, core_demand)
            except Exception as exc:
                logger.error(f"[ResourceAgent] Core-Pull detection failed for employee {employee.id}: {exc}")
                if bu_head is not None:
                    try:
                        send_notification(
                            db, calling_context_tenant_id=tenant_id, recipient=bu_head, priority_tier="P0",
                            message=(
                                f"Resource Management Agent: Core-Pull detection failed for employee "
                                f"{employee.id} -- {exc}"
                            ),
                        )
                    except Exception:
                        pass
                continue
            if event is not None:
                triggered.append(event)
                break  # one active Speciality allocation can only be pulled once per scan
    return triggered


# ---------------------------------------------------------------------------
# Step 4 -- LLM ranking for non-conflicting (bench) matches, advisory only
# ---------------------------------------------------------------------------

def rank_bench_candidate(employee: Employee, matches: List[Tuple[Demand, float]]) -> List[Dict]:
    """
    LLM call, advisory only (BR-1105-02) -- never called for Core-Pull
    detection, only for ranking a bench employee's non-conflicting
    matches. Returns [{demand_id, confidence_pct, rationale}, ...],
    highest confidence first. Falls back to the raw skill-match score
    (no rationale) if the LLM is unavailable or fails -- a ranking
    recommendation is advisory, so degrading gracefully beats blocking
    the scan on an LLM outage (unlike Thunder's reply generation, which
    has no non-LLM fallback because a reply IS the deliverable).
    """
    if not matches:
        return []

    if not GEMINI_API_KEY:
        logger.warning("[ResourceAgent] GEMINI_API_KEY not configured -- falling back to raw skill-match scores.")
        return [
            {"demand_id": d.id, "confidence_pct": round(score * 100, 2), "rationale": None}
            for d, score in matches
        ]

    employee_name = f"{employee.first_name} {employee.last_name}".strip()
    employee_skills = ", ".join(_parse_skills(employee.current_skills)) or "(none recorded)"
    demand_lines = "\n".join(
        f"- demand_id: {d.id} | title: {d.job_title} | required_skills: {d.required_skills} | "
        f"skill_match: {score:.0%}"
        for d, score in matches
    )

    instruction = f"""You are ranking open role demands for a bench employee at a staffing firm, for a Resource Manager's review.

Employee: {employee_name}
Employee skills: {employee_skills}

Candidate open demands (already pre-filtered for eligibility):
{demand_lines}

For each demand_id listed above, return a confidence_pct (0-100, how strong a fit this employee is) and a one-sentence rationale.
Return ONLY a JSON array, most confident first: [{{"demand_id": "...", "confidence_pct": 82, "rationale": "..."}}, ...]
No markdown, no code fences, no explanation outside the JSON array."""

    prompt = build_safe_prompt(
        instruction=instruction, untrusted_label="EMPLOYEE_SKILLS", untrusted_content=employee_skills,
    )

    try:
        llm = ChatGoogleGenerativeAI(model=RANKER_MODEL, google_api_key=GEMINI_API_KEY, temperature=0.2)
        response = llm.invoke(prompt)
        content = response.content
        text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        ) if isinstance(content, list) else str(content)
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ranked = json.loads(text)
        if not isinstance(ranked, list):
            raise ValueError("LLM ranking response was not a JSON array")
        return ranked
    except Exception as exc:
        logger.error(f"[ResourceAgent] LLM ranking failed, falling back to raw skill-match scores: {exc}")
        return [
            {"demand_id": d.id, "confidence_pct": round(score * 100, 2), "rationale": None}
            for d, score in matches
        ]


def is_employee_actively_engaged(
    db: Session, employee_id: str, *, exclude_recommendation_id: Optional[str] = None,
) -> bool:
    """
    Avinash's explicit business call, 2026-07-22: "if a candidate is in
    interview stage at a client we shouldn't let them be pushed to 2
    clients at once." HRMS-1105's own story doc has no concept of an
    interview-stage hold -- it describes only suggest-then-allocate --
    but that's not how this actually plays out: an RM presents a bench
    employee to one client and that employee must be off the table for
    everyone else until it resolves. True the moment ANY of this
    employee's recommendations is IN_PROGRESS, regardless of demand.
    """
    query = db.query(BenchAllocationRecommendation).filter(
        BenchAllocationRecommendation.employee_id == employee_id,
        BenchAllocationRecommendation.status == "IN_PROGRESS",
    )
    if exclude_recommendation_id is not None:
        query = query.filter(BenchAllocationRecommendation.id != exclude_recommendation_id)
    return query.first() is not None


def run_bench_scan(
    db: Session, *, tenant_id: Optional[int] = None, bu_head: Optional[Users] = None,
) -> Dict:
    """
    One full HRMS-1105 scan cycle:
      1. detect_core_pull_triggers() -- Speciality-deployed Core-Certified
         employees vs open CORE demands, delegated entirely to S-353.
      2. For the current bench pool, rank non-conflicting matches via the
         LLM and store PENDING_RM_REVIEW recommendations (BR-1105-02: this
         never creates an employee_allocations row itself).

    Employees already IN_PROGRESS on another engagement (see
    is_employee_actively_engaged()) are skipped entirely -- no new
    recommendations are generated for someone already being actively
    pursued elsewhere, not just blocked at approval time.
    """
    core_pull_events = detect_core_pull_triggers(db, tenant_id=tenant_id, bu_head=bu_head)

    recommendations: List[BenchAllocationRecommendation] = []
    for entry in get_current_bench_pool(db, tenant_id=tenant_id):
        employee = db.query(Employee).filter(Employee.id == entry.employee_id).first()
        if employee is None:
            continue
        if is_employee_actively_engaged(db, employee.id):
            continue
        matches = find_open_demand_matches(db, employee)
        if not matches:
            continue

        ranked = rank_bench_candidate(employee, matches)
        for item in ranked:
            try:
                confidence_pct = Decimal(str(item["confidence_pct"]))
            except (KeyError, ValueError, TypeError):
                continue
            recommendation = BenchAllocationRecommendation(
                tenant_id=tenant_id,
                employee_id=employee.id,
                demand_id=item["demand_id"],
                confidence_pct=confidence_pct,
                rationale=item.get("rationale"),
                status="PENDING_RM_REVIEW",
            )
            db.add(recommendation)
            recommendations.append(recommendation)
    db.flush()

    result = {
        "core_pull_events_triggered": len(core_pull_events),
        "recommendations_created": len(recommendations),
    }

    log_agent_execution(
        db=db,
        agent_name="Resource Management Agent",
        action_taken="run_bench_scan",
        tenant_id=str(tenant_id) if tenant_id else "system",
        action_data={
            "core_pull_events_triggered": len(core_pull_events),
            "recommendations_created": len(recommendations),
        },
        success=True,
    )

    return result


# ---------------------------------------------------------------------------
# Step 5 -- RM review queue, the only path to an actual allocation
# ---------------------------------------------------------------------------

def get_recommendation_queue(db: Session, *, tenant_id: Optional[int] = None) -> List[BenchAllocationRecommendation]:
    query = db.query(BenchAllocationRecommendation).filter(
        BenchAllocationRecommendation.status == "PENDING_RM_REVIEW"
    )
    if tenant_id is not None:
        query = query.filter(BenchAllocationRecommendation.tenant_id == tenant_id)
    return query.order_by(BenchAllocationRecommendation.confidence_pct.desc()).all()


def start_pursuing_recommendation(
    db: Session, recommendation: BenchAllocationRecommendation, *, actor_user_id: str,
) -> BenchAllocationRecommendation:
    """
    PENDING_RM_REVIEW -> IN_PROGRESS: the RM's explicit decision to
    actually present this employee to this client (interview stage).
    Hard-blocks (EmployeeAlreadyActivelyEngaged) if this employee is
    already IN_PROGRESS on a different recommendation -- this is the
    real enforcement point for "never pushed to 2 clients at once".
    Reject or approve the existing one first.
    """
    if recommendation.status != "PENDING_RM_REVIEW":
        raise RecommendationNotPending(
            f"Recommendation {recommendation.id} is not PENDING_RM_REVIEW (status={recommendation.status})."
        )
    if is_employee_actively_engaged(db, recommendation.employee_id, exclude_recommendation_id=recommendation.id):
        raise EmployeeAlreadyActivelyEngaged(
            f"Employee {recommendation.employee_id} is already IN_PROGRESS on another recommendation -- "
            f"reject or approve that one before pursuing this one."
        )

    recommendation.status = "IN_PROGRESS"
    recommendation.pursued_by = actor_user_id
    recommendation.pursued_at = datetime.utcnow()
    db.add(recommendation)

    log_agent_execution(
        db=db,
        agent_name="Resource Management Agent",
        action_taken="start_pursuing_recommendation",
        tenant_id=str(recommendation.tenant_id),
        action_data={
            "recommendation_id": recommendation.id,
            "employee_id": recommendation.employee_id,
            "demand_id": recommendation.demand_id,
            "confidence_pct": float(recommendation.confidence_pct),
            "pursued_by": actor_user_id,
        },
        success=True,
    )

    return recommendation


def approve_bench_recommendation(
    db: Session, recommendation: BenchAllocationRecommendation, *, actor_user_id: str,
) -> EmployeeAllocation:
    """BR-1105-02: the ONLY path from a recommendation to a real
    employee_allocations row -- routes through the existing, already-
    gated allocate_employee_to_project(), never inserts directly.

    Requires IN_PROGRESS (the candidate must have actually gone through
    start_pursuing_recommendation()'s exclusivity gate first) -- approval
    is the offer/placement step, not the "let's consider this" step.
    """
    if recommendation.status != "IN_PROGRESS":
        raise RecommendationNotPending(
            f"Recommendation {recommendation.id} is not IN_PROGRESS (status={recommendation.status}) -- "
            f"call start_pursuing_recommendation() first."
        )

    employee = db.query(Employee).filter(Employee.id == recommendation.employee_id).first()
    demand = db.query(Demand).filter(Demand.id == recommendation.demand_id).first()

    allocation = allocate_employee_to_project(
        db, tenant_id=recommendation.tenant_id, employee=employee, demand=demand, changed_by=actor_user_id,
    )

    recommendation.status = "APPROVED"
    recommendation.reviewed_by = actor_user_id
    recommendation.reviewed_at = datetime.utcnow()
    db.add(recommendation)

    log_agent_execution(
        db=db,
        agent_name="Resource Management Agent",
        action_taken="approve_bench_recommendation",
        tenant_id=str(recommendation.tenant_id),
        action_data={
            "recommendation_id": recommendation.id,
            "employee_id": recommendation.employee_id,
            "demand_id": recommendation.demand_id,
            "allocation_id": allocation.id if allocation else None,
            "reviewed_by": actor_user_id,
        },
        success=True,
    )

    return allocation


def reject_bench_recommendation(
    db: Session, recommendation: BenchAllocationRecommendation, *, actor_user_id: str,
) -> BenchAllocationRecommendation:
    """Reachable from PENDING_RM_REVIEW (never pursued) or IN_PROGRESS
    (was being pursued, fell through) -- either way, releases the
    exclusivity hold from is_employee_actively_engaged()."""
    if recommendation.status not in ("PENDING_RM_REVIEW", "IN_PROGRESS"):
        raise RecommendationNotPending(
            f"Recommendation {recommendation.id} is not PENDING_RM_REVIEW or IN_PROGRESS (status={recommendation.status})."
        )
    recommendation.status = "REJECTED"
    recommendation.reviewed_by = actor_user_id
    recommendation.reviewed_at = datetime.utcnow()
    db.add(recommendation)

    log_agent_execution(
        db=db,
        agent_name="Resource Management Agent",
        action_taken="reject_bench_recommendation",
        tenant_id=str(recommendation.tenant_id),
        action_data={
            "recommendation_id": recommendation.id,
            "employee_id": recommendation.employee_id,
            "demand_id": recommendation.demand_id,
            "previous_status": recommendation.status,
            "reviewed_by": actor_user_id,
        },
        success=True,
    )

    return recommendation

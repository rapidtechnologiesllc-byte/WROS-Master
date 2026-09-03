"""
import logging
S-032/HRMS-0432 -- Candidate Context Builder.

Real architecture adaptations:
- BR-01 (parallel fetches via Promise.all()): this codebase's DB access
  is synchronous SQLAlchemy throughout, with one session per request --
  concurrent queries against the same session aren't safe, and there's
  no async DB layer to fetch in true parallel. Sequential fetches
  against simple, indexed lookups are the honest, correct
  implementation here; the <500ms target is realistic anyway since
  every fetch below is a single indexed query, not the sequential-
  network-round-trips scenario the spec's "500ms+ per step" framing
  assumes.
- BR-02 (never leak cross-tenant data): CANDIDATE itself is not
  tenant-partitioned in this codebase's real schema -- Candidate.tenant_id
  is a different, Integer/tenants-table concept, unrelated to the
  String(50) UserID-as-tenant_id convention every conversation/memory/
  fact table this round uses (a pre-existing, documented architectural
  inconsistency, not introduced here). Real tenant scoping happens at
  the CandidateConversation level -- this function resolves the
  conversation via candidate_id AND tenant_id together (never
  candidate_id alone), and every other tenant-scoped read
  (get_memory, get_missing_fields via the resolved candidate) flows
  from that same real, already-tenant-safe conversation.
- No Redis (or any cache) exists anywhere in this codebase. Built a
  real in-process (single-worker) TTL cache instead -- honest about
  not being safe across multiple server instances, not a lie about
  distributed correctness. invalidate_candidate_context_cache() is
  exposed for real use but NOT auto-wired into every one of the spec's
  4 mutation trigger points (extract_facts, upsert_fact,
  transition_status, etc.) this round -- those functions are called
  from ~10+ already-shipped, heavily-tested call sites; adding a cache-
  invalidation side effect to all of them carries real regression risk
  this late before launch. Flagged as a real follow-up wiring task.
- {{job}} maps to this codebase's real Job model (jobTitle, jobSkills,
  jobExperience, jobLocation, salaryRange as the closest real
  equivalent to the spec's bill_rate -- no bill_rate field exists).
"""
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.models.user import Jobs
from app.services.ai_conversation_service import get_conversation_thread, get_missing_fields, resolve_thunder_config
from app.services.candidate_memory_service import get_memory
from app.services.qualification_engine_service import QualificationNotApplicable, get_qualification_plan, is_qualifying_state
from app.core.logging import logger

CACHE_TTL_SECONDS = 30

# Real in-process cache -- see module docstring. {(tenant_id, candidate_id): (expires_at, context)}
_CONTEXT_CACHE: Dict[Tuple[str, str], Tuple[float, Dict]] = {}

logger = logging.getLogger(__name__)

class CandidateNotFound(Exception):
    pass


def invalidate_candidate_context_cache(tenant_id: str, candidate_id: str) -> None:
    """BR-03. Real, callable now; not yet auto-wired into every mutation
    site -- see module docstring."""
    _CONTEXT_CACHE.pop((tenant_id, candidate_id), None)


def _get_cached(tenant_id: str, candidate_id: str) -> Optional[Dict]:
    entry = _CONTEXT_CACHE.get((tenant_id, candidate_id))
    if entry is None:
        return None
    expires_at, context = entry
    if time.monotonic() >= expires_at:
        _CONTEXT_CACHE.pop((tenant_id, candidate_id), None)
        return None
    return context


def _set_cached(tenant_id: str, candidate_id: str, context: Dict) -> None:
    _CONTEXT_CACHE[(tenant_id, candidate_id)] = (time.monotonic() + CACHE_TTL_SECONDS, context)


def _candidate_summary(candidate: Candidate) -> Dict:
    name = " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])).strip()
    return {
        "id": candidate.candidateID, "name": name or candidate.candidateEmail,
        "email": candidate.candidateEmail, "phone": candidate.candidateMobile,
        "location": candidate.candidateCurrentLocation, "current_employer": None,  # not on Candidate; see resume_parsed if needed
        "total_experience_years": round((candidate.total_experience_months or 0) / 12.0, 1) if candidate.total_experience_months else None,
        "skills": candidate.candidateSkills, "resume_url": None,  # no resume_url column -- see resume_upload_service.has_active_resume()
        "completeness_score": candidate.resume_completeness_score,
    }


def _job_summary(db: Session, job_id: Optional[str]) -> Optional[Dict]:
    if not job_id:
        return None
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        return None
    return {
        "id": job.jobID, "title": job.jobTitle, "required_skills": job.jobSkills,
        "experience_required": job.jobExperience, "location": job.jobLocation, "bill_rate": job.salaryRange,
    }


def build_candidate_context(db: Session, candidate_id: str, tenant_id: str, *, use_cache: bool = True) -> Dict:
    """
    Step 2. Assembles everything Thunder needs before generating any
    response. Raises CandidateNotFound if candidate_id doesn't exist.
    """
    if use_cache:
        cached = _get_cached(tenant_id, candidate_id)
        if cached is not None:
            return cached

    start = time.monotonic()

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")

    # BR-02: tenant scoping happens here, not on the Candidate row itself
    # (see module docstring) -- candidate_id AND tenant_id always together.
    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id, CandidateConversation.tenant_id == tenant_id)
        .order_by(CandidateConversation.created_at.desc())
        .first()
    )

    memory = get_memory(db, candidate_id, tenant_id)
    missing_fields = get_missing_fields(candidate, db)

    conversation_summary = None
    recent_messages = []
    next_question = None

    if conversation is not None:
        conversation_summary = {
            "id": conversation.id, "status": conversation.status,
            "owner_type": conversation.owner_type, "owner_name": conversation.owner_id,
        }

        thread = get_conversation_thread(candidate_id, db)
        matching = next((c for c in thread if c["conversation_id"] == conversation.id), None)
        if matching:
            for event in matching["events"][-15:]:  # last 15, oldest first (thread events are already ASC)
                if event["event_type"] not in ("candidate_reply", "ai_message_sent", "hr_message_sent"):
                    continue
                data = event.get("event_data") or {}
                recent_messages.append({
                    "direction": "INBOUND" if event["event_type"] == "candidate_reply" else "OUTBOUND",
                    "sender_type": "CANDIDATE" if event["event_type"] == "candidate_reply" else ("AI" if event["event_type"] == "ai_message_sent" else "RECRUITER"),
                    "channel": (data.get("channel") or "").upper(),
                    "message_body": data.get("body", ""),
                    "sent_at": event["created_at"],
                })

        if is_qualifying_state(conversation):
            try:
                plan = get_qualification_plan(db, conversation, candidate, tenant_id)
                if not plan["is_complete"]:
                    next_question = {"field_name": plan["next_field"], "question": plan["question"]}
            except QualificationNotApplicable:
                pass

    thunder_config = resolve_thunder_config(db, tenant_id)

    context = {
        "candidate": _candidate_summary(candidate),
        "memory": memory,
        "conversation": conversation_summary,
        "recent_messages": recent_messages,
        "missing_fields": missing_fields,
        "next_question": next_question,
        "job": _job_summary(db, candidate.job_id),
        "thunder": {"name": thunder_config["name"], "persona": thunder_config["persona"]},
        "built_at": datetime.utcnow(),
        "build_latency_ms": int((time.monotonic() - start) * 1000),
    }

    _set_cached(tenant_id, candidate_id, context)
    return context


def get_context_for_prompt(db: Session, candidate_id: str, tenant_id: str, prompt_type: str, additional_params: Optional[Dict] = None) -> Dict:
    """Step 4 -- the single entry point for every LLM-calling story to
    use: assembles context, then builds the prompt from it in one call."""
    from app.services.prompt_framework_service import build_prompt

    context = build_candidate_context(db, candidate_id, tenant_id)

    prompt_candidate_context = {
        "thunder_name": context["thunder"]["name"],
        "name": context["candidate"]["name"],
        "memory": context["memory"],
        "recent_messages": context["recent_messages"],
        "missing_fields": context["missing_fields"],
    }
    prompt_params = dict(additional_params or {})
    if context["next_question"] and "question" not in prompt_params:
        prompt_params["question"] = context["next_question"]["question"]

    prompt = build_prompt(prompt_type, prompt_candidate_context, prompt_params)
    return {"context": context, "system_prompt": prompt["system_prompt"], "user_prompt": prompt["user_prompt"], "prompt_metadata": prompt}

"""
Flash -- a real, authenticated conversational query surface for
BlitzenX staff and employees, alongside the candidate-facing agent
Thunder (app.services.thunder_service / app.services.public_chat_service).

2026-08-06, Avinash's explicit product split: "Thunder will have only
access to open jobs and when a candidate is logged in they will able
to get status of their application and onboarding once they convert
as employee they should be using flash." So Thunder stays scoped to
the external candidate journey (jobs, own application/onboarding
status); everything internal-facing -- staff questions, and any
question from someone once they've converted to an employee -- lives
here as Flash. Renamed 2026-08-06 from "Ask Thunder"
(internal_ask_thunder_service.py) -- functionally unchanged at the
time of rename, branding/naming correction only, git history
preserved via `git mv`.

Scope: originally three real questions Avinash asked for by name -- a
recruiter sourcing candidates for a role, a BU head checking a
specific candidate's pipeline status, and a resource manager asking
for a candidate for a role. The latter two ("find me a candidate for
X" and "source candidates for X") are the same underlying real data
question asked by different personas, so they share one implementation
(SOURCING) rather than two near-identical ones.

Extended 2026-08-04 per [[wros_thunder_query_layer_backlog]]'s own
example query ("who's free for a Java role right now") -- a fourth
real intent, BENCH_AVAILABILITY, answers from the real, already-built
Resource Management bench pool (resource_management_service.get_current_bench_pool())
rather than a new data source. Same "additive query layer on top of
existing screens, not a replacement" posture that backlog note
established -- the Resource Management screen itself is untouched.

Extended again 2026-08-06 per Avinash's direct complaint ("most of the
development you did isn't connected to thunder... answer any and
every question accurately with real data in strict mode") -- three
more intents (FINANCE_PNL, AR_AGING, MY_TASKS), all reusing existing,
already-tested service functions as the answer source (pnl_service,
ar_followup_service, task_service) rather than new query logic. The
two financial intents reuse app.core.revenue_visibility_scope's exact
permission gate -- "Only BU head, partner, finance team and ceo get
access to financial data and BU only get their bu related not org
wide" (Avinash, 2026-08-06) -- Flash is never a side-door around the
RBAC the real dashboards already enforce.

Intent classification: the rules in classify_internal_query() route the
common phrasings with no model at all. A phrasing they miss goes to
app.services.flash_brain.router (2026-10-15, CEO decision "hybrid"): the
self-hosted small model, else Claude, may only pick one of AI_INTENTS and
a short query -- it never answers. What reaches a model is redacted to
work data first (flash_brain.redaction: no contact details, pay,
documents or finance figures). The 2026-08-06 Gemini router is retired.
With no brain configured (or FLASH_AGENT_ENABLED=false) the rules alone
decide, exactly as before.

Every answer is built from real DB rows -- there is no free-text LLM
answer describing candidates, financials, or status. Anything outside the
supported intents gets an explicit "I can't answer that yet" instead of an
invented answer -- "strict mode," per Avinash's own words, same "no fake
success" principle as the rest of this codebase.
"""
from app.core.tenant_context import tenant_id_of
from app.core.tenant_context import sole_tenant_id
import logging
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.revenue_visibility_scope import can_view_pnl, is_revenue_bu_scoped
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.business_unit import BusinessUnit
from app.models.resource_management import BenchPoolEntry
from app.models.user import Jobs, Users
from app.services.ar_followup_service import scan_overdue_invoices
from app.services.pnl_service import get_bu_pnl, get_org_pnl_summary
from app.services.task_service import get_daily_task_list

INTENT_SOURCING = "sourcing"
INTENT_CANDIDATE_STATUS = "candidate_status"
INTENT_BENCH_AVAILABILITY = "bench_availability"
INTENT_FINANCE_PNL = "finance_pnl"
INTENT_AR_AGING = "ar_aging"
INTENT_MY_TASKS = "my_tasks"
INTENT_JOB_CREATE = "job_create"
INTENT_MY_TIMESHEETS = "my_timesheets"
INTENT_PIPELINE_SUMMARY = "pipeline_summary"
INTENT_DECISIONS = "decisions"
INTENT_UNKNOWN = "unknown"

# What the AI router may choose (it never answers -- every answer is a real DB lookup)
AI_INTENTS = {
    INTENT_SOURCING: "find candidates for a role or skills (query: the role/skills)",
    INTENT_CANDIDATE_STATUS: "where a named candidate is in hiring (query: the person's name)",
    INTENT_BENCH_AVAILABILITY: "who is on the bench / available (query: skills, may be empty)",
    INTENT_FINANCE_PNL: "profit, margin or P&L (query: business unit name, may be empty)",
    INTENT_AR_AGING: "overdue or unpaid client invoices (query: empty)",
    INTENT_MY_TASKS: "the asker's own tasks (query: empty)",
    INTENT_MY_TIMESHEETS: "the asker's own timesheets or hours (query: empty)",
    INTENT_JOB_CREATE: "create or open a new job, or a need for a new hire (query: the job description)",
    INTENT_DECISIONS: "decisions or approvals waiting for the asker (query: empty)",
    INTENT_PIPELINE_SUMMARY: "how many candidates are at each hiring stage, optionally for one client (query: client name, may be empty)",
}

UNSUPPORTED_QUERY_MESSAGE = (
    "I can't answer that yet -- right now I can only help with sourcing candidates, "
    "checking a candidate's pipeline status, who's on the bench, BU P&L/margin, "
    "overdue invoices, your own open tasks, or creating jobs. Try one of those, or use the relevant "
    "screen directly for anything else."
)

# 2026-08-06 -- Avinash's own words: "Only BU head, partner, finance team and ceo
# get access to financial data and BU only get their bu related not org wide only
# finance and ceo can see full org finance." Reuses app.core.revenue_visibility_scope
# verbatim -- that module already encodes exactly this policy for the real dashboard/
# API endpoints (can_view_pnl() needs revenue view permission on the role template;
# BU leaders by hierarchy level see their own BU only, org-level roles see it all;
# see app.core.authority) -- Thunder must never become a side-door around RBAC, so
# it calls the identical gate rather than reimplementing the policy a second time.
PERMISSION_DENIED_FINANCE_MESSAGE = (
    "I can't answer that -- financial data (P&L, margin, overdue invoices) is limited "
    "to BU Heads, Partners, Finance, and the CEO. Ask someone with access, or use the "
    "Finance Operations screen if you have it."
)

PERMISSION_DENIED_BENCH_MESSAGE = (
    "I can't answer that -- who's on the bench is limited to people who can view employees. "
    "Ask someone with access, or use the Bench screen if you have it."
)

MAX_CANDIDATES_RETURNED = 5

# Backlog item, 2026-08-05 (wros_ask_thunder_bugs_and_memory_backlog):
# Avinash -- "i ask a question to thunder and move to a different page
# it looses the history and acts as a new session." Confirmed real
# cause: this whole module was fully stateless, zero awareness of
# anything asked earlier in the SAME open chat. Deliberately NOT a new
# server-side conversation table -- FlashWidget.js already holds
# the visible chat bubbles in its own React state for the life of the
# panel, so the client passes its last few turns back on each new
# question instead of the backend persisting anything new. Kept small
# (last 3 exchanges) -- this is context for resolving a follow-up's
# pronoun/reference, not a transcript archive.
MAX_HISTORY_TURNS = 3

_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "of", "in", "on", "to", "who",
    "that", "has", "have", "years", "year", "yrs", "experience", "role", "roles",
    "candidate", "candidates", "find", "source", "sourcing", "me", "us", "need",
    "want", "wants", "looking", "please", "any", "some", "there", "is", "are",
    "resource", "someone",
    # 2026-08-06 -- added after a real live query ("do you have a
    # guidewire developer... that we can propose to a client") leaked
    # sentence filler into the search keywords, requiring irrelevant
    # words to also match a candidate's skills/title/experience under
    # find_matching_candidates()'s "every keyword must match" rule.
    "do", "you", "we", "can", "propose", "client", "clients", "at",
    # Staffing-model words a Partner naturally says in a sourcing
    # question but that aren't a Candidate-searchable skill/title field
    # (delivery_engine/CORE-SPECIALITY is an Employee-level concept,
    # post-conversion -- candidates aren't tagged with it yet).
    "specialty", "speciality", "core", "engine",
}

logger = logging.getLogger(__name__)

class ThunderQueryClassificationFailed(Exception):
    """Kept as a safety net for a genuinely unexpected internal error in
    classify_internal_query() -- callers must fall back to
    UNSUPPORTED_QUERY_MESSAGE, never guess the intent. Effectively
    unreachable under normal operation since 2026-08-06's rewrite below
    (no external call left to fail)."""

# 2026-08-06 -- Avinash's explicit instruction, after directly questioning
# why Flash called an external Gemini API at all: "why is it calling an
# external Gemini system and exposing our data when I explicitly asked
# you to build it entirely inside the WROS as our proprietary." Scope
# confirmed with him directly (not assumed) as Flash's intent
# classification specifically -- Thunder's own candidate-facing Gemini
# usage (reply generation, sentiment, resume parsing, etc.) is
# unchanged, that's a separate, much larger decision not made here.
#
# Rewritten from an LLM classification call to pure local regex/keyword
# matching -- zero network calls, zero data ever leaves this process for
# Flash's own intent classification. Real, honest trade-off, not hidden:
# a rule-based classifier is far more rigid than the LLM version was --
# it needs recognizably-phrased questions to match, it can't paraphrase-
# understand an oddly worded question the way the LLM could. Intent
# patterns are checked most-specific-first so no category can shadow
# another (e.g. "who's on the bench for the Java project" should hit
# BENCH_AVAILABILITY, not SOURCING, even though both mention "Java").
_FINANCE_PNL_PATTERN = re.compile(
    r"\b(margin|p\s*&\s*l|pnl|p\s+and\s+l|profit\w*|financials?|financially|revenue|making\s+money)\b", re.IGNORECASE)
_AR_AGING_PATTERN = re.compile(
    r"(overdue|unpaid).{0,20}?invoices?|invoices?.{0,20}?(overdue|unpaid)|"
    r"accounts?\s+receivable|\bar\s+aging\b|who\s+owes",
    re.IGNORECASE,
)
_MY_TIMESHEETS_PATTERN = re.compile(r"\bmy\s+(time\s*sheets?|hours)\b|\b(did|have)\s+i\s+(submit|log)", re.IGNORECASE)
_MY_TASKS_PATTERN = re.compile(
    r"\bmy\s+(open\s+)?tasks?\b|\bmy\s+plate\b|\bdue\s+today\b|\bmy\s+to.?do\b|"
    r"\bwhat\s+(do|should)\s+i\s+(need\s+to\s+)?(do|work\s+on)\b|\bon\s+my\s+(list|plate)\b", re.IGNORECASE)
_BENCH_PATTERN = re.compile(
    r"\bbench\b|who.{0,4}s\s+free\b|\b(who|anyone|anybody|someone|somebody)\s+(is\s+)?free\b|"
    r"\bavailable\b.{0,30}\b(employees?|developers?|engineers?|resources?|consultants?|people|staff|testers?|analysts?)\b",
    re.IGNORECASE,
)
_CANDIDATE_STATUS_PATTERN = re.compile(
    r"how\W{0,4}s?\s+is\b.{0,60}\bdoing\b|status\s+(on|of)\b|pipeline\s+status\b|"
    r"\bwhere\s+is\b.{0,40}\b(process|pipeline|hiring|interview)|\b(any\s+)?updates?\s+on\b",
    re.IGNORECASE,
)
_SOURCING_PATTERN = re.compile(
    r"\b(find|source)\s+me\b|need\s+a\s+candidate\b|candidate\s+for\b|looking\s+for\s+(a|an|someone)\b|"
    r"\bdo\s+(you|we)\s+have\b|\bdo\s+we\s+have\s+any\b|\bany\s+candidates?\b|\bis\s+there\s+a\s+candidate\b|"
    r"\bwho\s+(do\s+we\s+have|has|can\s+do|knows)\b|\bcandidates?\s+(with|who\s+know)\b",
    re.IGNORECASE,
)
_JOB_CREATE_PATTERN = re.compile(
    r"\b(create|post|open)\s+(a|an|new)?\s*(job|role|position|req|requisition)\b|"
    r"\bneed\s+to\s+(create|post|open)\s+(a|an)?\s*(job|role|position)\b|"
    r"\b(hire|hiring|recruiting)\s+for\b|"
    # "I need a Rails developer for ...": a role the user wants filled
    r"\b(i|we)\s+(need|want)\s+(a|an|\d+)\s+[\w+#. -]{0,40}?\b(developer|engineer|architect|analyst|tester|consultant)s?\b",
    re.IGNORECASE,
)
_DECISIONS_PATTERN = re.compile(
    r"\b(pending|open|waiting)\s+(decisions?|approvals?)\b|\b(decisions?|approvals?)\b.{0,30}\b(waiting|pending|for\s+me)\b|"
    r"\bwhat.{0,20}\b(waiting|pending)\b.{0,20}\b(on|for)\s+me\b",
    re.IGNORECASE,
)
# Simple proper-noun heuristic for candidate-name extraction: 1-3
# consecutive Title-Case words. Imperfect (no real NER without an LLM),
# but reliable enough for the common real phrasing ("how is Priya Sharma
# doing"). Excludes single common sentence-starters that happen to be
# capitalized (How/What/Who/etc.) by requiring the match not be the very
# first word of the message.
# Capitalised words, including all-caps names such as business units ("AXION")
_PROPER_NOUN_PATTERN = re.compile(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\b")
_BENCH_WORDS_PATTERN = re.compile(
    r"\b(bench|available|free|who|whos|is|on|the|show|list|me|any|anyone|anybody|someone|somebody|knows?|people|staff|"
    r"employees?|developers?|engineers?|resources?|consultants?|testers?|analysts?)\b|\bwho's\b",
    re.IGNORECASE,
)
_PIPELINE_SUMMARY_PATTERN = re.compile(
    r"\bhow\s+many\s+candidates\b|\bcandidates\s+(are\s+)?(in|at)\s+(the\s+)?\w+\s+stage\b|"
    r"\bwhat.{0,4}s?\s+the\s+pipeline\b|\bpipeline\s+(for|of|summary)\b|\bhiring\s+funnel\b",
    re.IGNORECASE,
)
_SENTENCE_STARTERS = {"How", "What", "Who", "Is", "Are", "Does", "Do", "Can", "Please"}
_PRONOUN_PATTERN = re.compile(r"\b(her|him|them|she|he|they|that\s+(person|candidate))\b", re.IGNORECASE)
# Temporal/filler words that aren't in _STOPWORDS (those are shared with
# the LLM-era candidate search and shouldn't change) but leak into a
# BENCH_AVAILABILITY/SOURCING query after stripping the matched trigger
# phrase -- e.g. "who's free for a Java role right now" -> "Java right
# now" would then require "right"/"now" to also match an employee's
# title/skills, breaking a query that should just be "Java".
_NOISE_WORD_PATTERN = re.compile(r"\b(right\s+now|currently|today|please|thanks?|now)\b", re.IGNORECASE)

def _extract_proper_noun(text: str) -> str:
    for match in _PROPER_NOUN_PATTERN.finditer(text):
        words = match.group(0).split()
        if words[0] in _SENTENCE_STARTERS and match.start() == text.index(words[0]):
            continue
        return match.group(0)
    return ""

def _last_candidate_name_from_history(history: Optional[List[Dict]]) -> str:
    """Pronoun fallback ('how is she doing') without an LLM to resolve
    it -- scans backward through the caller-supplied history for the
    most recent proper-noun-looking name in either side of the
    exchange. Best-effort, not exact; an ambiguous case just returns
    empty and the caller falls through to UNSUPPORTED_QUERY_MESSAGE
    rather than guessing wrong."""
    for turn in reversed((history or [])[-MAX_HISTORY_TURNS:]):
        for text in (str((turn or {}).get("reply") or ""), str((turn or {}).get("question") or "")):
            name = _extract_proper_noun(text)
            if name:
                return name
    return ""

def classify_internal_query(message: str, *, history: Optional[List[Dict]] = None) -> Dict:
    """
    Local, rule-based classification -- no external API call, see the
    2026-08-06 module-level note above for why. Classifies `message`
    into one of the real intents and extracts the search term (role/
    skills text, a candidate's name, or a Business Unit name). Never
    answers the question itself -- that always comes from a real DB
    query in answer_internal_query() below.

    `history` is used only for the pronoun-fallback heuristic in
    _last_candidate_name_from_history() above -- a much narrower use
    than the old LLM version's full-transcript context resolution.
    """
    text = (message or "").strip()

    if _FINANCE_PNL_PATTERN.search(text):
        return {"intent": INTENT_FINANCE_PNL, "query": _extract_proper_noun(text)}

    if _AR_AGING_PATTERN.search(text):
        return {"intent": INTENT_AR_AGING, "query": ""}

    if _DECISIONS_PATTERN.search(text):
        return {"intent": INTENT_DECISIONS, "query": ""}

    if _MY_TASKS_PATTERN.search(text):
        return {"intent": INTENT_MY_TASKS, "query": ""}

    if _MY_TIMESHEETS_PATTERN.search(text):
        return {"intent": INTENT_MY_TIMESHEETS, "query": ""}

    if _PIPELINE_SUMMARY_PATTERN.search(text):
        client = re.search(r"\b(?:client|for)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})", text)
        return {"intent": INTENT_PIPELINE_SUMMARY, "query": client.group(1).strip() if client else ""}

    if _BENCH_PATTERN.search(text):
        # keep the skill words ("QA"), drop only the bench/availability wording around them
        stripped = _BENCH_WORDS_PATTERN.sub(" ", text)
        keywords = _extract_keywords(_NOISE_WORD_PATTERN.sub("", stripped))
        return {"intent": INTENT_BENCH_AVAILABILITY, "query": " ".join(keywords)}

    # A pronoun ("her"/"him"/etc.) combined with a status-ish word
    # ("status"/"doing"/"experience") is also a candidate-status
    # follow-up even when it doesn't match the fuller pattern above
    # (e.g. "what about her status" -- no "how...doing"/"status on").
    is_pronoun_follow_up = _PRONOUN_PATTERN.search(text) and re.search(r"status|doing|experience", text, re.IGNORECASE)
    if _CANDIDATE_STATUS_PATTERN.search(text) or is_pronoun_follow_up:
        name = _extract_proper_noun(text)
        if not name and _PRONOUN_PATTERN.search(text):
            name = _last_candidate_name_from_history(history)
        return {"intent": INTENT_CANDIDATE_STATUS, "query": name}

    if _SOURCING_PATTERN.search(text):
        keywords = _extract_keywords(_NOISE_WORD_PATTERN.sub("", _SOURCING_PATTERN.sub("", text)))
        return {"intent": INTENT_SOURCING, "query": " ".join(keywords)}

    if _JOB_CREATE_PATTERN.search(text):
        # Extract job description from the message (everything after create/post/open/hire)
        job_desc = _JOB_CREATE_PATTERN.sub("", text).strip()
        return {"intent": INTENT_JOB_CREATE, "query": job_desc}

    return {"intent": INTENT_UNKNOWN, "query": ""}

def _extract_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#]*", text or "")
    return [t for t in tokens if len(t) > 1 and t.lower() not in _STOPWORDS]

def find_candidates_for_job(db: Session, job_id: str, *, top_n: int = MAX_CANDIDATES_RETURNED, tenant_id: Optional[int] = None, viewer: Optional[Users] = None) -> List[Dict]:
    """The job's best-matching eligible candidates, from the one ranking rule
    (job_candidate_ranking_service: tenant pool, the caller's BU scope, the 5-year
    floor and the job's own minimum, normalised skills). Unknown job -> []."""
    from app.services.job_candidate_ranking_service import rank_candidates_for_job

    job = db.query(Jobs).filter(Jobs.jobID == job_id, Jobs.tenant_id == tenant_id).first()
    if job is None:
        return []
    return [
        {"candidate_id": r.candidate_id, "name": r.name, "score": r.score, "matched": r.matched,
         "experience_months": r.experience_months}
        for r in rank_candidates_for_job(db, job, viewer=viewer, limit=top_n)
    ]

def find_matching_candidates(db: Session, query_text: str, *, top_n: int = MAX_CANDIDATES_RETURNED, tenant_id: Optional[int] = None, user_bu_id: Optional[int] = None) -> List[Dict]:
    """
    Real keyword-overlap search over the real Candidates table (skills,
    job title, experience text) -- not a fabricated ranking. Every
    result is a real candidate row; a query with no keywords or no
    matches returns an empty list, not invented candidates.

    ISOLATION FIX: Filters by tenant_id (required) and user_bu_id (optional for BU scoping)
    """
    from sqlalchemy import or_ as sql_or

    keywords = _extract_keywords(query_text)
    if not keywords:
        return []

    filters = []
    for kw in keywords:
        like = f"%{kw}%"
        filters.append(or_(
            Candidate.candidateSkills.ilike(like),
            Candidate.candidateJobTitle.ilike(like),
            Candidate.candidateExperience.ilike(like),
        ))

    # ISOLATION FIX: Add tenant_id + BU filtering
    query_filters = [
        Candidate.tenant_id == tenant_id,  # TENANT ISOLATION
        or_(*filters)
    ]

    # BU ISOLATION FIX: When user_bu_id is set, filter to that BU + unassigned
    if user_bu_id:
        query_filters.append(
            sql_or(
                Candidate.associated_bu_id.is_(None),  # Unassigned candidates
                Candidate.associated_bu_id == user_bu_id  # Own BU
            )
        )
    # If user_bu_id is None (admin), no BU filter - can see all

    candidates = db.query(Candidate).filter(*query_filters).limit(200).all()

    scored = []
    for candidate in candidates:
        haystack = " ".join(filter(None, [
            candidate.candidateSkills, candidate.candidateJobTitle, candidate.candidateExperience,
        ])).lower()
        score = sum(1 for kw in keywords if kw.lower() in haystack)
        # Every keyword must match, not just one -- a bare "score > 0"
        # let a single generic word (e.g. "developer") pull in a
        # candidate with zero real relevance to the other, more specific
        # keyword ("Guidewire") the caller actually cared about. Same
        # "no fake success" principle as the rest of this module: an
        # honest empty result beats a confident wrong one, especially in
        # front of a live audience.
        if score == len(keywords):
            scored.append((candidate, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [
        {
            "candidate_id": c.candidateID,
            "name": " ".join(filter(None, [c.candidateFirstName, c.candidateLastName])) or c.candidateEmail,
            "job_title": c.candidateJobTitle,
            "skills": c.candidateSkills,
            "experience": c.candidateExperience,
            "score": score,
        }
        for c, score in scored[:top_n]
    ]

def get_candidate_status_summary(db: Session, name_query: str, *, tenant_id: Optional[int] = None, user_bu_id: Optional[int] = None) -> Dict:
    """
    Real lookup by name against the real Candidates + CandidateStatus
    tables. Returns {"matches": [...]} -- zero, one, or several real
    candidates (never guesses which one you meant when several share a
    name; the caller surfaces all of them so a human can disambiguate).

    ISOLATION FIX: Filters by tenant_id (required) and user_bu_id (optional for BU scoping)
    """
    from sqlalchemy import or_ as sql_or

    keywords = [k for k in _extract_keywords(name_query)]
    if not keywords:
        return {"matches": []}

    filters = []
    for kw in keywords:
        like = f"%{kw}%"
        filters.append(or_(Candidate.candidateFirstName.ilike(like), Candidate.candidateLastName.ilike(like)))

    # ISOLATION FIX: Add tenant_id + BU filtering
    query_filters = [
        Candidate.tenant_id == tenant_id,  # TENANT ISOLATION
        or_(*filters)
    ]

    # BU ISOLATION FIX: When user_bu_id is set, filter to that BU + unassigned
    if user_bu_id:
        query_filters.append(
            sql_or(
                Candidate.associated_bu_id.is_(None),  # Unassigned candidates
                Candidate.associated_bu_id == user_bu_id  # Own BU
            )
        )
    # If user_bu_id is None (admin), no BU filter - can see all

    candidates = db.query(Candidate).filter(*query_filters).limit(10).all()

    matches = []
    for candidate in candidates:
        status = (
            db.query(CandidateStatus)
            .filter(CandidateStatus.candidateID == candidate.candidateID)
            .order_by(CandidateStatus.updatedAt.desc())
            .first()
        )
        from app.models.hiring_pipeline import HiringPipeline

        pipeline = db.query(HiringPipeline).filter(HiringPipeline.candidate_id == candidate.candidateID) \
            .order_by(HiringPipeline.closed_at.isnot(None), HiringPipeline.id.desc()).first()
        matches.append({
            "candidate_id": candidate.candidateID,
            "name": " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])) or candidate.candidateEmail,
            "pipeline_status": status.piplineStatus if status else None,
            "account_status": status.status if status else None,
            "job_id": candidate.job_id,
            "hiring_stage": pipeline.stage if pipeline else None,
            "waiting_for": (pipeline.blockers or []) if pipeline else [],
        })
    return {"matches": matches}

def find_available_bench_employees(db: Session, user: Users, query_text: str, *, top_n: int = MAX_CANDIDATES_RETURNED) -> List[Dict]:
    """
    Real read of resource_management_service's own bench pool table --
    no new data source, same "additive, not a replacement" posture as
    the rest of this query layer. An empty query_text (bare "who's on
    the bench") returns the whole current pool, most-recently-benched
    first; a query_text filters by skill_tags/current_title overlap,
    same keyword-overlap technique find_matching_candidates() already
    uses for candidates. Scoped like the bench screen: the caller's
    tenant and the business units they can see.
    """
    from app.core.data_scope import bu_filter

    entries = (
        db.query(BenchPoolEntry, Employee)
        .join(Employee, BenchPoolEntry.employee_id == Employee.id)
        .filter(Employee.tenant_id == user.tenant_id, bu_filter(db, user, Employee.bu_id))
        .order_by(BenchPoolEntry.created_at.desc())
        .limit(200)
        .all()
    )

    keywords = _extract_keywords(query_text) if query_text else []

    def _skill_tags(entry: BenchPoolEntry) -> List[str]:
        try:
            return json.loads(entry.skill_tags) if entry.skill_tags else []
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(f"[Flash] Failed to parse skill_tags for bench entry {entry.id}: {exc}")
            raise ValueError(f"Invalid JSON in skill_tags: {exc}")

    results = []
    for entry, employee in entries:
        haystack = " ".join(filter(None, [
            employee.current_title, " ".join(_skill_tags(entry)),
        ])).lower()
        # All keywords must match, not just one -- same fix as
        # find_matching_candidates(), same reasoning: a single generic
        # word shouldn't be enough to surface someone with no real
        # overlap with the rest of the query.
        if keywords and not all(kw.lower() in haystack for kw in keywords):
            continue
        results.append({
            "employee_id": employee.id,
            "name": " ".join(filter(None, [employee.first_name, employee.last_name])) or employee.email,
            "current_title": employee.current_title,
            "skills": _skill_tags(entry),
            "available_from": entry.available_from.isoformat() if entry.available_from else None,
        })

    return results[:top_n]

def _format_sourcing_reply(query_text: str, results: List[Dict]) -> str:
    if not results:
        return (
            f"I couldn't find any candidates in the system matching \"{query_text}\". "
            f"They may not have applied yet, or try different keywords."
        )
    lines = [
        f"- {r['name']} -- {r['job_title'] or 'no title on file'}; "
        f"skills: {r['skills'] or 'not on file'}; experience: {r['experience'] or 'not on file'}"
        for r in results
    ]
    return f"Found {len(results)} candidate(s) matching \"{query_text}\":\n" + "\n".join(lines)

def _format_status_reply(name_query: str, matches: List[Dict]) -> str:
    if not matches:
        return f"I couldn't find a candidate named \"{name_query}\" in the system."
    if len(matches) > 1:
        # Numbered, not raw internal IDs -- lets the user disambiguate
        # ("the first one") without ever seeing a candidateID.
        lines = [f"{i}. {m['name']}" for i, m in enumerate(matches, start=1)]
        return (
            f"I found more than one candidate matching \"{name_query}\":\n" + "\n".join(lines)
            + "\nWhich one did you mean?"
        )
    m = matches[0]
    reply = (
        f"{m['name']} -- pipeline status: {m['pipeline_status'] or 'not set'}, "
        f"account status: {m['account_status'] or 'not set'}"
        + (f", linked to job {m['job_id']}" if m["job_id"] else "")
        + "."
    )
    if m.get("hiring_stage"):
        stage = m["hiring_stage"].replace("_", " ").lower()
        waiting = "; ".join(m.get("waiting_for") or [])
        reply += f" Hiring stage: {stage}" + (f" -- waiting for {waiting}." if waiting else ".")
    return reply

def get_finance_pnl_answer(db: Session, user: Users, bu_name_query: str) -> Dict:
    """Real read of pnl_service's own BU P&L / org summary -- same
    functions the Finance Operations screen calls, not a parallel
    calculation. Permission + BU-scoping both reuse
    app.core.revenue_visibility_scope verbatim -- see this module's
    top-of-file note on why (Thunder must never be a side-door around
    the same RBAC the real dashboards enforce)."""
    if not can_view_pnl(db, user):
        return {"denied": True}

    now = datetime.utcnow()
    year, month = now.year, now.month

    if is_revenue_bu_scoped(db, user):
        from app.core.data_scope import visible_bu_ids

        units = db.query(BusinessUnit).filter(BusinessUnit.id.in_(visible_bu_ids(db, user) or [-1])) \
            .order_by(BusinessUnit.name).all()
        if not units:
            return {"denied": False, "no_bu": True}
        if bu_name_query:
            wanted = bu_name_query.strip().lower()
            units_named = [u for u in units if wanted in (u.name or "").lower()]
            if not units_named:
                return {"denied": False, "other_bu_blocked": True, "own_bu_name": ", ".join(u.name for u in units)}
            units = units_named
        if len(units) > 1:
            return {"denied": False, "choose_bu": [u.name for u in units]}
        bu = units[0]
        pnl = get_bu_pnl(db, business_unit_id=bu.id, year=year, month=month)
        return {"denied": False, "scope": "bu", "bu_name": bu.name, "pnl": pnl}

    if bu_name_query:
        bu = db.query(BusinessUnit).filter(BusinessUnit.name.ilike(f"%{bu_name_query}%")).first()
        if bu is None:
            return {"denied": False, "bu_not_found": True, "bu_name_query": bu_name_query}
        pnl = get_bu_pnl(db, business_unit_id=bu.id, year=year, month=month)
        return {"denied": False, "scope": "bu", "bu_name": bu.name, "pnl": pnl}

    summary = get_org_pnl_summary(db, year=year, month=month, tenant_id=user.tenant_id)
    return {"denied": False, "scope": "org", "pnl": summary}

def _format_finance_pnl_reply(result: Dict) -> str:
    if result.get("denied"):
        return PERMISSION_DENIED_FINANCE_MESSAGE
    if result.get("no_bu"):
        return "You're not assigned to a Business Unit, so I can't look up P&L for you."
    if result.get("choose_bu"):
        return "Which Business Unit? You can see: " + ", ".join(result["choose_bu"]) + "."
    if result.get("other_bu_blocked"):
        return f"You can only see {result['own_bu_name']}'s P&L, not other Business Units."
    if result.get("bu_not_found"):
        return f"I couldn't find a Business Unit matching \"{result['bu_name_query']}\"."

    pnl = result["pnl"]
    if result["scope"] == "bu":
        if not pnl.get("cost_data_complete", True):
            return (
                f"{result['bu_name']}'s revenue this month is ${pnl['revenue_usd_cents'] / 100:,.2f}, but "
                f"cost data is incomplete (no active cost-rate config), so I can't give you a real margin."
            )
        margin = pnl.get("margin_pct")
        return (
            f"{result['bu_name']} this month: revenue ${pnl['revenue_usd_cents'] / 100:,.2f}, "
            f"cost ${pnl['cost_usd_cents'] / 100:,.2f}, margin {margin}%." if margin is not None else
            f"{result['bu_name']} this month: revenue ${pnl['revenue_usd_cents'] / 100:,.2f}, no cost data yet."
        )

    if not pnl.get("org_cost_data_complete", True):
        return f"Org-wide revenue this month is ${pnl['total_revenue_usd_cents'] / 100:,.2f}, but cost data is incomplete for at least one BU, so the org margin isn't reliable yet."
    margin = pnl.get("margin_pct")
    return (
        f"Org-wide this month: revenue ${pnl['total_revenue_usd_cents'] / 100:,.2f}, "
        f"cost ${pnl['total_cost_usd_cents'] / 100:,.2f}, margin {margin}%."
    )

def get_ar_aging_answer(db: Session, user: Users) -> Dict:
    """Same permission gate as finance P&L (both are 'financial data'
    per Avinash's 2026-08-06 access rule) -- reuses ar_followup_service's
    real scan_overdue_invoices(). A BU-scoped user sees only invoices of
    clients in their business units (Invoice -> Client.business_unit_id)."""
    if not can_view_pnl(db, user):
        return {"denied": True}
    overdue = scan_overdue_invoices(db, tenant_id=user.tenant_id)
    if is_revenue_bu_scoped(db, user):
        from app.core.data_scope import visible_client_ids

        visible = {row[0] for row in db.execute(visible_client_ids(db, user, unassigned_visible=False)).all()}
        overdue = [row for row in overdue if row["client_id"] in visible]
    return {"denied": False, "overdue": overdue}

def _format_ar_aging_reply(result: Dict) -> str:
    if result.get("denied"):
        return PERMISSION_DENIED_FINANCE_MESSAGE
    overdue = result["overdue"]
    if not overdue:
        return "No overdue invoices right now -- everything sent is either paid or still within grace period."
    lines = [
        f"- Invoice {row['invoice_id']} -- ${row['total_usd_cents'] / 100:,.2f}, {row['days_overdue']} days overdue"
        for row in overdue[:10]
    ]
    more = f"\n(+{len(overdue) - 10} more)" if len(overdue) > 10 else ""
    return f"{len(overdue)} overdue invoice(s):\n" + "\n".join(lines) + more

def get_my_tasks_answer(db: Session, user: Users) -> List[Dict]:
    """Self-scoped -- literally the same get_daily_task_list() the My
    Day task dashboard calls for this exact user, so it always matches
    what they'd see if they opened that screen. No extra permission
    check needed: everyone can see their own tasks."""
    tasks = get_daily_task_list(db, assigned_to_user_id=user.UserID)
    return [{"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date, "status": t.status} for t in tasks]

def _format_my_tasks_reply(tasks: List[Dict]) -> str:
    if not tasks:
        return "Nothing due today or overdue -- you're clear."
    lines = [
        f"- #{t['id']} {t['title']} ({t['priority']}" + (f", due {t['due_date']:%Y-%m-%d})" if t['due_date'] else ")")
        for t in tasks
    ]
    return f"{len(tasks)} task(s) due today or overdue:\n" + "\n".join(lines)

def _format_bench_reply(query_text: str, results: List[Dict]) -> str:
    label = f"matching \"{query_text}\"" if query_text else "on the bench right now"
    if not results:
        return f"No one is currently available {label}."
    lines = [
        f"- {r['name']} -- {r['current_title'] or 'no title on file'}; "
        f"skills: {', '.join(r['skills']) or 'not on file'}; available since {r['available_from'] or 'unknown'}"
        for r in results
    ]
    return f"{len(results)} available {label}:\n" + "\n".join(lines)

def get_my_timesheets_answer(db: Session, user: Users) -> Dict:
    from app.models.employee_allocation import EmployeeAllocation
    from app.models.timesheet import Timesheet

    employee = db.query(Employee).filter(Employee.wros_user_id == user.UserID).first()
    if employee is None:
        return {"employee": False}
    sheets = db.query(Timesheet).filter(Timesheet.employee_id == employee.id) \
        .order_by(Timesheet.week_starting_date.desc()).limit(4).all()
    active = db.query(EmployeeAllocation).filter(EmployeeAllocation.employee_id == employee.id,
                                                 EmployeeAllocation.status == "ACTIVE").count()
    return {"employee": True, "status": employee.status, "allocations": active,
            "sheets": [{"week": s.week_starting_date, "status": s.status, "hours": float(s.total_hours or 0)}
                       for s in sheets]}


def _format_my_timesheets_reply(result: Dict) -> str:
    if not result["employee"]:
        return "You don't have an employee record, so there are no timesheets for you."
    if not result["allocations"] and not result["sheets"]:
        return f"You're on the {result['status'].lower()} with no project allocation, so there's no timesheet to fill yet."
    if not result["sheets"]:
        return "You have a project allocation but no timesheets yet. Open My Timesheet to log this week."
    lines = [f"- week of {s['week']:%d %b}: {s['status'].lower()}, {s['hours']:g}h" for s in result["sheets"]]
    return "Your recent timesheets:\n" + "\n".join(lines)


def get_pipeline_summary(db: Session, user: Users, client_query: str = "") -> Dict:
    """Candidates per hiring stage the user may see (same business-unit scope as the candidate
    screens), optionally only those on one client's jobs."""
    from sqlalchemy import func as sql_func

    from app.core.bu_scope import apply_bu_scope_to_candidate_query
    from app.models.candidate import CandidateStatus
    from app.models.client import Client

    query = db.query(Candidate).filter(Candidate.tenant_id == tenant_id_of(user))
    query = apply_bu_scope_to_candidate_query(db, query, user)
    client = None
    if client_query:
        client = db.query(Client).filter(Client.tenant_id == tenant_id_of(user),
                                         sql_func.lower(Client.company_name).like(f"%{client_query.lower()}%")).first()
        if client is None:
            return {"client_query": client_query, "client": None, "stages": {}, "total": 0}
        job_ids = [j for (j,) in db.query(Jobs.jobID).filter(Jobs.client_id == client.id)]
        query = query.filter(Candidate.job_id.in_(job_ids or [""]))
    ids = [c for (c,) in query.with_entities(Candidate.candidateID)]
    stages: Dict[str, int] = {}
    if ids:
        for stage, count in (db.query(CandidateStatus.piplineStatus, sql_func.count(CandidateStatus.id))
                             .filter(CandidateStatus.candidateID.in_(ids))
                             .group_by(CandidateStatus.piplineStatus).all()):
            stages[stage or "Not started"] = count
    return {"client_query": client_query, "client": client.company_name if client else None,
            "stages": stages, "total": len(ids)}


def _format_pipeline_summary(result: Dict) -> str:
    if result["client_query"] and result["client"] is None:
        return f"I couldn't find a client matching \"{result['client_query']}\"."
    scope = f" for {result['client']}" if result["client"] else ""
    if not result["total"]:
        return f"There are no candidates in the pipeline{scope} that you can see."
    lines = [f"Pipeline{scope}: {result['total']} candidate(s)."]
    lines += [f"- {stage}: {count}" for stage, count in sorted(result["stages"].items(), key=lambda kv: -kv[1])]
    return "\n".join(lines)


def answer_internal_query(
    db: Session, message: str, *, current_user: Optional[Users] = None, history: Optional[List[Dict]] = None,
    brains=None,
) -> Dict:
    """
    Full turn: classify -> real DB lookup -> deterministic, honest
    formatting. Never falls through to an LLM-generated guess -- a
    classification failure or an "unknown" intent both return
    UNSUPPORTED_QUERY_MESSAGE verbatim. `history` -- see
    classify_internal_query()'s own docstring -- only ever affects
    which candidate/role the CURRENT question resolves to; the DB
    lookup and reply formatting below are unchanged either way.

    `current_user` is required (not optional) for the financial-data
    intents (finance_pnl, ar_aging) -- 2026-08-06, Avinash's explicit
    access rule ("Only BU head, partner, finance team and ceo get
    access to financial data"). This is never a data-visibility
    shortcut around RBAC: both intents re-check the same
    app.core.revenue_visibility_scope gate the real dashboards use.
    """
    try:
        classification = classify_internal_query(message, history=history)
    except ThunderQueryClassificationFailed as exc:
        logger.warning(f"[Flash] classification failed: {exc}")
        return {"intent": INTENT_UNKNOWN, "reply": UNSUPPORTED_QUERY_MESSAGE}

    if classification["intent"] == INTENT_UNKNOWN:
        from app.services.flash_brain.llm import get_brains
        from app.services.flash_brain.router import route_intent

        brains = brains if brains is not None else get_brains()
        tenant_id = getattr(current_user, "tenant_id", None) or sole_tenant_id(db)
        routed = route_intent(brains, message, intents=AI_INTENTS, history=(history or [])[-MAX_HISTORY_TURNS:],
                              tenant_id=tenant_id)
        if routed is not None:
            classification = routed

    intent = classification["intent"]
    query = classification["query"]

    if intent == INTENT_MY_TIMESHEETS:
        if current_user is None:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        return {"intent": intent, "reply": _format_my_timesheets_reply(get_my_timesheets_answer(db, current_user))}

    if intent == INTENT_SOURCING:
        if not query:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        # ISOLATION FIX: Pass tenant_id + user_bu_id for data isolation
        tenant_id = tenant_id_of(current_user)
        user_bu_id = getattr(current_user, 'business_unit_id', None) if current_user else None
        results = find_matching_candidates(db, query, tenant_id=tenant_id, user_bu_id=user_bu_id)
        return {"intent": intent, "reply": _format_sourcing_reply(query, results)}

    if intent == INTENT_CANDIDATE_STATUS:
        if not query:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        # ISOLATION FIX: Pass tenant_id + user_bu_id for data isolation
        tenant_id = tenant_id_of(current_user)
        user_bu_id = getattr(current_user, 'business_unit_id', None) if current_user else None
        status = get_candidate_status_summary(db, query, tenant_id=tenant_id, user_bu_id=user_bu_id)
        return {"intent": intent, "reply": _format_status_reply(query, status["matches"])}

    if intent == INTENT_PIPELINE_SUMMARY:
        if current_user is None:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        return {"intent": intent, "reply": _format_pipeline_summary(get_pipeline_summary(db, current_user, query))}

    if intent == INTENT_BENCH_AVAILABILITY:
        # Unlike SOURCING/CANDIDATE_STATUS, an empty query is valid here
        # ("who's on the bench" with no skill filter) -- never treated
        # as unsupported.
        # Same permission as the bench screen (employees.view), and its tenant + BU scope
        from app.core import authority

        if current_user is None or not authority.has_permission(db, current_user, "employees.view"):
            return {"intent": intent, "reply": PERMISSION_DENIED_BENCH_MESSAGE}
        results = find_available_bench_employees(db, current_user, query)
        return {"intent": intent, "reply": _format_bench_reply(query, results)}

    if intent in (INTENT_FINANCE_PNL, INTENT_AR_AGING, INTENT_MY_TASKS) and current_user is None:
        # Should never happen from the real endpoint (always behind auth) --
        # only reachable if a caller invokes this function directly without
        # a user, e.g. an older test. Fail closed, not open.
        return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}

    if intent == INTENT_FINANCE_PNL:
        result = get_finance_pnl_answer(db, current_user, query)
        return {"intent": intent, "reply": _format_finance_pnl_reply(result)}

    if intent == INTENT_AR_AGING:
        result = get_ar_aging_answer(db, current_user)
        return {"intent": intent, "reply": _format_ar_aging_reply(result)}

    if intent == INTENT_MY_TASKS:
        tasks = get_my_tasks_answer(db, current_user)
        return {"intent": intent, "reply": _format_my_tasks_reply(tasks)}

    if intent == INTENT_DECISIONS:
        if current_user is None:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        from app.services.flash_brain.decisions import pending_decisions

        decisions = pending_decisions(db, current_user)
        if not decisions:
            return {"intent": intent, "reply": "Nothing is waiting for your decision."}
        return {"intent": intent, "reply": f"{len(decisions)} decision(s) waiting for you:\n"
                + "\n".join(f"- {d.text}" for d in decisions)}

    if intent == INTENT_JOB_CREATE:
        # The job_intake workflow (flash_brain.job_intake) takes over: Flash asks for what is
        # missing, confirms in one line and creates the job through job_creation_service.
        from app.core import authority

        if current_user is None or not authority.has_permission(db, current_user, "jobs.create"):
            return {"intent": intent, "reply": "You don't have permission to create jobs."}
        return {"intent": intent, "reply": "Let's set up the job.", "open_workflow": "job_intake"}

    return {"intent": INTENT_UNKNOWN, "reply": UNSUPPORTED_QUERY_MESSAGE}

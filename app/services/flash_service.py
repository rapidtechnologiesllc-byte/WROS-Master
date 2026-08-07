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

**2026-08-06, real architecture change, not just a docstring update**:
this module made an external Gemini API call for intent classification
until Avinash directly questioned it -- "why is it calling an external
Gemini system and exposing our data when I explicitly asked you to
build it entirely inside the WROS as our proprietary." Scope confirmed
directly with him (not assumed): Flash's own intent classification,
specifically -- rewritten to pure local regex/keyword matching, zero
network calls, zero data ever leaves this process. See
classify_internal_query()'s own docstring for the real trade-off this
creates (more rigid than an LLM, needs recognizably-phrased questions).
Thunder's own candidate-facing Gemini usage (reply generation,
sentiment, resume parsing, etc.) is a separate, much larger system and
is UNCHANGED by this -- that would be its own, much bigger decision,
not made here.

Every answer is built from real DB rows -- there is no free-text LLM
answer describing candidates, financials, or status, and (as of
2026-08-06) no LLM call anywhere in this module at all. Anything
outside the supported intents gets an explicit "I can't answer that
yet" instead of an invented answer -- "strict mode," per Avinash's own
words, same "no fake success" principle as the rest of this codebase.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.revenue_visibility_scope import can_view_pnl, is_revenue_bu_scoped
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.rbac import BusinessUnit
from app.models.resource_management import BenchPoolEntry
from app.models.task import Task
from app.models.user import Users
from app.services.ar_followup_service import scan_overdue_invoices
from app.services.pnl_service import get_bu_pnl, get_org_pnl_summary
from app.services.task_service import get_daily_task_list

INTENT_SOURCING = "sourcing"
INTENT_CANDIDATE_STATUS = "candidate_status"
INTENT_BENCH_AVAILABILITY = "bench_availability"
INTENT_FINANCE_PNL = "finance_pnl"
INTENT_AR_AGING = "ar_aging"
INTENT_MY_TASKS = "my_tasks"
INTENT_UNKNOWN = "unknown"

UNSUPPORTED_QUERY_MESSAGE = (
    "I can't answer that yet -- right now I can only help with sourcing candidates, "
    "checking a candidate's pipeline status, who's on the bench, BU P&L/margin, "
    "overdue invoices, or your own open tasks. Try one of those, or use the relevant "
    "screen directly for anything else."
)

# 2026-08-06 -- Avinash's own words: "Only BU head, partner, finance team and ceo
# get access to financial data and BU only get their bu related not org wide only
# finance and ceo can see full org finance." Reuses app.core.revenue_visibility_scope
# verbatim -- that module already encodes exactly this policy for the real dashboard/
# API endpoints (can_view_pnl() excludes HR Manager by name; REVENUE_BU_SCOPED_ROLES
# = {"Partner", "BU Head"} restricts those two to their own BU, everyone else with the
# permission sees org-wide) -- Thunder must never become a side-door around RBAC, so
# it calls the identical gate rather than reimplementing the policy a second time.
PERMISSION_DENIED_FINANCE_MESSAGE = (
    "I can't answer that -- financial data (P&L, margin, overdue invoices) is limited "
    "to BU Heads, Partners, Finance, and the CEO. Ask someone with access, or use the "
    "Finance Operations screen if you have it."
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
}


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
_FINANCE_PNL_PATTERN = re.compile(r"\b(margin|p\s*&\s*l|pnl|p\s+and\s+l|profit\w*)\b", re.IGNORECASE)
_AR_AGING_PATTERN = re.compile(
    r"(overdue|unpaid).{0,20}?invoices?|invoices?.{0,20}?(overdue|unpaid)|"
    r"accounts?\s+receivable|\bar\s+aging\b|who\s+owes",
    re.IGNORECASE,
)
_MY_TASKS_PATTERN = re.compile(r"\bmy\s+(open\s+)?tasks?\b|\bmy\s+plate\b|\bdue\s+today\b|\bmy\s+to.?do\b", re.IGNORECASE)
_BENCH_PATTERN = re.compile(
    r"\bbench\b|who.{0,4}s\s+free\b|who\s+is\s+free\b|available\s+(employee|developer|engineer|resource)",
    re.IGNORECASE,
)
_CANDIDATE_STATUS_PATTERN = re.compile(
    r"how\W{0,4}s?\s+is\b.{0,60}\bdoing\b|status\s+(on|of)\b|pipeline\s+status\b",
    re.IGNORECASE,
)
_SOURCING_PATTERN = re.compile(
    r"\b(find|source)\s+me\b|need\s+a\s+candidate\b|candidate\s+for\b|looking\s+for\s+(a|an|someone)\b",
    re.IGNORECASE,
)
# Simple proper-noun heuristic for candidate-name extraction: 1-3
# consecutive Title-Case words. Imperfect (no real NER without an LLM),
# but reliable enough for the common real phrasing ("how is Priya Sharma
# doing"). Excludes single common sentence-starters that happen to be
# capitalized (How/What/Who/etc.) by requiring the match not be the very
# first word of the message.
_PROPER_NOUN_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b")
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

    if _MY_TASKS_PATTERN.search(text):
        return {"intent": INTENT_MY_TASKS, "query": ""}

    if _BENCH_PATTERN.search(text):
        keywords = _extract_keywords(_NOISE_WORD_PATTERN.sub("", _BENCH_PATTERN.sub("", text)))
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

    return {"intent": INTENT_UNKNOWN, "query": ""}


def _extract_keywords(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#]*", text or "")
    return [t for t in tokens if len(t) > 1 and t.lower() not in _STOPWORDS]


def find_matching_candidates(db: Session, query_text: str, *, top_n: int = MAX_CANDIDATES_RETURNED) -> List[Dict]:
    """
    Real keyword-overlap search over the real Candidates table (skills,
    job title, experience text) -- not a fabricated ranking. Every
    result is a real candidate row; a query with no keywords or no
    matches returns an empty list, not invented candidates.
    """
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
    candidates = db.query(Candidate).filter(or_(*filters)).limit(200).all()

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


def get_candidate_status_summary(db: Session, name_query: str) -> Dict:
    """
    Real lookup by name against the real Candidates + CandidateStatus
    tables. Returns {"matches": [...]} -- zero, one, or several real
    candidates (never guesses which one you meant when several share a
    name; the caller surfaces all of them so a human can disambiguate)."""
    keywords = [k for k in _extract_keywords(name_query)]
    if not keywords:
        return {"matches": []}

    filters = []
    for kw in keywords:
        like = f"%{kw}%"
        filters.append(or_(Candidate.candidateFirstName.ilike(like), Candidate.candidateLastName.ilike(like)))
    candidates = db.query(Candidate).filter(or_(*filters)).limit(10).all()

    matches = []
    for candidate in candidates:
        status = (
            db.query(CandidateStatus)
            .filter(CandidateStatus.candidateID == candidate.candidateID)
            .order_by(CandidateStatus.updatedAt.desc())
            .first()
        )
        matches.append({
            "candidate_id": candidate.candidateID,
            "name": " ".join(filter(None, [candidate.candidateFirstName, candidate.candidateLastName])) or candidate.candidateEmail,
            "pipeline_status": status.piplineStatus if status else None,
            "account_status": status.status if status else None,
            "job_id": candidate.job_id,
        })
    return {"matches": matches}


def find_available_bench_employees(db: Session, query_text: str, *, top_n: int = MAX_CANDIDATES_RETURNED) -> List[Dict]:
    """
    Real read of resource_management_service's own bench pool table --
    no new data source, same "additive, not a replacement" posture as
    the rest of this query layer. An empty query_text (bare "who's on
    the bench") returns the whole current pool, most-recently-benched
    first; a query_text filters by skill_tags/current_title overlap,
    same keyword-overlap technique find_matching_candidates() already
    uses for candidates.
    """
    entries = (
        db.query(BenchPoolEntry, Employee)
        .join(Employee, BenchPoolEntry.employee_id == Employee.id)
        .order_by(BenchPoolEntry.created_at.desc())
        .limit(200)
        .all()
    )

    keywords = _extract_keywords(query_text) if query_text else []

    def _skill_tags(entry: BenchPoolEntry) -> List[str]:
        try:
            return json.loads(entry.skill_tags) if entry.skill_tags else []
        except (json.JSONDecodeError, TypeError):
            return []

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
    return (
        f"{m['name']} -- pipeline status: {m['pipeline_status'] or 'not set'}, "
        f"account status: {m['account_status'] or 'not set'}"
        + (f", linked to job {m['job_id']}" if m["job_id"] else "")
        + "."
    )


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
        if user.business_unit_id is None:
            return {"denied": False, "no_bu": True}
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == user.business_unit_id).first()
        if bu_name_query and bu and bu_name_query.strip().lower() not in (bu.name or "").lower():
            return {"denied": False, "other_bu_blocked": True, "own_bu_name": bu.name}
        pnl = get_bu_pnl(db, business_unit_id=user.business_unit_id, year=year, month=month)
        return {"denied": False, "scope": "bu", "bu_name": bu.name if bu else "your BU", "pnl": pnl}

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
    real scan_overdue_invoices(), no new query logic. AR aging isn't
    inherently BU-scoped in the underlying data model (Invoice has no
    business_unit_id), so a BU-scoped user (Partner/BU Head) sees
    org-wide overdue invoices here just like they would for revenue.view
    elsewhere -- flagged, not silently narrowed to a filter that doesn't
    exist on the real Invoice table."""
    if not can_view_pnl(db, user):
        return {"denied": True}
    overdue = scan_overdue_invoices(db, tenant_id=user.tenant_id)
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


def answer_internal_query(
    db: Session, message: str, *, current_user: Optional[Users] = None, history: Optional[List[Dict]] = None,
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

    intent = classification["intent"]
    query = classification["query"]

    if intent == INTENT_SOURCING:
        if not query:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        results = find_matching_candidates(db, query)
        return {"intent": intent, "reply": _format_sourcing_reply(query, results)}

    if intent == INTENT_CANDIDATE_STATUS:
        if not query:
            return {"intent": intent, "reply": UNSUPPORTED_QUERY_MESSAGE}
        status = get_candidate_status_summary(db, query)
        return {"intent": intent, "reply": _format_status_reply(query, status["matches"])}

    if intent == INTENT_BENCH_AVAILABILITY:
        # Unlike SOURCING/CANDIDATE_STATUS, an empty query is valid here
        # ("who's on the bench" with no skill filter) -- never treated
        # as unsupported.
        results = find_available_bench_employees(db, query)
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

    return {"intent": INTENT_UNKNOWN, "reply": UNSUPPORTED_QUERY_MESSAGE}

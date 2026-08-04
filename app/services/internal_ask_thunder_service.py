"""
Internal "Ask Thunder" -- a real, authenticated conversational query
surface for BlitzenX staff, alongside the candidate-facing chat
(app.services.thunder_service / app.services.public_chat_service).

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

Every answer is built from real DB rows -- there is no free-text LLM
answer describing candidates or their status. The LLM is used ONLY for
the narrow, low-risk task of classifying intent and extracting a
search term from the question; the actual facts always come straight
from the database. Anything outside the three real intents gets an
explicit "I can't answer that yet" instead of an invented answer --
same "no fake success" principle as the rest of this Thunder buildout.
"""
import json
import re
from typing import Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.llm_prompt_safety import build_safe_prompt
from app.core.logging import logger
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry
from app.services.thunder_service import GEMINI_API_KEY, THUNDER_REPLY_MODEL

INTENT_SOURCING = "sourcing"
INTENT_CANDIDATE_STATUS = "candidate_status"
INTENT_BENCH_AVAILABILITY = "bench_availability"
INTENT_UNKNOWN = "unknown"

UNSUPPORTED_QUERY_MESSAGE = (
    "I can't answer that yet -- right now I can only help with sourcing candidates "
    "for a role, or checking a specific candidate's pipeline status. Try one of those, "
    "or use the relevant screen directly for anything else."
)

MAX_CANDIDATES_RETURNED = 5

_STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "of", "in", "on", "to", "who",
    "that", "has", "have", "years", "year", "yrs", "experience", "role", "roles",
    "candidate", "candidates", "find", "source", "sourcing", "me", "us", "need",
    "want", "wants", "looking", "please", "any", "some", "there", "is", "are",
    "resource", "someone",
}


class ThunderQueryClassificationFailed(Exception):
    """Gemini couldn't be called or returned something unusable -- callers
    must fall back to UNSUPPORTED_QUERY_MESSAGE, never guess the intent."""


def classify_internal_query(message: str) -> Dict:
    """
    Narrow LLM task: classify `message` into one of INTENT_SOURCING /
    INTENT_CANDIDATE_STATUS / INTENT_UNKNOWN, and extract the search
    term (role/skills text, or a candidate's name). Never asked to
    answer the question itself -- that always comes from a real DB
    query in answer_internal_query() below.
    """
    if not GEMINI_API_KEY:
        raise ThunderQueryClassificationFailed("GEMINI_API_KEY not configured.")

    instruction = f"""Classify an internal BlitzenX staff member's question into exactly one category:

- "{INTENT_SOURCING}": asking to find/source CANDIDATES (not-yet-hired applicants) matching a role, skill, or experience level (e.g. "find me a Java developer", "I need a candidate for the Guidewire role", "source someone with React experience").
- "{INTENT_CANDIDATE_STATUS}": asking about ONE SPECIFIC NAMED candidate's current status, pipeline stage, or progress (e.g. "how is Priya Sharma doing", "what's the status on candidate John Doe").
- "{INTENT_BENCH_AVAILABILITY}": asking who's FREE/AVAILABLE/ON THE BENCH right now among existing EMPLOYEES (not candidates), optionally for a skill (e.g. "who's free for a Java role right now", "who's on the bench", "any available React developers").
- "{INTENT_UNKNOWN}": anything else -- compensation questions, general chit-chat, or anything not covered above.

Respond with ONLY a JSON object, no other text, no markdown code fences:
{{"intent": "<one of the four above>", "query": "<see below>"}}

"query" is:
- for "{INTENT_SOURCING}": the role/skills/experience text to search for.
- for "{INTENT_CANDIDATE_STATUS}": the candidate's name as mentioned.
- for "{INTENT_BENCH_AVAILABILITY}": the skill/role text to filter by, or empty string for "who's on the bench" with no filter.
- for "{INTENT_UNKNOWN}": empty string."""

    prompt = build_safe_prompt(
        instruction=instruction,
        untrusted_label="STAFF_QUESTION",
        untrusted_content=message,
    )

    llm = ChatGoogleGenerativeAI(
        model=THUNDER_REPLY_MODEL, google_api_key=GEMINI_API_KEY,
        temperature=0.0, timeout=20,
    )
    try:
        response = llm.invoke(prompt)
    except Exception as exc:
        raise ThunderQueryClassificationFailed(f"Gemini call failed or timed out: {exc}") from exc

    content = response.content
    raw = " ".join(
        block.get("text", "") if isinstance(block, dict) else str(block) for block in content
    ) if isinstance(content, list) else str(content)
    raw = raw.strip()
    # Strip an accidental ```json ... ``` fence -- models do this despite
    # being told not to.
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ThunderQueryClassificationFailed(f"Gemini returned non-JSON output: {raw!r}") from exc

    intent = parsed.get("intent")
    if intent not in (INTENT_SOURCING, INTENT_CANDIDATE_STATUS, INTENT_BENCH_AVAILABILITY, INTENT_UNKNOWN):
        raise ThunderQueryClassificationFailed(f"Gemini returned an unrecognized intent: {intent!r}")

    return {"intent": intent, "query": str(parsed.get("query") or "").strip()}


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
        if score > 0:
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
        if keywords and not any(kw.lower() in haystack for kw in keywords):
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
        f"- {r['name']} ({r['candidate_id']}) -- {r['job_title'] or 'no title on file'}; "
        f"skills: {r['skills'] or 'not on file'}; experience: {r['experience'] or 'not on file'}"
        for r in results
    ]
    return f"Found {len(results)} candidate(s) matching \"{query_text}\":\n" + "\n".join(lines)


def _format_status_reply(name_query: str, matches: List[Dict]) -> str:
    if not matches:
        return f"I couldn't find a candidate named \"{name_query}\" in the system."
    if len(matches) > 1:
        names = ", ".join(f"{m['name']} ({m['candidate_id']})" for m in matches)
        return f"I found more than one candidate matching \"{name_query}\": {names}. Which one did you mean?"
    m = matches[0]
    return (
        f"{m['name']} ({m['candidate_id']}) -- pipeline status: {m['pipeline_status'] or 'not set'}, "
        f"account status: {m['account_status'] or 'not set'}"
        + (f", linked to job {m['job_id']}" if m["job_id"] else "")
        + "."
    )


def _format_bench_reply(query_text: str, results: List[Dict]) -> str:
    label = f"matching \"{query_text}\"" if query_text else "on the bench right now"
    if not results:
        return f"No one is currently available {label}."
    lines = [
        f"- {r['name']} ({r['employee_id']}) -- {r['current_title'] or 'no title on file'}; "
        f"skills: {', '.join(r['skills']) or 'not on file'}; available since {r['available_from'] or 'unknown'}"
        for r in results
    ]
    return f"{len(results)} available {label}:\n" + "\n".join(lines)


def answer_internal_query(db: Session, message: str) -> Dict:
    """
    Full turn: classify -> real DB lookup -> deterministic, honest
    formatting. Never falls through to an LLM-generated guess -- a
    classification failure or an "unknown" intent both return
    UNSUPPORTED_QUERY_MESSAGE verbatim.
    """
    try:
        classification = classify_internal_query(message)
    except ThunderQueryClassificationFailed as exc:
        logger.warning(f"[AskThunder] classification failed: {exc}")
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

    return {"intent": INTENT_UNKNOWN, "reply": UNSUPPORTED_QUERY_MESSAGE}

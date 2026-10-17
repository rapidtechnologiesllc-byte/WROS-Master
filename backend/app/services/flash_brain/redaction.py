"""What Flash may show a language model (CEO decision 2026-10-15, "work data only").

Allowed: the requester's words and work data -- names, skills, experience, job titles, client and
job names, hiring stages, counts and dates. Never: email addresses, phone numbers, pay (salary,
compensation, rates, billing), document contents or links, finance figures.

Every string and every tool result passes through here before it reaches ANY model (the large and
small brains call it themselves, so no caller can skip it):

- structured payloads (tool results) are filtered by a whitelist of known keys: a key not listed
  below is dropped with its whole value, so a new field never leaks by default;
- every string that survives (free text, names, formatted replies) is scrubbed by pattern.
"""
import re
from typing import Any

# Keys a model may see. Anything else -- email, phone, salary, rate, bill_rate, revenue, margin,
# amount, document, resume_url, address... -- is dropped, never forwarded.
ALLOWED_KEYS = frozenset({
    # what a tool says and how it went
    "text", "error", "message", "reply", "missing", "done", "ok", "denied",
    # people and records (identifiers and names, never contact details)
    "id", "candidate_id", "employee_id", "user_id", "request_id", "ref", "kind",
    "name", "full_name", "first_name", "last_name", "candidate_name", "employee_name",
    "interviewer", "interviewer_name", "hiring_manager", "recruiter", "owner",
    # work data
    "title", "job_title", "current_title", "designation", "role",
    "skills", "skill", "matched", "missing_mandatory", "primary_skill",
    "experience_months", "experience_years", "min_experience_years", "years",
    "score", "level", "round", "round_name", "verdict",
    "status", "stage", "stages", "pipeline_stage", "state", "reason",
    "job_id", "client", "client_id", "client_name", "company_name", "business_unit", "bu",
    "location", "work_location", "company_type", "positions", "available_from",
    "start", "end", "start_time", "end_time", "due", "due_date", "priority", "created_at",
    "mission_id", "decision", "query",
    # collections of the above
    "results", "matches", "items", "tasks", "candidates", "jobs", "clients", "decisions",
    "count", "total",
})

REMOVED_EMAIL = "[email removed]"
REMOVED_PHONE = "[phone removed]"
REMOVED_LINK = "[link removed]"
REMOVED_AMOUNT = "[amount removed]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_LINK = re.compile(r"\b(?:https?://|www\.)\S+|\b\S+\.(?:pdf|docx?|xlsx?|pptx?|png|jpe?g)\b", re.IGNORECASE)
# 8+ digits with phone separators, not glued to an identifier (JOB-..., uuid) on either side
_PHONE = re.compile(r"(?<![\w-])\+?\(?\d[\d\s().-]{6,}\d(?![\w-])")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_MONEY = re.compile(
    r"(?:[$₹€£]|\b(?:USD|INR|EUR|GBP|Rs\.?)\s?)\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|mn|lakhs?|lacs?|cr|crores?|lpa)?\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s?(?:k|lakhs?|lacs?|cr|crores?|lpa)\b(?:\s*(?:per\s+(?:annum|year|month|hour)|/\s*(?:yr|year|hr|hour|month)))?",
    re.IGNORECASE)
# A number shortly after a pay or finance word ("rate 85/hr", "margin: 32%", "revenue 1,200,000")
_FINANCE_FIGURE = re.compile(
    r"(\b(?:salary|salaries|ctc|compensation|pay|payroll|rate|rates|billing|bill|billed|revenue|margin|profit|"
    r"loss|cost|costs|invoice|invoices|invoiced|amount|outstanding|budget|p&l|pnl|ebitda|fee|fees)\b[^\n.;]{0,24}?)"
    r"(\d[\d,]*(?:\.\d+)?\s?%?(?:\s*/\s*(?:hr|hour|day|month|yr|year))?)",
    re.IGNORECASE)


def _phone(match: "re.Match") -> str:
    found = match.group(0)
    if _ISO_DATE.search(found) or sum(ch.isdigit() for ch in found) < 8:
        return found
    return REMOVED_PHONE


def redact_text(text: Any) -> str:
    """Scrub contact details, links, pay and finance figures out of free text."""
    if text is None:
        return ""
    value = str(text)
    value = _EMAIL.sub(REMOVED_EMAIL, value)
    value = _LINK.sub(REMOVED_LINK, value)
    value = _MONEY.sub(REMOVED_AMOUNT, value)
    value = _FINANCE_FIGURE.sub(lambda m: m.group(1) + REMOVED_AMOUNT, value)
    return _PHONE.sub(_phone, value)


def redact_payload(value: Any) -> Any:
    """A tool result as a model may see it: whitelisted keys only, every string scrubbed."""
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items() if key in ALLOWED_KEYS}
    if isinstance(value, (list, tuple, set)):
        return [redact_payload(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(value)

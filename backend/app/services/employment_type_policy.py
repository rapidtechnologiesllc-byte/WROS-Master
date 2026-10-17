"""Employment type by the candidate's country (CEO 2026-10-15) -- the one rule, read everywhere.

One canonical set of types (app.models.candidate.CANDIDATE_EMPLOYMENT_TYPES): FULLTIME,
CONTRACT, C2C, 1099, UNKNOWN. Which of them a country accepts, and what they are called there
("W2 full-time" in the US, "Full-time" in India), is configuration: settings.
EMPLOYMENT_TYPE_POLICY_JSON. C2C, 1099 and UNKNOWN are never accepted anywhere.

Two strengths of the rule:
  - interview_check (interview selection, joining a job pipeline, the pipeline, the offer):
    an explicit type the candidate's country does not accept is out; UNKNOWN may interview (it
    is confirmed later), and so may an accepted type while the country is still unknown.
  - submission_check (client submission, HRMS-P606): fails closed -- the country must be known
    and accept the candidate's type; UNKNOWN never passes.

The candidate's country is Candidate.country (ISO 3166-1 alpha-2), set from the profile's
location picker, derived from a free-text location when it names a configured country, or from
the employee's delivery company on conversion.
"""
import json
from functools import lru_cache
from typing import Dict, List, Optional

from app.models.candidate import CANDIDATE_EMPLOYMENT_TYPES

NEVER_ACCEPTED = frozenset({"C2C", "1099", "UNKNOWN"})
UNKNOWN = "UNKNOWN"


class EmploymentTypePolicyError(ValueError):
    """The configured policy breaks the CEO rule or names an unknown type."""


@lru_cache(maxsize=4)
def _parse(raw: str) -> Dict:
    try:
        policy = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EmploymentTypePolicyError(f"EMPLOYMENT_TYPE_POLICY_JSON is not valid JSON: {exc}") from exc
    labels, countries = policy.get("labels") or {}, policy.get("countries") or {}
    missing = [t for t in CANDIDATE_EMPLOYMENT_TYPES if t not in labels]
    if missing:
        raise EmploymentTypePolicyError(f"EMPLOYMENT_TYPE_POLICY_JSON has no label for {missing}")
    for code, country in countries.items():
        if len(code) != 2 or code != code.upper():
            raise EmploymentTypePolicyError(f"Country code {code!r} must be ISO 3166-1 alpha-2 (e.g. US)")
        accepts = country.get("accepts") or {}
        unknown = [t for t in accepts if t not in CANDIDATE_EMPLOYMENT_TYPES]
        forbidden = [t for t in accepts if t in NEVER_ACCEPTED]
        if unknown or forbidden:
            raise EmploymentTypePolicyError(
                f"Country {code} may only accept {sorted(set(CANDIDATE_EMPLOYMENT_TYPES) - NEVER_ACCEPTED)}; "
                f"got unknown {unknown} / never-accepted {forbidden}")
    return {"labels": labels, "countries": countries}


def policy() -> Dict:
    from app.core.config import settings

    return _parse(settings.EMPLOYMENT_TYPE_POLICY_JSON)


def country_code(value: Optional[str]) -> Optional[str]:
    """A configured country's ISO code from an ISO code, a country name, or a free-text location
    whose last comma-separated part names the country ("Pune, Maharashtra, India"). None when it
    names no configured country."""
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    countries = policy()["countries"]
    if text.upper() in countries:
        return text.upper()
    last = text.split(",")[-1].strip().lower()
    for code, country in countries.items():
        if last in {n.lower() for n in country.get("names") or []} or last == (country.get("name") or "").lower():
            return code
    return None


def accepted_types(country: Optional[str]) -> List[str]:
    return list((policy()["countries"].get(country or "") or {}).get("accepts") or {})


def label(employment_type: Optional[str], country: Optional[str] = None) -> str:
    accepts = (policy()["countries"].get(country or "") or {}).get("accepts") or {}
    return accepts.get(employment_type) or policy()["labels"].get(employment_type or UNKNOWN, employment_type or "")


def options(country: Optional[str]) -> List[Dict]:
    """The employment-type picker for a candidate in this country: every canonical type with its
    label there, accepted ones first."""
    accepted = accepted_types(country)
    ordered = accepted + [t for t in CANDIDATE_EMPLOYMENT_TYPES if t not in accepted]
    return [{"value": t, "label": label(t, country), "accepted": t in accepted} for t in ordered]


def describe() -> Dict:
    """The whole policy for the screens (GET /candidates/employment-types)."""
    countries = policy()["countries"]
    return {
        "types": list(CANDIDATE_EMPLOYMENT_TYPES),
        "default_options": options(None),
        "countries": [{"code": code, "name": c.get("name") or code, "options": options(code)}
                      for code, c in countries.items()],
    }


def _country_name(country: Optional[str]) -> str:
    return (policy()["countries"].get(country or "") or {}).get("name") or (country or "")


def _accepted_phrase(country: str) -> str:
    return " or ".join(label(t, country) for t in accepted_types(country))


def submission_check(candidate) -> Dict:
    """Client submission (fails closed): known country that accepts the candidate's type."""
    employment_type, country = candidate.employment_type or UNKNOWN, candidate.country
    base = {"employment_type": employment_type, "country": country}
    if country not in policy()["countries"]:
        return {**base, "allowed": False, "error": "C2C_NOT_ACCEPTED",
                "message": ("The candidate's country is not recorded (or not one we hire in), so their "
                            "employment type cannot be confirmed. Set the candidate's country.")}
    if employment_type not in accepted_types(country):
        return {**base, "allowed": False, "error": "C2C_NOT_ACCEPTED",
                "message": (f"Only {_accepted_phrase(country)} candidates are accepted in "
                            f"{_country_name(country)}; this candidate is {label(employment_type, country)}.")}
    return {**base, "allowed": True}


def interview_check(candidate) -> Dict:
    """Interview selection: an explicit type the country never accepts is out; UNKNOWN (and an
    accepted type while the country is unknown) may interview."""
    employment_type, country = candidate.employment_type or UNKNOWN, candidate.country
    base = {"employment_type": employment_type, "country": country}
    if employment_type == UNKNOWN:
        return {**base, "allowed": True}
    countries = policy()["countries"]
    if country in countries:
        allowed = employment_type in accepted_types(country)
        where = f"in {_country_name(country)}"
    else:
        allowed = any(employment_type in accepted_types(code) for code in countries)
        where = "anywhere we hire"
    if allowed:
        return {**base, "allowed": True}
    return {**base, "allowed": False, "error": "EMPLOYMENT_TYPE_NOT_ACCEPTED",
            "message": f"{label(employment_type, country)} candidates are not accepted {where}."}


class EmploymentTypeNotAccepted(ValueError):
    """The interview-level rule failed (an explicit type the candidate's country never accepts)."""


def assert_may_interview(candidate, step: str) -> None:
    result = interview_check(candidate)
    if not result["allowed"]:
        raise EmploymentTypeNotAccepted(f"Cannot {step}: {result['message']}")

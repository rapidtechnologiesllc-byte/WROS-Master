"""
import logging
HRMS-0527 -- Curtis Rule: Partner Intent ML Engine.

See app.models.partner_intent's module docstring for the real blocker:
Demand has no delivery_engine/partner_user_id columns, and "partner" is
an undefined identity concept in this codebase. compute_partner_intent_
profile() takes historical demand data as a parameter rather than
querying Demand directly -- the inference math is real and tested;
wiring it to actual Demand rows is deferred pending that product
decision, not invented here.

This codebase's dedup elsewhere (R-07) is explicitly exact-match only,
no fuzzy/AI-based matching -- detect_new_client() follows the same
constraint: case-insensitive exact match on company_name, not true
fuzzy (e.g. Levenshtein) matching, which doesn't exist anywhere in this
codebase and isn't invented here either.
"""
import json
from collections import Counter
from datetime import datetime
from statistics import pstdev
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.partner_intent import PartnerIntentProfile

MIN_DEMANDS_FOR_INFERENCE = 3          # BR: below this, full qualification, no inference at all
CORE_INFERENCE_THRESHOLD_PCT = 95.0    # AC-2
CORE_INFERENCE_MIN_DEMANDS = 5
CORE_INFERENCE_CONFIDENCE = 97
EXPERIENCE_STD_DEV_THRESHOLD_YEARS = 1.0
# Doc gives one illustrative example ("$110-$125 range") rather than a
# numeric tolerance -- this session's judgment call: infer only when
# the spread is within 20% of the average, not just "has a min and max
# on file." Flagged, not a confirmed product decision.
BILLING_RANGE_RELATIVE_TOLERANCE = 0.20


def compute_partner_intent_profile(
    partner_user_id: str, historical_demands: List[dict], *, tenant_id=None,
) -> dict:
    """
    historical_demands: each dict may have delivery_engine ('CORE' or
    'SPECIALTY'), min_experience_years (float), billing_rate_usd_cents
    (int), required_skills (list[str]). Missing/None values are simply
    excluded from the relevant average, not treated as zero.
    """
    demand_count = len(historical_demands)
    if demand_count == 0:
        return {
            "partner_user_id": partner_user_id, "tenant_id": tenant_id, "demand_count": 0,
            "core_demand_pct": None, "specialty_demand_pct": None,
            "avg_experience_level": None, "experience_level_std_dev": None,
            "typical_billing_range_min_usd_cents": None, "typical_billing_range_max_usd_cents": None,
            "typical_skills": [],
        }

    core_count = sum(1 for d in historical_demands if d.get("delivery_engine") == "CORE")
    core_pct = round(100.0 * core_count / demand_count, 2)
    specialty_pct = round(100.0 - core_pct, 2)

    experience_values = [d["min_experience_years"] for d in historical_demands if d.get("min_experience_years") is not None]
    avg_experience = round(sum(experience_values) / len(experience_values), 1) if experience_values else None
    # "std_dev... across last 10 demands" -- most recent 10, assuming
    # historical_demands is supplied oldest-first (caller's ordering).
    recent_experience = experience_values[-10:]
    experience_std_dev = round(pstdev(recent_experience), 2) if len(recent_experience) >= 2 else None

    billing_values = [d["billing_rate_usd_cents"] for d in historical_demands if d.get("billing_rate_usd_cents") is not None]
    billing_min = min(billing_values) if billing_values else None
    billing_max = max(billing_values) if billing_values else None

    skill_counts = Counter()
    for d in historical_demands:
        for skill in (d.get("required_skills") or []):
            skill_counts[skill] += 1
    typical_skills = [skill for skill, _count in skill_counts.most_common(5)]

    return {
        "partner_user_id": partner_user_id, "tenant_id": tenant_id, "demand_count": demand_count,
        "core_demand_pct": core_pct, "specialty_demand_pct": specialty_pct,
        "avg_experience_level": avg_experience, "experience_level_std_dev": experience_std_dev,
        "typical_billing_range_min_usd_cents": billing_min, "typical_billing_range_max_usd_cents": billing_max,
        "typical_skills": typical_skills,
    }


def save_partner_intent_profile(db: Session, profile_data: dict) -> PartnerIntentProfile:
    """Upserts by partner_user_id (unique) -- the nightly batch job's
    write step, once real historical demand data can be sourced (see
    module docstring on what's still blocked)."""
    existing = (
        db.query(PartnerIntentProfile)
        .filter(PartnerIntentProfile.partner_user_id == profile_data["partner_user_id"])
        .first()
    )
    target = existing or PartnerIntentProfile(partner_user_id=profile_data["partner_user_id"])

    target.tenant_id = profile_data.get("tenant_id")
    target.demand_count = profile_data["demand_count"]
    target.core_demand_pct = profile_data["core_demand_pct"]
    target.specialty_demand_pct = profile_data["specialty_demand_pct"]
    target.avg_experience_level = profile_data["avg_experience_level"]
    target.experience_level_std_dev = profile_data["experience_level_std_dev"]
    target.typical_billing_range_min_usd_cents = profile_data["typical_billing_range_min_usd_cents"]
    target.typical_billing_range_max_usd_cents = profile_data["typical_billing_range_max_usd_cents"]
    target.typical_skills = json.dumps(profile_data["typical_skills"])
    target.last_updated = datetime.utcnow()

    db.add(target)
    return target


def infer_intent(profile: Optional[PartnerIntentProfile]) -> dict:
    """
    IntentInferenceEngine.infer() -- BR: demand_count >= 3 required;
    below threshold, every dimension is UNKNOWN and Thunder asks the
    full qualification set.
    """
    if profile is None or profile.demand_count < MIN_DEMANDS_FOR_INFERENCE:
        return {
            "inferred_delivery_engine": "UNKNOWN", "confidence": 0,
            "inferred_experience_level": "UNKNOWN", "inferred_billing_range": "UNKNOWN",
            "questions_to_skip": [], "questions_to_ask": ["delivery_type", "experience_level", "billing_range"],
        }

    questions_to_skip: List[str] = []
    questions_to_ask: List[str] = []

    core_pct = float(profile.core_demand_pct) if profile.core_demand_pct is not None else 0.0
    specialty_pct = float(profile.specialty_demand_pct) if profile.specialty_demand_pct is not None else 0.0

    if profile.demand_count >= CORE_INFERENCE_MIN_DEMANDS and core_pct >= CORE_INFERENCE_THRESHOLD_PCT:
        inferred_delivery_engine = "CORE"
        confidence = CORE_INFERENCE_CONFIDENCE
        questions_to_skip.append("delivery_type")
    elif profile.demand_count >= CORE_INFERENCE_MIN_DEMANDS and specialty_pct >= CORE_INFERENCE_THRESHOLD_PCT:
        inferred_delivery_engine = "SPECIALTY"
        confidence = CORE_INFERENCE_CONFIDENCE
        questions_to_skip.append("delivery_type")
    else:
        inferred_delivery_engine = "UNKNOWN"
        confidence = 0
        questions_to_ask.append("delivery_type")

    if profile.experience_level_std_dev is not None and float(profile.experience_level_std_dev) < EXPERIENCE_STD_DEV_THRESHOLD_YEARS:
        inferred_experience_level = float(profile.avg_experience_level) if profile.avg_experience_level is not None else "UNKNOWN"
        questions_to_skip.append("experience_level")
    else:
        inferred_experience_level = "UNKNOWN"
        questions_to_ask.append("experience_level")

    billing_min = profile.typical_billing_range_min_usd_cents
    billing_max = profile.typical_billing_range_max_usd_cents
    if billing_min is not None and billing_max is not None:
        avg_billing = (billing_min + billing_max) / 2
        spread = billing_max - billing_min
        if avg_billing > 0 and (spread / avg_billing) <= BILLING_RANGE_RELATIVE_TOLERANCE:
            inferred_billing_range = {"min": billing_min, "max": billing_max}
            questions_to_skip.append("billing_range")
        else:
            inferred_billing_range = "UNKNOWN"
            questions_to_ask.append("billing_range")
    else:
        inferred_billing_range = "UNKNOWN"
        questions_to_ask.append("billing_range")

    return {
        "inferred_delivery_engine": inferred_delivery_engine, "confidence": confidence,
        "inferred_experience_level": inferred_experience_level, "inferred_billing_range": inferred_billing_range,
        "questions_to_skip": questions_to_skip, "questions_to_ask": questions_to_ask,
    }


def detect_new_client(db: Session, client_name: str) -> Tuple[Optional[Client], bool]:
    """Returns (existing_client_or_None, is_new). Case-insensitive exact
    match only -- see module docstring on why this isn't fuzzy matching."""
    existing = (
        db.query(Client)
        .filter(func.lower(Client.company_name) == client_name.strip().lower())
        .first()
    )
    if existing:
        return existing, False
    return None, True


def create_pending_verification_client(db: Session, client_name: str, *, tenant_id=None) -> Client:
    """BR: new client always triggers PENDING_VERIFICATION, never silent
    creation as an assumed client type -- sourcing proceeds in parallel
    while a human confirms, per the story's "no stalling" requirement."""
    client = Client(company_name=client_name, tenant_id=tenant_id, status="PENDING_VERIFICATION")
    db.add(client)
    db.flush()
    return client

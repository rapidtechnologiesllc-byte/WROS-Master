"""
HRMS-0527 -- Curtis Rule: Partner Intent ML Engine.

Proves the inference math itself (AC-1, AC-2, AC-6, and the experience/
billing consistency rules) and the new-client PENDING_VERIFICATION flow
(AC-4) -- all real and tested, independent of the still-deferred
Demand.delivery_engine/partner_user_id wiring (see module docstrings).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.partner_intent import PartnerIntentProfile
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.partner_intent_service import (
    compute_partner_intent_profile,
    create_pending_verification_client,
    detect_new_client,
    infer_intent,
    save_partner_intent_profile,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__, PartnerIntentProfile.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


# ---------------------------------------------------------------------------
# compute_partner_intent_profile
# ---------------------------------------------------------------------------

def test_zero_demands_produces_empty_profile():
    profile = compute_partner_intent_profile("U-CURTIS", [])
    assert profile["demand_count"] == 0
    assert profile["core_demand_pct"] is None
    assert profile["typical_skills"] == []


def test_core_percentage_computed_correctly():
    demands = [{"delivery_engine": "CORE"}] * 23
    profile = compute_partner_intent_profile("U-CURTIS", demands)
    assert profile["demand_count"] == 23
    assert profile["core_demand_pct"] == 100.0
    assert profile["specialty_demand_pct"] == 0.0


def test_mixed_delivery_engine_percentages():
    demands = [{"delivery_engine": "CORE"}] * 3 + [{"delivery_engine": "SPECIALTY"}] * 1
    profile = compute_partner_intent_profile("U-X", demands)
    assert profile["core_demand_pct"] == 75.0
    assert profile["specialty_demand_pct"] == 25.0


def test_experience_average_and_std_dev():
    demands = [{"min_experience_years": v} for v in [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]]
    profile = compute_partner_intent_profile("U-X", demands)
    assert profile["avg_experience_level"] == 5.0
    assert profile["experience_level_std_dev"] == 0.0


def test_experience_std_dev_reflects_inconsistency():
    demands = [{"min_experience_years": v} for v in [2, 8, 3, 9, 2, 10, 1, 9, 2, 8]]
    profile = compute_partner_intent_profile("U-X", demands)
    assert profile["experience_level_std_dev"] > 1.0


def test_billing_range_min_max():
    demands = [{"billing_rate_usd_cents": v} for v in [11000, 11500, 12000, 12500]]
    profile = compute_partner_intent_profile("U-X", demands)
    assert profile["typical_billing_range_min_usd_cents"] == 11000
    assert profile["typical_billing_range_max_usd_cents"] == 12500


def test_typical_skills_top_five_most_frequent():
    demands = (
        [{"required_skills": ["Guidewire"]}] * 10
        + [{"required_skills": ["Java"]}] * 5
        + [{"required_skills": ["Python"]}] * 1
    )
    profile = compute_partner_intent_profile("U-X", demands)
    assert profile["typical_skills"][0] == "Guidewire"
    assert "Java" in profile["typical_skills"]


# ---------------------------------------------------------------------------
# save_partner_intent_profile -- upsert
# ---------------------------------------------------------------------------

def test_save_creates_new_profile(db_session):
    profile_data = compute_partner_intent_profile("U-CURTIS", [{"delivery_engine": "CORE"}] * 5)
    saved = save_partner_intent_profile(db_session, profile_data)
    db_session.commit()
    assert saved.partner_user_id == "U-CURTIS"
    assert db_session.query(PartnerIntentProfile).count() == 1


def test_save_upserts_existing_profile_not_duplicate(db_session):
    profile_data = compute_partner_intent_profile("U-CURTIS", [{"delivery_engine": "CORE"}] * 5)
    save_partner_intent_profile(db_session, profile_data)
    db_session.commit()

    updated_data = compute_partner_intent_profile("U-CURTIS", [{"delivery_engine": "CORE"}] * 23)
    save_partner_intent_profile(db_session, updated_data)
    db_session.commit()

    assert db_session.query(PartnerIntentProfile).count() == 1
    profile = db_session.query(PartnerIntentProfile).filter(PartnerIntentProfile.partner_user_id == "U-CURTIS").first()
    assert profile.demand_count == 23


# ---------------------------------------------------------------------------
# infer_intent -- BR: min 3 demands, AC-2 CORE skip, AC-6 full qualification
# ---------------------------------------------------------------------------

def test_no_profile_yields_full_qualification():
    result = infer_intent(None)
    assert result["inferred_delivery_engine"] == "UNKNOWN"
    assert result["confidence"] == 0
    assert set(result["questions_to_ask"]) == {"delivery_type", "experience_level", "billing_range"}
    assert result["questions_to_skip"] == []


def test_below_minimum_demand_count_yields_full_qualification():
    profile = PartnerIntentProfile(partner_user_id="U-NEW", demand_count=2, core_demand_pct=100.0)
    result = infer_intent(profile)
    assert result["inferred_delivery_engine"] == "UNKNOWN"
    assert "delivery_type" in result["questions_to_ask"]


def test_curtis_scenario_skips_delivery_type_question():
    """23 demands, 100% Core -- AC-2."""
    profile = PartnerIntentProfile(
        partner_user_id="U-CURTIS", demand_count=23, core_demand_pct=100.0, specialty_demand_pct=0.0,
    )
    result = infer_intent(profile)
    assert result["inferred_delivery_engine"] == "CORE"
    assert result["confidence"] == 97
    assert "delivery_type" in result["questions_to_skip"]
    assert "delivery_type" not in result["questions_to_ask"]


def test_specialty_dominant_partner_infers_specialty():
    profile = PartnerIntentProfile(
        partner_user_id="U-Y", demand_count=10, core_demand_pct=0.0, specialty_demand_pct=100.0,
    )
    result = infer_intent(profile)
    assert result["inferred_delivery_engine"] == "SPECIALTY"
    assert "delivery_type" in result["questions_to_skip"]


def test_mixed_pattern_below_threshold_still_asks():
    profile = PartnerIntentProfile(
        partner_user_id="U-Z", demand_count=10, core_demand_pct=80.0, specialty_demand_pct=20.0,
    )
    result = infer_intent(profile)
    assert result["inferred_delivery_engine"] == "UNKNOWN"
    assert "delivery_type" in result["questions_to_ask"]


def test_consistent_experience_is_inferred_and_skipped():
    profile = PartnerIntentProfile(
        partner_user_id="U-CURTIS", demand_count=10, core_demand_pct=100.0, specialty_demand_pct=0.0,
        avg_experience_level=8.0, experience_level_std_dev=0.5,
    )
    result = infer_intent(profile)
    assert result["inferred_experience_level"] == 8.0
    assert "experience_level" in result["questions_to_skip"]


def test_inconsistent_experience_is_asked():
    profile = PartnerIntentProfile(
        partner_user_id="U-CURTIS", demand_count=10, core_demand_pct=100.0, specialty_demand_pct=0.0,
        avg_experience_level=5.0, experience_level_std_dev=3.0,
    )
    result = infer_intent(profile)
    assert result["inferred_experience_level"] == "UNKNOWN"
    assert "experience_level" in result["questions_to_ask"]


def test_consistent_billing_range_is_inferred_and_skipped():
    profile = PartnerIntentProfile(
        partner_user_id="U-CURTIS", demand_count=10, core_demand_pct=100.0, specialty_demand_pct=0.0,
        typical_billing_range_min_usd_cents=11000, typical_billing_range_max_usd_cents=12500,
    )
    result = infer_intent(profile)
    assert result["inferred_billing_range"] == {"min": 11000, "max": 12500}
    assert "billing_range" in result["questions_to_skip"]


def test_wide_billing_range_is_asked_not_inferred():
    profile = PartnerIntentProfile(
        partner_user_id="U-CURTIS", demand_count=10, core_demand_pct=100.0, specialty_demand_pct=0.0,
        typical_billing_range_min_usd_cents=5000, typical_billing_range_max_usd_cents=20000,
    )
    result = infer_intent(profile)
    assert result["inferred_billing_range"] == "UNKNOWN"
    assert "billing_range" in result["questions_to_ask"]


# ---------------------------------------------------------------------------
# New client detection -- AC-4
# ---------------------------------------------------------------------------

def test_detect_new_client_finds_existing_case_insensitively(db_session):
    db_session.add(Client(company_name="Omega Insurance"))
    db_session.commit()

    existing, is_new = detect_new_client(db_session, "omega insurance")
    assert is_new is False
    assert existing.company_name == "Omega Insurance"


def test_detect_new_client_flags_unknown_client(db_session):
    existing, is_new = detect_new_client(db_session, "Zephyr Mutual")
    assert existing is None
    assert is_new is True


def test_create_pending_verification_client_never_silently_typed(db_session):
    client = create_pending_verification_client(db_session, "Zephyr Mutual")
    db_session.commit()
    assert client.status == "PENDING_VERIFICATION"

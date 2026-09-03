"""
S-267 (BU Revenue Target) + PartnerGoal (CEO-set only) + the FY
carry-forward design: a negative year's shortfall accumulates as a
persistent deficit; a positive year pays that deficit down first, and
only the leftover counts as that year's own surplus -- never banked
import logging
forward as credit.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.rbac_template import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.revenue_target_service import (
    RevenueTargetValidationError, get_bu_target_vs_actual, get_partner_multi_year_position,
    set_bu_revenue_target, set_partner_goal, status_band,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

def _make_invoice(db, client, amount_usd_cents, year):
    project = Project(client_id=client.id, name=f"{client.company_name} Engagement", status="ACTIVE", billing_type="TIME_AND_MATERIALS")
    db.add(project)
    db.commit()
    invoice = Invoice(
        client_id=client.id, project_id=project.id, status="PAID", total_usd_cents=amount_usd_cents,
        billing_period_start=datetime(year, 1, 1).date(), billing_period_end=datetime(year, 1, 31).date(),
        created_at=datetime(year, 1, 15),
    )
    db.add(invoice)
    db.commit()
    return invoice

def test_status_band_thresholds():
    assert status_band(96, 100) == "ON_TRACK"
    assert status_band(85, 100) == "AT_RISK"
    assert status_band(50, 100) == "BEHIND"
    assert status_band(0, 0) == "NO_TARGET"

def test_bu_target_vs_actual(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    builders = Client(company_name="Builders", business_unit_id=axion.id)
    db_session.add(builders)
    db_session.commit()

    set_bu_revenue_target(db_session, business_unit_id=axion.id, target_period="ANNUAL", fiscal_year=2026, target_amount_usd_cents=1000000, created_by="hemant")
    _make_invoice(db_session, builders, 900000, 2026)

    result = get_bu_target_vs_actual(db_session, axion.id, "ANNUAL", 2026)

    assert result["target_amount_usd_cents"] == 1000000
    assert result["actual_usd_cents"] == 900000
    assert result["status"] == "AT_RISK"  # 90% -- below the 95% ON_TRACK threshold

def test_bu_target_is_append_only_most_recent_wins(db_session):
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()

    set_bu_revenue_target(db_session, business_unit_id=axion.id, target_period="ANNUAL", fiscal_year=2026, target_amount_usd_cents=1000000, created_by="hemant")
    set_bu_revenue_target(db_session, business_unit_id=axion.id, target_period="ANNUAL", fiscal_year=2026, target_amount_usd_cents=1500000, created_by="hemant", notes="revised up")

    result = get_bu_target_vs_actual(db_session, axion.id, "ANNUAL", 2026)
    assert result["target_amount_usd_cents"] == 1500000  # most recent, old row still exists in history

def test_partner_goal_requires_ceo(db_session):
    troy = Users(UserID="troy", UserRole="Partner", UserEmail="troy@blitzenx.com", UserPassword="h")
    db_session.add(troy)
    db_session.commit()

    with pytest.raises(RevenueTargetValidationError):
        set_partner_goal(
            db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2026,
            target_amount_usd_cents=2000000, created_by_user=troy,
        )

def test_partner_goal_ceo_can_set(db_session):
    avinash = Users(UserID="avinash", UserRole="Super User", UserEmail="avinash@blitzenx.com", UserPassword="h")
    db_session.add(avinash)
    db_session.commit()

    goal = set_partner_goal(
        db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2026,
        target_amount_usd_cents=2000000, created_by_user=avinash,
    )
    assert goal.created_by == "avinash"
    assert goal.partner_user_id == "troy"

def test_fy_carry_forward_deficit_persists_and_gets_paid_down(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = Users(UserID="troy", UserRole="Partner", UserEmail="troy@blitzenx.com", UserPassword="h", business_unit_id=axion.id)
    avinash = Users(UserID="avinash", UserRole="Super User", UserEmail="avinash@blitzenx.com", UserPassword="h")
    db_session.add_all([troy, avinash])
    db_session.commit()
    builders = Client(company_name="Builders", business_unit_id=axion.id)
    db_session.add(builders)
    db_session.commit()

    # 2026: target 1,000,000, actual 700,000 -> -300,000 shortfall.
    set_partner_goal(db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2026, target_amount_usd_cents=1000000, created_by_user=avinash)
    _make_invoice(db_session, builders, 700000, 2026)

    # 2027: target 1,000,000, actual 1,200,000 -> +200,000, pays down
    # 200k of the 300k deficit, no surplus shown yet.
    set_partner_goal(db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2027, target_amount_usd_cents=1000000, created_by_user=avinash)
    _make_invoice(db_session, builders, 1200000, 2027)

    position = get_partner_multi_year_position(db_session, "troy")

    assert position["years"][0]["variance_usd_cents"] == -300000
    assert position["years"][0]["cumulative_deficit_usd_cents"] == 300000
    assert position["years"][0]["current_fy_surplus_usd_cents"] == 0

    assert position["years"][1]["variance_usd_cents"] == 200000
    assert position["years"][1]["cumulative_deficit_usd_cents"] == 100000  # 300k - 200k paydown
    assert position["years"][1]["current_fy_surplus_usd_cents"] == 0  # fully absorbed by paydown

    assert position["cumulative_deficit_usd_cents"] == 100000

def test_fy_surplus_shown_once_deficit_fully_paid(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    axion = BusinessUnit(name="Axion")
    db_session.add(axion)
    db_session.commit()
    troy = Users(UserID="troy", UserRole="Partner", UserEmail="troy@blitzenx.com", UserPassword="h", business_unit_id=axion.id)
    avinash = Users(UserID="avinash", UserRole="Super User", UserEmail="avinash@blitzenx.com", UserPassword="h")
    db_session.add_all([troy, avinash])
    db_session.commit()
    builders = Client(company_name="Builders", business_unit_id=axion.id)
    db_session.add(builders)
    db_session.commit()

    # 2026: -300,000 deficit.
    set_partner_goal(db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2026, target_amount_usd_cents=1000000, created_by_user=avinash)
    _make_invoice(db_session, builders, 700000, 2026)

    # 2027: +500,000 -- pays off the 300k deficit fully, 200k left over as real surplus.
    set_partner_goal(db_session, partner_user_id="troy", target_period="ANNUAL", fiscal_year=2027, target_amount_usd_cents=1000000, created_by_user=avinash)
    _make_invoice(db_session, builders, 1500000, 2027)

    position = get_partner_multi_year_position(db_session, "troy")

    assert position["years"][1]["cumulative_deficit_usd_cents"] == 0
    assert position["years"][1]["current_fy_surplus_usd_cents"] == 200000
    assert position["cumulative_deficit_usd_cents"] == 0
    assert position["current_fy_surplus_usd_cents"] == 200000

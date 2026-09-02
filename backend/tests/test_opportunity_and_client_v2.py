"""
Proves HRMS-0201's exactly-one-primary-contact rule (extending the
existing Client model rather than forking it into a second clients
table -- see app.models.client's module docstring), and HRMS-0207/0209/
import logging
0210/0211/0215's opportunity + revenue-potential calculations.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client, ClientContact
from app.models.demand import Demand, DemandHistory
from app.models.opportunity import Opportunity

from app.services.client_service import set_primary_contact
from app.services.opportunity_service import (
    create_opportunity,
    transition_stage,
    calculate_weighted_forecast,
    aggregate_weighted_forecast,
    calculate_pipeline_coverage_ratio,
    calculate_revenue_potential,
    recalculate_revenue_potential,
    create_role_demand_from_opportunity,
    get_opportunity_revenue_rollup,
    OpportunityValidationError,
    InvalidStageTransition,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Client.__table__, ClientContact.__table__,
        Demand.__table__, DemandHistory.__table__, Opportunity.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def tenant_and_client(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance", country="USA")
    db_session.add(client)
    db_session.commit()
    return tenant, client


# ---------------------------------------------------------------------------
# HRMS-0201 BR-0201-02: exactly one primary contact
# ---------------------------------------------------------------------------

def test_set_primary_contact_unsets_previous_primary(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    contact_a = ClientContact(client_id=client.id, name="Alice", email="alice@acme.com", role_type="PRIMARY", is_primary=True)
    contact_b = ClientContact(client_id=client.id, name="Bob", email="bob@acme.com", role_type="ACCOUNTS", is_primary=False)
    db_session.add_all([contact_a, contact_b])
    db_session.commit()

    set_primary_contact(db_session, client, contact_b)
    db_session.commit()

    db_session.refresh(contact_a)
    db_session.refresh(contact_b)
    assert contact_a.is_primary is False
    assert contact_b.is_primary is True


def test_set_primary_contact_rejects_contact_from_other_client(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    other_client = Client(tenant_id=tenant.id, company_name="Other Co")
    db_session.add(other_client)
    db_session.commit()
    foreign_contact = ClientContact(client_id=other_client.id, name="Eve", email="eve@other.com", role_type="PRIMARY")
    db_session.add(foreign_contact)
    db_session.commit()

    with pytest.raises(ValueError):
        set_primary_contact(db_session, client, foreign_contact)


# ---------------------------------------------------------------------------
# HRMS-0207: create_opportunity validation
# ---------------------------------------------------------------------------

def test_create_opportunity_rejects_non_positive_revenue(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    with pytest.raises(OpportunityValidationError):
        create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=0, probability_pct=50)


def test_create_opportunity_rejects_out_of_range_probability(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    with pytest.raises(OpportunityValidationError):
        create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100000, probability_pct=150)


def test_create_opportunity_success(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(
        db_session, tenant_id=tenant.id, client_id=client.id,
        revenue_value_usd_cents=50_000_00, probability_pct=40,
    )
    db_session.commit()
    assert opp.stage == "QUALIFICATION"


# ---------------------------------------------------------------------------
# HRMS-0209: shared weighted forecast calculation
# ---------------------------------------------------------------------------

def test_calculate_weighted_forecast(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(
        db_session, tenant_id=tenant.id, client_id=client.id,
        revenue_value_usd_cents=500_000_00, probability_pct=20,
    )
    db_session.commit()
    assert calculate_weighted_forecast(opp) == 100_000_00


def test_aggregate_weighted_forecast_sums_multiple(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp1 = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    opp2 = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=200_00, probability_pct=25)
    db_session.commit()
    # 50 + 50 = 100
    assert aggregate_weighted_forecast([opp1, opp2]) == 100_00


# ---------------------------------------------------------------------------
# HRMS-0215: pipeline coverage ratio
# ---------------------------------------------------------------------------

def test_pipeline_coverage_ratio():
    assert calculate_pipeline_coverage_ratio(300_00, 100_00) == 3.0


def test_pipeline_coverage_ratio_none_for_zero_target():
    assert calculate_pipeline_coverage_ratio(300_00, 0) is None


# ---------------------------------------------------------------------------
# Stage transitions
# ---------------------------------------------------------------------------

def test_transition_stage_success(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    db_session.commit()

    transition_stage(db_session, opp, "PROPOSAL")
    db_session.commit()
    assert opp.stage == "PROPOSAL"


def test_transition_stage_blocked_once_closed(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50, stage="WON")
    db_session.commit()

    with pytest.raises(InvalidStageTransition):
        transition_stage(db_session, opp, "PROPOSAL")


def test_transition_stage_rejects_invalid_stage(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    db_session.commit()

    with pytest.raises(InvalidStageTransition):
        transition_stage(db_session, opp, "BOGUS_STAGE")


# ---------------------------------------------------------------------------
# HRMS-0210/0211: role demand creation + revenue potential
# ---------------------------------------------------------------------------

def test_create_role_demand_from_opportunity(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=500_000_00, probability_pct=60)
    db_session.commit()

    demand = create_role_demand_from_opportunity(
        db_session, opp, tenant_id=tenant.id,
        job_title="Senior PolicyCenter Developer", required_skills='["Guidewire","PolicyCenter"]',
        min_experience_years=5.0, work_location="REMOTE",
        quantity=3, duration_hours=1000, billing_rate_usd_cents=125_00,
    )
    db_session.commit()

    assert demand.opportunity_id == opp.id
    assert demand.source_type == "OPPORTUNITY"
    assert demand.headcount == 3
    assert demand.client_id == client.id
    # bill_rate(12500) * duration(1000) * quantity(3)
    assert demand.revenue_potential_usd_cents == 125_00 * 1000 * 3


def test_create_role_demand_rejects_quantity_below_one(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    db_session.commit()

    with pytest.raises(ValueError):
        create_role_demand_from_opportunity(
            db_session, opp, tenant_id=tenant.id,
            job_title="QA", required_skills='["QA"]', min_experience_years=2.0,
            work_location="REMOTE", quantity=0, duration_hours=500, billing_rate_usd_cents=80_00,
        )


def test_recalculate_revenue_potential_updates_on_change(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=100_00, probability_pct=50)
    db_session.commit()

    demand = create_role_demand_from_opportunity(
        db_session, opp, tenant_id=tenant.id, job_title="Dev", required_skills='["GW"]',
        min_experience_years=5.0, work_location="REMOTE", quantity=1,
        duration_hours=1000, billing_rate_usd_cents=100_00,
    )
    db_session.commit()
    original = demand.revenue_potential_usd_cents

    demand.billing_rate_usd_cents = 200_00
    recalculate_revenue_potential(demand)
    db_session.commit()

    assert demand.revenue_potential_usd_cents == 200_00 * 1000 * 1
    assert demand.revenue_potential_usd_cents != original


def test_calculate_revenue_potential_none_when_missing_inputs(db_session):
    demand = Demand(
        client_id="c1", job_title="x", required_skills="[]",
        min_experience_years=1.0, work_location="REMOTE",
        billing_rate_usd_cents=None, duration_hours=1000,
    )
    assert calculate_revenue_potential(demand) is None


def test_opportunity_revenue_rollup_sums_linked_demands(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    opp = create_opportunity(db_session, tenant_id=tenant.id, client_id=client.id, revenue_value_usd_cents=500_000_00, probability_pct=60)
    db_session.commit()

    create_role_demand_from_opportunity(
        db_session, opp, tenant_id=tenant.id, job_title="Dev", required_skills='["GW"]',
        min_experience_years=5.0, work_location="REMOTE", quantity=2,
        duration_hours=1000, billing_rate_usd_cents=100_00,
    )
    create_role_demand_from_opportunity(
        db_session, opp, tenant_id=tenant.id, job_title="QA", required_skills='["QA"]',
        min_experience_years=3.0, work_location="REMOTE", quantity=1,
        duration_hours=500, billing_rate_usd_cents=80_00,
    )
    db_session.commit()

    expected = (100_00 * 1000 * 2) + (80_00 * 500 * 1)
    assert get_opportunity_revenue_rollup(db_session, opp) == expected

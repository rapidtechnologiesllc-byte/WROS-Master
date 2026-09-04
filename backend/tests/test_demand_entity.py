"""
Proves HRMS-0103: BR-01 (employment_type always W2_FULLTIME), BR-02
(sourcing gated on bench-first, R-04), BR-03 (auto-fill tracking), the
import logging
status state machine, and the duplicate-open-demand guard.

Throwaway SQLite -- never the real database.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.services.demand_service import (
    create_demand,
    transition_demand_status,
    enable_sourcing,
    record_placement,
    InvalidDemandTransition,
    DemandValidationError,
    BenchFirstNotChecked,
)

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__])
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
    client = Client(tenant_id=tenant.id, company_name="Acme Insurance")
    db_session.add(client)
    db_session.commit()
    return tenant, client

def _make_demand(db, tenant, client, **overrides):
    defaults = dict(
        tenant_id=tenant.id, client_id=client.id, job_title="Sr. Guidewire Developer",
        required_skills=json.dumps(["Guidewire", "PolicyCenter"]), min_experience_years=5.0,
        work_location="REMOTE", status="DRAFT",
    )
    defaults.update(overrides)
    demand = create_demand(db, **defaults)
    db.commit()
    return demand

# ---------------------------------------------------------------------------
# BR-01: employment_type always W2_FULLTIME (R-03)
# ---------------------------------------------------------------------------

def test_employment_type_defaults_to_w2_fulltime(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client)
    assert demand.employment_type == "W2_FULLTIME"

def test_negative_case_only_w2_fulltime_is_a_valid_enum_value(db_session, tenant_and_client):
    """Direct-API-bypass style negative test: even trying to force a
    different value must fail at the column/enum level."""
    tenant, client = tenant_and_client
    with pytest.raises(Exception):
        bad = _make_demand(db_session, tenant, client, employment_type="C2C")
        db_session.flush()

# ---------------------------------------------------------------------------
# BR-02 / R-04: bench-first gate
# ---------------------------------------------------------------------------

def test_negative_case_sourcing_blocked_without_bench_first(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, bench_first_checked=False)

    with pytest.raises(BenchFirstNotChecked):
        enable_sourcing(db_session, demand)
    assert demand.sourcing_enabled is False

def test_positive_case_sourcing_allowed_after_bench_first_checked(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, bench_first_checked=True)

    enable_sourcing(db_session, demand)
    assert demand.sourcing_enabled is True

def test_logged_override_path_sets_both_flags(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, bench_first_checked=False)

    enable_sourcing(db_session, demand, bench_first_override=True)
    assert demand.bench_first_checked is True
    assert demand.sourcing_enabled is True

# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------

def test_valid_transition_draft_to_open_with_required_fields(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client)

    transition_demand_status(db_session, demand, "OPEN")
    db_session.commit()
    assert demand.status == "OPEN"

def test_negative_case_cannot_open_demand_missing_required_fields(db_session, tenant_and_client):
    """
    required_skills/client_id/min_experience_years are NOT NULL at the
    column level (matching the spec's own CREATE TABLE), so a demand
    can never actually be persisted without them -- this test instead
    proves transition_demand_status()'s own runtime check catches a
    field that's blank at the Python level (in-memory, never committed
    with a null value), which is what step 4's "allowed when ... all
    set" validation is actually guarding against in practice (e.g. an
    empty string slipping through business-logic-level construction).
    """
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client)

    # no_autoflush: setting this in-memory would otherwise trigger an
    # autoflush on the next attribute access anywhere below (SQLAlchemy
    # expires all attributes after commit() by default, so the very next
    # read re-fetches from the DB -- flushing this invalid None first and
    # hitting the column's own NOT NULL constraint before this test even
    # gets to exercise transition_demand_status()'s own validation).
    with db_session.no_autoflush:
        demand.min_experience_years = None
        with pytest.raises(DemandValidationError):
            transition_demand_status(db_session, demand, "OPEN")

def test_negative_case_invalid_transition_rejected(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, status="FILLED")

    with pytest.raises(InvalidDemandTransition):
        transition_demand_status(db_session, demand, "OPEN")

def test_cancel_requires_reason_at_least_50_chars(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, status="OPEN")

    with pytest.raises(DemandValidationError):
        transition_demand_status(db_session, demand, "CANCELLED", reason="too short")

    long_reason = "Client put the role on indefinite hold due to internal reorg." * 1
    assert len(long_reason) >= 50
    transition_demand_status(db_session, demand, "CANCELLED", reason=long_reason)
    assert demand.status == "CANCELLED"

def test_duplicate_open_demand_rejected(db_session, tenant_and_client):
    tenant, client = tenant_and_client
    _make_demand(db_session, tenant, client, status="OPEN")

    with pytest.raises(DemandValidationError):
        _make_demand(db_session, tenant, client, status="OPEN")

# ---------------------------------------------------------------------------
# BR-03: auto-fill tracking
# ---------------------------------------------------------------------------

def test_positions_filled_increments_and_auto_transitions_to_filled(db_session, tenant_and_client):
    """
    Per HRMS-0103 step 3, FILLED is only reachable from IN_PROGRESS
    (OPEN -> IN_PROGRESS happens automatically once a submission is
    linked -- that's a later Phase 2 domain not yet built, so this test
    starts the demand already IN_PROGRESS, matching what the state
    would be by the time a real placement could occur).
    """
    tenant, client = tenant_and_client
    demand = _make_demand(db_session, tenant, client, status="IN_PROGRESS", headcount=2)

    record_placement(db_session, demand)
    db_session.commit()
    assert demand.positions_filled == 1
    assert demand.status == "IN_PROGRESS"

    record_placement(db_session, demand)
    db_session.commit()
    assert demand.positions_filled == 2
    assert demand.status == "FILLED"

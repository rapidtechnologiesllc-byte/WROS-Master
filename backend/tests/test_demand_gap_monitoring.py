"""
import logging
HRMS-1102 -- Workforce Demand Monitoring Agent.

Proves: BR-1102-01 (R-04 hard gate, reusing the existing
Demand.bench_first_checked flag, no bypass), BR-1102-03 (CRITICAL +
5-day-open pages the RM immediately via P0, bypassing business hours),
BR-1102-04 (append-only score history), and the AC-6 LLM-failure
default (WATCH, no alert created).

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand
from app.models.notification import Notification
from app.models.sourcing import DemandGapScore, SourcingAlert
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.demand_gap_monitoring_service import (
    classify_gap_severity,
    scan_demand_gap,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Client.__table__, Demand.__table__,
        DemandGapScore.__table__, SourcingAlert.__table__, Notification.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def demand(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    client = Client(company_name="Acme Carrier", tenant_id=tenant.id)
    db_session.add(client)
    db_session.commit()

    d = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Senior PC Developer",
        required_skills='["Guidewire PolicyCenter"]', min_experience_years=5,
        work_location="REMOTE", status="OPEN",
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(d)
    db_session.commit()
    return d, tenant


# ---------------------------------------------------------------------------
# classify_gap_severity
# ---------------------------------------------------------------------------

def test_classify_defaults_to_watch_when_no_classifier_wired():
    severity, rationale, llm_parse_failed = classify_gap_severity(
        required_skills="x", bench_match_count=0, days_open=3, demand_type="PLANNED",
    )
    assert severity == "WATCH"
    assert llm_parse_failed is True


def test_classify_uses_classifier_result():
    classifier = lambda payload: {"gap_severity": "CRITICAL", "rationale": "zero bench match"}
    severity, rationale, llm_parse_failed = classify_gap_severity(
        required_skills="x", bench_match_count=0, days_open=6, demand_type="PLANNED",
        llm_classifier=classifier,
    )
    assert severity == "CRITICAL"
    assert rationale == "zero bench match"
    assert llm_parse_failed is False


def test_classify_defaults_to_watch_when_classifier_raises():
    def broken(payload):
        raise RuntimeError("API down")
    severity, rationale, llm_parse_failed = classify_gap_severity(
        required_skills="x", bench_match_count=0, days_open=6, demand_type="PLANNED",
        llm_classifier=broken,
    )
    assert severity == "WATCH"
    assert llm_parse_failed is True


def test_classify_defaults_to_watch_on_malformed_severity():
    classifier = lambda payload: {"gap_severity": "SUPER_URGENT"}
    severity, rationale, llm_parse_failed = classify_gap_severity(
        required_skills="x", bench_match_count=0, days_open=6, demand_type="PLANNED",
        llm_classifier=classifier,
    )
    assert severity == "WATCH"
    assert llm_parse_failed is True


# ---------------------------------------------------------------------------
# scan_demand_gap -- BR-1102-01 R-04 gate
# ---------------------------------------------------------------------------

def test_no_alert_created_when_bench_first_not_checked(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = False
    db_session.add(d)
    db_session.commit()

    score = scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "CRITICAL", "rationale": "no bench"},
    )
    db_session.commit()

    assert score.gap_severity == "CRITICAL"
    assert db_session.query(SourcingAlert).count() == 0


def test_alert_created_when_bench_first_checked_and_severity_alert(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    db_session.add(d)
    db_session.commit()

    scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "ALERT", "rationale": "thin bench"},
    )
    db_session.commit()

    alerts = db_session.query(SourcingAlert).all()
    assert len(alerts) == 1
    assert alerts[0].severity == "ALERT"
    assert alerts[0].status == "OPEN"


def test_no_alert_created_for_watch_or_none_severity(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    db_session.add(d)
    db_session.commit()

    scan_demand_gap(db_session, d, bench_match_count=5)  # no classifier -> WATCH
    db_session.commit()

    assert db_session.query(SourcingAlert).count() == 0


def test_router_evaluate_called_before_alert_creation(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    db_session.add(d)
    db_session.commit()

    calls = []

    def fake_router(**kwargs):
        calls.append(kwargs)

    scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "CRITICAL", "rationale": "x"},
        router_evaluate=fake_router,
    )
    db_session.commit()

    assert len(calls) == 1
    assert calls[0]["agent_id"] == "HRMS-1102"
    assert calls[0]["action_type"] == "sourcing_alert_create"
    assert calls[0]["risk_tier"] == "LOW"
    assert db_session.query(SourcingAlert).count() == 1


# ---------------------------------------------------------------------------
# BR-1102-03 -- CRITICAL + 5-day-open escalation
# ---------------------------------------------------------------------------

def test_critical_over_five_days_pages_rm_via_p0(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    d.created_at = datetime.utcnow() - timedelta(days=6)
    db_session.add(d)
    db_session.commit()

    rm = Users(UserID="U-RM", UserRole="Recruiter", UserEmail="rm@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(rm)
    db_session.commit()

    scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "CRITICAL", "rationale": "no bench match, 6 days open"},
        rm_user=rm,
    )
    db_session.commit()

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].priority_tier == "P0"


def test_critical_under_five_days_does_not_page(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    d.created_at = datetime.utcnow() - timedelta(days=2)
    db_session.add(d)
    db_session.commit()

    rm = Users(UserID="U-RM", UserRole="Recruiter", UserEmail="rm@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(rm)
    db_session.commit()

    scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "CRITICAL", "rationale": "no bench match"},
        rm_user=rm,
    )
    db_session.commit()

    assert db_session.query(Notification).count() == 0


def test_no_page_without_an_rm_user_supplied(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    d.created_at = datetime.utcnow() - timedelta(days=6)
    db_session.add(d)
    db_session.commit()

    scan_demand_gap(
        db_session, d, bench_match_count=0,
        llm_classifier=lambda p: {"gap_severity": "CRITICAL", "rationale": "no bench match"},
    )
    db_session.commit()

    assert db_session.query(Notification).count() == 0


# ---------------------------------------------------------------------------
# BR-1102-04 -- append-only score history
# ---------------------------------------------------------------------------

def test_multiple_scans_accumulate_history_not_overwrite(db_session, demand):
    d, tenant = demand
    d.bench_first_checked = True
    db_session.add(d)
    db_session.commit()

    scan_demand_gap(db_session, d, bench_match_count=3)
    db_session.commit()
    scan_demand_gap(db_session, d, bench_match_count=1)
    db_session.commit()
    scan_demand_gap(db_session, d, bench_match_count=0)
    db_session.commit()

    scores = db_session.query(DemandGapScore).filter(DemandGapScore.demand_id == d.id).all()
    assert len(scores) == 3
    assert sorted(s.bench_match_count for s in scores) == [0, 1, 3]

"""Hiring analytics: source of hire, each recruiter's results and open positions against hires, read from the
hiring pipeline's stages and their history, inside the caller's tenant and business-unit scope."""
from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.candidate_ownership import POOL_BU, CandidateOwnership
from app.models.hiring_pipeline import HiringPipeline, HiringPipelineEvent
from app.services.hiring_analytics_service import HiringAnalyticsError, hiring_analytics
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.test_core_certification import _h, _user

TENANT = 7421  # its own tenant, so the counts are exactly what each test creates
TODAY = date(2026, 11, 9)
ADDED = datetime(2026, 10, 1, 9, 0)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def leader(db):
    """An org-level user of the test tenant: sees every business unit."""
    return factories.user(db, TENANT, role_template_id=factories.role(db, TENANT, org_level_access=True).id)


def _candidate(db, *, source=None, recruiter=None, added=ADDED, tenant_id=TENANT, **fields):
    return factories.candidate(db, tenant_id, recruitment_source=source, candidateCreatedAt=added,
                               assigned_recruiter_id=recruiter.UserID if recruiter else None, **fields)


def _pipeline(db, candidate, stage, *, history=(), job=None, employee=None, closed=False, tenant_id=TENANT):
    """A pipeline now at `stage`; history is (to_stage, when) pairs it went through."""
    row = HiringPipeline(tenant_id=tenant_id, candidate_id=candidate.candidateID, stage=stage,
                         job_id=job.jobID if job else None, employee_id=employee.id if employee else None,
                         stage_entered_at=datetime(2026, 10, 20), closed_at=datetime(2026, 10, 21) if closed else None)
    db.add(row)
    db.flush()
    for to_stage, when in history:
        db.add(HiringPipelineEvent(pipeline_id=row.id, to_stage=to_stage, created_at=when))
    db.flush()
    return row


def _by_label(rows):
    return {row["label"]: row for row in rows}


def _report(db, user, **kwargs):
    return hiring_analytics(db, user, today=TODAY, **kwargs)


# ------------------------------------------------------------------------------ source of hire

def test_each_source_shows_how_far_its_candidates_got(db, leader):
    _pipeline(db, _candidate(db, source="LINKEDIN"), "SCREEN")
    _pipeline(db, _candidate(db, source="LINKEDIN"), "L2", history=[("L1", datetime(2026, 10, 5))])
    hired = _candidate(db, source="EMPLOYEE_REFERRAL")
    _pipeline(db, hired, "BENCH", employee=factories.employee(db, TENANT),
              history=[("L1", datetime(2026, 10, 3)), ("OFFER", datetime(2026, 10, 11, 9, 0)), ("ACCEPTED", datetime(2026, 10, 12))])
    _candidate(db)  # no pipeline yet, no source recorded: counted as added only, under its channel

    report = _report(db, leader)
    sources = _by_label(report["sources"])
    assert sources["Linkedin"] == {"label": "Linkedin", "added": 2, "interviewed": 1, "offered": 0, "accepted": 0, "hired": 0,
                                   "rejected": 0, "hire_rate_pct": 0.0, "avg_days_to_offer": None}
    assert sources["Employee Referral"] == {"label": "Employee Referral", "added": 1, "interviewed": 1, "offered": 1, "accepted": 1,
                                            "hired": 1, "rejected": 0, "hire_rate_pct": 100.0, "avg_days_to_offer": 10.0}
    assert sources["Direct"]["added"] == 1 and sources["Direct"]["interviewed"] == 0
    assert report["sources"][0]["label"] == "Employee Referral"  # most hires first
    assert (report["totals"]["added"], report["totals"]["hired"], report["totals"]["hire_rate_pct"]) == (4, 1, 25.0)


def test_a_rejected_candidate_keeps_the_stage_they_reached(db, leader):
    """Rejected after the offer: the history still counts the interview and the offer."""
    candidate = _candidate(db, source="LINKEDIN")
    _pipeline(db, candidate, "REJECTED", closed=True,
              history=[("L1", datetime(2026, 10, 4)), ("OFFER", datetime(2026, 10, 6, 9, 0)), ("REJECTED", datetime(2026, 10, 21))])
    row = _by_label(_report(db, leader)["sources"])["Linkedin"]
    assert (row["interviewed"], row["offered"], row["hired"], row["rejected"], row["avg_days_to_offer"]) == (1, 1, 0, 1, 5.0)


def test_rejected_once_then_reopened_is_not_counted_as_rejected(db, leader):
    candidate = _candidate(db, source="LINKEDIN")
    _pipeline(db, candidate, "REJECTED", closed=True)
    _pipeline(db, candidate, "L1")
    row = _by_label(_report(db, leader)["sources"])["Linkedin"]
    assert (row["added"], row["interviewed"], row["rejected"]) == (1, 1, 0)


def test_only_candidates_added_in_the_period_and_not_merged_away(db, leader):
    kept = _candidate(db, source="A")
    _candidate(db, source="B", added=datetime(2026, 5, 1))  # before the default 90 days
    _candidate(db, source="C", merged_into_id=kept.candidateID)  # a duplicate folded into another record
    assert [r["label"] for r in _report(db, leader)["sources"]] == ["A"]
    wide = _report(db, leader, date_from=date(2026, 4, 1), date_to=date(2026, 11, 9))
    assert sorted(r["label"] for r in wide["sources"]) == ["A", "B"]
    last_day = _report(db, leader, date_from=date(2026, 10, 1), date_to=date(2026, 10, 1))
    assert last_day["totals"]["added"] == 1  # the end date is included


def test_a_period_that_makes_no_sense_is_refused(db, leader):
    with pytest.raises(HiringAnalyticsError, match="start date is after"):
        _report(db, leader, date_from=date(2026, 11, 1), date_to=date(2026, 10, 1))
    with pytest.raises(HiringAnalyticsError, match="at most 731 days"):
        _report(db, leader, date_from=date(2020, 1, 1), date_to=date(2026, 10, 1))


# ------------------------------------------------------------------------------ recruiters

def test_each_recruiter_gets_their_own_candidates(db, leader):
    asha = factories.user(db, TENANT, UserName="Asha")
    ben = factories.user(db, TENANT, UserName="Ben")
    _pipeline(db, _candidate(db, recruiter=asha), "BENCH", employee=factories.employee(db, TENANT))
    _pipeline(db, _candidate(db, recruiter=asha), "L1")
    _pipeline(db, _candidate(db, recruiter=ben), "SCREEN")
    _candidate(db)

    recruiters = _report(db, leader)["recruiters"]
    assert [(r["label"], r["recruiter_id"], r["added"], r["interviewed"], r["hired"]) for r in recruiters] == [
        ("Asha", asha.UserID, 2, 2, 1), ("Ben", ben.UserID, 1, 0, 0), ("No recruiter", None, 1, 0, 0)]


# ------------------------------------------------------------------------------ positions

def test_open_jobs_show_positions_against_people_who_joined(db, leader):
    big = factories.job(db, TENANT, jobTitle="Guidewire Developer", jobStatus="active", noOfPositions=3)
    small = factories.job(db, TENANT, jobTitle="Analyst", jobStatus="public", noOfPositions=None)
    factories.job(db, TENANT, jobTitle="Closed role", jobStatus="closed", noOfPositions=5)
    factories.job(db, TENANT, jobTitle="Deleted role", jobStatus="active", is_deleted=True)
    _pipeline(db, _candidate(db), "ALLOCATED", job=big, employee=factories.employee(db, TENANT))
    _pipeline(db, _candidate(db), "OFFER", job=big)
    _pipeline(db, _candidate(db), "L1", job=big)
    _pipeline(db, _candidate(db), "REJECTED", job=big, closed=True)
    _pipeline(db, _candidate(db, added=datetime(2025, 1, 1)), "BENCH", job=small)  # hired long before the period

    report = _report(db, leader)
    assert [(p["title"], p["positions"], p["hired"], p["offers_out"], p["in_progress"], p["still_to_hire"])
            for p in report["positions"]] == [("Guidewire Developer", 3, 1, 1, 1, 2), ("Analyst", 1, 1, 0, 0, 0)]
    assert report["position_totals"] == {"positions": 4, "hired": 2, "offers_out": 1, "in_progress": 1, "still_to_hire": 2}


# ------------------------------------------------------------------------------ scope

def test_a_business_unit_user_sees_their_unit_and_the_org_pool_only(db, leader):
    mine, other = factories.business_unit(db, TENANT), factories.business_unit(db, TENANT)
    member = factories.user(db, TENANT, business_unit_id=mine.id,
                            role_template_id=factories.role(db, TENANT, org_level_access=False).id)
    pooled, own, foreign = _candidate(db, source="POOL"), _candidate(db, source="MINE"), _candidate(db, source="THEIRS")
    db.add_all([CandidateOwnership(candidateID=own.candidateID, pool_status=POOL_BU, owned_by_bu_id=mine.id),
                CandidateOwnership(candidateID=foreign.candidateID, pool_status=POOL_BU, owned_by_bu_id=other.id)])
    factories.job(db, TENANT, jobTitle="Mine", jobStatus="active", business_unit_id=mine.id)
    factories.job(db, TENANT, jobTitle="Theirs", jobStatus="active", business_unit_id=other.id)
    db.flush()

    scoped = _report(db, member)
    assert sorted(r["label"] for r in scoped["sources"]) == ["Mine", "Pool"]
    assert [p["title"] for p in scoped["positions"]] == ["Mine"]
    everything = _report(db, leader)
    assert sorted(r["label"] for r in everything["sources"]) == ["Mine", "Pool", "Theirs"]
    assert sorted(p["title"] for p in everything["positions"]) == ["Mine", "Theirs"]


def test_another_tenant_is_never_counted(db, leader):
    _candidate(db, source="OURS")
    stranger = _candidate(db, source="NOT_OURS", tenant_id=TENANT + 1)
    _pipeline(db, stranger, "BENCH", tenant_id=TENANT + 1)
    factories.job(db, TENANT + 1, jobTitle="Not ours", jobStatus="active")
    report = _report(db, leader)
    assert [r["label"] for r in report["sources"]] == ["Ours"] and report["positions"] == []


# ------------------------------------------------------------------------------ route

def test_the_route_answers_for_a_role_with_candidates_and_refuses_one_without(db, api):
    viewer = _user(db, full_access_role(db), "Recruiter")
    outsider = _user(db, factories.role(db, 1), "Outsider")
    marker = f"SRC{factories.uid()}".upper()
    _pipeline(db, _candidate(db, source=marker, added=datetime.utcnow(), tenant_id=1), "L1", tenant_id=1)
    db.commit()

    answer = api.get("/api/v1/analytics/hiring", headers=_h(viewer))
    assert answer.status_code == 200, answer.text
    row = _by_label(answer.json()["sources"])[marker.title()]
    assert (row["added"], row["interviewed"], row["hired"]) == (1, 1, 0)
    assert api.get("/api/v1/analytics/hiring?date_from=2026-11-01&date_to=2026-10-01", headers=_h(viewer)).status_code == 400
    assert api.get("/api/v1/analytics/hiring", headers=_h(outsider)).status_code == 403

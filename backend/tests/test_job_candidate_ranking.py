"""The one ranking rule for "who fits this job": the job's tenant only, the viewer's business
units only, the 5-year floor and the job's own minimum at every call, canonical skill names
(tagged skills beat free text), and a stable order."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_ownership import POOL_BU, CandidateOwnership
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.tenant import Tenant
from app.models.user import Jobs
from app.services.job_candidate_ranking_service import rank_candidates_for_job
from app.services.skill_matching_service import SkillMatchingService
from tests.scope_fixtures import two_bu_world


def _uid():
    return uuid.uuid4().hex[:8]


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
def tenants(db):
    for tid in (1, 2):
        if db.query(Tenant).filter_by(id=tid).first() is None:
            db.add(Tenant(id=tid, name=f"tenant-{tid}"))
    db.flush()


@pytest.fixture
def skill():
    """A skill nobody else in the test database has, so results are only this test's candidates."""
    return f"Rails{_uid()}"


def _job(db, skills, *, tenant_id=1, min_years=None, mode="AND", work_location="REMOTE", location="Remote"):
    job = Jobs(tenant_id=tenant_id, jobTitle="Rails Developer", jobDescription="d",
               jobSkills=", ".join(s if isinstance(s, str) else s["name"] for s in skills),
               required_skills_canonical=[s if isinstance(s, dict) else {"name": s} for s in skills],
               job_skills_boolean_mode=mode, jobExperience="5+ years", jobLocation=location,
               work_location=work_location, min_experience_years=min_years, jobStatus="active")
    db.add(job)
    db.flush()
    return job


def _cand(db, *, months=72, text=None, tags=(), tenant_id=1, created=None, location="Pune", name="Priya"):
    cand = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"{_uid()}@example.com", candidatePassword="x",
                     candidateFirstName=name, candidateLastName=_uid(), tenant_id=tenant_id,
                     total_experience_months=months, candidateSkills=text, candidateCurrentLocation=location)
    if created:
        cand.candidateCreatedAt = created
    db.add(cand)
    db.flush()
    for tag in tags:
        db.add(CandidateSkillTag(tenant_id=str(tenant_id), candidate_id=cand.candidateID, skill_canonical=tag))
    db.flush()
    return cand


def _ids(results):
    return [r.candidate_id for r in results]


def test_a_perfect_match_in_another_tenant_is_never_returned(db, tenants, skill):
    job = _job(db, [skill])
    mine = _cand(db, tags=[skill])
    theirs = _cand(db, tags=[skill], tenant_id=2, months=200)
    ids = _ids(rank_candidates_for_job(db, job))
    assert mine.candidateID in ids and theirs.candidateID not in ids


def test_viewer_sees_only_the_org_pool_and_their_own_business_units(db, tenants, skill):
    w = two_bu_world(db)
    job = _job(db, [skill])
    pool, own, other = _cand(db, tags=[skill]), _cand(db, tags=[skill]), _cand(db, tags=[skill])
    db.add_all([CandidateOwnership(candidateID=own.candidateID, pool_status=POOL_BU, owned_by_bu_id=w.bu_a.id),
                CandidateOwnership(candidateID=other.candidateID, pool_status=POOL_BU, owned_by_bu_id=w.bu_b.id)])
    db.flush()
    seen = set(_ids(rank_candidates_for_job(db, job, viewer=w.partner_a)))
    assert {pool.candidateID, own.candidateID} <= seen and other.candidateID not in seen
    assert other.candidateID in _ids(rank_candidates_for_job(db, job, viewer=w.org_user))


def test_experience_gates_hold_at_every_call(db, tenants, skill):
    job = _job(db, [skill], min_years=6)
    short = _cand(db, tags=[skill], months=48)          # under the 5-year floor
    unverified = _cand(db, tags=[skill], months=None)    # unverified fails closed
    under_job = _cand(db, tags=[skill], months=66)       # over the floor, under the job's 6 years
    fits = _cand(db, tags=[skill], months=72)
    ids = _ids(rank_candidates_for_job(db, job))
    assert ids == [fits.candidateID]
    assert short.candidateID not in ids and unverified.candidateID not in ids and under_job.candidateID not in ids


def test_tagged_skill_beats_free_text_and_ties_keep_a_stable_order(db, tenants, skill):
    job = _job(db, [skill])
    now = datetime(2026, 1, 1)
    text_only = _cand(db, text=f"Excel, {skill}", months=200, created=now - timedelta(days=30))
    later = _cand(db, tags=[skill], months=72, created=now)
    earlier = _cand(db, tags=[skill], months=72, created=now - timedelta(days=1))
    ranked = rank_candidates_for_job(db, job)
    assert _ids(ranked) == [earlier.candidateID, later.candidateID, text_only.candidateID]
    assert [r.score for r in ranked] == [100, 100, 80] and ranked[0].matched == [skill]
    assert _ids(rank_candidates_for_job(db, job)) == _ids(ranked)
    assert _ids(rank_candidates_for_job(db, job, exclude_ids=[earlier.candidateID]))[0] == later.candidateID


def test_more_experience_wins_a_score_tie(db, tenants, skill):
    job = _job(db, [skill])
    junior = _cand(db, tags=[skill], months=70, created=datetime(2020, 1, 1))
    senior = _cand(db, tags=[skill], months=120, created=datetime(2026, 1, 1))
    assert _ids(rank_candidates_for_job(db, job)) == [senior.candidateID, junior.candidateID]


def test_skill_names_are_normalised_on_both_sides(db, tenants, skill):
    """'Core Java' in the candidate's text and 'J2EE' on the job are both the canonical 'Java'."""
    job = _job(db, [{"name": "J2EE", "is_primary": True}, skill])
    cand = _cand(db, text="Core Java", tags=[skill])
    result = SkillMatchingService.score_skills(SkillMatchingService.job_skills(job),
                                               SkillMatchingService.candidate_skills(db, cand))
    assert result["matched"] == ["Java", skill] and result["missing_mandatory"] == []
    assert cand.candidateID in _ids(rank_candidates_for_job(db, job))


def test_and_mode_needs_every_skill_or_mode_only_the_primary_ones(db, tenants, skill):
    skills = [{"name": f"{skill}A", "is_primary": True}, f"{skill}B", f"{skill}C"]
    cand = _cand(db, tags=[f"{skill}A", f"{skill}B"])
    assert cand.candidateID not in _ids(rank_candidates_for_job(db, _job(db, skills, mode="AND")))
    assert cand.candidateID in _ids(rank_candidates_for_job(db, _job(db, skills, mode="OR")))
    no_primary = _cand(db, tags=[f"{skill}B", f"{skill}C"])
    assert no_primary.candidateID not in _ids(rank_candidates_for_job(db, _job(db, skills, mode="OR")))


def test_onsite_job_draws_only_from_its_location(db, tenants, skill):
    job = _job(db, [skill], work_location="ONSITE", location="Pune")
    local, remote = _cand(db, tags=[skill], location="Pune, India"), _cand(db, tags=[skill], location="Austin")
    ids = _ids(rank_candidates_for_job(db, job))
    assert local.candidateID in ids and remote.candidateID not in ids


def test_a_job_with_no_skills_matches_nobody_and_a_job_without_tenant_fails(db, tenants):
    job = _job(db, [])
    job.jobSkills, job.required_skills = "", "[]"
    assert rank_candidates_for_job(db, job) == []
    orphan = _job(db, ["X"])
    orphan.tenant_id = None
    with pytest.raises(ValueError):
        rank_candidates_for_job(db, orphan)


def test_skill_matching_service_scores_by_candidate_id_and_tags(db, tenants, skill):
    """It used to read candidate.skills / candidate.candidate_id (neither exists) and always scored 0."""
    job = _job(db, [skill])
    cand = _cand(db, tags=[skill])
    result = SkillMatchingService.score_candidate_skill_recency(cand.candidateID, job.jobID, db)
    assert result["overall_recency_score"] == 100 and result["can_proceed"] is True
    with pytest.raises(ValueError):
        SkillMatchingService.score_candidate_skill_recency("CAN-missing", job.jobID, db)


def test_explicit_c2c_and_1099_are_never_ranked_but_unknown_is(db, tenants, skill):
    job = _job(db, [skill])
    unknown = _cand(db, tags=[skill])
    india_contract = _cand(db, tags=[skill])
    india_contract.employment_type, india_contract.country = "CONTRACT", "IN"
    c2c = _cand(db, tags=[skill])
    c2c.employment_type, c2c.country = "C2C", "US"
    ten99 = _cand(db, tags=[skill])
    ten99.employment_type = "1099"
    db.flush()
    ranked = set(_ids(rank_candidates_for_job(db, job)))
    assert {unknown.candidateID, india_contract.candidateID} <= ranked
    assert not ranked & {c2c.candidateID, ten99.candidateID}

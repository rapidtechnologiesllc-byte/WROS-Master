"""Boolean search over candidates' skills, titles and resumes: the query language, where a term is found,
and who the caller may find."""
import pytest
from sqlalchemy.orm import Session

from app.models.candidate import CandidateStatus
from app.models.candidate_ownership import POOL_BU, CandidateOwnership
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.services.boolean_search_service import (
    BooleanQueryError, CompiledQuery, Document, parse_query, search_candidates, to_text,
)
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.test_core_certification import _h, _user

TENANT = 7431


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
    return factories.user(db, TENANT, role_template_id=factories.role(db, TENANT, org_level_access=True).id)


def _person(db, first, *, skills="", title=None, resume=None, tags=(), months=96, tenant_id=TENANT, **fields):
    candidate = factories.candidate(db, tenant_id, candidateFirstName=first, candidateLastName="Test", candidateSkills=skills,
                                    candidateJobTitle=title, total_experience_months=months, **fields)
    for tag in tags:
        db.add(CandidateSkillTag(tenant_id=str(tenant_id), candidate_id=candidate.candidateID, skill_canonical=tag))
    if resume is not None:
        db.add(CandidateResumeParsed(tenant_id=str(tenant_id), candidate_id=candidate.candidateID, raw_text=resume))
    db.flush()
    return candidate


def _names(result):
    return [row["name"].split()[0] for row in result["results"]]


# ------------------------------------------------------------------------------ the query language

@pytest.mark.parametrize("query, document, expected", [
    ("java", Document(skills="Java, SQL"), True),
    ("java", Document(skills="JavaScript"), False),                     # whole words only
    ("JAVA sql", Document(skills="java", resume="uses SQL daily"), True),  # side by side means AND, any case
    ("java sql", Document(skills="java"), False),
    ("java OR python", Document(skills="Python"), True),
    ("java AND NOT tester", Document(skills="Java", title="QA Tester"), False),
    ("java NOT tester", Document(skills="Java", title="Developer"), True),
    ('"claim center"', Document(resume="Worked on Claim   Center upgrades"), True),  # a phrase, spacing ignored
    ('"claim center"', Document(resume="center of the claim"), False),
    ("guidewire AND (policycenter OR billingcenter)", Document(skills="Guidewire", resume="BillingCenter 10"), True),
    ("guidewire AND (policycenter OR billingcenter)", Document(skills="Guidewire", resume="ClaimCenter 10"), False),
    ("c++ OR .net", Document(skills="C++, Go"), True),                  # symbols are part of the word
    ("c++", Document(skills="C, Go"), False),
    ("guidewire", Document(resume="5 years of GWPC configuration"), True),   # a known skill finds its other names
    ('"guidewire"', Document(resume="5 years of GWPC configuration"), False),  # a quoted one is exact
    ("a OR b AND c", Document(skills="a"), True),                       # AND binds tighter than OR
    ("(a OR b) AND c", Document(skills="a"), False),
])
def test_what_a_query_finds(query, document, expected):
    assert (CompiledQuery(query).match(document) is not None) is expected


@pytest.mark.parametrize("query, message", [
    ("", "Type what to search for"),
    ("   ", "Type what to search for"),
    ('java "open', "quoted phrase is not closed"),
    ("(java OR sql", "bracket is not closed"),
    ("java)", "closing bracket with no opening"),
    ("java AND", "ends with AND, OR or NOT"),
    ("AND java", "AND needs a word before it"),
    ("java OR OR sql", "OR needs a word before it"),
    ("()", "empty pair of brackets"),
    ("NOT tester", "at least one word to find"),
    ("x" * 2001, "too long"),
    (" ".join(f"t{i}" for i in range(61)), "61 terms"),
])
def test_a_query_that_cannot_be_read_says_what_to_fix(query, message):
    with pytest.raises(BooleanQueryError, match=message):
        parse_query(query)


def test_the_query_is_written_back_the_same_way_every_time():
    assert to_text(parse_query('java   and (sql or "pl sql") not tester')) == 'java AND (sql OR "pl sql") AND NOT tester'
    assert CompiledQuery(CompiledQuery('a b OR c').text).text == "(a AND b) OR c"


def test_a_match_says_where_each_term_was_found_and_scores_skills_above_resume():
    compiled = CompiledQuery("java AND (sql OR oracle) NOT tester")
    document = Document(skills="Java", title="Java Developer", resume="Built reports. Wrote complex SQL for billing. Deployed.")
    match = compiled.match(document)
    assert match.found == {"java": ["skills", "title"], "sql": ["resume"]}  # oracle absent, tester excluded: not listed
    assert match.score == 3 + 2 + 1
    assert "complex SQL for billing" in match.snippet


# ------------------------------------------------------------------------------ candidates

def test_search_reads_skills_tags_title_and_resume_and_orders_by_strength(db, leader):
    _person(db, "Skill", skills="Guidewire, PolicyCenter", title="PolicyCenter Developer")
    _person(db, "Tagged", tags=["Guidewire", "PolicyCenter"])
    _person(db, "Resume", skills="Java", resume="Implemented Guidewire PolicyCenter rating for a carrier.")
    _person(db, "Other", skills="Salesforce", resume="CRM projects")

    result = search_candidates(db, leader, "guidewire AND policycenter")
    assert _names(result) == ["Skill", "Tagged", "Resume"]
    assert (result["searched"], result["total"], result["query"]) == (4, 3, "guidewire AND policycenter")
    by_name = {row["name"].split()[0]: row for row in result["results"]}
    assert by_name["Resume"]["found"] == {"guidewire": ["resume"], "policycenter": ["resume"]}
    assert "Guidewire PolicyCenter rating" in by_name["Resume"]["snippet"] and by_name["Resume"]["has_resume"]
    assert by_name["Skill"]["found"]["policycenter"] == ["skills", "title"] and not by_name["Skill"]["has_resume"]


def test_filters_narrow_the_search(db, leader):
    _person(db, "Senior", skills="Java", months=120, candidateCurrentLocation="Hyderabad, India")
    _person(db, "Junior", skills="Java", months=24, candidateCurrentLocation="Hyderabad, India")
    _person(db, "Abroad", skills="Java", months=120, candidateCurrentLocation="Dallas, USA")
    assert _names(search_candidates(db, leader, "java", min_experience_years=5)) == ["Abroad", "Senior"]
    assert _names(search_candidates(db, leader, "java", location="hyderabad")) == ["Senior", "Junior"]
    assert _names(search_candidates(db, leader, "java", limit=1)) == ["Abroad"]
    with pytest.raises(BooleanQueryError, match="negative"):
        search_candidates(db, leader, "java", min_experience_years=-1)


def test_archived_and_merged_candidates_are_left_out(db, leader):
    kept = _person(db, "Kept", skills="Java")
    archived = _person(db, "Archived", skills="Java")
    db.add(CandidateStatus(candidateID=archived.candidateID, status="Inactive"))
    _person(db, "Merged", skills="Java", merged_into_id=kept.candidateID)
    db.flush()
    assert _names(search_candidates(db, leader, "java")) == ["Kept"]
    assert _names(search_candidates(db, leader, "java", include_archived=True)) == ["Archived", "Kept"]


def test_a_business_unit_user_finds_their_unit_and_the_org_pool_and_never_another_tenant(db, leader):
    mine, other = factories.business_unit(db, TENANT), factories.business_unit(db, TENANT)
    member = factories.user(db, TENANT, business_unit_id=mine.id,
                            role_template_id=factories.role(db, TENANT, org_level_access=False).id)
    _person(db, "Pool", skills="Java")
    own, foreign = _person(db, "Own", skills="Java"), _person(db, "Foreign", skills="Java")
    db.add_all([CandidateOwnership(candidateID=own.candidateID, pool_status=POOL_BU, owned_by_bu_id=mine.id),
                CandidateOwnership(candidateID=foreign.candidateID, pool_status=POOL_BU, owned_by_bu_id=other.id)])
    _person(db, "Stranger", skills="Java", tenant_id=TENANT + 1)
    db.flush()
    assert sorted(_names(search_candidates(db, member, "java"))) == ["Own", "Pool"]
    assert sorted(_names(search_candidates(db, leader, "java"))) == ["Foreign", "Own", "Pool"]


# ------------------------------------------------------------------------------ route

def test_the_route_searches_refuses_a_bad_query_and_needs_the_candidates_right(db, api):
    viewer = _user(db, full_access_role(db), "Recruiter")
    outsider = _user(db, factories.role(db, 1), "Outsider")
    marker = f"zq{factories.uid()}"
    _person(db, "Found", skills=f"Java, {marker}", tenant_id=1)
    db.commit()

    answer = api.get("/api/v1/candidate-search", params={"q": f"java AND {marker}"}, headers=_h(viewer))
    assert answer.status_code == 200, answer.text
    assert [r["name"] for r in answer.json()["results"]] == ["Found Test"]
    bad = api.get("/api/v1/candidate-search", params={"q": "(java"}, headers=_h(viewer))
    assert bad.status_code == 400 and "bracket is not closed" in bad.json()["detail"]
    assert api.get("/api/v1/candidate-search", params={"q": "java"}, headers=_h(outsider)).status_code == 403

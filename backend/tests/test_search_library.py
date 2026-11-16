"""Boolean search, the rest of the open requirements (CEO 2026-11-16): the team's own skill synonyms (P902), how many
candidates each word finds and how to change a search that finds nothing or too much (P908), and saved searches
with when and how many they last found (P911)."""
import pytest

from app.models.job_search import SavedCandidateSearch, SkillSynonym
from app.services import search_library_service as library
from app.services.boolean_search_service import (
    BooleanQueryError, CompiledQuery, Document, search_candidates, suggestions, synonyms_for,
)
from app.services.search_library_service import SynonymError
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.test_boolean_search import TENANT, _names, _person, api, db, leader  # noqa: F401
from tests.test_core_certification import _h, _user


# ---- the team's synonyms
def test_a_name_the_team_adds_is_found_by_searching_the_skill(db, leader):
    marker = f"zq{factories.uid()}"
    _person(db, "Named", skills=f"alias{marker}")
    _person(db, "Plain", skills=marker)
    assert _names(search_candidates(db, leader, marker)) == ["Plain"]
    library.save_synonym(db, leader, marker, [f"alias{marker}", f"ALIAS{marker}", "  "])
    assert sorted(_names(search_candidates(db, leader, marker))) == ["Named", "Plain"]
    # a quoted phrase is still matched exactly as written
    assert _names(search_candidates(db, leader, f'"{marker}"')) == ["Plain"]


def test_team_names_add_to_the_platforms_and_stay_in_their_tenant(db, leader):
    library.save_synonym(db, leader, "Guidewire", ["GW Suite"])
    mine, other = synonyms_for(db, TENANT)["guidewire"], synonyms_for(db, TENANT + 1)["guidewire"]
    assert "GW Suite" in mine and "GW Suite" not in other and set(other) < set(mine)
    item = next(i for i in library.synonym_library(db, TENANT) if i["skill"].lower() == "guidewire")
    assert item["added"] == ["GW Suite"] and item["built_in"] and "GW Suite" not in item["built_in"]


def test_saving_again_replaces_the_teams_names_and_removing_keeps_the_platforms(db, leader):
    library.save_synonym(db, leader, "DuckCreek", ["DCT"])
    library.save_synonym(db, leader, "duckcreek", ["Duck Creek Technologies"])
    rows = db.query(SkillSynonym).filter(SkillSynonym.tenant_id == TENANT).all()
    assert len(rows) == 1 and rows[0].other_names == ["Duck Creek Technologies"]
    assert library.delete_synonym(db, leader, "DUCKCREEK") is True
    assert library.delete_synonym(db, leader, "DuckCreek") is False


@pytest.mark.parametrize("skill, names, message", [
    ("", ["x"], "Name the skill"),
    ('Java"', ["x"], "quotes"),
    ("Java", ["java", ""], "at least one other name"),
    ("Java", ['bad"name'], "can't be used"),
    ("Lead QA", ["QA Lead"], "one word"),
    ("OR", ["x"], "one word"),
])
def test_names_that_cannot_be_kept_say_why(db, leader, skill, names, message):
    with pytest.raises(SynonymError, match=message):
        library.save_synonym(db, leader, skill, names)


# ---- counts and suggestions
def test_each_word_says_how_many_it_finds_and_its_other_names():
    compiled = CompiledQuery('guidewire AND "claim center" NOT tester')
    documents = [Document(skills="Guidewire"), Document(skills="Guidewire", resume="claim center"), Document()]
    assert compiled.term_counts(documents) == {"guidewire": 2, "claim center": 1}
    assert compiled.expanded()["claim center"] == ["claim center"]
    assert len(compiled.expanded()["guidewire"]) >= 1


def test_a_search_that_finds_nobody_says_which_word_to_change():
    compiled = CompiledQuery("guidewire AND cobol")
    tips = suggestions(compiled, 0, {"guidewire": 5, "cobol": 0}, filtered=False)
    assert tips and '"cobol"' in tips[0]
    tips = suggestions(compiled, 0, {"guidewire": 5, "cobol": 3}, filtered=True)
    assert "OR instead of AND" in tips[0] and "filter" in tips[1]
    assert "add a skill" in suggestions(compiled, 500, {"guidewire": 500, "cobol": 500}, filtered=False)[0]
    assert suggestions(compiled, 12, {"guidewire": 20, "cobol": 12}, filtered=False) == []


def test_the_search_answer_carries_the_counts_and_suggestions(db, leader):
    marker = f"zq{factories.uid()}"
    _person(db, "Only", skills=marker)
    result = search_candidates(db, leader, f"{marker} AND nothingmatches{marker}")
    assert result["total"] == 0 and result["term_counts"][marker] == 1
    assert any(f'"nothingmatches{marker}"' in tip for tip in result["suggestions"])


# ---- saved searches
def test_a_saved_search_keeps_its_query_and_the_same_name_replaces_it(db, leader):
    first = library.save_search(db, leader, name="PC devs", query="policycenter  and  java", location=" Dallas ")
    again = library.save_search(db, leader, name="PC devs", query="policycenter OR billingcenter")
    assert first.id == again.id and again.query == "policycenter OR billingcenter" and again.location is None
    with pytest.raises(BooleanQueryError):
        library.save_search(db, leader, name="Broken", query="(java")
    with pytest.raises(BooleanQueryError, match="name"):
        library.save_search(db, leader, name=" ", query="java")


def test_the_routes_save_run_list_and_delete_your_own_searches_only(db, api):
    recruiter = _user(db, full_access_role(db), "Recruiter")
    other = _user(db, full_access_role(db), "Other")
    marker = f"zq{factories.uid()}"
    _person(db, "Hit", skills=marker, tenant_id=1)
    db.commit()
    saved = api.post("/api/v1/candidate-search/saved", json={"name": "Mine", "query": marker}, headers=_h(recruiter))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]
    ran = api.get("/api/v1/candidate-search", params={"q": marker, "saved_id": saved_id}, headers=_h(recruiter))
    assert ran.status_code == 200 and ran.json()["total"] == 1 and ran.json()["term_counts"] == {marker: 1}
    listed = api.get("/api/v1/candidate-search/saved", headers=_h(recruiter)).json()
    assert [(s["name"], s["last_result_count"]) for s in listed] == [("Mine", 1)] and listed[0]["last_run_at"]
    assert api.get("/api/v1/candidate-search/saved", headers=_h(other)).json() == []
    assert api.delete(f"/api/v1/candidate-search/saved/{saved_id}", headers=_h(other)).status_code == 404
    assert api.delete(f"/api/v1/candidate-search/saved/{saved_id}", headers=_h(recruiter)).status_code == 204
    assert db.query(SavedCandidateSearch).filter(SavedCandidateSearch.id == saved_id).count() == 0


def test_the_synonym_routes_need_the_right_to_edit_candidates(db, api):
    recruiter = _user(db, full_access_role(db), "Recruiter")
    outsider = _user(db, factories.role(db, 1), "Outsider")
    db.commit()
    skill = f"Skill{factories.uid()}"
    saved = api.put("/api/v1/skill-synonyms", json={"skill": skill, "other_names": ["Alias"]}, headers=_h(recruiter))
    assert saved.status_code == 200, saved.text
    assert saved.json()["added"] == ["Alias"] and saved.json()["updated_by_name"]
    assert any(i["skill"] == skill for i in api.get("/api/v1/skill-synonyms", headers=_h(recruiter)).json())
    assert api.put("/api/v1/skill-synonyms", json={"skill": skill, "other_names": ["X"]},
                   headers=_h(outsider)).status_code == 403
    assert api.delete(f"/api/v1/skill-synonyms/{skill}", headers=_h(recruiter)).status_code == 204


def test_a_new_name_reaches_every_job_on_the_systems_search_but_not_a_recruiters_own(db, leader):
    from app.models.job_search import JobSearchCriteria
    from app.services import job_search_service as job_search

    skill = f"Skill{factories.uid()}"
    jobs = [factories.job(db, TENANT, jobTitle="Developer", jobSkills=skill, jobStatus="active",
                          required_skills_canonical=[{"name": skill}]) for _ in range(2)]
    for job in jobs:
        job_search.ensure_criteria(db, job)
    job_search.save_criteria(db, jobs[1], leader, f"{skill} AND java")
    db.commit()
    library.save_synonym(db, leader, skill, ["Alias Name"])
    system, own = (db.get(JobSearchCriteria, j.jobID) for j in jobs)
    assert '"Alias Name"' in system.boolean_query and '"Alias Name"' in system.generated_query
    assert own.boolean_query == f"{skill} AND java" and '"Alias Name"' in own.generated_query
    library.delete_synonym(db, leader, skill)
    db.refresh(system)
    assert "Alias Name" not in system.boolean_query

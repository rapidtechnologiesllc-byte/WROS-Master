"""Pure tests for passive-talent enrichment: parsing, identity, scoring, orchestration."""
import time
from unittest.mock import patch

import pytest

from app.services.talent_intelligence import analysis
from app.services.talent_intelligence.service import BudgetExhausted, Sources, enrich
from app.services.talent_intelligence.sources import PersonalSiteSource

SLUG = "ankurjit-singh"
LI_ITEM = {
    "title": "Ankurjit Singh - Senior Software Engineer - Acme Corp | LinkedIn",
    "snippet": "Experience: Acme Corp · Education: IIT Delhi · Location: Bengaluru, Karnataka, India · 500+ connections",
    "link": f"https://in.linkedin.com/in/{SLUG}",
    "metatags": {},
}


class FakeSearch:
    name = "fake_search"

    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        for fragment, results in self.results_by_query.items():
            if query.startswith(fragment):
                return results
        return []


class FakeGitHub:
    def __init__(self, users, repos=None):
        self.users = users
        self.repos = repos or []

    def search_users(self, name, location=None):
        return list(self.users)

    def get_user(self, login):
        return self.users[login]

    def get_repos(self, login):
        return self.repos


class FakeSite:
    def __init__(self, pages):
        self.pages = pages
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return self.pages.get(url)


def _deadline():
    return time.monotonic() + 60


def test_parse_linkedin_result_extracts_profile_fields():
    parsed = analysis.parse_linkedin_result(LI_ITEM, SLUG)
    assert parsed["full_name"] == "Ankurjit Singh"
    assert parsed["headline"] == "Senior Software Engineer"
    assert parsed["current_company"] == "Acme Corp"
    assert parsed["education"] == "IIT Delhi"
    assert parsed["location"].startswith("Bengaluru")
    assert parsed["open_to_work"] is False


def test_parse_ignores_other_profiles_and_prefix_slugs():
    assert analysis.parse_linkedin_result({**LI_ITEM, "link": "https://linkedin.com/in/someone-else"}, SLUG) is None
    assert analysis.parse_linkedin_result({**LI_ITEM, "link": f"https://linkedin.com/in/{SLUG}-2"}, SLUG) is None


def test_open_to_work_lowers_passive_score_but_never_blocks():
    open_li = analysis.parse_linkedin_result({**LI_ITEM, "snippet": LI_ITEM["snippet"] + " #OpenToWork"}, SLUG)
    passive_li = analysis.parse_linkedin_result(LI_ITEM, SLUG)
    assert open_li["open_to_work"] is True
    assert analysis.passive_score(open_li, None) < analysis.passive_score(passive_li, None)


def test_same_name_github_user_without_backlink_stays_below_threshold():
    li = analysis.parse_linkedin_result(LI_ITEM, SLUG)
    namesake = {"login": "ankur", "name": "Ankurjit Singh", "location": "Bengaluru", "company": "Other Inc"}
    assert analysis.score_identity(li, namesake, SLUG) < analysis.PROFILE_DATA_THRESHOLD


def test_backlink_from_github_profile_confirms_identity():
    li = analysis.parse_linkedin_result(LI_ITEM, SLUG)
    user = {"login": "ankur", "name": "A S", "blog": f"https://www.linkedin.com/in/{SLUG}/"}
    assert analysis.score_identity(li, user, SLUG) == analysis.BACKLINK_SCORE


def test_contact_email_extraction_rejects_noreply_and_assets():
    html = "mail ankur@ankur.dev or 123+ankur@users.noreply.github.com logo@2x.png noreply@site.io"
    assert analysis.extract_contact_emails(html) == ["ankur@ankur.dev"]


def test_enrich_takes_contact_only_from_backlinked_personal_site():
    site_url = "https://ankur.dev"
    search = FakeSearch({
        "site:linkedin.com": [LI_ITEM],
        '"linkedin.com/in/': [
            {"link": "https://unrelated.example/about"},
            {"link": site_url},
        ],
    })
    site = FakeSite({
        "https://unrelated.example/about": "contact boss@unrelated.example",
        site_url: f'<a href="https://linkedin.com/in/{SLUG}">LinkedIn</a> hello@ankur.dev',
    })
    user = {"login": "ankur", "name": "Ankurjit Singh", "company": "Acme Corp", "location": "Bengaluru",
            "html_url": "https://github.com/ankur", "email": "leak@github-public.example"}
    github = FakeGitHub({"ankur": user}, repos=[
        {"name": "fastqueue", "language": "Python", "stargazers_count": 80, "pushed_at": "2026-09-30T10:00:00Z"},
    ])
    result = enrich(SLUG, Sources(search=[search], github=github, site=site), allow=lambda s: True, deadline=_deadline())

    assert result.contact_email == "hello@ankur.dev"
    assert result.contact_source == f"personal_site:{site_url}"
    assert result.profile["full_name"]["value"] == "Ankurjit Singh"
    assert result.profile["skills"]["value"] == ["Python"]
    assert result.identity_score >= analysis.PROFILE_DATA_THRESHOLD
    assert all("leak@" not in str(v) for v in result.profile.values())  # GitHub email never used


def test_enrich_without_backlinked_site_has_no_contact():
    search = FakeSearch({"site:linkedin.com": [LI_ITEM], '"linkedin.com/in/': [{"link": "https://x.example"}]})
    site = FakeSite({"https://x.example": "jobs@x.example"})
    result = enrich(SLUG, Sources(search=[search], site=site), allow=lambda s: True, deadline=_deadline())
    assert result.contact_email is None
    assert result.found_linkedin_snippet is True


def test_enrich_raises_budget_exhausted_when_no_quota():
    search = FakeSearch({"site:linkedin.com": [LI_ITEM]})
    with pytest.raises(BudgetExhausted):
        enrich(SLUG, Sources(search=[search]), allow=lambda s: False, deadline=_deadline())
    assert search.queries == []


def test_personal_site_source_refuses_linkedin_and_internal_hosts():
    source = PersonalSiteSource()
    with patch("app.services.talent_intelligence.sources.requests.get") as get:
        assert source.fetch(f"https://www.linkedin.com/in/{SLUG}") is None
        assert source.fetch("http://169.254.169.254/latest/meta-data") is None
        assert source.fetch("http://localhost:8080/admin") is None
        get.assert_not_called()

"""Orchestrates free sources into one enrichment result. No database access:
quota checks are injected as `allow(source_name) -> bool`."""
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.services.talent_intelligence import analysis
from app.services.talent_intelligence.sources import (
    GitHubSource, PersonalSiteSource, SourceRateLimited, SourceUnavailable, WebSearchSource,
)

logger = logging.getLogger(__name__)

LINKEDIN_SNIPPET_CONFIDENCE = 0.9
MIN_SECONDS_LEFT = 8


class BudgetExhausted(Exception):
    """Every configured web-search source is out of free quota for today."""


@dataclass
class Sources:
    search: List[WebSearchSource] = field(default_factory=list)
    github: Optional[GitHubSource] = None
    site: Optional[PersonalSiteSource] = None


@dataclass
class EnrichmentResult:
    profile: Dict = field(default_factory=dict)  # {field: {value, source, confidence}}
    identity_score: float = 0.0
    passive_score: float = 0.0
    contact_email: Optional[str] = None
    contact_source: Optional[str] = None
    found_linkedin_snippet: bool = False
    errors: List[str] = field(default_factory=list)


def _put(result: EnrichmentResult, key: str, value, source: str, confidence: float) -> None:
    if value in (None, "", [], {}):
        return
    current = result.profile.get(key)
    if current is None or current["confidence"] < confidence:
        result.profile[key] = {"value": value, "source": source, "confidence": confidence}


def _search(sources: Sources, query: str, allow: Callable[[str], bool]) -> List[Dict]:
    for source in sources.search:
        if not allow(source.name):
            continue
        return source.search(query)
    raise BudgetExhausted(f"No search quota left for: {query}")


def enrich(slug: str, sources: Sources, *, allow: Callable[[str], bool], deadline: float) -> EnrichmentResult:
    """Raises BudgetExhausted / SourceRateLimited so the caller can reschedule."""
    result = EnrichmentResult()

    def time_left() -> bool:
        return deadline - time.monotonic() > MIN_SECONDS_LEFT

    # 1. Public LinkedIn data via search-engine snippets (linkedin.com itself is never fetched)
    li: Dict = {}
    if sources.search:
        for item in _search(sources, f"site:linkedin.com/in/{slug}", allow):
            parsed = analysis.parse_linkedin_result(item, slug)
            if parsed:
                li = parsed
                result.found_linkedin_snippet = True
                break
    for key in ("full_name", "headline", "current_company", "location", "experience", "education", "open_to_work"):
        _put(result, key, li.get(key), "search_snippet", LINKEDIN_SNIPPET_CONFIDENCE)

    # 2. GitHub: identity + skills evidence only, never contact
    github_user = None
    if sources.github and li.get("full_name") and time_left():
        try:
            best_score = 0.0
            for login in sources.github.search_users(li["full_name"]):
                if not time_left():
                    break
                user = sources.github.get_user(login)
                score = analysis.score_identity(li, user, slug)
                if score > best_score:
                    best_score, github_user = score, user
            result.identity_score = best_score
        except SourceUnavailable as exc:
            result.errors.append(str(exc))

    evidence = None
    if github_user and result.identity_score >= analysis.PROFILE_DATA_THRESHOLD and time_left():
        try:
            evidence = analysis.github_evidence(sources.github.get_repos(github_user["login"]))
        except SourceUnavailable as exc:
            result.errors.append(str(exc))
        conf = result.identity_score
        _put(result, "github_login", github_user.get("login"), "github", conf)
        _put(result, "github_url", github_user.get("html_url"), "github", conf)
        _put(result, "location", github_user.get("location"), "github", conf * 0.8)
        if evidence:
            _put(result, "skills", evidence["top_languages"], "github", conf)
            _put(result, "open_source", evidence, "github", conf)

    # 3. Contact: only an address the person published on their own site, and
    # only when that site links back to this exact LinkedIn profile. Sites are
    # found by web search, never from GitHub data.
    if sources.site and sources.search and time_left():
        name = li.get("full_name", "")
        query = f'"linkedin.com/in/{slug}" {name} -site:linkedin.com -site:github.com'.strip()
        try:
            site_results = _search(sources, query, allow)[:3]
        except BudgetExhausted:
            site_results = []
            result.errors.append("contact search deferred: search quota exhausted")
        for item in site_results:
            if not time_left():
                break
            link = item.get("link") or ""
            if "linkedin.com" in link or "github.com" in link:
                continue
            html = sources.site.fetch(link)
            if not (html and analysis.links_to_profile(html, slug)):
                continue
            emails = analysis.extract_contact_emails(html)
            if emails:
                result.contact_email = emails[0]
                result.contact_source = f"personal_site:{link}"
                break

    result.passive_score = analysis.passive_score(li, evidence)
    return result

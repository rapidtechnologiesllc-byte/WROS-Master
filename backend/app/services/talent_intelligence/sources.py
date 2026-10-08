"""Free external sources for passive-talent enrichment.

Rules baked in here, not left to callers:
- linkedin.com is never fetched (search-engine snippets only).
- GitHub is identity/skills evidence only; its data is never used for
  contact (GitHub Acceptable Use Policy forbids it for recruiting email).
- Every call has a hard timeout; 403/429 surface as SourceRateLimited.
"""
import ipaddress
import logging
import socket
from typing import Dict, List, Optional, Protocol
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = (3, 5)  # (connect, read) seconds
MAX_PAGE_BYTES = 512 * 1024
USER_AGENT = "WROS-TalentIntelligence/1.0"
BLOCKED_FETCH_DOMAINS = ("linkedin.com", "lnkd.in")


class SourceRateLimited(RuntimeError):
    """Source quota or rate limit hit; retry later, not a failure of the candidate."""


class SourceUnavailable(RuntimeError):
    """Source errored or timed out; retryable."""


class WebSearchSource(Protocol):
    name: str

    def search(self, query: str) -> List[Dict]:
        """Return [{title, snippet, link, metatags}]."""


def _get(url: str, *, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
    try:
        response = requests.get(
            url, params=params, headers={"User-Agent": USER_AGENT, **(headers or {})},
            timeout=HTTP_TIMEOUT, allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise SourceUnavailable(f"{urlparse(url).netloc}: {exc}") from exc
    if response.status_code in (403, 429):
        raise SourceRateLimited(f"{urlparse(url).netloc} returned {response.status_code}")
    return response


class GoogleCSESource:
    """Google Programmable Search JSON API (100 free queries/day).

    Google closed this API to new customers in 2025 and ends it for existing
    ones on 2027-01-01, hence the WebSearchSource interface and SearxngSource.
    """
    name = "google_cse"
    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, engine_id: str):
        self.api_key = api_key
        self.engine_id = engine_id

    def search(self, query: str) -> List[Dict]:
        response = _get(self.ENDPOINT, params={"key": self.api_key, "cx": self.engine_id, "q": query, "num": 5})
        if response.status_code != 200:
            raise SourceUnavailable(f"google_cse returned {response.status_code}")
        results = []
        for item in response.json().get("items", []):
            metatags = (item.get("pagemap", {}).get("metatags") or [{}])[0]
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "metatags": metatags,
            })
        return results


class SearxngSource:
    """Self-hosted SearXNG metasearch (free, no quota beyond your own server)."""
    name = "searxng"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def search(self, query: str) -> List[Dict]:
        params = {"q": query}
        params["format"] = "json"
        response = _get(f"{self.base_url}/search", params=params)
        if response.status_code != 200:
            raise SourceUnavailable(f"searxng returned {response.status_code}")
        return [
            {"title": r.get("title", ""), "snippet": r.get("content", ""), "link": r.get("url", ""), "metatags": {}}
            for r in response.json().get("results", [])[:5]
        ]


class GitHubSource:
    """GitHub REST API. Token strongly recommended (search is 10/min unauthenticated)."""
    name = "github"
    API = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _json(self, path: str, params: Optional[Dict] = None):
        response = _get(f"{self.API}{path}", params=params, headers=self.headers)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise SourceUnavailable(f"github {path} returned {response.status_code}")
        return response.json()

    def search_users(self, name: str, location: Optional[str] = None) -> List[str]:
        query = f'"{name}" in:name' + (f' location:"{location}"' if location else "")
        data = self._json("/search/users", {"q": query, "per_page": 3}) or {}
        return [item["login"] for item in data.get("items", [])]

    def get_user(self, login: str) -> Optional[Dict]:
        return self._json(f"/users/{login}")

    def get_repos(self, login: str) -> List[Dict]:
        return self._json(f"/users/{login}/repos", {"sort": "pushed", "per_page": 30}) or []


def _resolves_to_public_ip(host: str) -> bool:
    # The URL comes from a third party's GitHub profile: never let it reach
    # loopback, private ranges or cloud metadata endpoints.
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except (socket.gaierror, UnicodeError):
        return False
    return bool(addresses) and all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses)


class PersonalSiteSource:
    name = "personal_site"

    def fetch(self, url: str) -> Optional[str]:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not host:
            return None
        if any(host == d or host.endswith("." + d) for d in BLOCKED_FETCH_DOMAINS):
            return None
        if not _resolves_to_public_ip(host):
            logger.warning(f"[TalentIntel] Refusing non-public host {host}")
            return None
        try:
            response = requests.get(
                parsed.geturl(), headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT,
                allow_redirects=False, stream=True,
            )
            if response.status_code != 200:
                return None
            body = response.raw.read(MAX_PAGE_BYTES, decode_content=True)
        except requests.RequestException as exc:
            logger.info(f"[TalentIntel] Personal site fetch failed for {host}: {exc}")
            return None
        return body.decode(response.encoding or "utf-8", errors="replace")

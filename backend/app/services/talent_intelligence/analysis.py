"""Pure parsing, identity resolution and passive-talent scoring (no I/O)."""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional

PROFILE_DATA_THRESHOLD = 0.7
# Contact is only ever taken from a page that links back to the exact
# LinkedIn profile: emailing the wrong "Singh" is worse than emailing nobody.
BACKLINK_SCORE = 1.0

OPEN_TO_WORK_PATTERN = re.compile(r"#?open\s*to\s*work", re.IGNORECASE)
SENIOR_PATTERN = re.compile(r"\b(senior|sr\.?|lead|principal|staff|architect|head|director|vp|manager)\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REJECTED_EMAIL_FRAGMENTS = ("noreply", "no-reply", "example.", "@users.noreply.github.com", "linkedin", "sentry", "wixpress")
SNIPPET_FIELDS = {
    "experience": re.compile(r"Experience:\s*([^·|\n]+)", re.IGNORECASE),
    "education": re.compile(r"Education:\s*([^·|\n]+)", re.IGNORECASE),
    "location": re.compile(r"Location:\s*([^·|\n]+)", re.IGNORECASE),
}


def _fold(text: Optional[str]) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _tokens(text: Optional[str]) -> set:
    return {t for t in _fold(text).split() if len(t) > 1}


def links_to_profile(text: Optional[str], slug: str) -> bool:
    return bool(text) and re.search(rf"linkedin\.com/in/{re.escape(slug)}(?![a-z0-9-])", text.lower()) is not None


def parse_linkedin_result(item: Dict, slug: str) -> Optional[Dict]:
    """Structured fields from a search result for linkedin.com/in/<slug>, or None."""
    if not links_to_profile(item.get("link"), slug):
        return None
    metatags = item.get("metatags") or {}
    title = metatags.get("og:title") or item.get("title") or ""
    title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title).strip()
    parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", title) if p.strip()]
    description = " ".join(filter(None, [metatags.get("og:description"), item.get("snippet")]))

    parsed = {"full_name": parts[0] if parts else None}
    if len(parts) > 1:
        parsed["headline"] = parts[1]
    if len(parts) > 2:
        parsed["current_company"] = parts[2]
    for field, pattern in SNIPPET_FIELDS.items():
        match = pattern.search(description)
        if match:
            parsed[field] = match.group(1).strip().rstrip(".")
    if "current_company" not in parsed and parsed.get("experience"):
        parsed["current_company"] = parsed["experience"]
    parsed["open_to_work"] = bool(OPEN_TO_WORK_PATTERN.search(f"{title} {description}"))
    return {k: v for k, v in parsed.items() if v not in (None, "")}


def extract_contact_emails(html: Optional[str]) -> List[str]:
    found = []
    for email in EMAIL_PATTERN.findall(html or ""):
        email = email.lower().strip(".")
        if any(fragment in email for fragment in REJECTED_EMAIL_FRAGMENTS):
            continue
        if email.endswith((".png", ".jpg", ".svg", ".webp", ".gif")):
            continue
        if email not in found:
            found.append(email)
    return found


def score_identity(li: Dict, github_user: Optional[Dict], slug: str) -> float:
    """How sure we are that a GitHub account is the LinkedIn person (0-1)."""
    if not github_user:
        return 0.0
    if links_to_profile(github_user.get("blog"), slug) or links_to_profile(github_user.get("bio"), slug):
        return BACKLINK_SCORE
    score = 0.0
    if li.get("full_name") and _fold(li["full_name"]) == _fold(github_user.get("name")):
        score += 0.4
    company = _tokens(li.get("current_company")) - {"inc", "ltd", "llc", "pvt", "limited", "technologies"}
    if company and company & _tokens(github_user.get("company")):
        score += 0.3
    location = _tokens(li.get("location"))
    if location and location & _tokens(github_user.get("location")):
        score += 0.2
    if _tokens(li.get("headline")) & _tokens(github_user.get("bio")):
        score += 0.1
    return round(min(score, 0.95), 2)


def github_evidence(repos: List[Dict], now: Optional[datetime] = None) -> Dict:
    now = now or datetime.utcnow()
    own = [r for r in repos if not r.get("fork")]
    languages: Dict[str, int] = {}
    for repo in own:
        if repo.get("language"):
            languages[repo["language"]] = languages.get(repo["language"], 0) + 1
    pushed = [datetime.strptime(r["pushed_at"], "%Y-%m-%dT%H:%M:%SZ") for r in own if r.get("pushed_at")]
    return {
        "top_languages": [lang for lang, _ in sorted(languages.items(), key=lambda kv: -kv[1])[:5]],
        "public_repos": len(own),
        "total_stars": sum(r.get("stargazers_count", 0) for r in own),
        "active_last_90_days": any(now - p <= timedelta(days=90) for p in pushed),
        "top_repos": [
            {"name": r.get("name"), "stars": r.get("stargazers_count", 0), "language": r.get("language")}
            for r in sorted(own, key=lambda r: -r.get("stargazers_count", 0))[:3]
        ],
    }


def passive_score(li: Dict, evidence: Optional[Dict]) -> float:
    """Priority for outreach (0-1). Open-to-work lowers it: those candidates
    are already flooded by other recruiters."""
    score = 0.5
    if li.get("open_to_work"):
        score -= 0.3
    if evidence and evidence.get("active_last_90_days"):
        score += 0.2
    if SENIOR_PATTERN.search(li.get("headline") or ""):
        score += 0.1
    if evidence and evidence.get("total_stars", 0) >= 50:
        score += 0.1
    return round(max(0.0, min(score, 1.0)), 2)

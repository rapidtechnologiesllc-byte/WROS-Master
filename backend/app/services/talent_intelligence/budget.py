"""Daily free-quota accounting per source, and source construction from config."""
from datetime import datetime
from typing import Dict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate_intelligence import EnrichmentSourceUsage
from app.services.talent_intelligence.service import Sources
from app.services.talent_intelligence.sources import (
    GitHubSource, GoogleCSESource, PersonalSiteSource, SearxngSource,
)


def daily_caps() -> Dict[str, int]:
    return {"google_cse": settings.GOOGLE_CSE_DAILY_BUDGET}


def consume(db: Session, source: str, daily_cap: int) -> bool:
    """Atomically count one call for today (UTC). False once over the cap.
    Commits immediately: quota spent stays spent even if the caller rolls back."""
    statement = insert(EnrichmentSourceUsage).values(
        source=source, usage_date=datetime.utcnow().date(), count=1,
    ).on_conflict_do_update(
        constraint="uq_enrichment_source_day",
        set_={"count": EnrichmentSourceUsage.count + 1},
    ).returning(EnrichmentSourceUsage.count)
    count = db.execute(statement).scalar_one()
    db.commit()
    return count <= daily_cap


def allow_for(db: Session):
    caps = daily_caps()

    def allow(source_name: str) -> bool:
        cap = caps.get(source_name)
        return True if cap is None else consume(db, source_name, cap)

    return allow


def build_sources() -> Sources:
    search = []
    if settings.SEARXNG_URL:
        search.append(SearxngSource(settings.SEARXNG_URL))
    if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID:
        search.append(GoogleCSESource(settings.GOOGLE_CSE_API_KEY, settings.GOOGLE_CSE_ID))
    return Sources(
        search=search,
        github=GitHubSource(settings.GITHUB_TOKEN) if settings.GITHUB_TOKEN else None,
        site=PersonalSiteSource(),
    )

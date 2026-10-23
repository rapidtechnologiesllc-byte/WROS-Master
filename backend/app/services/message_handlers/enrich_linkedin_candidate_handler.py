"""Message Handler: enrich_linkedin_candidate

Replaces the manual LinkedIn outreach steps (connect -> collect phone/email ->
Import) with autonomous enrichment from free sources. When identity and a
self-published contact address are confirmed, the candidate is imported to
Thunder and its email cadence starts (step 1 = first touch with source
disclosure and opt-out; see app/services/thunder_mail).

Compensation: enrichment never deletes anything. A failed run leaves the
candidate exactly as created (placeholder email, Thunder off) and the
recruiter task in place as the fallback.
"""
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate, CandidateEducationForm, CandidateExperienceForm
from app.models.candidate_intelligence import CandidateIntelligenceProfile
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.services.candidate_contact_policy import rejection_cooldown_until
from app.services.message_handlers.base_message_handler import time_bound
from app.services.talent_intelligence.service import BudgetExhausted, EnrichmentResult, enrich
from app.services.talent_intelligence.sources import SourceRateLimited

logger = logging.getLogger(__name__)

TASK_NAME = "enrich_linkedin_candidate"
TIMEOUT_SECONDS = 45
ENRICH_SECONDS = 35  # leaves room for the write phase inside TIMEOUT_SECONDS
RETRY_BACKOFF_HOURS = (6, 24, 72)  # after attempts 1, 2, 3; attempt 4 -> EXHAUSTED
MAX_ATTEMPTS = len(RETRY_BACKOFF_HOURS) + 1
STALE_CLAIM_MINUTES = 10
TERMINAL_STATUSES = ("IMPORTED", "EXHAUSTED", "DUPLICATE_CONTACT")


def queue_enrichment(pipeline_id: str, tenant_id: Optional[int], attempt: int = 0,
                     delay_seconds: int = 10, run_key: str = "") -> Dict[str, Any]:
    from app.services.message_queue_service import MessageQueueService
    return MessageQueueService.enqueue(
        task_name=TASK_NAME,
        data={"pipeline_id": str(pipeline_id), "tenant_id": tenant_id, "attempt": attempt},
        delay_seconds=delay_seconds,
        idempotency_key=f"{TASK_NAME}:{pipeline_id}:{attempt}{run_key}",
        tenant_id=int(tenant_id) if tenant_id is not None else None,  # enqueue resolves a missing tenant
    )


def _get_or_create_profile(db: Session, item: LinkedInCandidatePipeline, tenant_id) -> CandidateIntelligenceProfile:
    pipeline_id = str(item.id)
    profile = db.query(CandidateIntelligenceProfile).filter_by(pipeline_id=pipeline_id).first()
    if profile is not None:
        return profile
    try:
        profile = CandidateIntelligenceProfile(
            pipeline_id=pipeline_id, linkedin_slug=item.linkedin_profile_slug,
            tenant_id=int(tenant_id) if tenant_id else None, status="PENDING", attempts=0,
        )
        db.add(profile)
        db.commit()
    except IntegrityError:
        db.rollback()  # created concurrently by another worker
        profile = db.query(CandidateIntelligenceProfile).filter_by(pipeline_id=pipeline_id).one()
    return profile


def _claim(db: Session, profile_id: int) -> bool:
    """Atomic PENDING/NO_CONTACT/stale -> IN_PROGRESS, so two workers never enrich the same item."""
    stale_before = datetime.utcnow() - timedelta(minutes=STALE_CLAIM_MINUTES)
    claimed = db.execute(
        update(CandidateIntelligenceProfile)
        .where(CandidateIntelligenceProfile.id == profile_id)
        .where(or_(
            CandidateIntelligenceProfile.status.in_(("PENDING", "NO_CONTACT", "AMBIGUOUS")),
            (CandidateIntelligenceProfile.status == "IN_PROGRESS")
            & (CandidateIntelligenceProfile.updated_at < stale_before),
        ))
        .values(status="IN_PROGRESS", updated_at=datetime.utcnow())
    ).rowcount
    db.commit()
    return claimed == 1


def _release(db: Session, profile: CandidateIntelligenceProfile, status: str, error: str, retry_at: datetime) -> None:
    profile.status = status
    profile.last_error = error
    profile.next_attempt_at = retry_at
    db.add(profile)
    db.commit()


def _value(result: EnrichmentResult, key: str):
    entry = result.profile.get(key)
    return entry["value"] if entry else None


def _apply_profile_fields(db: Session, candidate: Candidate, slug: str, result: EnrichmentResult) -> None:
    from app.services.linkedin_pipeline_task_service import name_from_slug

    full_name = _value(result, "full_name")
    if full_name and (candidate.candidateFirstName, candidate.candidateLastName) == name_from_slug(slug):
        first, _, last = full_name.partition(" ")
        candidate.candidateFirstName = first[:150]
        candidate.candidateLastName = (last or candidate.candidateLastName)[:150]
    if not candidate.candidateJobTitle and _value(result, "headline"):
        candidate.candidateJobTitle = _value(result, "headline")[:512]
    if not candidate.candidateCurrentLocation and _value(result, "location"):
        candidate.candidateCurrentLocation = _value(result, "location")[:512]
    if not candidate.candidateSkills and _value(result, "skills"):
        candidate.candidateSkills = ", ".join(_value(result, "skills"))
    db.add(candidate)

    company = _value(result, "current_company") or _value(result, "experience")
    has_experience = db.query(CandidateExperienceForm).filter_by(candidateID=candidate.candidateID).first()
    if company and not has_experience:
        db.add(CandidateExperienceForm(
            candidateID=candidate.candidateID, company_name=company[:512],
            job_title=(_value(result, "headline") or "")[:512] or None,
        ))
    school = _value(result, "education")
    has_education = db.query(CandidateEducationForm).filter_by(candidateID=candidate.candidateID).first()
    if school and not has_education:
        db.add(CandidateEducationForm(candidateID=candidate.candidateID, education_institute=school[:512]))


class EnrichLinkedInCandidateHandler:
    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    MAX_RETRIES = 6
    RETRY_DELAY_MINUTES = 1

    @staticmethod
    @time_bound(timeout_seconds=TIMEOUT_SECONDS)
    def process(message: Any, db: Session, sources=None, allow=None) -> Dict[str, Any]:
        payload = message.payload or {}
        pipeline_id = payload.get("pipeline_id")
        tenant_id = payload.get("tenant_id")
        attempt = int(payload.get("attempt") or 0)
        if not pipeline_id:
            raise ValueError(f"Message {message.id} missing pipeline_id")
        logger.info(f"[Enrich] handler_start pipeline={pipeline_id} attempt={attempt}")

        if not settings.ENRICHMENT_ENABLED:
            logger.info(f"[Enrich] disabled by ENRICHMENT_ENABLED; skipping {pipeline_id}")
            return {"status": "skipped", "reason": "enrichment disabled", "pipeline_id": pipeline_id}

        item = db.query(LinkedInCandidatePipeline).filter(LinkedInCandidatePipeline.id == pipeline_id).first()
        if item is None:
            raise ValueError(f"Pipeline item {pipeline_id} not found")
        profile = _get_or_create_profile(db, item, tenant_id)

        if profile.status in TERMINAL_STATUSES:
            return {"status": "noop", "reason": f"already {profile.status}", "pipeline_id": pipeline_id}
        if item.status == LinkedInPipelineStatus.IMPORTED_TO_THUNDER:
            profile.status = "IMPORTED"
            db.commit()
            return {"status": "noop", "reason": "already imported manually", "pipeline_id": pipeline_id}
        if not item.candidate_id:
            raise RuntimeError(f"Candidate for pipeline {pipeline_id} not created yet")  # retryable race

        if not _claim(db, profile.id):
            return {"status": "noop", "reason": "another worker holds this item", "pipeline_id": pipeline_id}
        db.refresh(profile)
        profile.candidate_id = item.candidate_id
        logger.info(f"[Enrich] transition pipeline={pipeline_id} -> IN_PROGRESS")

        if sources is None or allow is None:
            from app.services.talent_intelligence.budget import allow_for, build_sources
            sources = sources or build_sources()
            allow = allow or allow_for(db)

        if not sources.search and not sources.github:
            retry_at = datetime.utcnow() + timedelta(hours=24)
            logger.error("[Enrich] No enrichment source configured (set SEARXNG_URL or GOOGLE_CSE_*, GITHUB_TOKEN)")
            _release(db, profile, "PENDING", "no enrichment sources configured", retry_at)
            queue_enrichment(pipeline_id, tenant_id, attempt, delay_seconds=24 * 3600, run_key=":nosrc")
            return {"status": "deferred", "reason": "no sources configured", "pipeline_id": pipeline_id}

        try:
            result = enrich(item.linkedin_profile_slug, sources, allow=allow,
                            deadline=time.monotonic() + ENRICH_SECONDS)
        except BudgetExhausted as exc:
            tomorrow = datetime.utcnow().date() + timedelta(days=1)
            retry_at = datetime.combine(tomorrow, datetime.min.time()) + timedelta(minutes=random.randint(1, 15))
            _release(db, profile, "PENDING", str(exc), retry_at)
            queue_enrichment(pipeline_id, tenant_id, attempt,
                             delay_seconds=int((retry_at - datetime.utcnow()).total_seconds()),
                             run_key=f":budget:{tomorrow.isoformat()}")
            logger.info(f"[Enrich] budget exhausted; pipeline={pipeline_id} deferred to {retry_at.isoformat()}")
            return {"status": "deferred", "reason": "daily search quota used", "pipeline_id": pipeline_id}
        except SourceRateLimited as exc:
            retry_at = datetime.utcnow() + timedelta(hours=1)
            _release(db, profile, "PENDING", str(exc), retry_at)
            queue_enrichment(pipeline_id, tenant_id, attempt, delay_seconds=3600,
                             run_key=f":rl:{retry_at.strftime('%Y%m%d%H')}")
            return {"status": "deferred", "reason": "source rate limited", "pipeline_id": pipeline_id}
        except Exception as exc:
            db.rollback()
            _release(db, profile, "PENDING", f"enrichment error: {exc}", datetime.utcnow())
            logger.error(f"[Enrich] enrichment failed pipeline={pipeline_id}: {exc}", exc_info=True)
            raise RuntimeError(f"Enrichment failed for {pipeline_id}: {exc}") from exc

        return EnrichLinkedInCandidateHandler._write(db, item, profile, result, tenant_id, attempt)

    @staticmethod
    def _write(db: Session, item, profile, result: EnrichmentResult, tenant_id, attempt: int) -> Dict[str, Any]:
        pipeline_id = str(item.id)
        try:
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == item.candidate_id
            ).with_for_update().first()
            if candidate is None:
                raise ValueError(f"Candidate {item.candidate_id} linked to {pipeline_id} no longer exists")

            profile.profile_json = result.profile
            profile.identity_score = result.identity_score
            profile.passive_score = result.passive_score
            profile.attempts = attempt + 1
            profile.last_error = "; ".join(result.errors) or None
            _apply_profile_fields(db, candidate, item.linkedin_profile_slug, result)

            imported = False
            if result.contact_email:
                taken = db.query(Candidate).filter(
                    Candidate.candidateEmail == result.contact_email,
                    Candidate.candidateID != candidate.candidateID,
                ).first()
                cooldown = rejection_cooldown_until(db, candidate.candidateID)
                if taken:
                    profile.status = "DUPLICATE_CONTACT"
                    profile.last_error = f"{result.contact_email} already belongs to {taken.candidateID}"
                elif cooldown is not None:
                    profile.status = "NO_CONTACT"
                    profile.next_attempt_at = cooldown
                else:
                    from app.services.candidate_activity_service import log_linkedin_pipeline_step
                    from app.services.linkedin_pipeline_task_service import sync_outreach_task

                    candidate.candidateEmail = result.contact_email
                    candidate.thunder_enabled = True
                    db.add(candidate)
                    item.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
                    item.imported_at = datetime.utcnow()
                    item.updated_at = datetime.utcnow()
                    db.add(item)
                    log_linkedin_pipeline_step(
                        db, candidate.candidateID, "Imported to Thunder",
                        notes=f"Autonomous enrichment: contact from {result.contact_source}",
                        performed_by_id=None, performed_by_name="Thunder Enrichment",
                    )
                    sync_outreach_task(db, item, tenant_id)
                    profile.profile_json = {**(result.profile or {}), "contact_source": {
                        "value": result.contact_source, "source": "personal_site", "confidence": 1.0}}
                    from app.services.thunder_mail.cadence_service import start_cadence
                    cadence_state = start_cadence(db, candidate)
                    profile.status = "IMPORTED"
                    imported = True
            else:
                profile.status = "NO_CONTACT" if result.found_linkedin_snippet else "AMBIGUOUS"

            if not imported and profile.status in ("NO_CONTACT", "AMBIGUOUS"):
                if profile.attempts >= MAX_ATTEMPTS:
                    profile.status = "EXHAUSTED"
                elif profile.next_attempt_at is None or profile.next_attempt_at <= datetime.utcnow():
                    profile.next_attempt_at = datetime.utcnow() + timedelta(
                        hours=RETRY_BACKOFF_HOURS[profile.attempts - 1])
            db.add(profile)
            db.commit()
        except ValueError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.error(f"[Enrich] write phase failed pipeline={pipeline_id}: {exc}", exc_info=True)
            raise RuntimeError(f"Enrichment write failed for {pipeline_id}: {exc}") from exc

        logger.info(
            f"[Enrich] handler_complete pipeline={pipeline_id} status={profile.status} "
            f"identity={profile.identity_score} passive={profile.passive_score}"
        )
        # Enqueue only after commit: enqueue uses its own session and can't share this transaction
        if imported:
            from app.services.thunder_mail.cadence_service import enqueue_send
            enqueue_send(cadence_state)
        elif profile.status in ("NO_CONTACT", "AMBIGUOUS") and profile.next_attempt_at:
            delay = max(60, int((profile.next_attempt_at - datetime.utcnow()).total_seconds()))
            queue_enrichment(pipeline_id, tenant_id, profile.attempts, delay_seconds=delay)

        return {
            "status": profile.status, "pipeline_id": pipeline_id, "candidate_id": candidate.candidateID,
            "identity_score": profile.identity_score, "passive_score": profile.passive_score,
            "imported_to_thunder": imported,
        }

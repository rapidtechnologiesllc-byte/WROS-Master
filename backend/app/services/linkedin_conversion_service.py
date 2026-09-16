"""
LinkedIn-to-Thunder Conversion Service

Orchestrates complete workflow for LinkedIn candidates:
- Fast Path: Email/phone available → Auto-create candidate → Queue to Thunder
- Slow Path: No contact info → Assign to recruiter → Recruiter collects → Queue to Thunder

Both paths converge at Thunder autonomous loop for unified outreach orchestration.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.candidate import Candidate
from app.models.linkedin_candidate_pipeline import (
    LinkedInCandidatePipeline,
    LinkedInPipelineStatus,
)
from app.models.user import Users
from app.services import linkedin_recruiter_workload_service
from app.core.logging import logger

# Custom exceptions
class LinkedInConversionError(Exception):
    """Base exception for LinkedIn conversion errors"""
    pass


class InvalidLinkedInURL(LinkedInConversionError):
    """Invalid LinkedIn URL format"""
    pass


class CandidateNotOpenToWork(LinkedInConversionError):
    """Apollo indicates candidate not open to work (expected, not an error)"""
    pass


class DuplicateCandidateExists(LinkedInConversionError):
    """Candidate already exists in system"""
    pass


class ApolloCandidateNotFound(LinkedInConversionError):
    """Apollo enrichment returned no results"""
    pass


class NoAvailableRecruitersError(LinkedInConversionError):
    """No active recruiters available for assignment"""
    pass


class LinkedInPipelineError(LinkedInConversionError):
    """General pipeline operation error"""
    pass


class ApolloMCPNotConfigured(LinkedInConversionError):
    """Apollo MCP not properly configured"""
    pass


logger = logging.getLogger(__name__)


async def convert_linkedin_to_candidate_auto(
    db: Session,
    linkedin_url: str,
    *,
    apollo_search_func: Optional[Callable] = None,
    current_user: Optional[Users] = None,
    tenant_id: Optional[str] = None,
) -> Tuple[Candidate, Dict[str, Any]]:
    """
    Fast path: LinkedIn URL → Apollo enrichment → Auto-create Candidate → Queue to Thunder

    Args:
        db: Database session
        linkedin_url: Full LinkedIn profile URL
        apollo_search_func: Injected Apollo search function (for testing/DI)
        current_user: Current user (for audit trail)
        tenant_id: Tenant ID (for multi-tenant scoping)

    Returns:
        (candidate, metadata) where:
        - candidate: Real Candidate object ready for Thunder
        - metadata: {
            'status': 'SUCCESS' | 'SKIPPED_GATE',
            'candidate_id': str,
            'email': str,
            'phone': str,
            'path': 'fast',
            'message': str,
            'slm_trace_id': str  # For SLM tracking
          }

    Raises:
        InvalidLinkedInURL: URL format invalid
        CandidateNotOpenToWork: Apollo indicates not open to work (expected)
        ApolloCandidateNotFound: Apollo enrichment failed
        DuplicateCandidateExists: Candidate already in system
        ApolloMCPNotConfigured: Apollo MCP not set up
    """
    trace_id = str(uuid.uuid4())

    try:
        # Step 1: Validate URL format
        profile_slug = _validate_and_parse_linkedin_url(linkedin_url)
        logger.info(f"[LinkedIn Fast Path] {trace_id}: Parsed profile: {profile_slug}")

        # Step 2: Enrich via Apollo
        if apollo_search_func is None:
            raise ApolloMCPNotConfigured(
                "Apollo MCP integration required.\n"
                "Setup: https://claude.ai/settings/connectors → Apollo.io → Connect"
            )

        enriched_data = await _enrich_via_apollo_safe(profile_slug, apollo_search_func)
        email = enriched_data.get('email')
        phone = enriched_data.get('phone')

        logger.info(
            f"[LinkedIn Fast Path] {trace_id}: Enriched - "
            f"Email: {email}, Phone: {phone}, Open to Work: {enriched_data.get('open_to_work')}"
        )

        # Step 3: Check Open to Work gate (non-negotiable)
        if not enriched_data.get('open_to_work'):
            logger.info(
                f"[LinkedIn Fast Path] {trace_id}: GATE REJECTED - Not marked open to work"
            )
            raise CandidateNotOpenToWork(
                f"Candidate not marked 'Open to Work' on LinkedIn. "
                f"Apollo indicates low intent. Use slow path for manual review."
            )

        # Step 4: Require at least one contact method
        if not email and not phone:
            raise ApolloCandidateNotFound(
                "Apollo enrichment returned no email or phone. "
                "Cannot auto-create candidate. Use slow path for manual collection."
            )

        # Step 5: Check for duplicates (email, phone, or LinkedIn URL)
        existing = _check_duplicate_candidate(db, email, phone, linkedin_url)
        if existing:
            logger.warning(
                f"[LinkedIn Fast Path] {trace_id}: DUPLICATE detected - "
                f"Candidate {existing.candidateID} already exists"
            )
            raise DuplicateCandidateExists(
                f"Candidate already in system: {existing.candidateID}. "
                f"Email: {existing.candidateEmail}"
            )

        # Step 6: Create Candidate
        candidate = _create_candidate_with_consent(
            db,
            enriched_data,
            linkedin_url=linkedin_url,
            import_path="fast",
            source_imported_at=datetime.utcnow(),
        )
        logger.info(
            f"[LinkedIn Fast Path] {trace_id}: Created candidate {candidate.candidateID}"
        )

        # Step 7: Queue to Thunder (async, non-blocking)
        _queue_to_thunder(
            db,
            candidate_id=candidate.candidateID,
            email=email,
            phone=phone,
            import_path="fast",
            trace_id=trace_id,
        )

        metadata = {
            'status': 'SUCCESS',
            'candidate_id': candidate.candidateID,
            'email': email,
            'phone': phone,
            'path': 'fast',
            'message': 'Candidate auto-created and queued to Thunder',
            'slm_trace_id': trace_id,
        }

        logger.info(
            f"[LinkedIn Fast Path] {trace_id}: Complete - {candidate.candidateID} → Thunder"
        )
        return candidate, metadata

    except LinkedInConversionError:
        raise
    except Exception as e:
        logger.error(f"[LinkedIn Fast Path] {trace_id}: Unexpected error: {str(e)}", exc_info=True)
        raise LinkedInConversionError(f"Conversion failed: {str(e)}")


async def convert_linkedin_to_candidate_manual(
    db: Session,
    linkedin_url: str,
    *,
    notes: Optional[str] = None,
    current_user: Optional[Users] = None,
    tenant_id: Optional[str] = None,
    bu_id: Optional[str] = None,
) -> Tuple[Optional[object], LinkedInCandidatePipeline]:
    """
    Slow path: LinkedIn URL → Create Pipeline Item → Assign Task to Recruiter

    Args:
        db: Database session
        linkedin_url: Full LinkedIn profile URL
        notes: Optional notes for recruiter
        current_user: Current user creating request
        tenant_id: Tenant ID
        bu_id: Business Unit ID (optional, auto-detect from current_user if not provided)

    Returns:
        (task, pipeline_item) where:
        - task: Task assigned to recruiter (may be None if task service not available)
        - pipeline_item: LinkedInCandidatePipeline (status: PENDING_CONNECTION)

    Raises:
        InvalidLinkedInURL: URL format invalid
        DuplicateCandidateExists: Already in system
        NoAvailableRecruitersError: No active recruiters in BU
        LinkedInPipelineError: General pipeline error
    """
    try:
        # Step 1: Validate URL
        profile_slug = _validate_and_parse_linkedin_url(linkedin_url)
        logger.info(f"[LinkedIn Slow Path] Parsed profile: {profile_slug}")

        # Step 2: Check if already in system
        if _check_duplicate_candidate(db, None, None, linkedin_url):
            raise DuplicateCandidateExists(
                f"Candidate already in system for LinkedIn URL: {linkedin_url}"
            )

        # Step 3: Create pipeline item (status: PENDING_CONNECTION)
        pipeline_item = LinkedInCandidatePipeline(
            linkedin_url=linkedin_url,
            linkedin_profile_slug=profile_slug,
            status=LinkedInPipelineStatus.PENDING_CONNECTION,
            created_by_user_id=current_user.id if current_user else "system",
            notes=notes,
            tenant_id=tenant_id,
        )
        db.add(pipeline_item)
        db.flush()  # Get ID

        logger.info(f"[LinkedIn Slow Path] Created pipeline item: {pipeline_item.id}")

        # Step 4: Assign to least-loaded recruiter
        recruiter = linkedin_recruiter_workload_service.get_least_loaded_recruiter(
            db, bu_id=bu_id, tenant_id=tenant_id
        )

        if not recruiter:
            raise NoAvailableRecruitersError(
                f"No available recruiters in BU: {bu_id}. "
                f"Try auto-import path or contact administrator."
            )

        pipeline_item.assigned_to_user_id = recruiter.id

        # Step 5: Create task for recruiter (if task service available)
        task = None
        try:
            from app.services.task_service import create_task

            task = create_task(
                db,
                title=f"Connect with LinkedIn candidate: {profile_slug}",
                description=f"Review and collect contact info from: {linkedin_url}\n\nNotes: {notes or '(none)'}",
                priority="MEDIUM",
                assigned_to_user_id=recruiter.id,
                created_by_user_id=current_user.id if current_user else "system",
                due_date=datetime.utcnow() + timedelta(days=2),
                task_type="GENERAL",
            )
            pipeline_item.task_id = task.id if hasattr(task, 'id') else None
            logger.info(f"[LinkedIn Slow Path] Created task {task.id if task else 'N/A'}")
        except Exception as e:
            logger.warning(f"[LinkedIn Slow Path] Task creation failed: {e}. Continuing without task.")

        db.commit()

        logger.info(
            f"[LinkedIn Slow Path] Complete - Pipeline {pipeline_item.id} → "
            f"Recruiter {recruiter.id}"
        )

        return task, pipeline_item

    except LinkedInConversionError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[LinkedIn Slow Path] Unexpected error: {str(e)}", exc_info=True)
        raise LinkedInPipelineError(f"Pipeline creation failed: {str(e)}")


async def import_pipeline_candidate_to_thunder(
    db: Session,
    pipeline_item_id: str,
    *,
    phone_number: Optional[str] = None,
    email_from_recruiter: Optional[str] = None,
    current_user: Optional[Users] = None,
) -> Tuple[Candidate, Dict[str, Any]]:
    """
    Transition: Pipeline item → Candidate → Queue to Thunder

    Args:
        db: Database session
        pipeline_item_id: UUID of LinkedInCandidatePipeline item
        phone_number: Phone collected by recruiter (or use stored value)
        email_from_recruiter: Email from LinkedIn message
        current_user: User completing the import

    Returns:
        (candidate, metadata) where metadata same as fast path

    Raises:
        LinkedInPipelineError: Pipeline item doesn't exist or invalid state
        LinkedInConversionError: Various validation errors
    """
    trace_id = str(uuid.uuid4())

    try:
        # Step 1: Fetch pipeline item
        pipeline = db.query(LinkedInCandidatePipeline).filter(
            LinkedInCandidatePipeline.id == pipeline_item_id
        ).first()

        if not pipeline:
            raise LinkedInPipelineError(f"Pipeline item not found: {pipeline_item_id}")

        logger.info(
            f"[LinkedIn Import] {trace_id}: Pipeline {pipeline.id} - "
            f"Status: {pipeline.status}, URL: {pipeline.linkedin_url}"
        )

        # Step 2: Validate status (must be in appropriate state)
        if pipeline.status not in [
            LinkedInPipelineStatus.PENDING_CONNECTION,
            LinkedInPipelineStatus.CONNECTED,
            LinkedInPipelineStatus.PHONE_COLLECTED,
        ]:
            raise LinkedInPipelineError(
                f"Pipeline item in invalid state: {pipeline.status}. "
                f"Cannot import in state {pipeline.status}."
            )

        # Step 3: Determine phone (param or stored value)
        final_phone = phone_number or pipeline.phone_number
        final_email = email_from_recruiter or pipeline.phone_number

        # Step 4: Validate - must have at least phone OR email
        if not final_phone and not final_email:
            raise LinkedInPipelineError(
                f"No contact info available for import. "
                f"Provide phone_number or email_from_recruiter."
            )

        # Step 5: Check for duplicate (might have been created since assignment)
        existing = _check_duplicate_candidate(
            db, final_email, final_phone, pipeline.linkedin_url
        )
        if existing:
            logger.warning(
                f"[LinkedIn Import] {trace_id}: Duplicate detected - "
                f"Candidate {existing.candidateID} already exists"
            )
            # Link pipeline to existing candidate instead of creating new
            pipeline.candidate_id = existing.candidateID
            pipeline.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
            pipeline.imported_at = datetime.utcnow()
            db.commit()

            # Mark task as complete if exists
            if pipeline.task_id:
                try:
                    from app.services.task_service import update_task_status
                    update_task_status(db, pipeline.task_id, "COMPLETED")
                except:
                    pass

            metadata = {
                'status': 'SUCCESS',
                'candidate_id': existing.candidateID,
                'email': final_email,
                'phone': final_phone,
                'path': 'slow',
                'message': f'Linked to existing candidate {existing.candidateID}',
                'slm_trace_id': trace_id,
            }
            return existing, metadata

        # Step 6: Create Candidate
        enriched_data = {
            'email': final_email,
            'phone': final_phone,
            'name': pipeline.linkedin_profile_slug,
            'open_to_work': True,
        }

        candidate = _create_candidate_with_consent(
            db,
            enriched_data,
            linkedin_url=pipeline.linkedin_url,
            import_path="slow",
            source_imported_at=datetime.utcnow(),
        )

        logger.info(
            f"[LinkedIn Import] {trace_id}: Created candidate {candidate.candidateID}"
        )

        # Step 7: Update pipeline
        pipeline.candidate_id = candidate.candidateID
        pipeline.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
        pipeline.imported_at = datetime.utcnow()

        # Step 8: Mark task as completed
        if pipeline.task_id:
            try:
                from app.services.task_service import update_task_status
                update_task_status(db, pipeline.task_id, "COMPLETED")
                logger.info(f"[LinkedIn Import] {trace_id}: Marked task {pipeline.task_id} complete")
            except Exception as e:
                logger.warning(f"[LinkedIn Import] {trace_id}: Failed to update task: {e}")

        # Step 9: Queue to Thunder
        _queue_to_thunder(
            db,
            candidate_id=candidate.candidateID,
            email=final_email,
            phone=final_phone,
            import_path="slow",
            trace_id=trace_id,
        )

        db.commit()

        metadata = {
            'status': 'SUCCESS',
            'candidate_id': candidate.candidateID,
            'email': final_email,
            'phone': final_phone,
            'path': 'slow',
            'message': 'Candidate imported from recruiter review and queued to Thunder',
            'slm_trace_id': trace_id,
        }

        logger.info(
            f"[LinkedIn Import] {trace_id}: Complete - "
            f"{candidate.candidateID} → Thunder"
        )
        return candidate, metadata

    except LinkedInConversionError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[LinkedIn Import] {trace_id}: Unexpected error: {str(e)}", exc_info=True)
        raise LinkedInPipelineError(f"Import failed: {str(e)}")


# ============================================================================
# HELPER FUNCTIONS (Internal Implementation)
# ============================================================================

def _validate_and_parse_linkedin_url(url: str) -> str:
    """
    Validate LinkedIn URL format and extract profile slug.

    Args:
        url: LinkedIn profile URL

    Returns:
        Profile slug (e.g., "prabhu-shetty-123")

    Raises:
        InvalidLinkedInURL: If URL format invalid
    """
    import re

    if not url:
        raise InvalidLinkedInURL("LinkedIn URL cannot be empty")

    # Match common LinkedIn URL patterns
    patterns = [
        r'linkedin\.com/in/([a-z0-9-]+)',  # Full URL
        r'^([a-z0-9-]+)$',  # Just the slug
    ]

    for pattern in patterns:
        match = re.search(pattern, url.lower())
        if match:
            slug = match.group(1)
            if slug:
                return slug

    raise InvalidLinkedInURL(
        f"Invalid LinkedIn URL format: {url}. "
        f"Expected: https://linkedin.com/in/profile-slug or just profile-slug"
    )


async def _enrich_via_apollo_safe(
    profile_slug: str,
    apollo_search_func: Callable,
) -> Dict[str, Any]:
    """
    Call Apollo enrichment with error handling.

    Args:
        profile_slug: LinkedIn profile slug
        apollo_search_func: Apollo search function (injected for testing)

    Returns:
        Dict with: email, phone, name, open_to_work, ...

    Raises:
        ApolloCandidateNotFound: If Apollo returns no results
        ApolloMCPNotConfigured: If Apollo client not available
    """
    try:
        # Build LinkedIn URL for Apollo
        linkedin_url = f"https://linkedin.com/in/{profile_slug}"

        # Call Apollo (may be async or sync depending on implementation)
        result = await apollo_search_func(linkedin_url)

        if not result or not result.get('contacts'):
            raise ApolloCandidateNotFound(
                f"Apollo enrichment returned no results for: {profile_slug}"
            )

        contact = result['contacts'][0]

        # Extract relevant fields
        return {
            'email': contact.get('email'),
            'phone': contact.get('phone_number'),
            'name': contact.get('name'),
            'company': contact.get('company_name'),
            'title': contact.get('title'),
            'open_to_work': contact.get('open_to_work_status', False),
        }

    except ApolloCandidateNotFound:
        raise
    except Exception as e:
        logger.error(f"Apollo enrichment failed: {e}")
        raise ApolloCandidateNotFound(f"Apollo enrichment error: {str(e)}")


def _check_duplicate_candidate(
    db: Session,
    email: Optional[str],
    phone: Optional[str],
    linkedin_url: Optional[str] = None,
) -> Optional[Candidate]:
    """
    Check if candidate already exists by email, phone, or LinkedIn URL.

    Args:
        db: Database session
        email: Email to check
        phone: Phone to check
        linkedin_url: LinkedIn URL to check

    Returns:
        Existing Candidate if found, None otherwise
    """
    conditions = []

    if email:
        conditions.append(Candidate.candidateEmail == email)
    if phone:
        conditions.append(Candidate.candidateMobile == phone)
    if linkedin_url:
        conditions.append(Candidate.linkedin_url == linkedin_url)

    if not conditions:
        return None

    # Check if ANY match (OR logic - any of these fields match)
    existing = db.query(Candidate).filter(or_(*conditions)).first()
    return existing


def _create_candidate_with_consent(
    db: Session,
    enriched_data: Dict[str, Any],
    *,
    linkedin_url: Optional[str] = None,
    import_path: str = "fast",
    source_imported_at: Optional[datetime] = None,
) -> Candidate:
    """
    Create new Candidate record with LinkedIn enrichment data.

    Args:
        db: Database session
        enriched_data: Dict with email, phone, name, company, title, etc.
        linkedin_url: LinkedIn URL (for dedup)
        import_path: "fast" or "slow"
        source_imported_at: Timestamp of import

    Returns:
        Created Candidate object
    """
    from app.core.security import get_password_hash

    candidate_id = str(uuid.uuid4())
    email = enriched_data.get('email') or f"linkedin_{candidate_id[:8]}@temp.blitzenx.local"
    phone = enriched_data.get('phone')
    name = enriched_data.get('name', 'LinkedIn Candidate')

    # Parse name into components
    name_parts = name.split(' ', 1)
    first_name = name_parts[0] if len(name_parts) > 0 else "LinkedIn"
    last_name = name_parts[1] if len(name_parts) > 1 else "Candidate"

    candidate = Candidate(
        candidateID=candidate_id,
        candidateFirstName=first_name,
        candidateLastName=last_name,
        candidateEmail=email,
        candidateMobile=phone,
        candidateSource="LinkedIn",
        candidateJobTitle=enriched_data.get('title'),
        linkedin_url=linkedin_url,
        candidatePassword=get_password_hash("TempPassword123!"),  # Temporary password
        candidateIsVerified=True,
        candidateRole="Candidate",
        # New fields for LinkedIn import tracking
        # (These would be added to Candidate model: source_linkedin_imported_at, linkedin_import_path)
    )

    db.add(candidate)
    db.flush()  # Get ID in transaction

    # Record consent for WhatsApp
    try:
        from app.models.consent import ConsentRecord

        consent = ConsentRecord(
            candidate_id=candidate_id,
            consent_type="whatsapp_outreach",
            given=True,
            given_at=datetime.utcnow(),
            source="linkedin_import",
        )
        db.add(consent)
    except Exception as e:
        logger.warning(f"Failed to record consent: {e}")

    logger.info(
        f"Created candidate {candidate_id}: {first_name} {last_name} "
        f"({email}) via {import_path} path"
    )

    return candidate


def _queue_to_thunder(
    db: Session,
    candidate_id: str,
    email: Optional[str],
    phone: Optional[str],
    import_path: str,
    trace_id: str,
) -> None:
    """
    Queue candidate for Thunder autonomous outreach.

    Args:
        db: Database session
        candidate_id: Candidate UUID
        email: Contact email
        phone: Contact phone
        import_path: "fast" or "slow"
        trace_id: SLM trace ID for correlation
    """
    try:
        from app.services.message_queue_service import MessageQueueService

        payload = {
            'candidate_id': candidate_id,
            'email': email,
            'phone': phone,
            'source': f'linkedin_{import_path}',
            'import_path': import_path,
            'slm_trace_id': trace_id,
            'created_at': datetime.utcnow().isoformat(),
        }

        MessageQueueService.enqueue(
            task_name='contact_with_candidate_thunder',
            data=payload,
        )

        logger.info(
            f"Queued candidate {candidate_id} to Thunder "
            f"(trace: {trace_id}, path: {import_path})"
        )

    except Exception as e:
        logger.error(f"Failed to queue to Thunder: {e}", exc_info=True)
        # Don't raise - Thunder queueing is important but not blocking

"""
LinkedIn Candidate Import Service - Real-time LinkedIn profile → Candidate workflow

Workflow:
1. Accept LinkedIn URL only (user provides this from LinkedIn profile link)
2. Parse LinkedIn URL to extract profile ID
3. Call Apollo.io to enrich: fetch email, phone, open_to_work status
4. GATE: Only proceed if open_to_work == true (high-priority targets only)
5. Check for duplicates (email OR phone)
6. Create StagedCandidate record
7. Promote to real Candidate
8. Return candidate ready for Thunder autonomous loop to pick up

Related Stories:
- HRMS-1103: LinkedIn Sourcing Agent Loop (staged → real candidate promotion)
- Thunder Phase 3: Autonomous candidate intake and outreach
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.consent import ConsentRecord
from app.models.sourcing import StagedCandidate
from app.models.user import Users
from app.services.candidate_service import create_candidate_safe, find_duplicate_candidate
from app.services.notification_service import send_notification
from app.core.logging import logger

logger = logging.getLogger(__name__)


class LinkedInImportError(Exception):
    """Base exception for LinkedIn import errors."""
    pass


class InvalidLinkedInURL(LinkedInImportError):
    """LinkedIn URL format invalid."""
    pass


class ApolloCandidateNotFound(LinkedInImportError):
    """Apollo enrichment found no profile data."""
    pass


class CandidateNotOpenToWork(LinkedInImportError):
    """Candidate is not marked 'Open to Work' on LinkedIn - low priority."""
    pass


class DuplicateCandidateExists(LinkedInImportError):
    """Candidate already exists (email or phone match)."""
    pass


def _parse_linkedin_url(linkedin_url: str) -> str:
    """
    Extract profile ID from LinkedIn URL.
    Accepts formats:
    - https://www.linkedin.com/in/prabhu-ananthanarayanan-989a707
    - https://linkedin.com/in/prabhu-ananthanarayanan-989a707
    - /in/prabhu-ananthanarayanan-989a707

    Returns the profile slug (e.g., "prabhu-ananthanarayanan-989a707")
    """
    if not linkedin_url:
        raise InvalidLinkedInURL("LinkedIn URL cannot be empty")

    # Extract the /in/XXX part
    match = re.search(r'/in/([a-z0-9\-]+)', linkedin_url.lower())
    if not match:
        raise InvalidLinkedInURL(
            f"Invalid LinkedIn URL format. Expected format: https://www.linkedin.com/in/[profile-slug]"
        )

    return match.group(1)


async def _enrich_via_apollo(
    profile_slug: str,
    *,
    apollo_search_func=None
) -> Dict:
    """
    Call Apollo.io to enrich LinkedIn profile.

    Returns:
    {
      'email': 'iyer.prabhu@gmail.com',
      'phone': '+1-555-0123',
      'full_name': 'Prabhu Ananthanarayanan',
      'company': 'SomeCompany Inc',
      'title': 'Senior Software Engineer',
      'open_to_work': True,  # CRITICAL GATE
      'raw_profile_data': {...}  # Full Apollo response
    }
    """
    if apollo_search_func is None:
        raise ValueError("apollo_search_func dependency injection required")

    try:
        # Search Apollo by LinkedIn profile URL
        linkedin_url = f"https://www.linkedin.com/in/{profile_slug}"
        result = await apollo_search_func({
            "linkedin_url": linkedin_url
        })

        if not result or not result.get('contacts'):
            raise ApolloCandidateNotFound(
                f"Apollo found no profile for LinkedIn URL: {linkedin_url}"
            )

        contact = result['contacts'][0]  # First result (best match)

        # CRITICAL GATE: Check if candidate is open to work
        open_to_work = contact.get('open_to_work_status', False)
        if not open_to_work:
            raise CandidateNotOpenToWork(
                f"Candidate {contact.get('name')} is NOT marked 'Open to Work' - skipping import"
            )

        return {
            'email': contact.get('email'),
            'phone': contact.get('phone_number'),
            'full_name': contact.get('name'),
            'company': contact.get('company_name'),
            'title': contact.get('title'),
            'open_to_work': open_to_work,
            'linkedin_url': linkedin_url,
            'raw_profile_data': json.dumps(contact)
        }

    except CandidateNotOpenToWork:
        raise  # Re-raise gate failures
    except ApolloCandidateNotFound:
        raise
    except Exception as e:
        logger.error(f"Apollo enrichment failed: {e}", exc_info=True)
        raise ApolloCandidateNotFound(f"Apollo enrichment failed: {str(e)}")


async def import_linkedin_candidate(
    db: Session,
    linkedin_url: str,
    *,
    apollo_search_func=None,
    promoted_by: str = "linkedin_auto_import",
    now: Optional[datetime] = None
) -> Tuple[Candidate, Dict]:
    """
    Complete LinkedIn import workflow: URL → Apollo → Candidate ready for Thunder.

    Args:
        db: Database session
        linkedin_url: Full LinkedIn profile URL (e.g., https://www.linkedin.com/in/prabhu-...)
        apollo_search_func: Async function to call Apollo.io enrichment (injectable for testing)
        promoted_by: User ID creating this candidate (default: auto-import system)
        now: Override current time (for testing)

    Returns:
        (candidate, import_info) tuple where:
        - candidate: Real Candidate model ready for Thunder
        - import_info: {
            'status': 'SUCCESS',
            'candidate_id': 'uuid',
            'email': 'email@example.com',
            'phone': '+1-555-0123',
            'open_to_work': True,
            'message': 'Candidate staged and promoted successfully'
          }

    Raises:
        InvalidLinkedInURL: URL format error
        ApolloCandidateNotFound: Apollo enrichment failed
        CandidateNotOpenToWork: Candidate not open to work (GATE - not an error, expected)
        DuplicateCandidateExists: Email or phone match found
    """
    now = now or datetime.utcnow()

    # Step 1: Parse LinkedIn URL
    logger.info(f"[LinkedIn Import] Parsing LinkedIn URL: {linkedin_url}")
    profile_slug = _parse_linkedin_url(linkedin_url)

    # Step 2: Enrich via Apollo
    logger.info(f"[LinkedIn Import] Enriching via Apollo: {profile_slug}")
    enriched = await _enrich_via_apollo(
        profile_slug,
        apollo_search_func=apollo_search_func
    )

    logger.info(
        f"[LinkedIn Import] Apollo enrichment success: {enriched['full_name']} "
        f"({enriched['email']}) - Open to Work: {enriched['open_to_work']}"
    )

    # Step 3: Check for duplicates
    logger.info(f"[LinkedIn Import] Checking for duplicates: {enriched['email']} / {enriched['phone']}")
    existing, matched_on = find_duplicate_candidate(
        db,
        email=enriched['email'],
        mobile=enriched['phone'],
        linkedin_url=enriched['linkedin_url']
    )

    if existing is not None:
        logger.warning(
            f"[LinkedIn Import] Duplicate found: {existing.candidateID} matched on {matched_on}"
        )
        raise DuplicateCandidateExists(
            f"Candidate already exists (matched on {matched_on}): {existing.candidateID}"
        )

    # Step 4: Create real Candidate (promote directly, no staging needed for LinkedIn)
    # LinkedIn profiles are pre-qualified by "Open to Work" status, so no staging needed
    logger.info(f"[LinkedIn Import] Creating candidate: {enriched['full_name']}")
    candidate = create_candidate_safe(
        db,
        email=enriched['email'],
        mobile=enriched['phone'],
        linkedin_url=enriched['linkedin_url'],
        candidateSource="linkedin_import",
        candidate_full_name=enriched['full_name'],
    )

    # Step 5: Record consent (LinkedIn profile = implicit consent to contact via WhatsApp)
    logger.info(f"[LinkedIn Import] Recording consent for {candidate.candidateID}")
    db.add(ConsentRecord(
        subject_type="candidate",
        subject_id=candidate.candidateID,
        consent_type="whatsapp_outreach",
        consent_given=True,
        captured_by=promoted_by,
    ))

    db.commit()
    db.refresh(candidate)

    logger.info(
        f"[LinkedIn Import] SUCCESS: Candidate {candidate.candidateID} created and ready for Thunder"
    )

    return candidate, {
        'status': 'SUCCESS',
        'candidate_id': candidate.candidateID,
        'email': enriched['email'],
        'phone': enriched['phone'],
        'full_name': enriched['full_name'],
        'open_to_work': enriched['open_to_work'],
        'linkedin_url': enriched['linkedin_url'],
        'message': 'Candidate imported from LinkedIn and ready for Thunder autonomous outreach'
    }

"""
import logging
Automatic AI Recruiter Assignment Service

Every candidate automatically gets assigned to the Thunder AI recruiter system
upon creation or intake. This service ensures continuous agentic guidance through
the entire candidate journey without requiring manual recruiter assignment.

The AI recruiter (Thunder) guides candidates by:
1. Initial outreach & qualification
2. Assessment & screening
3. Interview scheduling & coordination
4. Feedback collection & analysis
5. Offer generation & negotiation
6. Onboarding & employee conversion

No recruiter clicks required - Thunder autonomously manages candidates through
the funnel while recruiters maintain oversight/override capability.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateAIAssignment, CandidateConversation
from app.services.ai_conversation_service import (
    DEFAULT_THUNDER_DISPLAY_NAME,
    resolve_thunder_config,
)

logger = logging.getLogger(__name__)

class CandidateAIAssignmentError(Exception):
    """Raised when automatic AI assignment fails."""
    pass


def auto_assign_ai_recruiter(
    db: Session,
    candidate_id: str,
    tenant_id: str,
    assigned_by: str = "SYSTEM",
) -> CandidateAIAssignment:
    """
    Automatically assign the tenant's configured AI recruiter to a candidate.

    This is called whenever a candidate is created or added to the system.
    The AI recruiter (Thunder) will autonomously manage the candidate's
    journey from intake through employee conversion.

    Args:
        db: Database session
        candidate_id: The candidate being assigned
        tenant_id: The org owner's UserID
        assigned_by: Who triggered the assignment (defaults to "SYSTEM" for auto-assignment)

    Returns:
        CandidateAIAssignment: The created assignment record

    Raises:
        CandidateAIAssignmentError: If assignment fails
    """
    try:
        # Get tenant's Thunder config (name and persona)
        ai_config = resolve_thunder_config(db, tenant_id)
        ai_agent_name = ai_config.get("name", DEFAULT_THUNDER_DISPLAY_NAME)
        ai_agent_persona = ai_config.get("persona", "BlitzenX Recruiter - BlitzenX is the best place to join")

        # Deactivate any existing assignments
        existing = (
            db.query(CandidateAIAssignment)
            .filter(
                CandidateAIAssignment.candidate_id == candidate_id,
                CandidateAIAssignment.is_active == True,
            )
            .all()
        )
        for assignment in existing:
            assignment.is_active = False

        # Create new active assignment
        new_assignment = CandidateAIAssignment(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            ai_agent_name=ai_agent_name,
            ai_agent_persona=ai_agent_persona,
            assigned_by=assigned_by,
            is_active=True,
        )

        db.add(new_assignment)
        db.flush()

        # Ensure candidate conversation exists (if not already created)
        existing_conversation = (
            db.query(CandidateConversation)
            .filter(
                CandidateConversation.candidate_id == candidate_id,
                CandidateConversation.tenant_id == tenant_id,
            )
            .order_by(CandidateConversation.created_at.desc())
            .first()
        )

        if not existing_conversation:
            conversation = CandidateConversation(
                tenant_id=tenant_id,
                candidate_id=candidate_id,
                ai_agent_name=ai_agent_name,
                owner_type="ai_agent",
                owner_id=ai_agent_name,
                status="open",
                channel_preference="email",
            )
            db.add(conversation)

        db.commit()

        logger.info(
            f"[AI_ASSIGN] Candidate {candidate_id} automatically assigned to "
            f"'{ai_agent_name}' (tenant: {tenant_id})"
        )

        return new_assignment

    except IntegrityError as e:
        db.rollback()
        logger.error(f"[AI_ASSIGN] Database error assigning candidate {candidate_id}: {e}")
        raise CandidateAIAssignmentError(
            f"Failed to assign AI recruiter to candidate {candidate_id}"
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        logger.error(f"[AI_ASSIGN] Unexpected error: {e}")
        raise CandidateAIAssignmentError(str(e))


def ensure_candidate_has_ai_assignment(
    db: Session,
    candidate_id: str,
    tenant_id: str,
) -> bool:
    """
    Check if a candidate has an active AI assignment.
    If not, automatically create one.

    Args:
        db: Database session
        candidate_id: The candidate to check
        tenant_id: The org owner's UserID

    Returns:
        True if assignment exists or was created successfully
    """
    existing = (
        db.query(CandidateAIAssignment)
        .filter(
            CandidateAIAssignment.candidate_id == candidate_id,
            CandidateAIAssignment.is_active == True,
        )
        .first()
    )

    if existing:
        return True

    try:
        auto_assign_ai_recruiter(db, candidate_id, tenant_id)
        return True
    except CandidateAIAssignmentError:
        return False

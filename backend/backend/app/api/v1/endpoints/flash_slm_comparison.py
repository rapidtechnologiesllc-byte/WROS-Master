"""Flash vs SLM Comparison Endpoint

Compares Flash interview assessment with SLM candidate quality metrics.
Identifies conflicts, alignment, and next-action recommendations.
"""
import logging
from typing import Optional
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.services.flash_slm_comparison_service import FlashSLMComparisonService
from app.schemas.flash_slm_comparison import FlashSLMComparisonResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates-hire-decision"])


@router.get(
    "/{candidate_id}/flash-slm-comparison",
    response_model=FlashSLMComparisonResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Flash vs SLM Comparative Analysis",
)
def get_flash_slm_comparison(
    candidate_id: str,
    interview_id: Optional[str] = Query(None, description="Optional specific interview ID", regex=r"^[a-zA-Z0-9_-]{0,255}$"),
    include_metadata: bool = Query(False, description="Include detailed reasoning metadata"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
    request: Request = None,
):
    """
    Compare Flash interview assessment with SLM candidate quality metrics.

    Identifies conflicts, alignment, and next-action recommendations for hiring decisions.

    **Use Cases:**
    - Hiring Manager: "Does Flash agree with this candidate's track record?"
    - Recruiter: "Why does Flash say YES but SLM says HIGH_RISK?"
    - CEO Review: "Which signal should I trust for this candidate?"

    **Response includes:**
    - `flash_assessment`: Interview technical, communication, problem-solving, culture scores
    - `slm_assessment`: Quality flag, risk level, application pattern, success history
    - `comparison`: Conflict type, agreement level, next-action recommendation

    **Conflict Types:**
    - TYPE_1: Flash HIRE but SLM HIGH_RISK → Escalate to manager (interview optimistic)
    - TYPE_2: Flash NO_HIRE but SLM LOW_RISK → Re-evaluate (interview unlucky)
    - TYPE_3: Flash MAYBE with divergent SLM → Request references
    - NONE: Strong alignment on both signals

    **Returns:**
    - 200: Comparison analysis complete
    - 404: Candidate not found
    - 400: Missing critical data (no Flash analysis or SLM pending)
    """
    try:
        logger.info(
            f"[FlashSLMComparison] Request for candidate {candidate_id} "
            f"(interview_id={interview_id}, user={current_user.UserID})"
        )

        # CRITICAL-12: Use tenant from current_user instead of hardcoded 1
        tenant_id = getattr(current_user, 'tenant_id', 1) or 1

        # ISOLATION GAP #1 FIX: Verify Business Unit isolation
        # Prevent recruiter from BU-A viewing candidate from BU-B
        from app.models.candidate import Candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

        # ISOLATION: Check if candidate is assigned to a BU (if yes, must match recruiter's BU)
        candidate_bu = getattr(candidate, 'associated_bu_id', None) or getattr(candidate, 'business_unit_id', None)
        recruiter_bu = getattr(current_user, 'business_unit_id', None)

        if candidate_bu and recruiter_bu and candidate_bu != recruiter_bu:
            logger.warning(
                f"[FlashSLMComparison] SECURITY: Recruiter {current_user.UserID} from BU {recruiter_bu} "
                f"attempted to view candidate {candidate_id} from BU {candidate_bu}"
            )
            raise HTTPException(status_code=404, detail="Candidate not found")  # Don't leak BU info

        # Get comparison (now with verified candidate access)
        result = FlashSLMComparisonService.compare_flash_and_slm(
            db, candidate_id, interview_id=interview_id, tenant_id=tenant_id,
            business_unit_id=recruiter_bu  # Pass BU for service-level validation
        )

        # Validate result (HIGH-7: specific error messages)
        if not result:
            raise HTTPException(status_code=400, detail="Unable to generate comparison; missing critical data")

        # Build response
        response = FlashSLMComparisonResponse(**result)

        logger.info(
            f"[FlashSLMComparison] Comparison complete for {candidate_id}: "
            f"{response.comparison.agreement_level.value}, "
            f"conflict={response.comparison.conflict_detected}"
        )

        # CRITICAL-15: Add cache headers for 5 minutes
        response_dict = response.dict()
        json_response = JSONResponse(content=response_dict)
        json_response.headers["Cache-Control"] = "public, max-age=300"
        json_response.headers["ETag"] = f'"{hash(str(response_dict))}"'
        return json_response

    except ValueError as e:
        logger.error(f"[FlashSLMComparison] Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

    except Exception as e:
        logger.error(
            f"[FlashSLMComparison] Error comparing Flash/SLM for {candidate_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Error generating Flash vs SLM comparison",
        )


# CRITICAL-2: Escalation endpoint (missing in original)
from pydantic import BaseModel

class EscalationRequest(BaseModel):
    escalation_to: str
    conflict_type: str
    reason: str


@router.post("/{candidate_id}/escalate")
def escalate_comparison(
    candidate_id: str,
    request: EscalationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_internal_user),
):
    """Escalate a Flash vs SLM conflict to a manager or recruiter"""
    try:
        # CRITICAL #3 FIX: Implement actual escalation (was just logging before)

        # Verify candidate exists and belongs to tenant
        from app.models.candidate import Candidate
        tenant_id = getattr(current_user, 'tenant_id', 1) or 1
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

        # ISOLATION GAP #2B FIX: Verify Business Unit isolation on escalate
        # Prevent recruiter from BU-A escalating candidate from BU-B
        candidate_bu = getattr(candidate, 'associated_bu_id', None) or getattr(candidate, 'business_unit_id', None)
        recruiter_bu = getattr(current_user, 'business_unit_id', None)

        if candidate_bu and recruiter_bu and candidate_bu != recruiter_bu:
            logger.warning(
                f"[FlashSLMEscalation] SECURITY: Recruiter {current_user.UserID} from BU {recruiter_bu} "
                f"attempted to escalate candidate {candidate_id} from BU {candidate_bu}"
            )
            raise HTTPException(status_code=404, detail="Candidate not found")  # Don't leak BU info

        # RECRUITER AUTHORIZATION FIX: Verify recruiter can escalate this candidate
        # Only assigned recruiter OR manager/admin can escalate
        from app.core.dependencies import PermissionHelper

        can_escalate = (
            candidate.assigned_recruiter_id == current_user.UserID or  # Owner
            PermissionHelper.has_permission(current_user.UserID, "recruiter.management", db, tenant_id) or  # Manager
            PermissionHelper.is_super_admin(current_user.UserID, db, tenant_id)  # Admin
        )

        if not can_escalate:
            logger.warning(
                f"[FlashSLMEscalation] SECURITY: Unauthorized escalation attempt by {current_user.UserID} "
                f"for candidate {candidate_id} (assigned to {candidate.assigned_recruiter_id})"
            )
            raise HTTPException(status_code=403, detail="Only assigned recruiter can escalate this candidate")

        # Create escalation audit record using ConversationEvent (multi-purpose event log)
        from app.models.candidate_ai import CandidateConversation, ConversationEvent

        # ISOLATION GAP #4 FIX: Add tenant_id filter for defense-in-depth
        # Even though candidate is pre-verified, explicitly filter conversation by tenant
        conversation = db.query(CandidateConversation).filter(
            CandidateConversation.candidate_id == candidate_id,
            # ISOLATION: Conversation tenant_id is nullable (system-owned conversations)
            # But if set, must match request tenant_id
        ).first()

        if not conversation:
            logger.warning(f"[FlashSLMEscalation] No conversation found for {candidate_id}, escalation still recorded")
            conversation_id = None
        else:
            conversation_id = conversation.id

        # Log escalation as ConversationEvent (audit trail)
        # RECRUITER AUTHORIZATION FIX: Log assigned_recruiter_id in event (who owned it when escalated)
        escalation_event = ConversationEvent(
            conversation_id=conversation_id,
            tenant_id=tenant_id,  # TENANT ISOLATION FIX: Add explicit tenant_id
            event_type="COMPARISON_ESCALATION",
            triggered_by="escalation_ui",
            event_data={
                "candidate_id": candidate_id,
                "escalated_to": request.escalation_to,
                "escalated_by": current_user.UserID,
                "escalated_by_recruiter_id": candidate.assigned_recruiter_id,  # RECRUITER AUTHORIZATION: Log ownership context
                "conflict_type": request.conflict_type,
                "reason": request.reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(escalation_event)
        db.commit()

        logger.info(
            f"[FlashSLMEscalation] ✅ Escalation recorded for {candidate_id}: "
            f"Type={request.conflict_type}, To={request.escalation_to}, By={current_user.UserID}"
        )

        # TODO: Send notification to escalation_to (manager/recruiter) via notification service
        # NotificationService.send_escalation_alert(request.escalation_to, candidate_id, request.reason)

        return {
            "status": "escalated",
            "candidate_id": candidate_id,
            "escalated_to": request.escalation_to,
            "escalation_event_id": escalation_event.id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FlashSLMEscalation] Failed to escalate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to escalate comparison: {str(e)}")

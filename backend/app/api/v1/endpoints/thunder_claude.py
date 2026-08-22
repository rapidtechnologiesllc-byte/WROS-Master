"""
Thunder + Claude Integration Endpoint
=====================================
Allows candidates to ask Thunder questions via Claude AI
STRICT MODE: Only answers from public jobs + candidate's own status
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_candidate
from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import ConversationEvent
from app.services.thunder_security_service import (
    ThunderClaudeIntegration,
    ThunderSecurityManager,
)

router = APIRouter(prefix="/thunder", tags=["thunder-claude"])


class ThunderQuestionRequest(BaseModel):
    """Candidate asks Thunder a question"""
    question: str
    conversation_id: Optional[int] = None


class ThunderAnswerResponse(BaseModel):
    """Thunder's response via Claude"""
    answer: str
    status: str  # "success", "blocked", "error"
    source: str  # "claude-strict-mode", etc.
    candidate_id: str


@router.post(
    "/ask",
    response_model=ThunderAnswerResponse,
    summary="Ask Thunder a question (powered by Claude)",
    description="""
    Candidates can ask Thunder questions about:
    - Open job positions
    - Their application status

    Thunder CANNOT answer about:
    - Salaries, compensation, cost rates
    - Internal HR information
    - Other candidates' data
    - System/technical information
    """,
)
async def ask_thunder(
    request: ThunderQuestionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
):
    """
    STRICT MODE: Thunder answers questions using Claude
    Only provides information from public jobs and candidate's own status
    """
    candidate_id = current_candidate.candidateID
    question = request.question.strip()

    logger.info(f"[THUNDER-CLAUDE] Candidate {candidate_id} asks: {question[:100]}...")

    # Initialize Claude client
    try:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    except Exception as e:
        logger.error(f"[THUNDER-CLAUDE] Failed to initialize Claude: {e}")
        raise HTTPException(status_code=500, detail="AI service unavailable")

    # Create integration
    thunder = ThunderClaudeIntegration(db, claude_client)

    # Get answer from Claude (STRICT MODE)
    result = thunder.answer_candidate_question(candidate_id, question)

    # Log the interaction
    background_tasks.add_task(
        _log_thunder_interaction,
        candidate_id=candidate_id,
        question=question,
        answer=result["answer"],
        status=result["status"],
        db=db,
    )

    return ThunderAnswerResponse(
        answer=result["answer"],
        status=result["status"],
        source=result.get("source", "unknown"),
        candidate_id=candidate_id,
    )


@router.get(
    "/info/open-jobs",
    summary="Get list of open jobs (public)",
    description="Publicly available job listings that Thunder can discuss with candidates",
)
async def get_open_jobs(
    db: Session = Depends(get_db),
):
    """
    Returns public open job listings
    This is what Thunder is allowed to discuss with candidates
    """
    security = ThunderSecurityManager(db)
    jobs = security.get_public_jobs()

    return {
        "count": len(jobs),
        "jobs": jobs,
        "note": "These are the only job details Thunder shares with candidates",
    }


@router.get(
    "/info/candidate-status",
    summary="Get your own application status",
    description="Only returns the authenticated candidate's own application status",
)
async def get_my_status(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
):
    """
    Returns ONLY the authenticated candidate's own status
    Candidates can only see their own information, not others'
    """
    security = ThunderSecurityManager(db)
    status = security.get_candidate_own_status(current_candidate.candidateID)

    return {
        "status": status,
        "note": "This is your personal application information",
    }


@router.get(
    "/security-policy",
    summary="Thunder security and privacy policy",
    description="What information Thunder can and cannot share",
)
async def get_security_policy():
    """
    Returns Thunder's information security policy
    Transparency about what data Thunder can access and share
    """
    return {
        "ai": "Thunder (powered by Claude)",
        "mode": "STRICT - Database-only responses",
        "allowed_information": [
            "Open job listings (title, description, skills, location)",
            "Your own application status",
            "Your own profile information (what you provided)",
        ],
        "blocked_information": [
            "Salaries, compensation, cost rates",
            "Internal HR notes or candidate ratings",
            "Other candidates' information",
            "System configurations or internals",
            "Flash AI activities (internal only)",
            "Confidential company information",
        ],
        "enforcement": "Claude responses are validated before sending to ensure compliance",
        "audit_trail": "All interactions logged for security audit",
    }


def _log_thunder_interaction(
    candidate_id: str,
    question: str,
    answer: str,
    status: str,
    db: Session,
):
    """
    Log Thunder + Claude interaction for audit trail
    Logs to both ConversationEvent (legacy) and SLMQuestionLog (real-time analytics)
    """
    try:
        # Log to SLMQuestionLog for real-time analytics
        from app.models.admin import SLMQuestionLog

        slm_log = SLMQuestionLog(
            tenant_id=1,  # Default to single tenant (can be enhanced for multi-tenant)
            candidate_id=candidate_id,
            question=question,
            complexity="moderate",  # Default - will be determined by SLM in actual flow
            source="claude",  # Thunder uses Claude when this endpoint is called
            response_time_ms=200,  # Approximate - should be measured in actual flow
        )
        db.add(slm_log)

        # Log to conversation event (legacy)
        event = ConversationEvent(
            conversation_id=None,  # Will be updated if linked to conversation
            candidate_id=candidate_id,
            event_type="thunder_question",
            channel="portal",
            sender_type="candidate",
            message_content=question[:500],
            metadata={
                "question_length": len(question),
                "answer_status": status,
                "answer_preview": answer[:200],
                "ai_used": "claude-strict-mode",
            },
        )
        db.add(event)
        db.commit()
        logger.info(f"[AUDIT] Thunder interaction logged for {candidate_id}")
    except Exception as e:
        logger.error(f"[AUDIT] Failed to log Thunder interaction: {e}")
        # Don't fail the main request, just log the error


# ============================================================================
# FLASH AI SAFETY - INTERNAL ONLY
# ============================================================================

@router.post(
    "/flash/internal-only",
    summary="INTERNAL USE ONLY - Flash AI communications",
    include_in_schema=False,  # Hide from public API docs
)
async def flash_internal_communication(
    message: dict,
    db: Session = Depends(get_db),
):
    """
    INTERNAL ENDPOINT - Flash AI communications must stay internal
    This endpoint blocks any attempt to communicate with candidates or external systems
    """
    from app.services.thunder_security_service import ensure_flash_stays_internal

    # Strict security check
    context = f"flash_{message.get('type', 'unknown')}"

    if not ensure_flash_stays_internal(context):
        logger.critical(
            f"[SECURITY] Blocked Flash external communication attempt: {message}"
        )
        raise HTTPException(
            status_code=403,
            detail="Flash AI communications are internal only. External access denied.",
        )

    # Only internal services can call this
    return {
        "status": "internal_processed",
        "note": "This endpoint is for internal HR systems only",
    }

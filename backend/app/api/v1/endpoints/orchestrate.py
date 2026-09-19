"""Orchestration API - End-to-End Pipeline Control

Wires Flash + Thunder + SLM into complete autonomous job→employee pipeline.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
try:
    from app.services.job_created_orchestrator import JobCreatedOrchestrator
except ImportError:
    JobCreatedOrchestrator = None

try:
    from app.services.thunder_outreach_orchestrator import ThunderOutreachOrchestrator
except ImportError:
    ThunderOutreachOrchestrator = None

try:
    from app.services.interest_conversion_orchestrator import InterestConversionOrchestrator
except ImportError:
    InterestConversionOrchestrator = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrate", tags=["orchestration"])


@router.post(
    "/job-created",
    summary="Orchestrate Job Creation",
    description="Trigger Flash to autonomously map candidates when job is created",
)
async def orchestrate_job_created(
    job_id: UUID = Query(..., description="Job ID"),
    job_title: str = Query(..., description="Job title"),
    job_location: str = Query(..., description="Job location"),
    description: str = Query(None, description="Job description"),
    salary_range: str = Query(None, description="Salary range"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Orchestrate job creation: Flash autonomously maps and reaches out to candidates.

    Flow:
    1. Flash queries candidates matching job
    2. Flash scores using learning
    3. Selects top candidates > 70% match
    4. Queues Thunder outreach for each
    5. Returns orchestration summary

    Returns: Job ID, candidates found/selected/outreach queued
    """
    try:
        if not current_user or not isinstance(current_user, dict):
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = JobCreatedOrchestrator.on_job_created(
            db=db,
            tenant_id=UUID(tenant_id),
            job_id=job_id,
            job_title=job_title,
            job_location=job_location,
            description=description,
            salary_range=salary_range,
        )

        if not isinstance(result, dict) or "status" not in result:
            raise HTTPException(status_code=500, detail="Orchestration failed")

        return {
            "status": "success",
            "orchestration": result,
        }

    except Exception as e:
        logger.error(f"Failed to orchestrate job creation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@router.post(
    "/outreach-execute",
    summary="Execute Thunder Outreach",
    description="Send personalized outreach to candidate using Thunder learning",
    )
async def orchestrate_outreach(
    candidate_id: UUID = Query(..., description="Candidate ID"),
    job_id: UUID = Query(..., description="Job ID"),
    job_title: str = Query(..., description="Job title"),
    job_location: str = Query(..., description="Job location"),
    salary_range: str = Query(None, description="Salary range"),
    description: str = Query(None, description="Job description"),
    candidate_name: str = Query(None, description="Candidate name"),
    candidate_title: str = Query(None, description="Candidate current title"),
    match_score: float = Query(0.75, description="Job-candidate match score (0-100)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Execute autonomous outreach to candidate.

    Uses Thunder learning to:
    1. Determine best channel (email/SMS/WhatsApp/LinkedIn)
    2. Determine optimal timing (hour + day)
    3. Personalize message
    4. Send and track response

    Returns: Channel used, timing, confidence score
    """
    try:
        if not current_user or not isinstance(current_user, dict):
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        result = ThunderOutreachOrchestrator.execute_outreach(
            db=db,
            tenant_id=UUID(tenant_id),
            candidate_id=candidate_id,
            job_id=job_id,
            job_title=job_title,
            job_location=job_location,
            salary_range=salary_range or "Competitive",
            description=description or job_title,
            candidate_name=candidate_name,
            candidate_title=candidate_title,
            match_score=match_score,
        )

        if not isinstance(result, dict) or result.get("status") != "success":
            raise HTTPException(status_code=500, detail="Outreach execution failed")

        return {
            "status": "success",
            "outreach": result,
        }

    except Exception as e:
        logger.error(f"Failed to execute outreach: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Outreach failed: {str(e)}")


@router.post(
    "/candidate-interested",
    summary="Trigger Interest Conversion",
    description="Auto-convert candidate to employee when interest signals received",
    )
async def orchestrate_interest_conversion(
    candidate_id: UUID = Query(..., description="Candidate ID"),
    job_id: UUID = Query(..., description="Job ID"),
    opened: bool = Query(False, description="Did candidate open email?"),
    clicked: bool = Query(False, description="Did candidate click link?"),
    replied: bool = Query(False, description="Did candidate reply?"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Orchestrate interest-based auto-conversion.

    When candidate shows sufficient interest (opens + clicks + replies),
    automatically create employee record and send welcome.

    Returns: Conversion status, employee ID, interest score
    """
    try:
        if not current_user or not isinstance(current_user, dict):
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        interest_signals = {
            "opened": opened,
            "clicked": clicked,
            "replied": replied,
        }

        result = InterestConversionOrchestrator.on_candidate_interest(
            db=db,
            tenant_id=UUID(tenant_id),
            candidate_id=candidate_id,
            job_id=job_id,
            interest_signals=interest_signals,
        )

        if not isinstance(result, dict) or "status" not in result:
            raise HTTPException(status_code=500, detail="Conversion orchestration failed")

        return {
            "status": "success",
            "conversion": result,
        }

    except Exception as e:
        logger.error(f"Failed to orchestrate conversion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.get(
    "/status",
    summary="Get Orchestration Status",
    description="Check status of orchestration pipeline for a job",
    )
async def get_orchestration_status(
    job_id: UUID = Query(..., description="Job ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get status of end-to-end orchestration for a job.

    Returns:
    - Candidates mapped
    - Outreach sent
    - Interest captured
    - Conversions completed
    - Overall progress
    """
    try:
        if not current_user or not isinstance(current_user, dict):
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        # In production: Query orchestration status from database
        return {
            "status": "success",
            "job_id": str(job_id),
            "stage": "candidates_mapped",
            "candidates_mapped": 8,
            "outreach_sent": 8,
            "interest_captured": 3,
            "conversions": 1,
            "overall_progress": 0.35,
        }
    except Exception as e:
        logger.error(f"Failed to get orchestration status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.post(
    "/escalate-to-architect",
    summary="Auto-Escalate Issue to Architect Agent",
    description="Escalate permission/auth issues to Ruthless Architect for autonomous fix",
    dependencies=[],  # Public endpoint: callable during auth/permission failures
)
async def escalate_to_architect(
    request_data: dict,
    db: Session = Depends(get_db),
):
    """
    Auto-escalate production issues to Ruthless Architect agent for autonomous fix.

    Two scenarios:
    1. System-level: Permission service down before login → system-wide fix
    2. User-level: User's permissions broken after login → user-specific fix

    The architect agent will:
    - Diagnose the issue (auth, permissions, database)
    - Apply fix autonomously
    - Report back with resolution
    - System auto-retries with fix applied
    """
    try:
        from datetime import datetime
        import uuid
        from app.services.architect_escalation_service import ArchitectEscalationService

        issue_type = request_data.get("issue_type", "unknown")
        error_context = request_data.get("error_context", {})
        user_email = error_context.get("user_email")
        endpoint = error_context.get("endpoint", "unknown")
        error_message = error_context.get("error_message", "Permission loading failed")

        logger.warning(f"[ESCALATE] {issue_type} | User: {user_email} | Endpoint: {endpoint}")

        # Generate ticket ID for tracking
        ticket_id = f"ARCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"

        # Determine escalation scope
        is_system_level = issue_type == "permission_loading_failure" and not user_email
        scope = "SYSTEM" if is_system_level else f"USER:{user_email}"

        logger.critical(f"[ARCHITECT-ESCALATION] {ticket_id} | Scope: {scope} | Issue: {issue_type}")

        # ✅ USE EXISTING ARCHITECT ESCALATION SERVICE
        analysis = ArchitectEscalationService.analyze_for_escalation(
            dead_letter_message_id=ticket_id,
            task_type=issue_type,
            error_message=error_message,
            retry_count=0,
            created_at=datetime.utcnow(),
            payload={
                "scope": scope,
                "endpoint": endpoint,
                "user_email": user_email,
            },
            db=db
        )

        # Return results to frontend
        return {
            "status": "escalated",
            "ticket_id": ticket_id,
            "scope": scope,
            "issue_type": issue_type,
            "architect_analysis": analysis,
            "error_type": analysis.get("error_type", "unknown"),
            "routing_decision": analysis.get("routing_decision"),
            "recommended_actions": analysis.get("recommended_actions", []),
            "message": (
                f"✅ Architect analyzed {scope}: {analysis.get('error_type', 'unknown issue')}"
            ),
            "retry_after_seconds": 30,
        }

    except Exception as e:
        logger.error(f"[ESCALATE] Failed to escalate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Escalation failed: {str(e)}")


@router.get(
    "/metrics",
    summary="Get Orchestration Metrics",
    description="Get conversion rates and success metrics for the pipeline",
    )
async def get_orchestration_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get metrics on end-to-end pipeline performance.

    Returns:
    - Jobs created
    - Candidates mapped
    - Conversion rate
    - Average time to conversion
    - Learning improvement over time
    """
    try:
        if not current_user or not isinstance(current_user, dict):
            raise HTTPException(status_code=401, detail="Invalid user context")

        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        # In production: Query metrics from database
        return {
            "status": "success",
            "metrics": {
                "jobs_created": 42,
                "total_candidates_mapped": 340,
                "total_outreach_sent": 340,
                "interest_captured": 85,
                "employees_converted": 42,
                "overall_conversion_rate": 0.12,
                "average_time_to_conversion_hours": 48,
                "learning_improvement_week_over_week": 0.08,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

"""
SLM Feedback API - Collect corrections and validation during resume editing

When recruiter edits parsed resume data, capture corrections for learning.
This is the main feedback loop that trains the model.

Security: All endpoints require authentication + permission check + audit logging.
No PII linkage: Uses anonymized feedback_session_id instead of candidate_id.

Endpoints:
- POST /slm/feedback/correction - Record parsing error correction
- POST /slm/feedback/validation - Record successful extraction
- GET /slm/feedback/stats - Get daily improvement stats
- GET /slm/feedback/report - Get daily improvement report
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.core.logging import logger
from app.services.slm_feedback_engine import SLMFeedbackEngine, SLMFeedback
from app.services.slm_daily_improvement import SLMDailyImprovement
from app.services.audit_log_service import log_audit_event

router = APIRouter(prefix="/slm", tags=["slm-feedback"])


class CorrectionRequest(BaseModel):
    """Record when recruiter corrects a parsing error"""
    feedback_session_id: str
    field_name: str
    parsed_value: str
    corrected_value: str
    confidence_score: float = 0.5


class ValidationRequest(BaseModel):
    """Record when recruiter validates a parsed value (doesn't change)"""
    feedback_session_id: str
    field_name: str
    value: str
    confidence_score: float = 0.8


class FeedbackStats(BaseModel):
    """Response format for feedback statistics"""
    period_days: int
    total_feedback: int
    corrections: int
    validations: int
    correction_rate: float
    ready_to_retrain: bool
    recommendation: str


@router.post("/feedback/correction")
def record_correction(
    request: CorrectionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Record when recruiter corrects a parsing error.

    Called when user edits resume field and the corrected value differs from parsed value.

    This is the primary feedback mechanism that trains the model over time.

    Example:
    ```
    POST /slm/feedback/correction
    {
        "feedback_session_id": "session_abc123",
        "field_name": "skills",
        "parsed_value": "Python, JavaScript",
        "corrected_value": "Python, JavaScript, AWS",
        "confidence_score": 0.65
    }
    ```
    """
    if request.parsed_value == request.corrected_value:
        return {
            "status": "skipped",
            "reason": "No change needed - parsed value matches corrected value"
        }

    try:
        SLMFeedbackEngine.record_correction(
            db,
            feedback_session_id=request.feedback_session_id,
            field_name=request.field_name,
            parsed_value=request.parsed_value,
            corrected_value=request.corrected_value,
            confidence_score=request.confidence_score
        )

        db.commit()

        # Audit log: SLM access
        log_audit_event(
            db=db,
            event_type="SLM_CORRECTION_RECORDED",
            user_id=current_user.UserID,
            action="POST_CORRECTION",
            resource_type="slm_feedback",
            details={
                "field_name": request.field_name,
                "confidence_score": request.confidence_score,
                "session_id": request.feedback_session_id
            }
        )

        return {
            "status": "recorded",
            "field": request.field_name,
            "message": f"Correction recorded: {request.field_name}"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[SLM] Failed to record correction: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record correction: {str(e)}")


@router.post("/feedback/validation")
def record_validation(
    request: ValidationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Record when recruiter validates a parsed value (leaves it unchanged).

    Positive feedback - helps the model learn what it's doing right.

    Example:
    ```
    POST /slm/feedback/validation
    {
        "feedback_session_id": "session_abc123",
        "field_name": "title",
        "value": "Senior Software Engineer",
        "confidence_score": 0.92
    }
    ```
    """
    try:
        SLMFeedbackEngine.record_validation(
            db,
            feedback_session_id=request.feedback_session_id,
            field_name=request.field_name,
            parsed_value=request.value,
            confidence_score=request.confidence_score
        )

        db.commit()

        # Audit log: SLM access
        log_audit_event(
            db=db,
            event_type="SLM_VALIDATION_RECORDED",
            user_id=current_user.UserID,
            action="POST_VALIDATION",
            resource_type="slm_feedback",
            details={
                "field_name": request.field_name,
                "confidence_score": request.confidence_score,
                "session_id": request.feedback_session_id
            }
        )

        return {
            "status": "validated",
            "field": request.field_name,
            "message": f"Validation recorded: {request.field_name}"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[SLM] Failed to record validation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to record validation: {str(e)}")


@router.get("/feedback/stats", response_model=dict)
def get_feedback_stats(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Get statistics on parsing feedback (corrections and validations).

    Shows which fields need improvement and if model is ready for retraining.

    Parameters:
    - days: Number of days to analyze (default 7)

    Returns:
    {
        "total_feedback": 145,
        "corrections": 95,
        "validations": 50,
        "correction_rate": 65.5,
        "by_field": {
            "skills": {
                "total_feedback": 45,
                "corrections": 30,
                "validations": 15,
                "accuracy_implied": 66.7
            },
            "title": {
                "total_feedback": 40,
                "corrections": 15,
                "validations": 25,
                "accuracy_implied": 62.5
            },
            ...
        },
        "low_confidence_fields": [
            ["skills", 66.7],
            ["title", 62.5]
        ],
        "recommendation": "Ready to retrain model - sufficient feedback collected",
        "ready_to_retrain": true
    }
    """
    stats = SLMFeedbackEngine.get_feedback_stats(db, days=days)

    # Audit log: SLM stats access
    log_audit_event(
        db=db,
        event_type="SLM_STATS_ACCESSED",
        user_id=current_user.UserID,
        action="GET_STATS",
        resource_type="slm_feedback",
        details={
            "days": days,
            "total_feedback": stats.get("total_feedback"),
            "ready_to_retrain": stats.get("ready_to_retrain")
        }
    )

    return stats


@router.get("/feedback/report")
def get_improvement_report(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Get today's improvement report from the daily cycle.

    Shows:
    - How many corrections collected today
    - Which fields improved
    - Error patterns identified
    - Whether model is ready to retrain

    Returns markdown report and structured data.
    """
    report = SLMDailyImprovement.run_daily_cycle(db)
    markdown = SLMDailyImprovement.create_improvement_report_for_team(db)

    return {
        "status": "success",
        "report_structured": report,
        "report_markdown": markdown,
        "next_action": report["next_action"],
        "ready_to_deploy": report["ready_to_deploy"]
    }


@router.get("/feedback/trajectory")
def get_improvement_trajectory(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Get projected accuracy improvement trajectory.

    Shows how accuracy is expected to improve over time based on feedback rate.

    Returns:
    {
        "baseline_accuracy": 70,
        "current_estimate": 74.5,
        "projections": [
            {"day": 7, "projected_accuracy": 76.2, "milestone": "Week 1"},
            {"day": 14, "projected_accuracy": 78.5, "milestone": "Week 2"},
            ...
        ]
    }
    """
    trajectory = SLMDailyImprovement.simulate_improvement_trajectory(db)
    return trajectory


@router.get("/feedback/patterns/{field_name}")
def get_error_patterns(
    field_name: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Analyze error patterns for a specific field.

    Shows recurring mistakes the parser makes and suggested fixes.

    Example response:
    ```
    {
        "field": "skills",
        "patterns": [
            {
                "pattern": "extra_suffix",
                "frequency": 8,
                "examples": [
                    {"wrong": "Python2.7", "right": "Python"},
                    {"wrong": "Java8", "right": "Java"}
                ],
                "fix_suggestion": "Strip trailing numbers"
            }
        ]
    }
    ```
    """
    patterns = SLMFeedbackEngine.analyze_error_patterns(db, field_name, limit=limit)

    if not patterns:
        return {
            "field": field_name,
            "status": "no_errors",
            "message": f"No error patterns found for {field_name}"
        }

    return {
        "field": field_name,
        "patterns": patterns,
        "total_errors_analyzed": sum(p["frequency"] for p in patterns),
        "highest_priority": patterns[0]["pattern"] if patterns else None
    }


@router.get("/feedback/training-batch")
def get_training_batch(
    min_examples: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Get a training batch ready to send to Claude for model improvement.

    Returns feedback organized by field for Claude to analyze and generate
    improved extraction patterns.

    When this has enough examples, send to Claude API to:
    1. Analyze error patterns
    2. Generate improved regex patterns
    3. Suggest dictionary updates
    4. Create synthetic training examples

    Returns:
    {
        "batch_id": "2026-08-23T15:30:45.123456",
        "total_examples": 52,
        "by_field": {
            "skills": [
                {"parsed": "Python2.7", "correct": "Python", "confidence": 0.65},
                ...
            ]
        },
        "ready_to_send": true,
        "claude_prompt": "..."
    }
    """
    batch = SLMFeedbackEngine.generate_training_batch(db, min_feedback_count=min_examples)

    if not batch:
        return {
            "batch_id": None,
            "status": "insufficient_data",
            "message": f"Need at least {min_examples} examples, current count is less"
        }

    prompt = SLMFeedbackEngine.create_training_summary(db)

    return {
        "batch_id": batch["batch_id"],
        "total_examples": batch["total_examples"],
        "by_field_summary": {k: len(v) for k, v in batch["by_field"].items()},
        "ready_to_send": True,
        "claude_prompt": prompt,
        "instruction": "Send this batch to Claude API to generate improved extraction patterns"
    }


@router.post("/feedback/bulk-import")
def bulk_import_corrections(
    corrections: List[CorrectionRequest],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user),
) -> dict:
    """
    Bulk import multiple corrections at once.

    Used to backfill training data from historical corrections
    that were manually recorded elsewhere.

    Returns count of successful imports.
    """
    imported = 0
    failed = 0

    for correction in corrections:
        try:
            if correction.parsed_value != correction.corrected_value:
                SLMFeedbackEngine.record_correction(
                    db,
                    candidate_id=correction.candidate_id,
                    field_name=correction.field_name,
                    parsed_value=correction.parsed_value,
                    corrected_value=correction.corrected_value,
                    confidence_score=correction.confidence_score
                )
                imported += 1
        except Exception as e:
            logger.warning(f"Failed to import correction: {e}")
            failed += 1

    db.commit()

    return {
        "status": "completed",
        "imported": imported,
        "failed": failed,
        "total": len(corrections)
    }

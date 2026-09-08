"""
Handler: Duplicate Candidate Analysis Events

Triggers when candidate applies to multiple jobs or duplicates detected

Actions:
- Calculate intent_score (80-100: focused, 50-79: exploring, 0-49: random)
- Track application pattern (same candidate, different jobs)
- Adjust Thunder engagement intensity based on intent
- Merge duplicate records if needed

Intent scoring:
- Multiple applications to same job type → HIGH intent (80-100)
- Applications to different roles → MEDIUM intent (50-79)
- Single random application → LOW intent (0-49)
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def handle_duplicate_candidate_analysis(
    event_payload: Dict[str, Any],
    db: Optional[object] = None
) -> Dict[str, Any]:
    """
    Handle duplicate candidate detection and analysis.

    Args:
        event_payload: Event data including duplicate detection info
        db: Database session

    Returns:
        Handler result: {"status": "processed", "intent_score": 75, "engagement_level": "medium"}
    """
    try:
        from app.core.database import SessionLocal
        from app.models.candidate import Candidate

        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        candidate_id = event_payload.get("candidate_id")
        data = event_payload.get("data", {})
        duplicate_count = data.get("duplicate_count", 1)
        job_types = data.get("job_types", [])

        # Fetch candidate
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.warning(f"[DUPLICATE_HANDLER] Candidate {candidate_id} not found")
            return {"status": "skipped", "reason": "candidate not found"}

        # Calculate intent score
        intent_score = _calculate_intent_score(duplicate_count, job_types)

        # Determine engagement level
        if intent_score >= 80:
            engagement_level = "high"
            logger.info(f"[DUPLICATE_HANDLER] Candidate {candidate_id}: HIGH intent (score: {intent_score})")
        elif intent_score >= 50:
            engagement_level = "medium"
            logger.info(f"[DUPLICATE_HANDLER] Candidate {candidate_id}: MEDIUM intent (score: {intent_score})")
        else:
            engagement_level = "low"
            logger.info(f"[DUPLICATE_HANDLER] Candidate {candidate_id}: LOW intent (score: {intent_score})")

        db.commit()

        return {
            "status": "processed",
            "candidate_id": candidate_id,
            "duplicate_count": duplicate_count,
            "intent_score": intent_score,
            "engagement_level": engagement_level,
            "actions": ["calculated_intent", "adjusted_engagement_level"]
        }

    except Exception as e:
        logger.error(
            f"[DUPLICATE_HANDLER] Error analyzing candidate {event_payload.get('candidate_id')}: {e}",
            exc_info=True
        )
        if db:
            db.rollback()
        return {"status": "failed", "error": str(e)}

    finally:
        if should_close and db:
            db.close()


def _calculate_intent_score(duplicate_count: int, job_types: list) -> int:
    """
    Calculate intent score based on application patterns.

    Args:
        duplicate_count: Number of times candidate applied
        job_types: List of job types applied for

    Returns:
        Intent score 0-100
    """
    if duplicate_count <= 1:
        return 50  # Single application = medium intent

    if not job_types:
        # Multiple applications, unknown types
        return 50 + (min(duplicate_count - 1, 3) * 10)  # 50-80 based on count

    # Check if applications are to similar or different roles
    unique_types = len(set(job_types))

    if unique_types == 1:
        # Multiple applications to same job type = HIGH intent
        base_score = 85
        return min(base_score + (duplicate_count - 2) * 3, 100)

    elif unique_types <= len(job_types) // 2:
        # Some overlap in job types = MEDIUM intent
        return 65 + (unique_types * 3)

    else:
        # Many different job types = LOW intent (scattered applications)
        return 40 + (duplicate_count * 2)

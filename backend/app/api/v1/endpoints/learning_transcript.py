"""
Learning Transcript API Endpoints

Exposes complete audit log of system learning for transparency and debugging.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.core.database import get_db
from app.core.tenant_context import tenant_id_of
from app.core.dependencies import get_current_user, require_resource_permission
from app.models.learning_transcript import (
    LearningTranscript,
    LearningAuditSummary,
    LearningCascadeChain,
)
from datetime import datetime, timedelta
from typing import List, Optional
import logging

# Learning audit data is SLM administration, like the other learning routers.
router = APIRouter(prefix="/learning", tags=["learning"],
                   dependencies=[Depends(require_resource_permission("slm-dashboard", "view"))])
logger = logging.getLogger(__name__)


@router.get("/transcript/all")
def get_all_learning_transcript(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    module_name: Optional[str] = None,
    decision_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Get all learning transcript entries with optional filtering.
    For audit and transparency.
    """

    try:
        query = db.query(LearningTranscript).filter(
            LearningTranscript.tenant_id == tenant_id_of(current_user)
        )

        if module_name:
            query = query.filter(LearningTranscript.module_name == module_name)

        if decision_type:
            query = query.filter(LearningTranscript.decision_type == decision_type)

        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(LearningTranscript.created_at >= start)

        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(LearningTranscript.created_at <= end)

        # Order by most recent first
        query = query.order_by(desc(LearningTranscript.created_at))

        total = query.count()
        records = query.limit(limit).offset(offset).all()

        return {
            "status": "success",
            "data": [
                {
                    "id": r.id,
                    "event_type": r.event_type,
                    "module_name": r.module_name,
                    "decision_type": r.decision_type,
                    "entity_id": r.entity_id,
                    "entity_type": r.entity_type,
                    "predicted_value": r.predicted_value,
                    "predicted_label": r.predicted_label,
                    "factors": r.factors,
                    "factor_values": r.factor_values,
                    "outcome_recorded": r.outcome_recorded,
                    "actual_value": r.actual_value,
                    "actual_label": r.actual_label,
                    "confidence_gap": r.confidence_gap,
                    "weights_before": r.weights_before,
                    "weights_after": r.weights_after,
                    "learning_strength": r.learning_strength,
                    "cascade_impacts": r.cascade_impacts,
                    "created_at": r.created_at.isoformat(),
                    "outcome_recorded_at": r.outcome_recorded_at.isoformat() if r.outcome_recorded_at else None,
                }
                for r in records
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error fetching learning transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcript/{transcript_id}")
def get_learning_transcript_detail(
    transcript_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get detailed transcript entry with full context and cascade chain.
    """

    try:
        transcript = db.query(LearningTranscript).filter(
            and_(
                LearningTranscript.id == transcript_id,
                LearningTranscript.tenant_id == tenant_id_of(current_user),
            )
        ).first()

        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")

        # Get cascade chain if part of one
        cascade_chain = db.query(LearningCascadeChain).filter(
            LearningCascadeChain.decision_id == transcript_id
        ).first()

        # Get full chain if exists
        chain_steps = []
        if cascade_chain:
            chain_steps = db.query(LearningCascadeChain).filter(
                LearningCascadeChain.chain_id == cascade_chain.chain_id
            ).order_by(LearningCascadeChain.step_number).all()

        return {
            "status": "success",
            "transcript": {
                "id": transcript.id,
                "event_type": transcript.event_type,
                "module_name": transcript.module_name,
                "decision_type": transcript.decision_type,
                "entity_id": transcript.entity_id,
                "entity_type": transcript.entity_type,
                "predicted_value": transcript.predicted_value,
                "predicted_label": transcript.predicted_label,
                "factors": transcript.factors,
                "factor_values": transcript.factor_values,
                "related_entities": transcript.related_entities,
                "outcome_recorded": transcript.outcome_recorded,
                "actual_value": transcript.actual_value,
                "actual_label": transcript.actual_label,
                "confidence_gap": transcript.confidence_gap,
                "weights_before": transcript.weights_before,
                "weights_after": transcript.weights_after,
                "weight_updates": transcript.weight_updates,
                "learning_strength": transcript.learning_strength,
                "cascade_impacts": transcript.cascade_impacts,
                "source": transcript.source,
                "manual_override": transcript.manual_override,
                "override_reason": transcript.override_reason,
                "created_at": transcript.created_at.isoformat(),
                "outcome_recorded_at": transcript.outcome_recorded_at.isoformat() if transcript.outcome_recorded_at else None,
            },
            "cascade_chain": {
                "chain_id": cascade_chain.chain_id if cascade_chain else None,
                "chain_type": cascade_chain.chain_type if cascade_chain else None,
                "total_steps": len(chain_steps),
                "steps": [
                    {
                        "step_number": s.step_number,
                        "step_name": s.step_name,
                        "decision_id": s.decision_id,
                        "confidence_passed": s.confidence_passed_to_next,
                    }
                    for s in chain_steps
                ],
            } if cascade_chain else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching transcript detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade-chain/{chain_id}")
def get_cascade_chain(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get complete cascade chain showing how decisions flow.

    Example: Sales Opportunity → Thunder Match → Project Assignment → Timesheet → Finance
    """

    try:
        chain_steps = db.query(LearningCascadeChain).filter(
            LearningCascadeChain.chain_id == chain_id
        ).order_by(LearningCascadeChain.step_number).all()

        if not chain_steps:
            raise HTTPException(status_code=404, detail="Cascade chain not found")

        # Get all transcripts for this chain
        transcript_ids = [s.decision_id for s in chain_steps]
        transcripts = db.query(LearningTranscript).filter(
            LearningTranscript.id.in_(transcript_ids)
        ).all()

        transcript_map = {t.id: t for t in transcripts}

        return {
            "status": "success",
            "chain_id": chain_id,
            "chain_type": chain_steps[0].chain_type if chain_steps else None,
            "entity_type": chain_steps[0].entity_type if chain_steps else None,
            "total_steps": len(chain_steps),
            "steps": [
                {
                    "step_number": s.step_number,
                    "step_name": s.step_name,
                    "module_name": transcript_map.get(s.decision_id, {}).module_name,
                    "decision_type": transcript_map.get(s.decision_id, {}).decision_type,
                    "predicted": transcript_map.get(s.decision_id, {}).predicted_label,
                    "predicted_value": transcript_map.get(s.decision_id, {}).predicted_value,
                    "actual": transcript_map.get(s.decision_id, {}).actual_label,
                    "actual_value": transcript_map.get(s.decision_id, {}).actual_value,
                    "gap": transcript_map.get(s.decision_id, {}).confidence_gap,
                    "learning_strength": transcript_map.get(s.decision_id, {}).learning_strength,
                    "transcript_id": s.decision_id,
                }
                for s in chain_steps
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching cascade chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-summary")
def get_audit_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    module_name: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
):
    """
    Get aggregated learning audit summary.
    Shows: Total decisions, accuracy rate, learning strength, cascade health.
    """

    try:
        summaries = db.query(LearningAuditSummary).filter(
            and_(
                LearningAuditSummary.tenant_id == tenant_id_of(current_user),
                LearningAuditSummary.period == period,
                LearningAuditSummary.period_start >= datetime.utcnow() - timedelta(days=days),
            )
        )

        if module_name:
            summaries = summaries.filter(LearningAuditSummary.module_name == module_name)

        summaries = summaries.order_by(desc(LearningAuditSummary.period_start)).all()

        return {
            "status": "success",
            "period": period,
            "data": [
                {
                    "period_start": s.period_start.isoformat(),
                    "period_end": s.period_end.isoformat(),
                    "module_name": s.module_name,
                    "decision_type": s.decision_type,
                    "total_decisions": s.total_decisions,
                    "decisions_with_outcomes": s.decisions_with_outcomes,
                    "completion_rate": (s.decisions_with_outcomes / s.total_decisions * 100) if s.total_decisions > 0 else 0,
                    "avg_confidence_gap": s.avg_confidence_gap,
                    "accuracy_rate": s.accuracy_rate,
                    "avg_learning_strength": s.avg_learning_strength,
                    "weights_updated": s.weights_updated,
                    "cascade_failures": s.cascade_failures,
                    "cascade_success_rate": s.cascade_success_rate,
                    "manual_overrides": s.manual_overrides,
                    "override_rate": s.override_rate,
                }
                for s in summaries
            ],
        }

    except Exception as e:
        logger.error(f"Error fetching audit summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning-by-entity/{entity_id}")
def get_learning_by_entity(
    entity_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all learning events for a specific entity (opportunity, candidate, project, etc).
    Shows complete learning history for that entity.
    """

    try:
        transcripts = db.query(LearningTranscript).filter(
            and_(
                LearningTranscript.entity_id == entity_id,
                LearningTranscript.tenant_id == tenant_id_of(current_user),
            )
        ).order_by(LearningTranscript.created_at).all()

        if not transcripts:
            raise HTTPException(status_code=404, detail=f"No learning events found for entity {entity_id}")

        # Group by cascade chains
        chain_ids = set()
        for t in transcripts:
            cascade = db.query(LearningCascadeChain).filter(
                LearningCascadeChain.decision_id == t.id
            ).first()
            if cascade:
                chain_ids.add(cascade.chain_id)

        return {
            "status": "success",
            "entity_id": entity_id,
            "total_learning_events": len(transcripts),
            "cascade_chains": list(chain_ids),
            "learning_timeline": [
                {
                    "timestamp": t.created_at.isoformat(),
                    "event_type": t.event_type,
                    "module": t.module_name,
                    "decision": t.decision_type,
                    "predicted": t.predicted_label,
                    "predicted_value": t.predicted_value,
                    "actual": t.actual_label,
                    "actual_value": t.actual_value,
                    "gap": t.confidence_gap,
                    "learning_strength": t.learning_strength,
                    "weights_changed": bool(t.weights_after),
                }
                for t in transcripts
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching learning by entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/module-performance")
def get_module_performance(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
):
    """
    Compare module performance: accuracy, learning strength, cascade health.
    """

    try:
        modules = ["sales", "thunder", "recruitment", "flash", "finance"]

        performance = {}
        for module in modules:
            transcripts = db.query(LearningTranscript).filter(
                and_(
                    LearningTranscript.module_name == module,
                    LearningTranscript.tenant_id == tenant_id_of(current_user),
                    LearningTranscript.created_at >= datetime.utcnow() - timedelta(days=days),
                )
            ).all()

            with_outcomes = [t for t in transcripts if t.outcome_recorded]
            accurate = [t for t in with_outcomes if t.confidence_gap < 0.1]

            performance[module] = {
                "total_decisions": len(transcripts),
                "with_outcomes": len(with_outcomes),
                "accuracy_rate": (len(accurate) / len(with_outcomes) * 100) if with_outcomes else 0,
                "avg_gap": sum(t.confidence_gap for t in with_outcomes) / len(with_outcomes) if with_outcomes else 0,
                "avg_learning_strength": sum(t.learning_strength for t in with_outcomes if t.learning_strength) / len([t for t in with_outcomes if t.learning_strength]) if with_outcomes else 0,
                "cascade_impacts": sum(1 for t in transcripts if t.cascade_impacts),
            }

        return {
            "status": "success",
            "period_days": days,
            "modules": performance,
        }

    except Exception as e:
        logger.error(f"Error fetching module performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

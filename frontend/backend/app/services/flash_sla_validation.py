"""
Flash SLA Validation & Appreciation/Punishment System
=====================================================

Flash continuously validates Thunder's 5-second SLA compliance:
- If Thunder MEETS SLA: Apply appreciation (boost confidence/rating)
- If Thunder MISSES SLA: Apply punishment (reduce confidence/rating)

Daily standup reports both appreciations and punishments.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.candidate_ai import ConversationEvent
from app.models.agent_logging import AgentExecutionLog
from app.core.logging import logger


SLA_TARGET_SECONDS = 5.0
CONFIDENCE_APPRECIATION_BOOST = 5  # Confidence +5 for meeting SLA
CONFIDENCE_PUNISHMENT_REDUCTION = 10  # Confidence -10 for missing SLA


def validate_thunder_sla(db: Session, candidate_id: str) -> Dict:
    """
    Validate if Thunder met the 5-second SLA for a candidate.
    Returns appreciation/punishment decision.
    """
    event = (
        db.query(ConversationEvent)
        .filter(
            and_(
                ConversationEvent.event_type == "THUNDER_SLA_TRACKED",
                ConversationEvent.event_data["candidate_id"].astext == candidate_id
            )
        )
        .first()
    )

    if not event:
        return {"candidate_id": candidate_id, "action": "none", "reason": "No SLA data"}

    event_data = event.event_data or {}
    sla_elapsed = event_data.get("sla_elapsed_seconds", 0)
    sla_met = sla_elapsed <= SLA_TARGET_SECONDS

    return {
        "candidate_id": candidate_id,
        "sla_elapsed_seconds": sla_elapsed,
        "sla_met": sla_met,
        "action": "appreciation" if sla_met else "punishment",
        "adjustment": CONFIDENCE_APPRECIATION_BOOST if sla_met else -CONFIDENCE_PUNISHMENT_REDUCTION,
    }


def apply_flash_appreciation(db: Session, candidate_id: str, sla_data: Dict) -> None:
    """Apply appreciation to Thunder for meeting SLA."""
    if not sla_data.get("sla_met"):
        return

    db.add(ConversationEvent(
        conversation_id=None,
        event_type="FLASH_APPRECIATION_APPLIED",
        triggered_by="flash_agent",
        event_data={
            "candidate_id": candidate_id,
            "reason": "Thunder met 5-second SLA",
            "confidence_boost": CONFIDENCE_APPRECIATION_BOOST,
            "timestamp": datetime.utcnow().isoformat()
        }
    ))
    db.commit()
    logger.info(f"✨ Flash appreciation applied: Thunder +{CONFIDENCE_APPRECIATION_BOOST} confidence for candidate {candidate_id}")


def apply_flash_punishment(db: Session, candidate_id: str, sla_data: Dict) -> None:
    """Apply punishment to Thunder for missing SLA."""
    if sla_data.get("sla_met"):
        return

    sla_elapsed = sla_data.get("sla_elapsed_seconds", 0)
    db.add(ConversationEvent(
        conversation_id=None,
        event_type="FLASH_PUNISHMENT_APPLIED",
        triggered_by="flash_agent",
        event_data={
            "candidate_id": candidate_id,
            "reason": f"Thunder missed 5-second SLA (took {sla_elapsed}s)",
            "confidence_reduction": CONFIDENCE_PUNISHMENT_REDUCTION,
            "timestamp": datetime.utcnow().isoformat()
        }
    ))
    db.commit()
    logger.warning(f"🚨 Flash punishment applied: Thunder -{CONFIDENCE_PUNISHMENT_REDUCTION} confidence for candidate {candidate_id} (SLA: {sla_elapsed}s)")


def get_daily_standup_report(db: Session, days: int = 1) -> Dict:
    """
    Generate daily standup report of Thunder's SLA performance.
    Shows appreciations, punishments, and trend.
    """
    since = datetime.utcnow() - timedelta(days=days)

    appreciations = db.query(ConversationEvent).filter(
        and_(
            ConversationEvent.event_type == "FLASH_APPRECIATION_APPLIED",
            ConversationEvent.created_at >= since
        )
    ).all()

    punishments = db.query(ConversationEvent).filter(
        and_(
            ConversationEvent.event_type == "FLASH_PUNISHMENT_APPLIED",
            ConversationEvent.created_at >= since
        )
    ).all()

    total_tracked = len(appreciations) + len(punishments)
    success_rate = (len(appreciations) / total_tracked * 100) if total_tracked > 0 else 0

    return {
        "period_days": days,
        "appreciations_count": len(appreciations),
        "punishments_count": len(punishments),
        "total_tracked": total_tracked,
        "success_rate_percent": round(success_rate, 2),
        "status": "✅ IMPROVING" if success_rate >= 99.99 else "⚠️ NEEDS IMPROVEMENT",
        "appreciations": [e.event_data for e in appreciations],
        "punishments": [e.event_data for e in punishments],
    }

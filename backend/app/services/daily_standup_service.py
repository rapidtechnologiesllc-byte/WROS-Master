"""
import logging
Daily Standup Report - Shows metrics from ALL agents (50+ agents)

Reports per agent:
- Actions completed
- Success metrics
- SLA compliance
- Activity summary
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from collections import defaultdict

from app.models.candidate_ai import ConversationEvent, CandidateConversation
from app.models.candidate import Candidate

def get_daily_standup(db: Session, days: int = 1, agent_name: str = None) -> dict:
    """
    Get daily standup data for agent(s).

    If agent_name is None, returns summary for ALL agents.
    If agent_name is provided, returns details for that agent.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Get all events from the period
    query = db.query(ConversationEvent).filter(
        ConversationEvent.created_at >= since
    )

    if agent_name:
        query = query.filter(ConversationEvent.triggered_by == agent_name)

    events = query.order_by(ConversationEvent.created_at.desc()).all()

    # Group events by agent
    agent_stats = defaultdict(lambda: {
        "actions": [],
        "success_count": 0,
        "failure_count": 0,
        "total_actions": 0,
    })

    for event in events:
        triggered_by = event.triggered_by or "system"
        agent_stats[triggered_by]["actions"].append({
            "type": event.event_type,
            "timestamp": event.created_at.isoformat(),
            "data": event.event_data or {}
        })
        agent_stats[triggered_by]["total_actions"] += 1

        # Count successes/failures
        if "failed" in event.event_type.lower() or "error" in event.event_type.lower():
            agent_stats[triggered_by]["failure_count"] += 1
        elif event.event_type in ["ai_message_sent", "INTERVIEW_CONFIRMED", "OFFER_RELEASED"]:
            agent_stats[triggered_by]["success_count"] += 1

    # Build report
    agents_report = []
    total_actions = 0
    total_successes = 0

    for agent, stats in sorted(agent_stats.items()):
        success_rate = (
            stats["success_count"] / stats["total_actions"] * 100
            if stats["total_actions"] > 0 else 0
        )
        agents_report.append({
            "agent": agent,
            "actions": stats["total_actions"],
            "successes": stats["success_count"],
            "failures": stats["failure_count"],
            "success_rate_percent": round(success_rate, 1),
            "latest_activity": stats["actions"][0]["timestamp"] if stats["actions"] else None,
        })
        total_actions += stats["total_actions"]
        total_successes += stats["success_count"]

    overall_rate = (total_successes / total_actions * 100) if total_actions > 0 else 0

    return {
        "period": f"Last {days} day(s)",
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_agents_active": len(agents_report),
            "total_actions": total_actions,
            "total_successes": total_successes,
            "overall_success_rate_percent": round(overall_rate, 1),
            "status": "ACTIVE" if total_actions > 0 else "IDLE",
        },
        "agents": sorted(agents_report, key=lambda x: x["actions"], reverse=True),
    }

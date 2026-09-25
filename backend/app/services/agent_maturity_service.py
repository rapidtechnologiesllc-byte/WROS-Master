"""
Agent Maturity Calculation Service
===================================

Weekly job that:
1. Aggregates agent execution logs
2. Calculates success rates, performance metrics
3. Updates maturity levels
4. Identifies agents that are improving vs. struggling
5. Flags agents for potential retirement if declining

This is part of the Reporting/Oversight agent infrastructure (S-324).
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.agent_execution_log import AgentExecutionLog
from app.models.agent_maturity import AgentMaturityLevel, AgentPerformanceMetric


def calculate_weekly_metrics(db: Session, week_start: datetime, agent_name: str = None):
    """
    Calculate metrics for a specific week.

    Args:
        db: Database session
        week_start: Start of the week (Monday)
        agent_name: Optional - if provided, calculate only for that agent

    Returns:
        List of AgentPerformanceMetric rows created
    """
    week_end = week_start + timedelta(days=7)

    # Get all agents if not specified
    agents = db.query(
        func.distinct(AgentExecutionLog.agent_name)
    ).filter(
        AgentExecutionLog.execution_at >= week_start,
        AgentExecutionLog.execution_at < week_end
    )

    if agent_name:
        agents = agents.filter(AgentExecutionLog.agent_name == agent_name)

    agent_names = [a[0] for a in agents.all()]
    metrics_created = []

    for agent in agent_names:
        # Get logs for this agent this week
        logs = db.query(AgentExecutionLog).filter(
            AgentExecutionLog.agent_name == agent,
            AgentExecutionLog.execution_at >= week_start,
            AgentExecutionLog.execution_at < week_end
        ).all()

        if not logs:
            continue

        # Calculate metrics
        total = len(logs)
        successes = sum(1 for log in logs if log.success)
        failures = total - successes
        success_rate = (successes / total * 100) if total > 0 else 0

        # Execution time stats
        times = [log.duration_ms for log in logs if log.duration_ms]
        avg_time = sum(times) / len(times) if times else None
        min_time = min(times) if times else None
        max_time = max(times) if times else None

        # Error analysis
        errors = [log.error_message for log in logs if log.error_message]
        top_error = None
        if errors:
            # Simple: find most common error message
            error_counts = {}
            for err in errors:
                error_counts[err] = error_counts.get(err, 0) + 1
            top_error = max(error_counts, key=error_counts.get)

        # Calculate maturity (0-100)
        # Formula: success_rate (60%) + speed (20%) + quality (20%)
        speed_score = 100 - min(100, (avg_time or 0) / 1000)  # Penalize slow execution
        maturity = (success_rate * 0.6) + (speed_score * 0.2) + (80 * 0.2)  # Default quality 80

        # Create metric row
        metric = AgentPerformanceMetric(
            tenant_id="system",  # Weekly system calculation
            agent_name=agent,
            week_starting=week_start,
            executions_count=total,
            success_count=successes,
            failure_count=failures,
            success_rate=success_rate,
            avg_execution_time_ms=int(avg_time) if avg_time else None,
            min_execution_time_ms=min_time,
            max_execution_time_ms=max_time,
            quality_score=80,  # Default; can be set by Reporting agent
            top_error_type=top_error,
            error_count=failures,
            maturity_level=maturity,
            calculated_at=datetime.utcnow()
        )
        db.add(metric)
        metrics_created.append(metric)

    db.commit()
    return metrics_created


def update_maturity_levels(db: Session, agent_name: str = None):
    """
    Update current maturity levels based on recent metrics.

    Args:
        db: Database session
        agent_name: Optional - if provided, update only that agent
    """
    # Get all agents or specific agent
    query = db.query(AgentPerformanceMetric)

    if agent_name:
        query = query.filter(AgentPerformanceMetric.agent_name == agent_name)

    # Get latest metric for each agent
    agents = db.query(AgentPerformanceMetric.agent_name).distinct()
    if agent_name:
        agents = agents.filter(AgentPerformanceMetric.agent_name == agent_name)

    for (ag,) in agents.all():
        # Get latest and previous metrics
        metrics = db.query(AgentPerformanceMetric).filter(
            AgentPerformanceMetric.agent_name == ag
        ).order_by(AgentPerformanceMetric.week_starting.desc()).limit(2).all()

        if not metrics:
            continue

        latest = metrics[0]
        previous = metrics[1] if len(metrics) > 1 else None

        # Calculate trend
        if previous:
            improvement = latest.maturity_level - previous.maturity_level
            improvement_pct = (improvement / previous.maturity_level * 100) if previous.maturity_level > 0 else 0

            if improvement > 2:
                trend = "improving"
            elif improvement < -2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            improvement = 0
            improvement_pct = 0
            trend = "stable"

        # Find or create maturity level record
        maturity_level = db.query(AgentMaturityLevel).filter(
            AgentMaturityLevel.agent_name == ag,
            AgentMaturityLevel.tenant_id == "system"
        ).first()

        if not maturity_level:
            maturity_level = AgentMaturityLevel(
                tenant_id="system",
                agent_name=ag,
                maturity_level=latest.maturity_level,
                success_rate=latest.success_rate,
                avg_execution_time_ms=latest.avg_execution_time_ms,
                total_executions=latest.executions_count,
                total_successes=latest.success_count,
                quality_score=latest.quality_score,
                trend_direction=trend,
                improvement_percentage=improvement_pct,
                last_calculated_at=datetime.utcnow()
            )
            db.add(maturity_level)
        else:
            # Update existing
            maturity_level.previous_week_maturity = maturity_level.maturity_level
            maturity_level.maturity_level = latest.maturity_level
            maturity_level.success_rate = latest.success_rate
            maturity_level.avg_execution_time_ms = latest.avg_execution_time_ms
            maturity_level.total_executions += latest.executions_count
            maturity_level.total_successes += latest.success_count
            maturity_level.quality_score = latest.quality_score
            maturity_level.trend_direction = trend
            maturity_level.improvement_percentage = improvement_pct
            maturity_level.last_calculated_at = datetime.utcnow()

        db.commit()


def check_agent_health(db: Session, agent_name: str) -> dict:
    """
    Check if an agent should be flagged or retired.

    Rules:
    - If maturity < 50% for 2+ consecutive weeks → "struggling"
    - If declining for 4+ consecutive weeks → recommend retirement

    Returns:
        {
            "status": "healthy" | "struggling" | "critical",
            "recommendation": None | "retire",
            "reason": explanation
        }
    """
    metrics = db.query(AgentPerformanceMetric).filter(
        AgentPerformanceMetric.agent_name == agent_name
    ).order_by(AgentPerformanceMetric.week_starting.desc()).limit(12).all()

    if not metrics:
        return {"status": "unknown", "recommendation": None, "reason": "No metrics available"}

    # Check trend
    declining_weeks = 0
    low_maturity_weeks = 0

    for metric in metrics:
        if metric.maturity_level < 50:
            low_maturity_weeks += 1
        if metric.maturity_level < (metrics[0].maturity_level - 5):  # 5-point decline
            declining_weeks += 1

    status = "healthy"
    recommendation = None
    reason = "Agent performing well"

    if declining_weeks >= 4:
        status = "critical"
        recommendation = "retire"
        reason = f"Agent has been declining for {declining_weeks} weeks. Recommend retirement."
    elif low_maturity_weeks >= 2:
        status = "struggling"
        reason = f"Agent maturity below 50% for {low_maturity_weeks} consecutive weeks"

    return {
        "status": status,
        "recommendation": recommendation,
        "reason": reason,
        "declining_weeks": declining_weeks,
        "low_maturity_weeks": low_maturity_weeks
    }


def retire_agent(db: Session, agent_name: str, reason: str):
    """Mark an agent as retired."""
    maturity_level = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.agent_name == agent_name
    ).first()

    if maturity_level:
        maturity_level.is_retired = True
        maturity_level.is_active = False
        maturity_level.retirement_reason = reason
        db.commit()

    return {
        "agent_name": agent_name,
        "status": "retired",
        "retired_at": datetime.utcnow(),
        "reason": reason
    }

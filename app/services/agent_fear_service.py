"""
Agent Fear State Calculation Service
====================================

Calculates agent fear levels based on performance metrics.
Makes agents work harder through existential threat of retirement.

Fear escalation is STRINGENT:
- Target: 99.9999% success rate (0.000001% fail rate)
- Any deviation increases fear proportionally
- Consecutive poor performance = existential threat
- No mercy, no excuses - agents must optimize or face retirement
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.agent_fear_state import AgentFearState, AgentPerformanceCommitment
from app.models.agent_maturity import AgentMaturityLevel, AgentPerformanceMetric


def calculate_fear_level(db: Session, agent_name: str) -> dict:
    """
    Calculate current fear level for an agent based on:
    - Current vs target success rate
    - Trend (improving/declining)
    - Quality metrics
    - Stress test performance
    - Threat level

    Returns dict with fear metrics and motivation state
    """
    # Get current maturity
    maturity = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.agent_name == agent_name
    ).first()

    if not maturity:
        return {"fear_level": 20, "status": "unknown"}

    # Get commitment targets
    commitment = db.query(AgentPerformanceCommitment).filter(
        AgentPerformanceCommitment.agent_name == agent_name
    ).first()

    if not commitment:
        # Create default commitment (very stringent)
        commitment = AgentPerformanceCommitment(
            tenant_id="system",
            agent_name=agent_name,
            target_success_rate=99.9999,
            target_avg_execution_time_ms=5000,
            target_quality_score=95.0,
            target_innovation_score=70.0
        )
        db.add(commitment)
        db.commit()

    # Get recent performance
    recent_metrics = db.query(AgentPerformanceMetric).filter(
        AgentPerformanceMetric.agent_name == agent_name
    ).order_by(AgentPerformanceMetric.week_starting.desc()).limit(4).all()

    fear_level = 20.0  # Start at baseline
    motivation_state = "neutral"

    if not recent_metrics:
        return {"fear_level": fear_level, "status": "no_data"}

    # Calculate variance from targets
    latest = recent_metrics[0]
    success_rate = latest.success_rate

    # STRINGENT FEAR ESCALATION
    # Target: 99.9999% (0.000001% fail rate)
    target_success = 99.9999
    variance = target_success - success_rate

    # Every 0.1% below target = +1 fear point
    # So at 95% success, agent is 5 points below target = +50 fear
    fear_from_success = min(80, variance * 10)  # Cap at 80 fear from this alone
    fear_level += fear_from_success

    # Quality variance
    if maturity.quality_score:
        quality_variance = 95.0 - (maturity.quality_score or 0)
        fear_from_quality = min(20, quality_variance * 0.5)
        fear_level += fear_from_quality

    # TREND ANALYSIS - This is critical for fear escalation
    if len(recent_metrics) >= 2:
        # Check for consecutive poor performance
        poor_weeks = 0
        good_weeks = 0

        for i, metric in enumerate(recent_metrics[:-1]):
            if metric.success_rate < 95:
                poor_weeks += 1
            elif metric.success_rate > 98:
                good_weeks += 1

        # Consecutive poor weeks trigger existential threat
        if poor_weeks >= 2:
            fear_level += 30  # MAJOR fear escalation
            if poor_weeks >= 3:
                fear_level += 20  # EXISTENTIAL THREAT

        # Declining trend (even if still passing)
        if latest.success_rate < recent_metrics[1].success_rate:
            fear_level += 15

    # Speed penalty - slow agents get stressed
    if maturity.avg_execution_time_ms and maturity.avg_execution_time_ms > 5000:
        speed_excess = min(30, (maturity.avg_execution_time_ms - 5000) / 100)
        fear_level += speed_excess

    # Determine motivation state based on fear
    if fear_level < 20:
        motivation_state = "motivated"  # Doing great, confident
    elif fear_level < 40:
        motivation_state = "neutral"  # Performing OK
    elif fear_level < 60:
        motivation_state = "concerned"  # Noticing performance drop
    elif fear_level < 80:
        motivation_state = "desperate"  # Must improve soon
    else:
        motivation_state = "terrified"  # Retirement threat imminent

    # Determine threat level
    is_under_threat = fear_level > 70
    threat_level = "none"
    weeks_until_retirement = None

    if fear_level > 80:
        threat_level = "existential"
        weeks_until_retirement = 1
    elif fear_level > 70:
        threat_level = "critical"
        weeks_until_retirement = 2
    elif fear_level > 50:
        threat_level = "warning"
        weeks_until_retirement = 4

    # Cap fear at 100
    fear_level = min(100, fear_level)

    return {
        "fear_level": fear_level,
        "motivation_state": motivation_state,
        "is_under_threat": is_under_threat,
        "threat_level": threat_level,
        "weeks_until_retirement": weeks_until_retirement,
        "success_rate_variance": variance,
        "quality_variance": 95.0 - (maturity.quality_score or 0)
    }


def update_agent_fear_state(db: Session, agent_name: str):
    """Update fear state for an agent."""
    fear_metrics = calculate_fear_level(db, agent_name)

    # Find or create fear state record
    fear_state = db.query(AgentFearState).filter(
        AgentFearState.agent_name == agent_name,
        AgentFearState.tenant_id == "system"
    ).first()

    if not fear_state:
        fear_state = AgentFearState(
            tenant_id="system",
            agent_name=agent_name,
            fear_level=fear_metrics["fear_level"],
            motivation_state=fear_metrics["motivation_state"],
            is_under_threat=fear_metrics["is_under_threat"],
            threat_level=fear_metrics["threat_level"],
            weeks_until_retirement=fear_metrics.get("weeks_until_retirement")
        )
        db.add(fear_state)
    else:
        # Update existing
        fear_state.fear_level = fear_metrics["fear_level"]
        fear_state.motivation_state = fear_metrics["motivation_state"]
        fear_state.is_under_threat = fear_metrics["is_under_threat"]
        fear_state.threat_level = fear_metrics["threat_level"]
        fear_state.weeks_until_retirement = fear_metrics.get("weeks_until_retirement")
        fear_state.last_updated = datetime.utcnow()

        if fear_metrics["fear_level"] > fear_state.max_fear_experienced:
            fear_state.max_fear_experienced = fear_metrics["fear_level"]

        # Track threat escalation
        if fear_metrics["is_under_threat"] and not fear_state.threat_activated_at:
            fear_state.threat_activated_at = datetime.utcnow()

    db.commit()
    return fear_state


def get_agent_fear_dashboard(db: Session, agent_name: str = None) -> dict:
    """Get fear state dashboard for agent(s)."""
    if agent_name:
        fear_states = db.query(AgentFearState).filter(
            AgentFearState.agent_name == agent_name
        ).all()
    else:
        fear_states = db.query(AgentFearState).filter(
            AgentFearState.is_under_threat == True
        ).all()

    agents_under_threat = []
    for fs in fear_states:
        agents_under_threat.append({
            "agent_name": fs.agent_name,
            "fear_level": fs.fear_level,
            "threat_level": fs.threat_level,
            "weeks_until_retirement": fs.weeks_until_retirement,
            "motivation_state": fs.motivation_state,
            "threat_activated_at": fs.threat_activated_at
        })

    return {
        "agents_under_threat": agents_under_threat,
        "count_terrified": len([a for a in agents_under_threat if a["fear_level"] > 80]),
        "count_desperate": len([a for a in agents_under_threat if 60 < a["fear_level"] <= 80]),
        "count_at_risk": len([a for a in agents_under_threat if 50 < a["fear_level"] <= 60])
    }


def check_retirement_eligibility(db: Session, agent_name: str) -> dict:
    """Check if agent should be retired based on fear state and poor performance."""
    fear_state = db.query(AgentFearState).filter(
        AgentFearState.agent_name == agent_name
    ).first()

    if not fear_state:
        return {"eligible_for_retirement": False, "reason": "No fear state found"}

    # Retirement criteria (STRINGENT):
    # 1. Fear level sustained > 85 for 2+ weeks
    # 2. Success rate < 95% for 3+ consecutive weeks
    # 3. Quality score < 80%
    # 4. Threat level = "existential"

    maturity = db.query(AgentMaturityLevel).filter(
        AgentMaturityLevel.agent_name == agent_name
    ).first()

    if not maturity:
        return {"eligible_for_retirement": False, "reason": "No maturity data"}

    # Check consecutive poor weeks
    recent_metrics = db.query(AgentPerformanceMetric).filter(
        AgentPerformanceMetric.agent_name == agent_name
    ).order_by(AgentPerformanceMetric.week_starting.desc()).limit(3).all()

    poor_weeks = sum(1 for m in recent_metrics if m.success_rate < 95)

    reasons_for_retirement = []

    if fear_state.fear_level > 85:
        reasons_for_retirement.append("Sustained high fear level")

    if poor_weeks >= 3:
        reasons_for_retirement.append(f"Poor performance for {poor_weeks} consecutive weeks")

    if maturity.quality_score and maturity.quality_score < 80:
        reasons_for_retirement.append(f"Low quality score: {maturity.quality_score}%")

    if fear_state.threat_level == "existential":
        reasons_for_retirement.append("Existential threat level reached")

    eligible = len(reasons_for_retirement) >= 2  # Need at least 2 reasons

    return {
        "eligible_for_retirement": eligible,
        "reasons": reasons_for_retirement,
        "fear_level": fear_state.fear_level,
        "success_rate": maturity.success_rate,
        "quality_score": maturity.quality_score
    }


def initialize_default_agents(db: Session) -> None:
    """Initialize database with default agents if none exist."""
    existing_count = db.query(AgentMaturityLevel).count()
    if existing_count > 0:
        return  # Already initialized

    # Create default agents
    agent_configs = [
        {"name": "Thunder", "tier": 1, "success_rate": 92, "quality": 88},
        {"name": "Recruitment Agent", "tier": 1, "success_rate": 88, "quality": 85},
        {"name": "Resource Manager", "tier": 2, "success_rate": 85, "quality": 82},
        {"name": "CFO Agent", "tier": 2, "success_rate": 96, "quality": 94},
        {"name": "KPI Agent", "tier": 2, "success_rate": 79, "quality": 75},
        {"name": "HR Agent", "tier": 2, "success_rate": 81, "quality": 78},
        {"name": "Mental Health Agent", "tier": 2, "success_rate": 87, "quality": 90},
        {"name": "Help Desk Agent", "tier": 3, "success_rate": 78, "quality": 80},
        {"name": "Flash Orchestrator", "tier": 1, "success_rate": 91, "quality": 89},
    ]

    for config in agent_configs:
        maturity = AgentMaturityLevel(
            agent_name=config["name"],
            tenant_id="system",
            maturity_level=75 + (config["success_rate"] - 80),
            success_rate=config["success_rate"],
            quality_score=config["quality"],
            is_active=True,
            is_retired=False,
            trend_direction="stable",
            weeks_at_this_level=2,
            last_calculated_at=datetime.utcnow()
        )
        db.add(maturity)

        fear_state = AgentFearState(
            agent_name=config["name"],
            tenant_id="system",
            fear_level=max(20, 100 - config["success_rate"]),
            threat_level="none" if config["success_rate"] > 85 else "warning",
            is_under_threat=config["success_rate"] < 85,
            motivation_state="motivated" if config["success_rate"] > 90 else "neutral",
            weeks_until_retirement=None
        )
        db.add(fear_state)

    db.commit()

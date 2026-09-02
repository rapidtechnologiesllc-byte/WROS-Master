import logging
"""Agent Phalanx Models - Spartan shield wall formation tracking."""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

logger = logging.getLogger(__name__)

class AgentPhalanxFormation(Base):
    """Tracks phalanx formations (Recruitment, Resource, Finance, etc.)."""

    __tablename__ = "agent_phalanx_formations"

    formation_id = Column(String(512), primary_key=True)  # "phalanx_recruitment_001"
    phalanx_name = Column(String(512), nullable=False, unique=True)  # "Recruitment Phalanx"
    description = Column(Text)
    position_count = Column(Integer)  # How many agents in formation
    formation_strength = Column(Float, default=100.0)  # 0-100% health
    status = Column(String(512), default="OPERATIONAL")  # OPERATIONAL, WEAKENING, BROKEN
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Alert tracking
    alerts = Column(JSON)  # List of active alerts
    last_alert_at = Column(DateTime)


class AgentInFormation(Base):
    """Tracks each agent's position in a phalanx."""

    __tablename__ = "agents_in_formations"

    assignment_id = Column(String(512), primary_key=True)  # "aif_thunder_recruitment_001"

    # Phalanx context
    phalanx_name = Column(String(512), nullable=False)
    agent_name = Column(String(512), nullable=False)

    # Position in formation
    position = Column(Integer, nullable=False)  # 1, 2, 3, ...

    # Neighbors
    left_neighbor = Column(String(100))  # Agent I protect
    right_neighbor = Column(String(100))  # Agent protecting me

    # Shield duty
    shield_sla = Column(String(500))  # "95% success rate, <2s latency"
    shield_failure_action = Column(String(512), default="KILL_SWITCH")

    # Vulnerabilities
    flank_vulnerabilities = Column(JSON)  # ["rate_limited", "false_positives"]
    flank_coverage_expected = Column(String(500))

    # Shield status
    shield_strength = Column(Float, default=100.0)  # 0-100%
    shield_status = Column(String(50))  # HEALTHY, WEAKENING, FAILING, BROKEN

    # Monitoring
    monitor_left_neighbor = Column(Boolean, default=False)
    monitor_right_neighbor = Column(Boolean, default=False)
    shield_watch_interval = Column(Integer, default=60)  # seconds
    last_shield_check = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ShieldWatch(Base):
    """Tracks shield monitoring and neighbor health checks."""

    __tablename__ = "shield_watches"

    watch_id = Column(String(512), primary_key=True)  # "watch_recruitment_agent_001"

    # Who is watching
    monitor_agent = Column(String(512), nullable=False)
    phalanx_name = Column(String(512), nullable=False)

    # What they're watching
    watch_type = Column(String(50))  # "monitor_left", "monitor_right"
    target_agent = Column(String(512), nullable=False)
    target_position = Column(Integer)  # Position of target in formation

    # Shield metrics being watched
    metric_name = Column(String(100))  # "success_rate", "latency", "quality"
    threshold = Column(Float)  # When to alert
    current_value = Column(Float)  # Last measured value

    # Alert tracking
    status = Column(String(50))  # HEALTHY, WARNING, CRITICAL
    alert_count = Column(Integer, default = False)
    alert_triggered_at = Column(DateTime)

    # Escalation
    escalated = Column(Boolean, default=False)
    escalated_to = Column(String(100))  # "CEO", "Leadership"
    escalation_reason = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PhalanxAlert(Base):
    """Alerts when shield fails or phalanx integrity compromised."""

    __tablename__ = "phalanx_alerts"

    alert_id = Column(String(512), primary_key=True)  # "alert_recruitment_001"

    # Which formation
    phalanx_name = Column(String(512), nullable=False)

    # What broke
    source_agent = Column(String(512), nullable=False)  # Agent whose shield failed
    alert_type = Column(String(50))  # "shield_weakening", "shield_failing", "neighbor_down"
    severity = Column(String(50))  # "INFO", "WARNING", "CRITICAL", "EXISTENTIAL"

    # Details
    description = Column(Text)
    metrics = Column(JSON)  # {"success_rate": 0.80, "latency_ms": 5000}

    # Impact
    affected_agents = Column(JSON)  # Who else is impacted
    impact_description = Column(Text)  # "Interview Reminder Agent is exposed"

    # Response
    recommended_action = Column(String(500))
    auto_triggered_kill_switch = Column(Boolean, default=False)

    # Timeline
    detected_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class FormationIntegrity(Base):
    """Overall phalanx formation health and integrity."""

    __tablename__ = "formation_integrity"

    integrity_id = Column(String(512), primary_key=True)  # "fi_recruitment_001"
    phalanx_name = Column(String(512), nullable=False)

    # Overall health
    formation_strength = Column(Float)  # Weighted average of all shields
    overall_status = Column(String(50))  # OPERATIONAL, WEAKENING, BROKEN

    # Shield distribution
    healthy_shields = Column(Integer)  # Count of agents at 100% shield
    weakening_shields = Column(Integer)  # Count of agents at 50-99%
    failing_shields = Column(Integer)  # Count of agents at <50%

    # Position-specific
    weakest_position = Column(Integer)  # Which position has worst shield
    weakest_shield_strength = Column(Float)
    strongest_position = Column(Integer)
    strongest_shield_strength = Column(Float)

    # Breach risk
    breach_risk_score = Column(Float)  # 0-100 (how likely formation breaks)
    breach_likely_at = Column(String(100))  # "position_3" if that shield fails

    # Cascading failure
    cascade_risk = Column(String(500))  # "If position 3 fails, position 4 exposed"
    critical_gaps = Column(JSON)  # Vulnerabilities that span multiple agents

    # Recommendations
    reinforcement_needed = Column(String(500))
    fallback_position = Column(String(50))  # Temporary human intervention location

    measured_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

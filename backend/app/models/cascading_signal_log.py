"""
Cascading Signal Protocol Models - Inter-orchestrator learning signals

Tracks all signals exchanged between Thunder→Flash→Interview→Offer→Finance
with impact analysis and recommendation logging.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime


class CascadingSignalLog(Base):
    """Every signal between orchestrators gets logged."""

    __tablename__ = "cascading_signal_logs"

    signal_id = Column(String(512), primary_key=True)
    orchestrator = Column(String(50), nullable=False, index=True)  # thunder, flash, interview, offer, finance
    source_orchestrator = Column(String(50), nullable=False)  # Who sent this signal
    target_orchestrator = Column(String(50), nullable=False)  # Who receives it
    tenant_id = Column(String(512), nullable=False, index=True)

    # Signal content
    signal_type = Column(String(50))  # QUALITY_ALERT, BOTTLENECK, PERFORMANCE_GAIN, FAILURE_CASCADE
    priority = Column(String(50))  # CRITICAL, HIGH, MEDIUM, LOW

    # The actual data that triggered signal
    metric_name = Column(String(255))  # accuracy, throughput, calibration, health
    metric_previous_value = Column(Float)  # Previous measurement
    metric_current_value = Column(Float)  # Current measurement
    metric_threshold = Column(Float)  # What triggers alert
    variance_percent = Column(Float)  # % change from previous

    # Impact analysis
    predicted_cascade_impact = Column(Text)  # What will happen downstream if ignored
    cascade_impact_severity = Column(String(50))  # CRITICAL, HIGH, MEDIUM, LOW
    cascade_impact_timeline_minutes = Column(Integer)  # How many minutes before it cascades

    # Recommendation from source
    recommended_action = Column(Text)  # Exact action target should take
    recommended_action_priority = Column(String(50))  # IMMEDIATE, URGENT, NORMAL

    # Track what target orchestrator did
    action_taken = Column(Text, nullable=True)  # What target actually did
    action_taken_at = Column(DateTime, nullable=True)
    action_effectiveness = Column(Float, nullable=True)  # Did it help? (0-1)

    # Signal lifecycle
    sent_at = Column(DateTime, default=datetime.utcnow)
    received_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # If signal was ignored/missed
    missed_response = Column(Boolean, default=False)  # Did target not respond?
    missed_response_consequence = Column(Text, nullable=True)  # What broke because no response

    created_at = Column(DateTime, default=datetime.utcnow)


class CascadingSignalMetrics(Base):
    """Aggregated signal health per orchestrator pair."""

    __tablename__ = "cascading_signal_metrics"

    metrics_id = Column(String(512), primary_key=True)
    source_orchestrator = Column(String(50), nullable=False, index=True)
    target_orchestrator = Column(String(50), nullable=False, index=True)
    tenant_id = Column(String(512), nullable=False, index=True)

    # Signal patterns
    total_signals_sent = Column(Integer, default=0)
    signals_acknowledged_count = Column(Integer, default=0)
    acknowledgment_rate = Column(Float)  # % of signals acknowledged

    signals_action_taken_count = Column(Integer, default=0)
    action_taken_rate = Column(Float)  # % of signals that resulted in action

    signals_ignored_count = Column(Integer, default=0)
    ignore_rate = Column(Float)  # % ignored (should be 0)

    # Effectiveness tracking
    average_action_effectiveness = Column(Float)  # Avg impact of actions taken
    cascade_prevented_count = Column(Integer, default=0)  # How many cascades prevented
    cascade_occurred_count = Column(Integer, default=0)  # How many happened anyway
    cascade_prevention_rate = Column(Float)  # Should be 100%

    # Response time
    avg_signal_to_action_seconds = Column(Integer)  # SLA: should be < 60 seconds
    median_signal_to_action_seconds = Column(Integer)
    p99_signal_to_action_seconds = Column(Integer)

    # Bidirectional signal health
    signal_quality_score = Column(Float)  # 0-1 (1 = perfect communication)
    formation_integrity_score = Column(Float)  # Phalanx formation health from this pair

    # Last signal metrics
    last_signal_at = Column(DateTime, nullable=True)
    last_signal_type = Column(String(50), nullable=True)
    last_action_effectiveness = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

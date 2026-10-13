from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from datetime import datetime
from app.models.base import Base


class CascadingSignalLog(Base):
    """Logs cascading signals sent between orchestrators."""
    __tablename__ = "cascading_signal_logs"

    id = Column(Integer, primary_key=True)
    source_orchestrator_id = Column(String(100), nullable=False, index=True)
    target_orchestrator_id = Column(String(100), nullable=False, index=True)
    signal_type = Column(String(100), nullable=False)  # cascade_failure, performance_alert, coordination, etc.
    signal_severity = Column(String(50), default="NORMAL")  # CRITICAL, HIGH, NORMAL, LOW
    signal_message = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)  # Signal data
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    action_taken = Column(Text, nullable=True)
    outcome = Column(String(50), nullable=True)  # SUCCESS, FAILED, IGNORED

    def __repr__(self):
        return f"<CascadingSignalLog {self.source_orchestrator_id}->{self.target_orchestrator_id} {self.signal_type}>"


class CascadingSignalMetrics(Base):
    """Aggregated metrics for cascading signal activity."""
    __tablename__ = "cascading_signal_metrics"

    id = Column(Integer, primary_key=True)
    orchestrator_id = Column(String(100), nullable=False, index=True)
    time_window = Column(String(50), nullable=False)  # 1h, 1d, 1w
    total_signals_sent = Column(Integer, default=0)
    total_signals_received = Column(Integer, default=0)
    critical_signals = Column(Integer, default=0)
    successful_cascades = Column(Integer, default=0)
    failed_cascades = Column(Integer, default=0)
    avg_cascade_depth = Column(Float, nullable=True)  # Average number of hops
    max_cascade_depth = Column(Integer, nullable=True)  # Deepest cascade
    cascade_failure_rate = Column(Float, nullable=True)  # % of cascades that failed
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<CascadingSignalMetrics {self.orchestrator_id} {self.time_window} sent={self.total_signals_sent} recv={self.total_signals_received}>"

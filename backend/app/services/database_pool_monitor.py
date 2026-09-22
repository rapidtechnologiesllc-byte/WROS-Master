"""
Database Connection Pool Monitoring - Operational visibility.

Tracks pool utilization and raises alerts when pool is at risk of exhaustion.
Critical for detecting issues before they cascade to production failures.
"""

import logging
import time
from threading import Lock
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class PoolMetrics:
    """Snapshot of pool metrics at a point in time"""

    def __init__(self, timestamp: float, available: int, checked_out: int, total: int):
        self.timestamp = timestamp
        self.available = available
        self.checked_out = checked_out
        self.total = total
        self.utilization_percent = (checked_out / total * 100) if total > 0 else 0


class DatabasePoolMonitor:
    """Monitor database connection pool health"""

    ALERT_THRESHOLD_PERCENT = 80  # Alert when pool > 80% used
    WARNING_THRESHOLD_PERCENT = 60  # Warning when pool > 60% used

    def __init__(self, engine):
        self.engine = engine
        self.metrics_history: List[PoolMetrics] = []
        self.alerts: List[str] = []
        self.lock = Lock()
        self.last_check = 0

    def check_pool_health(self) -> Dict:
        """
        Check current pool health and raise alerts if needed.

        Returns:
            {
                "utilization_percent": X,
                "available_connections": N,
                "checked_out_connections": N,
                "total_capacity": N,
                "status": "HEALTHY" | "WARNING" | "CRITICAL",
                "recent_alerts": [...]
            }
        """
        try:
            pool = self.engine.pool

            # Get pool status
            available = pool.checkedout() if hasattr(pool, 'checkedout') else 0
            # Total = pool_size + max_overflow
            total = getattr(pool, 'size', 20) + getattr(pool, 'max_overflow', 10)
            checked_out = available
            available = total - checked_out

            metrics = PoolMetrics(time.time(), available, checked_out, total)

            with self.lock:
                self.metrics_history.append(metrics)
                # Keep last 100 metrics (for historical analysis)
                if len(self.metrics_history) > 100:
                    self.metrics_history = self.metrics_history[-100:]

                # Determine status and raise alerts
                status = "HEALTHY"
                current_alerts = []

                if metrics.utilization_percent >= self.ALERT_THRESHOLD_PERCENT:
                    status = "CRITICAL"
                    alert = f"Pool utilization CRITICAL: {metrics.utilization_percent:.0f}% ({metrics.checked_out}/{metrics.total} connections)"
                    current_alerts.append(alert)
                    self.alerts.append(alert)
                    logger.error(f"[PoolMonitor] {alert}")
                elif metrics.utilization_percent >= self.WARNING_THRESHOLD_PERCENT:
                    status = "WARNING"
                    alert = f"Pool utilization WARNING: {metrics.utilization_percent:.0f}% ({metrics.checked_out}/{metrics.total} connections)"
                    current_alerts.append(alert)
                    if not any("WARNING" in a for a in self.alerts[-5:]):  # Avoid alert spam
                        self.alerts.append(alert)
                    logger.warning(f"[PoolMonitor] {alert}")

                # Keep last 50 alerts
                self.alerts = self.alerts[-50:]

                return {
                    "status": status,
                    "utilization_percent": metrics.utilization_percent,
                    "available_connections": available,
                    "checked_out_connections": checked_out,
                    "total_capacity": total,
                    "timestamp": datetime.fromtimestamp(metrics.timestamp).isoformat(),
                    "current_alerts": current_alerts,
                    "recent_alerts": self.alerts[-5:] if self.alerts else []
                }

        except Exception as e:
            logger.error(f"[PoolMonitor] Health check failed: {e}", exc_info=True)
            return {
                "status": "UNKNOWN",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_trend(self) -> Dict:
        """Get pool utilization trend (last 10 checks)"""
        with self.lock:
            if not self.metrics_history:
                return {"trend": []}

            recent = self.metrics_history[-10:]
            return {
                "trend": [
                    {
                        "timestamp": datetime.fromtimestamp(m.timestamp).isoformat(),
                        "utilization_percent": m.utilization_percent,
                        "checked_out": m.checked_out,
                        "available": m.available
                    }
                    for m in recent
                ],
                "max_utilization": max(m.utilization_percent for m in recent),
                "avg_utilization": sum(m.utilization_percent for m in recent) / len(recent)
            }


# Global instance
_pool_monitor = None
_pool_monitor_lock = Lock()

def get_pool_monitor(engine=None) -> DatabasePoolMonitor:
    """Get or create global pool monitor"""
    global _pool_monitor
    if _pool_monitor is None and engine is not None:
        with _pool_monitor_lock:
            if _pool_monitor is None:
                _pool_monitor = DatabasePoolMonitor(engine)
    return _pool_monitor

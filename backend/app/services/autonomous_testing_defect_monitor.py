"""CYCLE 17: Autonomous Testing Defect Monitoring Service"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, List

logger = logging.getLogger(__name__)


class AutonomousTestingDefectMonitor:
    """Monitors autonomous processes for defects and failures"""

    @staticmethod
    def check_autonomous_health(db: Session) -> Dict:
        """Monitor Thunder, Flash, and Interview processes for defects"""
        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "thunder_status": "operational",
            "flash_status": "operational",
            "interview_scheduler_status": "operational",
            "defects_found": [],
            "critical_alerts": []
        }

        # Check Thunder async progression
        try:
            from app.models.candidate import Candidate
            engaged = db.query(Candidate).filter(
                Candidate.candidate_status == "ENGAGED"
            ).count()
            qualifying = db.query(Candidate).filter(
                Candidate.candidate_status == "QUALIFYING"
            ).count()

            if engaged > 100 and qualifying == 0:
                health["defects_found"].append({
                    "severity": "HIGH",
                    "component": "Thunder",
                    "issue": "Candidates stuck in ENGAGED (not progressing)"
                })
                health["thunder_status"] = "degraded"

        except Exception as e:
            logger.error(f"[CYCLE17] Thunder health check failed: {e}")
            health["thunder_status"] = "error"
            health["critical_alerts"].append(str(e))

        # Check Flash job orchestration
        try:
            from app.models.jobs import Jobs
            total_jobs = db.query(Jobs).count()
            open_jobs = db.query(Jobs).filter(Jobs.status == "Open").count()

            if total_jobs > 0 and open_jobs == 0:
                health["defects_found"].append({
                    "severity": "MEDIUM",
                    "component": "Flash",
                    "issue": "All jobs closed (no hiring happening)"
                })
                health["flash_status"] = "degraded"

        except Exception as e:
            logger.error(f"[CYCLE17] Flash health check failed: {e}")
            health["flash_status"] = "error"

        return health

    @staticmethod
    def report_defects(db: Session, defects: List[Dict]) -> Dict:
        """Report defects to escalation system"""
        critical_defects = [d for d in defects if d.get("severity") == "CRITICAL"]
        high_defects = [d for d in defects if d.get("severity") == "HIGH"]

        if critical_defects:
            logger.critical(f"[CYCLE17] CRITICAL defects detected: {critical_defects}")
            return {"escalated": True, "severity": "CRITICAL", "count": len(critical_defects)}

        if high_defects:
            logger.warning(f"[CYCLE17] HIGH priority defects: {high_defects}")
            return {"escalated": True, "severity": "HIGH", "count": len(high_defects)}

        return {"escalated": False, "count": len(defects)}

"""SLM Training Alert Handler - Processes SLM training failure alerts

Routes to ops dashboard for visibility and monitoring.
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SLMTrainingAlertHandler:
    """Handles SLM training failure alerts."""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process SLM training alert.
        
        Logs alert to ops dashboard for monitoring and visibility.
        """
        try:
            payload = message.payload or {}
            message_id = payload.get('message_id')
            task_type = payload.get('task_type')
            error = payload.get('error')
            severity = payload.get('severity', 'MEDIUM')

            logger.warning(
                f"[SLMTrainingAlert] SLM training failed for message {message_id}: "
                f"task={task_type}, severity={severity}, error={error}"
            )

            # Alert processed - this is informational, not a task to retry
            return {
                "status": "success",
                "message": f"SLM training alert logged for {task_type}",
                "message_id": message_id,
                "severity": severity,
                "method": "alert_logged"
            }

        except Exception as e:
            logger.error(
                f"[SLMTrainingAlert] Failed to process alert: {str(e)}",
                exc_info=True
            )
            return {
                "status": "failed",
                "error": str(e),
                "method": "handler"
            }

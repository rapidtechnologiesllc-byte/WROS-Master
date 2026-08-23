"""
Agent Execution Logger Utility

Centralized logging for all 50+ agents. Every agent in BlitzenX uses this single
logging function to track execution, metrics, and decisions. This creates a unified
observability layer across the entire agentic system.

Usage:
    from app.utils.agent_logger import log_agent_execution

    log_agent_execution(
        db=db_session,
        agent_name="Recruitment Agent",
        action_taken="generate_job_description",
        tenant_id=user.tenant_id,
        candidate_id=candidate.id,  # optional
        action_data={
            "job_title": "Guidewire Developer",
            "clarifying_questions": [...]
        },
        success=True,
        error_message=None,
        duration_ms=1250
    )
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.models.agent_execution_log import AgentExecutionLog

logger = logging.getLogger(__name__)


def log_agent_execution(
    db: Session,
    agent_name: str,
    action_taken: str,
    tenant_id: str,
    candidate_id: Optional[str] = None,
    action_data: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> Optional[AgentExecutionLog]:
    """
    Log an agent execution to the centralized agent_execution_log table.

    This function is called by every agent in BlitzenX to track:
    - What action was taken
    - Whether it succeeded
    - How long it took
    - What data was involved
    - Any errors encountered

    Args:
        db: SQLAlchemy session
        agent_name: Name of the agent (e.g., "Recruitment Agent", "Thunder")
                   Must match name in agent_registry_service.py
        action_taken: Specific action (e.g., "generate_job_description", "auto_assign")
        tenant_id: Tenant ID (required for multi-tenancy)
        candidate_id: Candidate ID if action relates to a candidate (optional)
        action_data: JSON data about the action (optional)
        success: Whether the action succeeded (default: True)
        error_message: Error message if success=False (optional)
        duration_ms: Milliseconds the action took (optional)

    Returns:
        AgentExecutionLog record if created successfully, None if error

    Example:
        >>> from app.utils.agent_logger import log_agent_execution
        >>> log = log_agent_execution(
        ...     db=session,
        ...     agent_name="Recruitment Agent",
        ...     action_taken="generate_job_description",
        ...     tenant_id="tenant_123",
        ...     action_data={"job_title": "Guidewire Developer"},
        ...     success=True,
        ...     duration_ms=1250
        ... )
    """
    try:
        log_entry = AgentExecutionLog(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            agent_name=agent_name,
            action_taken=action_taken,
            action_data=action_data,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            execution_at=datetime.utcnow(),
        )

        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        # Log to application logger as well
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            f"Agent execution: {agent_name} | {action_taken} | "
            f"success={success} | duration={duration_ms}ms"
        )

        return log_entry

    except Exception as e:
        logger.error(
            f"Failed to log agent execution for {agent_name}: {str(e)}",
            exc_info=True
        )
        db.rollback()
        return None


def get_agent_metrics(
    db: Session,
    agent_name: str,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Get execution metrics for an agent over the last N days.

    Used by the Agent Maturity Dashboard to calculate performance scores.

    Args:
        db: SQLAlchemy session
        agent_name: Name of the agent
        days: Number of days to look back (default: 7)

    Returns:
        Dictionary with keys:
        - execution_count: Total executions in period
        - success_count: Successful executions
        - error_count: Failed executions
        - success_rate: Percentage (0-100)
        - avg_duration_ms: Average execution time
        - last_execution: Datetime of most recent execution
    """
    from app.models.agent_execution_log import AgentExecutionLog
    from datetime import timedelta

    cutoff_date = func.current_timestamp() - timedelta(days=days)

    logs = db.query(AgentExecutionLog).filter(
        AgentExecutionLog.agent_name == agent_name,
        AgentExecutionLog.execution_at >= cutoff_date,
    ).all()

    if not logs:
        return {
            "execution_count": 0,
            "success_count": 0,
            "error_count": 0,
            "success_rate": 0.0,
            "avg_duration_ms": 0,
            "last_execution": None,
        }

    successful = [log for log in logs if log.success]
    failed = [log for log in logs if not log.success]
    durations = [log.duration_ms for log in logs if log.duration_ms]

    avg_duration = sum(durations) / len(durations) if durations else 0

    return {
        "execution_count": len(logs),
        "success_count": len(successful),
        "error_count": len(failed),
        "success_rate": (len(successful) / len(logs) * 100) if logs else 0.0,
        "avg_duration_ms": int(avg_duration),
        "last_execution": max(log.execution_at for log in logs),
    }

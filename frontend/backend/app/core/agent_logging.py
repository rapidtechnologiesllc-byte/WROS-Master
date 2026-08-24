"""
Unified Agent Execution Logging

Provides decorators and context managers for all agents to log execution
to agent_execution_log. Drop-in for existing agent services.

Usage:
  @log_agent_execution("MyAgent", "agent_action")
  async def do_something(candidate_id, tenant_id, db, **kwargs):
      ...

Or with context manager:
  async with agent_execution_log(db, tenant_id, candidate_id, "MyAgent", "action"):
      ...
"""

import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.agent_execution_log import AgentExecutionLog


@asynccontextmanager
async def agent_execution_log(
    db: Session,
    tenant_id: str,
    candidate_id: Optional[str],
    agent_name: str,
    action_taken: str,
    action_data: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for logging agent execution.

    Usage:
      async with agent_execution_log(db, tenant_id, cand_id, "MyAgent", "action"):
          # your agent logic here
          pass
    """
    start_time = time.time()
    success = False
    error_message = None

    try:
        yield
        success = True
    except Exception as e:
        error_message = str(e)
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)

        log_entry = AgentExecutionLog(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            agent_name=agent_name,
            action_taken=action_taken,
            action_data=action_data,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
        )
        db.add(log_entry)
        db.commit()


def log_agent_execution(agent_name: str, action_taken: str):
    """
    Decorator for agent execution methods.

    The decorated function must have signature:
      async def agent_func(candidate_id, tenant_id, db, **kwargs)

    Or for non-candidate-scoped agents:
      async def agent_func(tenant_id, db, **kwargs)

    Usage:
      @log_agent_execution("MyAgent", "process_candidate")
      async def process(candidate_id, tenant_id, db, **kwargs):
          ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract db, tenant_id, candidate_id from kwargs or positional args
            db = kwargs.get("db")
            tenant_id = kwargs.get("tenant_id")
            candidate_id = kwargs.get("candidate_id")

            # Fallback: try positional args if not in kwargs
            # Assumes: func(candidate_id, tenant_id, db, ...)
            if not db and len(args) > 2:
                db = args[2]
            if not tenant_id and len(args) > 1:
                tenant_id = args[1]
            if not candidate_id and len(args) > 0:
                candidate_id = args[0]

            if not db or not tenant_id:
                # If we can't log, just run the function
                return await func(*args, **kwargs)

            start_time = time.time()
            success = False
            error_message = None
            result = None

            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_message = str(e)
                raise
            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                log_entry = AgentExecutionLog(
                    tenant_id=tenant_id,
                    candidate_id=candidate_id,
                    agent_name=agent_name,
                    action_taken=action_taken,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_message,
                )
                db.add(log_entry)
                db.commit()

        return wrapper
    return decorator

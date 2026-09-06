"""
Queue Monitoring API - Proxies Celery Flower REST API with auth & error handling

Production: Calls Flower on localhost:5555
Development: Calls Flower on localhost:5555

Provides dashboard access to queue stats, worker status, and task management.
All endpoints require system.manage permission (admin only).
"""

from fastapi import APIRouter, Depends, HTTPException
import httpx
import logging
from typing import Optional

from app.core.dependencies import get_current_user, require_role_template_permission
from app.models.user import Users
from app.core.permission_registry import Permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/queue", tags=["queue-monitoring"])

# Flower REST API base URL (localhost, not exposed externally)
FLOWER_API_URL = "http://localhost:5555/api"
FLOWER_TIMEOUT = 5.0
MAX_TASK_LIMIT = 1000
QUERY_PARAMS_LIMIT = 10000


@router.get(
    "/workers",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_workers(current_user: Users = Depends(get_current_user)):
    """
    Get active Celery workers status

    Response format (from Flower):
    {
      "worker1": {
        "status": "online",
        "processed": 1234,
        "active": 5,
        "pool": {"max-concurrency": 4, "processes": [123, 124, ...]}
      }
    }

    Error responses:
    - 503: Flower not running
    - 401: User lacks permissions
    """
    try:
        async with httpx.AsyncClient(timeout=FLOWER_TIMEOUT) as client:  # noqa: timeout constant
            response = await client.get(f"{FLOWER_API_URL}/workers")

            if response.status_code == 404:
                raise HTTPException(
                    status_code=503,
                    detail="Queue monitoring service unavailable (Flower not running)"
                )

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        logger.error("Flower API timeout calling /workers")
        raise HTTPException(
            status_code=504,
            detail="Queue monitoring service timeout"
        )
    except Exception as e:
        logger.error(f"Failed to get workers: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve queue workers"
        )


@router.get(
    "/tasks",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_tasks(
    state: Optional[str] = None,
    limit: int = 100,
    current_user: Users = Depends(get_current_user),
):
    """
    Get Celery tasks by state

    Query params:
    - state: Filter by task state (optional, default: all)
      Valid values: PENDING, RECEIVED, STARTED, SUCCESS, FAILURE
    - limit: Max tasks to return (default: 100, max: 1000)

    Response format:
    {
      "tasks": [
        {
          "uuid": "abc-123",
          "name": "app.tasks.send_email",
          "state": "SUCCESS",
          "received": 1234567890,
          "started": 1234567891,
          "succeeded": 1234567892,
          "result": "Email sent",
          "worker": "worker1"
        }
      ]
    }
    """
    try:
        limit = min(limit, MAX_TASK_LIMIT)

        params = {"limit": limit}
        if state:
            params["state"] = state.upper()

        async with httpx.AsyncClient(timeout=FLOWER_TIMEOUT) as client:  # noqa: timeout constant
            response = await client.get(
                f"{FLOWER_API_URL}/tasks",
                params=params
            )
            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        logger.error("Flower API timeout calling /tasks")
        raise HTTPException(status_code=504, detail="Queue monitoring timeout")
    except Exception as e:
        logger.error(f"Failed to get tasks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve tasks")


@router.get(
    "/tasks/{task_id}",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_task(task_id: str, current_user: Users = Depends(get_current_user)):
    """Get single task details"""
    try:
        async with httpx.AsyncClient(timeout=FLOWER_TIMEOUT) as client:  # noqa: timeout constant
            response = await client.get(f"{FLOWER_API_URL}/tasks/{task_id}")

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Task not found")

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Queue monitoring timeout")
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve task")


@router.get(
    "/stats",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def get_stats(current_user: Users = Depends(get_current_user)):
    """
    Get queue statistics (total tasks, success rate, etc.)

    Response format:
    {
      "total_tasks": 5000,
      "succeeded": 4950,
      "failed": 50,
      "active": 12,
      "reserved": 8,
      "workers_online": 2,
      "state_breakdown": {
        "SUCCESS": 4950,
        "FAILURE": 50,
        "STARTED": 12
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=FLOWER_TIMEOUT) as client:  # noqa: timeout constant
            workers = await client.get(f"{FLOWER_API_URL}/workers")
            tasks = await client.get(f"{FLOWER_API_URL}/tasks?limit={QUERY_PARAMS_LIMIT}")

            workers.raise_for_status()
            tasks.raise_for_status()

            workers_data = workers.json()
            tasks_data = tasks.json()

            # Calculate stats
            if not workers_data or not isinstance(workers_data, dict):
                workers_data = {}
            if not tasks_data or not isinstance(tasks_data, dict):
                tasks_data = {}

            total_processed = sum(
                w.get("processed", 0)
                for w in workers_data.values()
            )

            task_states = {}
            for task in tasks_data.get("tasks", []):
                state = task.get("state", "UNKNOWN")
                task_states[state] = task_states.get(state, 0) + 1

            return {
                "total_tasks": total_processed,
                "succeeded": task_states.get("SUCCESS", 0),
                "failed": task_states.get("FAILURE", 0),
                "active": sum(w.get("active", 0) for w in workers_data.values()),
                "workers_online": len(workers_data),
                "state_breakdown": task_states,
            }

    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve queue stats")


@router.post(
    "/tasks/{task_id}/retry",
    dependencies=[Depends(require_role_template_permission(*Permissions.USERS_EDIT))],
)
async def retry_task(task_id: str, current_user: Users = Depends(get_current_user)):
    """
    Retry a failed task

    Note: Only works for specific task types that support retry.
    Some tasks (like email sends) may not support retries.
    """
    try:
        async with httpx.AsyncClient(timeout=FLOWER_TIMEOUT) as client:  # noqa: timeout constant
            response = await client.post(f"{FLOWER_API_URL}/tasks/{task_id}/retry")
            response.raise_for_status()

            logger.info(f"Task {task_id} retry requested by {current_user.email}")
            return {"status": "retry_requested", "task_id": task_id}

    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retry task")

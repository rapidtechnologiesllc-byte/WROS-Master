"""
Message Queue Management Endpoints
import logging
===================================

Admin endpoints for monitoring and managing background tasks (Celery/APScheduler).
Provides visibility into task status, error messages, and manual retry/clear capabilities.

Endpoints:
  GET /admin/queue/tasks - List all tasks with status
  GET /admin/queue/tasks/{task_id} - Get task details and messages
  POST /admin/queue/tasks/{task_id}/retry - Retry failed task
  POST /admin/queue/tasks/{task_id}/clear - Clear failed task
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.dependencies import get_current_internal_user, require_resource_permission
from datetime import datetime, timedelta
from typing import List, Optional
from app.core.logging import logger

router = APIRouter(prefix="/admin/queue", tags=["admin"])

logger = logging.getLogger(__name__)

class TaskStatus:
    """In-memory task registry. In production, use Celery results backend or dedicated table."""
    _tasks = {}  # {task_id: {"task_name": str, "status": str, "progress": int, "messages": [...], ...}}

    @classmethod
    def add_task(cls, task_id: str, task_name: str, status: str = "queued"):
        """Add a new task to tracking."""
        if task_id not in cls._tasks:
            cls._tasks[task_id] = {
                "task_id": task_id,
                "task_name": task_name,
                "status": status,  # queued, active, completed, failed
                "progress": 0,
                "messages": [],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

    @classmethod
    def update_task(cls, task_id: str, status: Optional[str] = None, progress: Optional[int] = None):
        """Update task status or progress."""
        if task_id in cls._tasks:
            if status:
                cls._tasks[task_id]["status"] = status
            if progress is not None:
                cls._tasks[task_id]["progress"] = progress
            cls._tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()

    @classmethod
    def add_message(cls, task_id: str, message: str, level: str = "info"):
        """Add a message to task log."""
        if task_id not in cls._tasks:
            cls.add_task(task_id, "unknown")

        cls._tasks[task_id]["messages"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,  # info, warning, error
            "message": message,
        })

    @classmethod
    def get_task(cls, task_id: str):
        """Get task details."""
        return cls._tasks.get(task_id)

    @classmethod
    def get_all_tasks(cls):
        """Get all tasks."""
        return list(cls._tasks.values())

    @classmethod
    def retry_task(cls, task_id: str):
        """Mark task for retry."""
        if task_id in cls._tasks:
            cls._tasks[task_id]["status"] = "queued"
            cls._tasks[task_id]["progress"] = 0
            cls._tasks[task_id]["messages"] = []
            cls.add_message(task_id, "Task queued for retry", "info")

    @classmethod
    def clear_task(cls, task_id: str):
        """Clear a task."""
        if task_id in cls._tasks:
            del cls._tasks[task_id]

@router.get(
    "/tasks",
    dependencies=[Depends(require_resource_permission("task", "view"))]
)
async def list_tasks(
    current_user: dict = Depends(get_current_internal_user),
    db: Session = Depends(SessionLocal),
):
    """
    List all tasks in the message queue.

    Returns:
      - tasks: List of task objects with status, progress, messages
      - stats: Breakdown of tasks by status
    """
    all_tasks = TaskStatus.get_all_tasks()

    # Calculate stats
    stats = {
        "total": len(all_tasks),
        "queued": len([t for t in all_tasks if t["status"] == "queued"]),
        "active": len([t for t in all_tasks if t["status"] == "active"]),
        "completed": len([t for t in all_tasks if t["status"] == "completed"]),
        "failed": len([t for t in all_tasks if t["status"] == "failed"]),
    }

    return {
        "status": "success",
        "tasks": sorted(all_tasks, key=lambda t: t["created_at"], reverse=True),
        "stats": stats,
    }

@router.get(
    "/tasks/{task_id}",
    dependencies=[Depends(require_resource_permission("task", "view"))]
)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_internal_user),
    db: Session = Depends(SessionLocal),
):
    """
    Get detailed information about a specific task.

    Returns:
      - task: Task object with all details and message history
    """
    task = TaskStatus.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "status": "success",
        "task": task,
    }

@router.post(
    "/tasks/{task_id}/retry",
    dependencies=[Depends(require_resource_permission("task", "create"))]
)
async def retry_task(
    task_id: str,
    current_user: dict = Depends(get_current_internal_user),
    db: Session = Depends(SessionLocal),
):
    """
    Retry a failed task.

    Returns:
      - success: Boolean indicating if retry was queued
      - message: Status message
    """
    task = TaskStatus.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task["status"] != "failed":
        raise HTTPException(status_code=400, detail=f"Only failed tasks can be retried. Current status: {task['status']}")

    # Queue for retry
    TaskStatus.retry_task(task_id)

    return {
        "status": "success",
        "message": f"Task {task_id} queued for retry",
    }

@router.post(
    "/tasks/{task_id}/clear",
    dependencies=[Depends(require_resource_permission("task", "create"))]
)
async def clear_task(
    task_id: str,
    current_user: dict = Depends(get_current_internal_user),
    db: Session = Depends(SessionLocal),
):
    """
    Clear a failed task from the queue.

    Returns:
      - success: Boolean indicating if task was cleared
      - message: Status message
    """
    task = TaskStatus.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    TaskStatus.clear_task(task_id)

    return {
        "status": "success",
        "message": f"Task {task_id} cleared",
    }

# Example usage for backend tasks
def log_task_message(task_id: str, message: str, level: str = "info"):
    """Helper function to log messages from background tasks."""
    TaskStatus.add_message(task_id, message, level)

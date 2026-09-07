"""Celery queue monitoring endpoints."""
import logging
import json
import base64
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from redis import Redis
from app.core.dependencies import require_resource_permission, get_db
from app.celery_app import app as celery_app
from app.models.message_queue import ChannelMessage

router = APIRouter(prefix="/celery", tags=["celery"])
logger = logging.getLogger(__name__)
redis_client = Redis.from_url('redis://localhost:6379/0', decode_responses=True)
MAX_TASKS_PER_QUEUE = 100
MAX_FINISHED_TASKS = 50


@router.get("/workers", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_workers_status():
    """Get Celery worker status (working/idle/stopped)."""
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active() or {}
        stats = inspect.stats() or {}

        workers = []
        if isinstance(stats, dict) and stats:
            stats_items = list(stats.items())
            if stats_items:
                for worker_name, stat_data in stats_items:
                    active_count = len(active.get(worker_name, [])) if isinstance(active.get(worker_name), list) else 0
                    status = "working" if active_count > 0 else "idle"
                    workers.append({
                        "name": worker_name,
                        "status": status,
                        "active_tasks": active_count,
                        "pool_size": stat_data.get("pool", {}).get("max-concurrency", 0)
                    })

        return {"workers": workers, "total_workers": len(workers), "working": sum(1 for w in workers if w["status"] == "working")}
    except Exception as e:
        logger.error(f"Failed to get worker status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queues", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_queues():
    """Get all configured queues with real-time task counts from Redis and Celery."""
    try:
        configured_queues = ["default", "thunder", "email", "sms", "whatsapp", "slack"]
        queue_data = {}

        if configured_queues and isinstance(configured_queues, list):
            for queue_name in configured_queues:
                queue_data[queue_name] = {
                    "name": queue_name,
                    "key": f"celery.{queue_name}",
                    "pending": 0,
                    "active": 0,
                    "reserved": 0,
                    "failed": 0,
                    "completed": 0
                }

        try:
            result_keys = redis_client.keys('celery*')
            if result_keys:
                for key in result_keys:
                    try:
                        length = redis_client.llen(key)
                        # Map Redis key to queue name: "celery" -> "default", "celery.thunder" -> "thunder"
                        if key == 'celery':
                            queue_name = 'default'
                        else:
                            queue_name = key.split('.')[-1] if '.' in key else key
                        if queue_name in queue_data:
                            queue_data[queue_name]["pending"] = length
                            queue_data[queue_name]["key"] = key
                    except Exception as e:
                        logger.warning(f"Failed to get length for Redis key {key}: {e}")
        except Exception as e:
            logger.warning(f"Failed to get Redis keys: {e}")

        try:
            inspect = celery_app.control.inspect()

            active_tasks = inspect.active() or {}
            if active_tasks and isinstance(active_tasks, dict):
                active_items = list(active_tasks.items())
                if active_items:
                    for worker_name, tasks in active_items:
                        if tasks and isinstance(tasks, list):
                            for task in tasks:
                                queue_name = task.get('delivery_info', {}).get('routing_key', 'default')
                                if queue_name not in queue_data:
                                    queue_data[queue_name] = {
                                        "name": queue_name,
                                        "key": f"celery.{queue_name}",
                                        "pending": 0,
                                        "active": 0,
                                        "reserved": 0,
                                        "failed": 0,
                                        "completed": 0
                                    }
                                queue_data[queue_name]["active"] += 1

            reserved_tasks = inspect.reserved() or {}
            if reserved_tasks and isinstance(reserved_tasks, dict):
                reserved_items = list(reserved_tasks.items())
                if reserved_items:
                    for worker_name, tasks in reserved_items:
                        if tasks and isinstance(tasks, list):
                            for task in tasks:
                                queue_name = task.get('delivery_info', {}).get('routing_key', 'default')
                                if queue_name not in queue_data:
                                    queue_data[queue_name] = {
                                        "name": queue_name,
                                        "key": f"celery.{queue_name}",
                                        "pending": 0,
                                        "active": 0,
                                        "reserved": 0,
                                        "failed": 0,
                                        "completed": 0
                                    }
                                queue_data[queue_name]["reserved"] += 1
        except Exception as e:
            logger.warning(f"Failed to get Celery inspect data: {e}")

        queues = list(queue_data.values())
        total_pending = sum(q["pending"] for q in queues)
        total_active = sum(q["active"] for q in queues)
        total_reserved = sum(q["reserved"] for q in queues)

        return {
            "queues": queues,
            "total_queues": len(queues),
            "total_pending": total_pending,
            "total_active": total_active,
            "total_reserved": total_reserved
        }
    except Exception as e:
        logger.error(f"Failed to get queues: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{queue_name}/tasks", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_queue_tasks(queue_name: str = "celery"):
    """Get pending tasks from a queue via Redis."""
    try:
        # Map queue name to Redis key: "default" -> "celery", others -> "celery.{queue_name}"
        if queue_name == "default":
            queue_key = "celery"
        elif queue_name.startswith('celery'):
            queue_key = queue_name
        else:
            queue_key = f"celery.{queue_name}"

        try:
            queue_length = redis_client.llen(queue_key)
        except Exception as e:
            logger.error(f"Failed to get queue length for {queue_key}: {e}")
            queue_length = 0

        tasks = []
        if queue_length and queue_length > 0:
            max_tasks = min(queue_length, MAX_TASKS_PER_QUEUE)
            for i in range(max_tasks):
                try:
                    task_data = redis_client.lindex(queue_key, i)
                    if task_data:
                        try:
                            obj = json.loads(task_data)
                            headers = obj.get('headers', {})

                            # Decode base64-encoded body to get task arguments
                            args_dict = {}
                            try:
                                body_b64 = obj.get('body', '')
                                if body_b64:
                                    body_json = base64.b64decode(body_b64).decode('utf-8')
                                    body_data = json.loads(body_json)
                                    # body_data is typically [args_list, {}, properties_dict]
                                    if isinstance(body_data, list) and len(body_data) > 0:
                                        args_list = body_data[0]
                                        if isinstance(args_list, list) and len(args_list) > 0:
                                            # First argument is usually the main object
                                            first_arg = args_list[0]
                                            if isinstance(first_arg, dict):
                                                args_dict = first_arg
                            except Exception as e:
                                logger.warning(f"Failed to decode body for task {i}: {e}")

                            # Build display string based on task type and args
                            display_name = headers.get('task', 'unknown')
                            if args_dict:
                                # Extract meaningful info based on task type
                                if 'candidate_email' in args_dict:
                                    display_name = f"{display_name} - {args_dict.get('candidate_email', 'unknown')}"
                                elif 'candidate_name' in args_dict:
                                    display_name = f"{display_name} - {args_dict.get('candidate_name', 'unknown')}"

                            tasks.append({
                                "id": headers.get('id', 'unknown'),
                                "name": display_name,
                                "args": args_dict
                            })
                        except Exception as e:
                            logger.warning(f"Failed to parse task at index {i}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to read task at {i} from {queue_key}: {e}")

        logger.info(f"Retrieved {len(tasks)} from queue {queue_name}")
        return {"queue": queue_name, "total_pending": queue_length, "tasks": tasks}
    except Exception as e:
        logger.error(f"Failed to get queue tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_queue_stats():
    """Get Celery queue statistics."""
    try:
        # Count pending tasks from all configured queue keys in Redis
        pending_count = 0
        try:
            result_keys = redis_client.keys('celery*')
            if result_keys:
                for key in result_keys:
                    try:
                        length = redis_client.llen(key)
                        # Map Redis key to queue name: "celery" -> "default", "celery.thunder" -> "thunder"
                        if key == 'celery':
                            queue_name = 'default'
                        else:
                            queue_name = key.split('.')[-1] if '.' in key else key
                        # Only count configured queues
                        configured_queues = ["default", "thunder", "email", "sms", "whatsapp", "slack"]
                        if queue_name in configured_queues:
                            pending_count += length
                    except Exception as e:
                        logger.warning(f"Failed to get length for Redis key {key}: {e}")
        except Exception as e:
            logger.warning(f"Failed to get Redis keys for stats: {e}")

        inspect = celery_app.control.inspect()
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
        active_count = 0
        active_vals = list(active.values()) if active else []
        if active_vals:
            for v in active_vals:
                active_count += len(v)
        scheduled_count = 0
        scheduled_vals = list(scheduled.values()) if scheduled else []
        if scheduled_vals:
            for v in scheduled_vals:
                scheduled_count += len(v)
        reserved_count = 0
        reserved_vals = list(reserved.values()) if reserved else []
        if reserved_vals:
            for v in reserved_vals:
                reserved_count += len(v)
        return {"pending": pending_count, "active": active_count, "reserved": reserved_count, "scheduled": scheduled_count}
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/finished", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_finished_tasks(limit: int = 50):
    """Get finished tasks from Redis."""
    try:
        result_keys = redis_client.keys('celery-task-meta-*')
        finished_tasks = []
        if result_keys:
            max_limit = min(len(result_keys), limit)
            for i in range(max_limit):
                key = result_keys[i]
                try:
                    data = redis_client.get(key)
                    if data:
                        obj = json.loads(data)
                        finished_tasks.append({"id": key.replace('celery-task-meta-', ''), "status": obj.get("status", "UNKNOWN"), "result": obj.get("result"), "traceback": obj.get("traceback")})
                except Exception as e:
                    logger.warning(f"Failed to parse {key}: {e}")
        logger.info(f"Retrieved {len(finished_tasks)} finished tasks")
        return {"total_finished": len(finished_tasks), "tasks": finished_tasks}
    except Exception as e:
        logger.error(f"Failed to get finished tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-public")
def test_public():
    """Simple test endpoint with no dependencies."""
    return {"status": "ok", "test": "public"}

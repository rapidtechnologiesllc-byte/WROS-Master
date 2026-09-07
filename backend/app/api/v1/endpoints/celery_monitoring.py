"""Celery queue monitoring endpoints."""
import logging
import json
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
    """Get list of Celery queues with real-time task counts (pending, active, failed, reserved)."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        queues_list = ["default", "thunder", "email", "sms", "whatsapp", "slack"]
        queues_from_db = {}
        logger.info(f"[QUEUE_DEBUG] Starting database query for {len(queues_list)} queues")

        for queue_name in queues_list:
            try:
                logger.info(f"[QUEUE_DEBUG] Querying queue: {queue_name}")

                try:
                    pending = db.query(func.count(ChannelMessage.id)).filter(
                        ChannelMessage.queue_type == queue_name,
                        ChannelMessage.status == "PENDING"
                    ).scalar() or 0
                except Exception as e:
                    logger.error(f"Failed to query pending for {queue_name}: {e}", exc_info=True)
                    pending = 0

                try:
                    active = db.query(func.count(ChannelMessage.id)).filter(
                        ChannelMessage.queue_type == queue_name,
                        ChannelMessage.status == "PROCESSING"
                    ).scalar() or 0
                except Exception as e:
                    logger.error(f"Failed to query active for {queue_name}: {e}", exc_info=True)
                    active = 0

                try:
                    reserved = db.query(func.count(ChannelMessage.id)).filter(
                        ChannelMessage.queue_type == queue_name,
                        ChannelMessage.status == "RESERVED"
                    ).scalar() or 0
                except Exception as e:
                    logger.error(f"Failed to query reserved for {queue_name}: {e}", exc_info=True)
                    reserved = 0

                try:
                    failed = db.query(func.count(ChannelMessage.id)).filter(
                        ChannelMessage.queue_type == queue_name,
                        ChannelMessage.status == "FAILED"
                    ).scalar() or 0
                except Exception as e:
                    logger.error(f"Failed to query failed for {queue_name}: {e}", exc_info=True)
                    failed = 0

                try:
                    completed = db.query(func.count(ChannelMessage.id)).filter(
                        ChannelMessage.queue_type == queue_name,
                        ChannelMessage.status == "COMPLETED"
                    ).scalar() or 0
                except Exception as e:
                    logger.error(f"Failed to query completed for {queue_name}: {e}", exc_info=True)
                    completed = 0

                queues_from_db[queue_name] = {
                    "name": queue_name,
                    "key": f"celery.{queue_name}",
                    "pending": pending,
                    "active": active,
                    "reserved": reserved,
                    "failed": failed,
                    "completed": completed
                }
            except Exception as e:
                logger.warning(f"Failed to query queue {queue_name} from database: {e}")
                queues_from_db[queue_name] = {
                    "name": queue_name,
                    "key": f"celery.{queue_name}",
                    "pending": 0,
                    "active": 0,
                    "reserved": 0,
                    "failed": 0,
                    "completed": 0
                }

        # If we have database data for all configured queues, return that
        if queues_from_db and len(queues_from_db) == len(queues_list):
            queue_values = list(queues_from_db.values()) if queues_from_db else []
            if queue_values:
                total_pending = 0
                total_active = 0
                total_reserved = 0
                total_completed = 0
                if isinstance(queue_values, list) and len(queue_values) > 0:
                    for q in queue_values:
                        if q and isinstance(q, dict):
                            total_pending += q.get("pending", 0)
                            total_active += q.get("active", 0)
                            total_reserved += q.get("reserved", 0)
                            total_completed += q.get("completed", 0)

                return {
                    "queues": queue_values,
                    "total_queues": len(queues_from_db),
                    "total_pending": total_pending,
                    "total_active": total_active,
                    "total_reserved": total_reserved,
                    "total_completed": total_completed
                }

        queue_data = {}
        seen_queues = set()

        # Get configured queues from Celery app config (primary source of truth)
        if hasattr(celery_app.conf, 'task_queues') and celery_app.conf.task_queues:
            task_queues_list = list(celery_app.conf.task_queues)
            if task_queues_list:
                for queue in task_queues_list:
                    queue_name = queue.name
                    queue_data[queue_name] = {
                        "name": queue_name,
                        "key": f"celery.{queue_name}",
                        "pending": 0,
                        "active": 0,
                        "reserved": 0,
                        "failed": 0
                    }
                    seen_queues.add(queue_name)

        # Get Redis keys for actual queue task data
        result_keys = redis_client.keys('celery*')

        # Get Celery inspect data for all task states
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        reserved_tasks = inspect.reserved() or {}

        # Update queue data with actual tasks from Redis (pending)
        if result_keys:
            for key in result_keys:
                try:
                    length = redis_client.llen(key)
                    queue_name = key.split('.')[-1] if '.' in key else key
                    if queue_name not in queue_data:
                        queue_data[queue_name] = {
                            "name": queue_name,
                            "key": key,
                            "pending": 0,
                            "active": 0,
                            "reserved": 0,
                            "failed": 0
                        }
                    queue_data[queue_name]["pending"] = length
                    seen_queues.add(queue_name)
                except Exception as e:
                    logger.warning(f"Failed to get length for {key}: {e}")

        # Count active tasks per queue
        if active_tasks:
            active_items = list(active_tasks.items())
            if active_items:
                for worker_name, tasks in active_items:
                    if isinstance(tasks, list) and tasks:
                        task_list = [t for t in tasks]
                        if task_list:
                            for task in task_list:
                                queue_name = task.get('delivery_info', {}).get('routing_key', 'default')
                                if queue_name not in queue_data:
                                    queue_data[queue_name] = {
                                        "name": queue_name,
                                        "key": f"celery.{queue_name}",
                                        "pending": 0,
                                        "active": 0,
                                        "reserved": 0,
                                        "failed": 0
                                    }
                                    seen_queues.add(queue_name)
                                queue_data[queue_name]["active"] += 1

        # Count reserved tasks per queue
        if reserved_tasks:
            reserved_items = list(reserved_tasks.items())
            if reserved_items:
                for worker_name, tasks in reserved_items:
                    if isinstance(tasks, list) and tasks:
                        task_list = [t for t in tasks]
                        if task_list:
                            for task in task_list:
                                queue_name = task.get('delivery_info', {}).get('routing_key', 'default')
                                if queue_name not in queue_data:
                                    queue_data[queue_name] = {
                                        "name": queue_name,
                                        "key": f"celery.{queue_name}",
                                        "pending": 0,
                                        "active": 0,
                                        "reserved": 0,
                                        "failed": 0
                                    }
                                    seen_queues.add(queue_name)
                                queue_data[queue_name]["reserved"] += 1

        # Get registered queues from Celery inspect API to discover all queues
        try:
            registered_queues = inspect.registered() or {}
            if isinstance(registered_queues, dict) and registered_queues:
                queue_items = list(registered_queues.items())
                if queue_items:
                    for worker_name, tasks in queue_items:
                        if tasks:
                            for task_name in tasks:
                                if hasattr(celery_app.conf, 'task_routes') and celery_app.conf.task_routes:
                                    if callable(celery_app.conf.task_routes):
                                        route = celery_app.conf.task_routes(task_name)
                                        if route and 'queue' in route:
                                            queue_name = route['queue']
                                            if queue_name not in seen_queues:
                                                queue_data[queue_name] = {
                                                    "name": queue_name,
                                                    "key": f"celery.{queue_name}",
                                                    "pending": 0,
                                                    "active": 0,
                                                    "reserved": 0,
                                                    "failed": 0
                                                }
                                                seen_queues.add(queue_name)
        except Exception as e:
            logger.warning(f"Failed to get registered queues: {e}")

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
def get_queue_tasks(queue_name: str = "celery", db: Session = Depends(get_db)):
    """Get pending tasks from a queue (from database)."""
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()

        try:
            normalized_queue = queue_name.upper() if queue_name.upper() in ["THUNDER", "DEFAULT", "EMAIL", "SMS", "WHATSAPP", "SLACK"] else queue_name

            try:
                pending_messages = db.query(ChannelMessage).filter(
                    ChannelMessage.queue_type == normalized_queue,
                    ChannelMessage.status == "PENDING"
                ).limit(MAX_TASKS_PER_QUEUE).all()
            except Exception as e:
                logger.error(f"Database query failed for queue {normalized_queue}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

            tasks = []
            if pending_messages:
                for msg in pending_messages:
                    try:
                        tasks.append({
                            "id": str(msg.id) if msg.id else "unknown",
                            "name": msg.type or "unknown",
                            "queue": msg.queue_type,
                            "status": msg.status,
                            "created_at": msg.created_at.isoformat() if msg.created_at else None,
                            "payload": msg.payload if msg.payload else {}
                        })
                    except Exception as e:
                        logger.warning(f"Failed to process task {msg.id}: {e}")

            logger.info(f"Retrieved {len(tasks)} pending tasks from {normalized_queue}")
            return {"queue": normalized_queue, "total_pending": len(tasks), "tasks": tasks}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to get queue tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", dependencies=[Depends(require_resource_permission("queue", "view"))])
def get_queue_stats():
    """Get Celery queue statistics."""
    try:
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
        pending_count = redis_client.llen('celery')
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

"""Celery queue utilities and helpers."""
import logging

logger = logging.getLogger(__name__)

CONFIGURED_QUEUES = ["default", "thunder", "email", "sms", "whatsapp", "slack"]


def redis_key_to_queue_name(redis_key: str) -> str:
    """
    Map Redis key to configured queue name.

    Handles both formats:
    - "celery" → "default" (default queue, no dot notation)
    - "celery.thunder" → "thunder" (named queues)
    """
    if redis_key == "celery":
        return "default"
    elif "." in redis_key:
        return redis_key.split(".")[-1]
    else:
        return redis_key


def queue_name_to_redis_key(queue_name: str) -> str:
    """
    Map configured queue name to Redis key.

    Handles both formats:
    - "default" → "celery" (default queue)
    - "thunder" → "celery.thunder" (named queues)
    """
    if queue_name == "default":
        return "celery"
    elif queue_name.startswith("celery"):
        return queue_name
    else:
        return f"celery.{queue_name}"


def get_configured_queues() -> list:
    """Return list of configured queue names."""
    return CONFIGURED_QUEUES.copy()

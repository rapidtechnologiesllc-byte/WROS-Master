"""Timeout handling for async operations."""
import asyncio
import logging

logger = logging.getLogger(__name__)

# Default timeout configurations (in seconds)
DEFAULT_API_TIMEOUT = 30
DEFAULT_BULK_TIMEOUT = 60
DEFAULT_DATABASE_TIMEOUT = 15

async def with_timeout(coro, timeout_seconds: int, operation_name: str = "Operation"):
    """Execute a coroutine with timeout protection.
    
    Args:
        coro: The coroutine to execute
        timeout_seconds: Timeout in seconds
        operation_name: Name of operation for logging
        
    Returns:
        Result of the coroutine
        
    Raises:
        TimeoutError: If operation exceeds timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(
            f"[TIMEOUT] {operation_name} exceeded {timeout_seconds}s timeout",
            extra={"timeout_seconds": timeout_seconds, "operation": operation_name}
        )
        raise TimeoutError(
            f"{operation_name} timed out after {timeout_seconds} seconds"
        )
    except Exception as e:
        logger.error(
            f"[ERROR] {operation_name} failed: {str(e)}",
            exc_info=True,
            extra={"operation": operation_name}
        )
        raise

async def api_call_with_timeout(coro, operation_name: str = "API Call"):
    """Execute an API call with 30-second timeout."""
    return await with_timeout(coro, DEFAULT_API_TIMEOUT, operation_name)

async def bulk_operation_with_timeout(coro, operation_name: str = "Bulk Operation"):
    """Execute a bulk operation with 60-second timeout."""
    return await with_timeout(coro, DEFAULT_BULK_TIMEOUT, operation_name)

async def database_call_with_timeout(coro, operation_name: str = "Database Call"):
    """Execute a database call with 15-second timeout."""
    return await with_timeout(coro, DEFAULT_DATABASE_TIMEOUT, operation_name)

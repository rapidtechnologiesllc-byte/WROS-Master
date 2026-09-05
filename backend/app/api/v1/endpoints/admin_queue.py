"""Admin Queue endpoint stub - minimal implementation to prevent import errors"""

from enum import Enum
from fastapi import APIRouter

# Minimal exports to satisfy imports
class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# Router stub
router = APIRouter()

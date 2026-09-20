from fastapi import APIRouter
from app.api.v1.endpoints.candidates.crud import router as crud_router
from app.api.v1.endpoints.candidates.create_queue_first import router as queue_router

# Combine all candidate routers
# Note: Queue-based endpoint takes priority (registered first)
# CRITICAL: create_queue_first must be registered before crud to match /candidates/ route first
router = APIRouter()
router.include_router(queue_router)  # POST /candidates/ - queue-based (async)
router.include_router(crud_router)   # Other candidate operations

__all__ = ["router", "crud_router", "queue_router"]

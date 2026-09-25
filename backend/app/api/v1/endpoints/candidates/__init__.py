from fastapi import APIRouter
from app.api.v1.endpoints.candidates.crud import router as crud_router
from app.api.v1.endpoints.candidates.create_queue_first import router as queue_router

# Combine all candidate routers
# Note: candidates.py routes are now directly included in main.py
router = APIRouter()
router.include_router(queue_router)  # POST /candidates/ - queue-based (async)
router.include_router(crud_router)   # Other candidate operations

__all__ = ["router", "crud_router", "queue_router"]

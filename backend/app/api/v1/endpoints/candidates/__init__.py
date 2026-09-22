from fastapi import APIRouter
from app.api.v1.endpoints.candidates.crud import router as crud_router

# Combine all candidate routers
# Note: candidates.py routes are now directly included in main.py
router = APIRouter()
router.include_router(crud_router)

__all__ = ["router", "crud_router"]

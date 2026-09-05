from fastapi import APIRouter
from app.api.v1.endpoints.candidates.crud import router as crud_router

# Combine all candidate routers
# Note: create and conversions modules moved to crud.py for consolidation
router = APIRouter()
router.include_router(crud_router)

__all__ = ["router", "crud_router"]

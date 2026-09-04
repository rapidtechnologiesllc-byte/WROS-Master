from fastapi import APIRouter
from app.api.v1.endpoints.candidates.create import router as create_router
from app.api.v1.endpoints.candidates.conversions import router as conversions_router

# Combine queue-based and conversion routers
router = APIRouter()
router.include_router(create_router)
router.include_router(conversions_router)

__all__ = ["router", "create_router", "conversions_router"]

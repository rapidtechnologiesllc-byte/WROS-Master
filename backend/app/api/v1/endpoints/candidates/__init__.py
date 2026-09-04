from fastapi import APIRouter
from app.api.v1.endpoints.candidates.crud import router as crud_router
from app.api.v1.endpoints.candidates.create import router as create_router
import logging
from app.api.v1.endpoints.candidates.conversions import router as conversions_router

# Combine both microservice routers into single export
router = APIRouter()
router.include_router(create_router)
router.include_router(crud_router)
router.include_router(conversions_router)

__all__ = ["router", "create_router", "crud_router", "conversions_router"]

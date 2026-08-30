# Users microservice package
from fastapi import APIRouter
from app.api.v1.endpoints.users.crud import router as crud_router

router = APIRouter()
router.include_router(crud_router)

__all__ = ["router", "crud_router"]

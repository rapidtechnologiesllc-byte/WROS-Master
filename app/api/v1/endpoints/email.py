"""Email management endpoints - templates and delivery tracking."""

import fastapi
from app.api.v1.endpoints.email_templates import router as email_templates_router
from app.api.v1.endpoints.email_deliveries import router as email_deliveries_router

router = fastapi.APIRouter()

# Include email template and delivery routers
router.include_router(email_templates_router)
router.include_router(email_deliveries_router)

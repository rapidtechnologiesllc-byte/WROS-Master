"""
API Router - Main entry point for all endpoints
"""
from fastapi import APIRouter
import logging
from app.routes import api_v1_revenue, api_v1_invoices, api_v1_pnl

router = APIRouter()

# Include all API routers
router.include_router(api_v1_revenue.router)
router.include_router(api_v1_invoices.router)
router.include_router(api_v1_pnl.router)

__all__ = ["router"]

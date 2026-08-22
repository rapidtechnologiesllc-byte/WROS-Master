"""HRMS-0532 (S-376) — Demand Forecasting REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.predictive_demand_service import forecast_demand, get_demand_variance

router = APIRouter(prefix="/demand-forecast", tags=["demand-forecast"])


@router.get("/forecast/{business_unit_id}")
async def get_forecast(business_unit_id: int, days_ahead: int = 90, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get demand forecast."""
    return forecast_demand(db, business_unit_id, days_ahead)


@router.get("/variance/{business_unit_id}")
async def get_variance(business_unit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get demand variance."""
    return get_demand_variance(db, business_unit_id)

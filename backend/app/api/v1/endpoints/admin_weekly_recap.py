"""Admin Weekly Recap API -- agent health, alerts and pipeline for one week."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.services.admin_weekly_recap_service import get_weekly_recap

router = APIRouter(prefix="/admin", tags=["admin-weekly-recap"])


@router.get(
    "/weekly-recap",
    dependencies=[Depends(require_resource_permission("admin-weekly-recap", "view"))],
)
def weekly_recap(
    weeks_back: int = Query(default=0, ge=0, le=52, description="0 = this week, 1 = last week, ..."),
    db: Session = Depends(get_db),
):
    return get_weekly_recap(db, weeks_back=weeks_back)

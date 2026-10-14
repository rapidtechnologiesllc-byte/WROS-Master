"""
Workforce Overview -- API
=========================================================================
Prefix: /workforce
Tag:    workforce

Where every employee stands between the bench, Staff Aug and Core (CEO 2026-10-14), grouped so
the groups add up to headcount (app.services.workforce_report_service). Scoped like the
Employees screen: the caller's tenant and business units.

Auth: the employee-in-bench permission (Workforce module).

Routes:
  GET  /workforce/overview
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.workforce import WorkforceOverviewResponse
from app.services.workforce_report_service import workforce_overview

router = APIRouter(prefix="/workforce", tags=["workforce"])


@router.get(
    "/overview",
    dependencies=[
        Depends(require_resource_permission("employee-in-bench", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=WorkforceOverviewResponse,
    summary="Bench / Staff Aug / Core: every employee in exactly one group",
)
def get_workforce_overview(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    return workforce_overview(db, current_user)

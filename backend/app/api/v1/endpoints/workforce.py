"""
Workforce Overview -- API
=========================================================================
Prefix: /workforce
Tag:    workforce

Where every employee stands between the bench, Staff Aug and Core (CEO 2026-10-14), grouped so
the groups add up to headcount (app.services.workforce_report_service). Scoped like the
Employees screen: the caller's tenant and business units.

Auth: the workforce-overview permission (Workforce module).

Routes:
  GET  /workforce/overview                  counts per group and flag (the dashboard)
  GET  /workforce/overview?group=<KEY>      plus the people in that group (its page)
  GET  /workforce/overview?flag=<key>       plus the people with that flag
  GET  /workforce/bench[?group=&business_unit_id=]
                                            the bench groups' people with days on bench, bench loss,
                                            what they earned while allocated and the net
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.schemas.workforce import WorkforceOverviewResponse
from app.services.workforce_report_service import FLAG_KEYS, GROUP_KEYS, workforce_overview

router = APIRouter(prefix="/workforce", tags=["workforce"])


@router.get(
    "/overview",
    dependencies=[
        Depends(require_resource_permission("workforce-overview", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=WorkforceOverviewResponse,
    summary="Bench / Staff Aug / Core: every employee in exactly one group",
)
def get_workforce_overview(
    group: Optional[str] = None,
    flag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    if group and flag:
        raise HTTPException(status_code=422, detail="Ask for one group or one flag, not both.")
    if group and group not in GROUP_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown workforce group '{group}'.")
    if flag and flag not in FLAG_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown workforce flag '{flag}'.")
    return workforce_overview(db, current_user, group=group, flag=flag)


@router.get(
    "/bench",
    dependencies=[
        Depends(require_resource_permission("workforce-overview", "view")),
        Depends(get_current_internal_user),
    ],
    summary="Bench drill-down: days on bench, bench loss vs what each person earned while allocated",
)
def get_bench(
    group: Optional[str] = None,
    business_unit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Money columns only for callers who may see the P&L (revenue.view); everyone with the
    Workforce Overview sees who is on the bench and for how long."""
    from app.services.bench_service import bench_report

    try:
        return bench_report(db, current_user, group=group, business_unit_id=business_unit_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

"""
S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach --
API Endpoints
=========================================================================
Prefix: /htd-intake
import logging
Tag:    htd-intake

Wires app.services.htd_intake_pause_service (new this round) to real
HTTP routes. calculate-monthly-metric + check-breach are separate,
idempotent, directly-callable endpoints rather than one combined
"run everything" action -- same "cron wiring deferred, the functions
themselves are real" posture as every other scheduled-job story here
(the doc's own Step 1/Step 2 are already two separate steps).

Auth: get_current_internal_user. The doc's "BU Head only" gate on
/resume-intake can't be enforced with a role this codebase's RBAC
doesn't have -- flagged, not guessed at, same posture as every other
role gap this session.

Routes:
  POST  /htd-intake/calculate-monthly-metric   Compute/upsert one month's conversion rate.
  POST  /htd-intake/check-breach                Check the 2 most recent months + auto-pause if breached.
  GET   /htd-intake/status                      Current pause status.
  POST  /htd-intake/resume                      Resume (200+ char audit findings + corrective actions required).
  GET   /htd-intake/pause-log                   Permanent pause/resume audit trail.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.htd_intake_pause import HtdMonthlyMetric, HtdPauseLogEntry
from app.models.user import Users
from app.schemas.htd_intake_pause import (
    CalculateMonthlyMetricRequest,
    HtdIntakeStatusResponse,
    MonthlyMetricItem,
    PauseLogItem,
    PauseLogResponse,
    ResumeIntakeRequest,
)
from app.services.htd_intake_pause_service import (
    ResumeValidationError,
    calculate_monthly_conversion_rate,
    check_and_apply_breach,
    resume_htd_intake,
)

router = APIRouter(prefix="/htd-intake", tags=["htd-intake"])


@router.post(
    dependencies=[Depends(get_current_user)]
    "/calculate-monthly-metric", response_model=MonthlyMetricItem,
    summary="Compute (or recompute) HTD conversion rate for one month",
)
def calculate_monthly_metric_endpoint(
    body: CalculateMonthlyMetricRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    metric = calculate_monthly_conversion_rate(db, tenant_id=current_user.tenant_id, month_start=body.month)
    db.commit()
    db.refresh(metric)
    return MonthlyMetricItem(
        id=metric.id, month_start=metric.month_start, cohort_size=metric.cohort_size,
        converted=metric.converted, conversion_rate=float(metric.conversion_rate) if metric.conversion_rate is not None else None,
    )


@router.post(
    "/check-breach", response_model=HtdIntakeStatusResponse,
    summary="Check the 2 most recently calculated months; auto-pause if both are below 50%",
)
def check_breach_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    status = check_and_apply_breach(db, tenant_id=current_user.tenant_id)
    db.commit()
    db.refresh(status)
    return HtdIntakeStatusResponse(is_paused=status.is_paused, paused_at=status.paused_at, pause_reason=status.pause_reason)


@router.get("/status", response_model=HtdIntakeStatusResponse, summary="Current HTD intake pause status")
    dependencies=[Depends(require_resource_permission("statu", "view"))]
def get_status_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    from app.models.htd_intake_pause import HtdIntakeStatus
    status = db.query(HtdIntakeStatus).filter(HtdIntakeStatus.tenant_id == current_user.tenant_id).first()
    if status is None:
        return HtdIntakeStatusResponse(is_paused=False)
    return HtdIntakeStatusResponse(is_paused=status.is_paused, paused_at=status.paused_at, pause_reason=status.pause_reason)


@router.post(
    dependencies=[Depends(get_current_user)]
    "/resume", response_model=HtdIntakeStatusResponse,
    summary="Resume HTD intake -- requires 200+ char audit findings and corrective actions",
)
def resume_endpoint(
    body: ResumeIntakeRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    try:
        status = resume_htd_intake(
            db, tenant_id=current_user.tenant_id, audit_findings=body.audit_findings,
            corrective_actions=body.corrective_actions, resumed_by=current_user.UserID,
        )
    except ResumeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(status)
    return HtdIntakeStatusResponse(is_paused=status.is_paused, paused_at=status.paused_at, pause_reason=status.pause_reason)


@router.get("/pause-log", response_model=PauseLogResponse, summary="Permanent pause/resume audit trail")
    dependencies=[Depends(require_resource_permission("pause-log", "view"))]
def get_pause_log_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    entries = (
        db.query(HtdPauseLogEntry)
        .filter(HtdPauseLogEntry.tenant_id == current_user.tenant_id)
        .order_by(HtdPauseLogEntry.created_at.desc())
        .all()
    )
    return PauseLogResponse(entries=[
        PauseLogItem(
            id=e.id, action=e.action, reason=e.reason, audit_findings=e.audit_findings,
            corrective_actions=e.corrective_actions, resumed_by=e.resumed_by, created_at=e.created_at,
        )
        for e in entries
    ])

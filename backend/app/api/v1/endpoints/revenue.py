"""
HRMS-0906 (Revenue Realization & Leakage Detection) + HRMS-0903
(Timesheet-to-Revenue Bridge Reconciliation) + HRMS-0909 (Client
Revenue Realization Dashboard) -- API Endpoints
=========================================================================
Prefix: /revenue
import logging
Tag:    revenue

Wires app.services.revenue_leakage_service and app.services.client_
revenue_dashboard_service (real, tested backend, pre-existing this
codebase) to real HTTP routes. No REST layer previously existed for
any of the three. Per revenue_leakage_service.py's own docstring
(BR-0906-01), this leakage-detection module is meant to be the shared
source a broader Revenue Visibility feature (HRMS-0214, not built)
reads from -- nothing here reimplements that.

The dashboard route returns 200 with a note field (not 404) when a
client has no projects, matching client_revenue_dashboard_service.py's
own "insufficient data, not a misleading number" convention -- this
endpoint does not invent a different contract on top of it.

Auth: get_current_internal_user. Same RBAC "Finance" role gap noted in
invoices.py applies here too.

Routes:
  POST   /revenue/leakage/scan                    Scan a project+period for unbilled leakage.
  POST   /revenue/leakage/{flag_id}/log-reason     Suppress a flag with a logged reason (e.g. negotiated cap).
  GET    /revenue/leakage                          List active (unresolved) leakage flags.
  POST   /revenue/reconciliation/scan              Find + create alerts for approved-but-uninvoiced timesheets.
  GET    /revenue/reconciliation/alerts            List reconciliation alerts (optional status filter).
  POST   /revenue/reconciliation/alerts/{id}/resolve   Mark an alert resolved.
  GET    /revenue/dashboard/clients/{client_id}    Client revenue realization dashboard.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.client import Client
from app.models.project import Project
from app.models.revenue_leakage import ReconciliationAlert, RevenueLeakageFlag
from app.models.timesheet import Timesheet
from app.models.user import Users
from app.schemas.revenue import (
    ClientRevenueDashboardResponse,
    LeakageFlagItem,
    LeakageFlagsResponse,
    LogPartialBillingReasonRequest,
    ReconciliationAlertItem,
    ReconciliationAlertsResponse,
    ReconciliationScanResponse,
    ScanLeakageRequest,
)
from app.services.client_revenue_dashboard_service import get_client_revenue_dashboard
from app.services.revenue_leakage_service import (
    create_reconciliation_alert,
    find_reconciliation_gaps,
    get_active_leakage_flags,
    log_partial_billing_reason,
    resolve_reconciliation_alert,
    scan_project_revenue_leakage,
)
from app.services.revenue_scanning_service import (
    get_recent_scan_results,
    get_scan_statistics,
    run_daily_revenue_scan_job,
)

router = APIRouter(prefix="/revenue", tags=["revenue"])


def _flag_to_item(flag: RevenueLeakageFlag) -> LeakageFlagItem:
    return LeakageFlagItem(
        id=flag.id, project_id=flag.project_id, period_start=flag.period_start, period_end=flag.period_end,
        approved_hours=float(flag.approved_hours), invoiced_hours=float(flag.invoiced_hours),
        unbilled_hours=float(flag.unbilled_hours), partial_billing_reason=flag.partial_billing_reason,
        detected_at=flag.detected_at,
    )


def _alert_to_item(alert: ReconciliationAlert) -> ReconciliationAlertItem:
    return ReconciliationAlertItem(
        id=alert.id, timesheet_id=alert.timesheet_id, employee_id=alert.employee_id,
        billable_hours=float(alert.billable_hours), status=alert.status, gap_detected_at=alert.gap_detected_at,
    )


@router.post(
    dependencies=[Depends(get_current_user)]
    "/leakage/scan", response_model=Optional[LeakageFlagItem],
    summary="Scan a project+period for unbilled revenue leakage (null if too early or nothing unbilled)",
)
def scan_leakage(
    body: ScanLeakageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = db.query(Project).filter(Project.id == body.project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    flag = scan_project_revenue_leakage(db, project, period_start=body.period_start, period_end=body.period_end)
    db.commit()
    if flag is None:
        return None
    db.refresh(flag)
    return _flag_to_item(flag)


@router.post(
    dependencies=[Depends(get_current_user)]
    "/leakage/{flag_id}/log-reason", response_model=LeakageFlagItem,
    summary="Log a reason (e.g. client-negotiated cap) that suppresses a leakage flag",
)
def log_leakage_reason(
    flag_id: str,
    body: LogPartialBillingReasonRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    flag = db.query(RevenueLeakageFlag).filter(RevenueLeakageFlag.id == flag_id).first()
    if flag is None:
        raise HTTPException(status_code=404, detail="Leakage flag not found.")
    flag = log_partial_billing_reason(db, flag, reason=body.reason)
    db.commit()
    db.refresh(flag)
    return _flag_to_item(flag)


@router.get("/leakage", response_model=LeakageFlagsResponse, summary="List active (unresolved) leakage flags (cached from daily scan)")
    dependencies=[Depends(require_resource_permission("leakage", "view"))]
def list_leakage_flags(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Returns cached revenue leakage results from the daily autonomous scan.
    No manual project UUID entry needed — results are cached and updated daily (02:00 UTC).

    The manual "rescan specific project" action is available via POST /revenue/leakage/scan.
    """
    flags = get_active_leakage_flags(db, tenant_id=current_user.tenant_id)
    return LeakageFlagsResponse(flags=[_flag_to_item(f) for f in flags])


@router.get("/leakage/statistics", response_model=dict, summary="Get revenue leakage statistics and totals")
    dependencies=[Depends(require_resource_permission("leakage", "view"))]
def get_leakage_statistics(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Returns aggregate statistics about revenue leakage:
    - Total active leakage flags
    - Total unbilled hours across all projects
    - Estimated value of unbilled revenue (advisory only)
    - Number of affected projects
    """
    stats = get_scan_statistics(db, tenant_id=current_user.tenant_id)
    return stats


@router.post("/leakage/rescan-all", response_model=dict, summary="Manually trigger full revenue scan (secondary action)")
    dependencies=[Depends(require_resource_permission("leakage", "create"))]
def rescan_all_projects(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Manually trigger a full scan of all projects for revenue leakage.
    This is a secondary action — the primary flow uses the daily cached results from GET /revenue/leakage.

    Returns scan results and updates the cache for subsequent requests.
    """
    result = run_daily_revenue_scan_job(db)
    return result


@router.post(
    dependencies=[Depends(get_current_user)]
    "/reconciliation/scan", response_model=ReconciliationScanResponse,
    summary="Find approved-but-uninvoiced timesheets past the grace period and create alerts",
)
def scan_reconciliation(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    gaps = find_reconciliation_gaps(db, tenant_id=current_user.tenant_id)
    alerts = [create_reconciliation_alert(db, ts, tenant_id=current_user.tenant_id) for ts in gaps]
    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return ReconciliationScanResponse(alerts=[_alert_to_item(a) for a in alerts])


@router.get(
    dependencies=[Depends(get_current_user)]
    "/reconciliation/alerts", response_model=ReconciliationAlertsResponse,
    summary="List reconciliation alerts",
)
def list_reconciliation_alerts(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(ReconciliationAlert).filter(ReconciliationAlert.tenant_id == current_user.tenant_id)
    if status:
        query = query.filter(ReconciliationAlert.status == status)
    alerts = query.order_by(ReconciliationAlert.gap_detected_at.desc()).all()
    return ReconciliationAlertsResponse(alerts=[_alert_to_item(a) for a in alerts])


@router.post(
    dependencies=[Depends(get_current_user)]
    "/reconciliation/alerts/{alert_id}/resolve", response_model=ReconciliationAlertItem,
    summary="Mark a reconciliation alert resolved",
)
def resolve_reconciliation_alert_endpoint(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    alert = db.query(ReconciliationAlert).filter(ReconciliationAlert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Reconciliation alert not found.")
    alert = resolve_reconciliation_alert(db, alert)
    db.commit()
    db.refresh(alert)
    return _alert_to_item(alert)


@router.get(
    dependencies=[Depends(get_current_user)]
    "/dashboard/clients/{client_id}", response_model=ClientRevenueDashboardResponse,
    summary="Client revenue realization dashboard (internal only, estimate)",
)
def get_client_dashboard(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    result = get_client_revenue_dashboard(db, client, tenant_id=current_user.tenant_id)
    return ClientRevenueDashboardResponse(**result)

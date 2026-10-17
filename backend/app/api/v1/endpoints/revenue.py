"""
HRMS-0906 (Revenue Realization & Leakage Detection) + HRMS-0903
(Timesheet-to-Revenue Bridge Reconciliation) + HRMS-0909 (Client
Revenue Realization Dashboard) -- API Endpoints
=========================================================================
Prefix: /revenue
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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.data_scope import client_bu_id, client_filter, ensure_visible
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
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

router = APIRouter(prefix="/revenue", tags=["revenue"])


# Business-unit scope (app.core.data_scope): revenue is money, so a record counts only for
# the business units of its client; unassigned clients are visible to org-level users only.
def _visible_projects(db: Session, user: Users):
    return select(Project.id).where(client_filter(db, user, Project.client_id, unassigned_visible=False))


def _visible_timesheets(db: Session, user: Users):
    from app.models.employee_allocation import EmployeeAllocation

    allocations = select(EmployeeAllocation.id).where(
        client_filter(db, user, EmployeeAllocation.client_id, unassigned_visible=False))
    return select(Timesheet.id).where(Timesheet.allocation_id.in_(allocations))


def _get_project_or_404(db: Session, user: Users, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == user.tenant_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    ensure_visible(db, user, client_bu_id(db, project.client_id), "Project", unassigned_visible=False)
    return project


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
    "/leakage/scan",
    dependencies=[
        Depends(require_resource_permission("sales-ops", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=Optional[LeakageFlagItem],
    summary="Scan a project+period for unbilled revenue leakage (null if too early or nothing unbilled)",
)
def scan_leakage(
    body: ScanLeakageRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    project = _get_project_or_404(db, current_user, body.project_id)
    flag = scan_project_revenue_leakage(db, project, period_start=body.period_start, period_end=body.period_end)
    db.commit()
    if flag is None:
        return None
    db.refresh(flag)
    return _flag_to_item(flag)

@router.post(
    "/leakage/{flag_id}/log-reason",
    dependencies=[
        Depends(require_resource_permission("sales-ops", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=LeakageFlagItem,
    summary="Log a reason (e.g. client-negotiated cap) that suppresses a leakage flag",
)
def log_leakage_reason(
    flag_id: str,
    body: LogPartialBillingReasonRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    flag = db.query(RevenueLeakageFlag).filter(
        RevenueLeakageFlag.id == flag_id, RevenueLeakageFlag.project_id.in_(_visible_projects(db, current_user)),
    ).first()
    if flag is None:
        raise HTTPException(status_code=404, detail="Leakage flag not found.")
    flag = log_partial_billing_reason(db, flag, reason=body.reason)
    db.commit()
    db.refresh(flag)
    return _flag_to_item(flag)

@router.get(
    "/leakage",
    response_model=LeakageFlagsResponse,
    summary="List active (unresolved) leakage flags (cached from daily scan)",
    dependencies=[Depends(require_resource_permission("sales-ops", "view"))]
)
def list_leakage_flags(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """
    Returns cached revenue leakage results from the daily autonomous scan.
    No manual project UUID entry needed — results are cached and updated daily (02:00 UTC).

    The manual "rescan specific project" action is available via POST /revenue/leakage/scan.
    """
    visible = {row[0] for row in db.execute(_visible_projects(db, current_user)).all()}
    flags = [f for f in get_active_leakage_flags(db, tenant_id=current_user.tenant_id) if f.project_id in visible]
    return LeakageFlagsResponse(flags=[_flag_to_item(f) for f in flags])


@router.post(
    "/reconciliation/scan",
    dependencies=[
        Depends(require_resource_permission("sales-ops", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=ReconciliationScanResponse,
    summary="Find approved-but-uninvoiced timesheets past the grace period and create alerts",
)
def scan_reconciliation(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    visible = {row[0] for row in db.execute(_visible_timesheets(db, current_user)).all()}
    gaps = [ts for ts in find_reconciliation_gaps(db, tenant_id=current_user.tenant_id) if ts.id in visible]
    alerts = [create_reconciliation_alert(db, ts, tenant_id=current_user.tenant_id) for ts in gaps]
    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return ReconciliationScanResponse(alerts=[_alert_to_item(a) for a in alerts])

@router.get(
    "/reconciliation/alerts",
    dependencies=[
        Depends(require_resource_permission("sales-ops", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=ReconciliationAlertsResponse,
    summary="List reconciliation alerts",
)
def list_reconciliation_alerts(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    query = db.query(ReconciliationAlert).filter(
        ReconciliationAlert.tenant_id == current_user.tenant_id,
        ReconciliationAlert.timesheet_id.in_(_visible_timesheets(db, current_user)),
    )
    if status:
        query = query.filter(ReconciliationAlert.status == status)
    alerts = query.order_by(ReconciliationAlert.gap_detected_at.desc()).all()
    return ReconciliationAlertsResponse(alerts=[_alert_to_item(a) for a in alerts])

@router.post(
    "/reconciliation/alerts/{alert_id}/resolve",
    dependencies=[
        Depends(require_resource_permission("sales-ops", "create")),
        Depends(get_current_internal_user),
    ],
    response_model=ReconciliationAlertItem,
    summary="Mark a reconciliation alert resolved",
)
def resolve_reconciliation_alert_endpoint(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    alert = db.query(ReconciliationAlert).filter(
        ReconciliationAlert.id == alert_id, ReconciliationAlert.tenant_id == current_user.tenant_id,
        ReconciliationAlert.timesheet_id.in_(_visible_timesheets(db, current_user)),
    ).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Reconciliation alert not found.")
    alert = resolve_reconciliation_alert(db, alert)
    db.commit()
    db.refresh(alert)
    return _alert_to_item(alert)

@router.get(
    "/dashboard/clients/{client_id}",
    dependencies=[
        Depends(require_resource_permission("resources", "view")),
        Depends(get_current_internal_user),
    ],
    response_model=ClientRevenueDashboardResponse,
    summary="Get revenue dashboard for a client",
)
def get_client_dashboard(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    client = db.query(Client).filter(Client.id == client_id, Client.tenant_id == current_user.tenant_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    ensure_visible(db, current_user, client.business_unit_id, "Client", unassigned_visible=False)
    result = get_client_revenue_dashboard(db, client, tenant_id=current_user.tenant_id)
    return ClientRevenueDashboardResponse(**result)

"""Fiscal year definition (tenant setting).

The fiscal year starts on the 1st of a configurable month
(system_config key "fiscal_year_start_month"; unset = January). A fiscal
year is named by the calendar year it starts in: with an April start,
FY 2026 runs 1 Apr 2026 - 31 Mar 2027 and is labelled "FY 2026-27".
Everything that reports "this FY" (CEO Dashboard, goal tree, executive
revenue) takes its window from here.
"""
from app.core.tenant_context import sole_tenant_id
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

CONFIG_KEY = "fiscal_year_start_month"
DEFAULT_START_MONTH = 1


def _row(db: Session, tenant_id: int):
    from app.models.system_config import SystemConfig
    return db.query(SystemConfig).filter(
        SystemConfig.tenant_id == tenant_id, SystemConfig.business_unit_id.is_(None),
        SystemConfig.config_key == CONFIG_KEY,
    ).first()


def get_fy_start_month(db: Session, tenant_id: Optional[int] = None) -> int:
    row = _row(db, tenant_id if tenant_id is not None else sole_tenant_id(db))
    month = (row.config_value or {}).get("month") if row and isinstance(row.config_value, dict) else None
    return month if isinstance(month, int) and 1 <= month <= 12 else DEFAULT_START_MONTH


def set_fy_start_month(db: Session, month: int, tenant_id: int, updated_by: Optional[str] = None) -> int:
    from app.models.system_config import SystemConfig
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Fiscal year start month must be 1-12")
    row = _row(db, tenant_id)
    if row is None:
        row = SystemConfig(tenant_id=tenant_id, business_unit_id=None, config_category="FINANCE",
                           config_key=CONFIG_KEY, config_value={})
        db.add(row)
    row.config_value = {"month": month}
    row.updated_by = updated_by
    db.commit()
    return month


def current_fy(db: Session, tenant_id: Optional[int] = None, today: Optional[date] = None) -> int:
    today = today or date.today()
    start_month = get_fy_start_month(db, tenant_id)
    return today.year if today.month >= start_month else today.year - 1


def fy_window(db: Session, fy: int, tenant_id: Optional[int] = None) -> Tuple[datetime, datetime]:
    """[start, end) of the fiscal year as datetimes."""
    start_month = get_fy_start_month(db, tenant_id)
    start = datetime(fy, start_month, 1)
    end = datetime(fy + 1, start_month, 1)
    return start, end


def fy_label(fy: int, start_month: int) -> str:
    return f"FY {fy}" if start_month == 1 else f"FY {fy}-{str(fy + 1)[-2:]}"


def fy_month_starts(db: Session, fy: int, tenant_id: Optional[int] = None) -> List[date]:
    start, _ = fy_window(db, fy, tenant_id)
    months = []
    y, m = start.year, start.month
    for _ in range(12):
        months.append(date(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def fy_info(db: Session, fy: Optional[int] = None, tenant_id: Optional[int] = None) -> dict:
    start_month = get_fy_start_month(db, tenant_id)
    fy = fy or current_fy(db, tenant_id)
    start, end = fy_window(db, fy, tenant_id)
    return {"fy_year": fy, "label": fy_label(fy, start_month), "start_month": start_month,
            "start": start.date().isoformat(), "end": (end - timedelta(days=1)).date().isoformat(),
            "current_fy": current_fy(db, tenant_id)}

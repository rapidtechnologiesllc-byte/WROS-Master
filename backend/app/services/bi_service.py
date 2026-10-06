"""Business Intelligence Service - whitelisted table and column exploration.

Queries are built with SQLAlchemy Core from the models' own Table objects
(correct quoting and schema on PostgreSQL; the old hand-built SQL used
MySQL backticks and failed on every query). Only whitelisted tables and
columns are reachable; secrets/PII columns (passwords, bank details, OTPs)
are deliberately not whitelisted.
"""
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import logger

# Security gate: table -> columns the BI layer may read (real column names)
ALLOWED_TABLES = {
    "candidates": ["candidateID", "candidateFirstName", "candidateLastName", "candidateEmail",
                   "candidateJobTitle", "candidateSource", "candidateCurrentLocation", "candidateCreatedAt"],
    "employees": ["id", "first_name", "last_name", "email", "status", "bu_id", "current_title", "joining_date"],
    "employee_certifications": ["id", "employee_id", "certification_id", "status", "earned_date", "expires_date"],
    "certifications": ["id", "cert_name", "cert_code", "level", "is_core_certification"],
    "jobs": ["jobID", "jobTitle", "jobStatus", "jobCreatedAt", "business_unit_id", "noOfPositions"],
    "invoices": ["id", "client_id", "project_id", "total_usd_cents", "status", "created_at"],
    "opportunities": ["id", "client_id", "stage", "revenue_value_usd_cents", "probability_pct", "expected_close_date"],
    "timesheets": ["id", "employee_id", "week_starting_date", "status", "total_hours", "billable_hours"],
    "projects": ["id", "name", "client_id", "status", "start_date", "end_date"],
}
MAX_ROWS = 1000


def _table(table_name: str):
    """The model Table for a whitelisted name (raises ValueError otherwise)."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table_name}' not available for BI queries")
    import app.models  # noqa: F401  (registers every model on Base.metadata)
    from app.models.base import Base

    for table in Base.metadata.tables.values():
        if table.name == table_name:
            return table
    raise ValueError(f"Table '{table_name}' has no model")


def get_available_tables(db: Session) -> List[Dict[str, Any]]:
    """Tables available for BI queries."""
    return [
        {"table_name": name, "columns": columns, "description": f"Explore {name} data"}
        for name, columns in ALLOWED_TABLES.items()
    ]


def get_table_schema(table_name: str) -> Dict[str, Any]:
    """Whitelisted columns for one table."""
    _table(table_name)
    columns = ALLOWED_TABLES[table_name]
    return {"table_name": table_name, "columns": columns, "column_count": len(columns)}


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def query_table(
    db: Session,
    table_name: str,
    columns: List[str] = None,
    filters: Dict[str, Any] = None,
    limit: int = MAX_ROWS,
    offset: int = 0,
) -> Dict[str, Any]:
    """Read whitelisted columns of one table, equality filters only, paginated."""
    table = _table(table_name)
    allowed = ALLOWED_TABLES[table_name]

    columns = columns or allowed
    for col in columns:
        if col not in allowed:
            raise ValueError(f"Column '{col}' not available in table '{table_name}'")

    stmt = select(*[table.c[col] for col in columns])
    for col, value in (filters or {}).items():
        if col not in allowed:
            raise ValueError(f"Cannot filter on column '{col}'")
        stmt = stmt.where(table.c[col] == value)

    limit = max(1, min(limit, MAX_ROWS))
    stmt = stmt.limit(limit).offset(max(0, offset))

    try:
        result = db.execute(stmt).mappings().all()
    except Exception as e:
        logger.error(f"BI query on {table_name} failed: {e}", exc_info=True)
        raise ValueError(f"Query failed: {e}")

    return {
        "status": "success",
        "table": table_name,
        "columns_requested": columns,
        "row_count": len(result),
        "rows": [{k: _json_value(v) for k, v in row.items()} for row in result],
        "limit": limit,
        "offset": offset,
    }


def get_table_summary(db: Session, table_name: str) -> Dict[str, Any]:
    """Row count for one table."""
    table = _table(table_name)
    row_count = db.execute(select(func.count()).select_from(table)).scalar() or 0
    return {
        "status": "success",
        "table": table_name,
        "row_count": row_count,
        "columns": ALLOWED_TABLES[table_name],
        "available_for_analysis": True,
    }

"""Business Intelligence Service - Dynamic table and column exploration."""
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, MetaData
from sqlalchemy.sql.schema import Table as SQLTable
from typing import List, Dict, Any


# Whitelist of tables that can be queried via BI layer (security gate)
ALLOWED_TABLES = {
    "candidates": ["candidateID", "candidateEmail", "candidateFirstName", "pipelineStatus", "accountStatus"],
    "employees": ["id", "employee_name", "email", "status", "business_unit_id"],
    "employees_certifications": ["id", "employee_id", "certification_id", "earned_date", "status"],
    "certifications": ["id", "cert_name", "cert_code", "level", "is_core_certification"],
    "jobs": ["jobID", "jobTitle", "jobStatus", "createdAt", "business_unit_id"],
    "invoices": ["id", "client_id", "total_usd_cents", "status", "created_at", "business_unit_id"],
    "opportunities": ["id", "opportunity_name", "status", "estimated_revenue_usd_cents"],
    "timesheets": ["id", "employee_id", "week_starting", "status", "total_hours"],
    "projects": ["id", "project_name", "status", "start_date", "end_date"],
}


def get_available_tables(db: Session) -> List[Dict[str, Any]]:
    """Get list of tables available for BI queries."""
    return [
        {
            "table_name": table_name,
            "columns": columns,
            "description": f"Explore {table_name} data"
        }
        for table_name, columns in ALLOWED_TABLES.items()
    ]


def get_table_schema(table_name: str) -> Dict[str, Any]:
    """Get schema details for a specific table."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table_name}' not available for BI queries")

    columns = ALLOWED_TABLES[table_name]
    return {
        "table_name": table_name,
        "columns": columns,
        "column_count": len(columns),
    }


def query_table(
    db: Session,
    table_name: str,
    columns: List[str] = None,
    filters: Dict[str, Any] = None,
    limit: int = 1000,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Execute a dynamic BI query on allowed tables.

    Args:
        db: Database session
        table_name: Name of table to query
        columns: List of columns to select (None = all allowed columns)
        filters: Dictionary of column:value filters (equality only for security)
        limit: Max rows to return
        offset: Row offset for pagination

    Returns:
        Query results with row count and data
    """
    # Security gate: Table whitelist
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table_name}' not available for BI queries")

    allowed_columns = ALLOWED_TABLES[table_name]

    # Security gate: Column whitelist
    if columns is None:
        columns = allowed_columns
    else:
        for col in columns:
            if col not in allowed_columns:
                raise ValueError(f"Column '{col}' not available in table '{table_name}'")

    # Build dynamic query using text() for safety
    select_clause = ", ".join([f"`{table_name}`.`{col}`" for col in columns])
    query_str = f"SELECT {select_clause} FROM `{table_name}`"

    # Add filters (equality only - no injection risk)
    where_clauses = []
    params = {}
    if filters:
        for col, value in filters.items():
            if col not in allowed_columns:
                raise ValueError(f"Cannot filter on column '{col}'")
            where_clauses.append(f"`{table_name}`.`{col}` = :{col}")
            params[col] = value

    if where_clauses:
        query_str += " WHERE " + " AND ".join(where_clauses)

    # Add pagination with parameterization
    query_str += " LIMIT :limit OFFSET :offset"
    params["limit"] = min(limit, 1000)
    params["offset"] = offset

    try:
        # Execute safe parameterized query
        result = db.execute(text(query_str), params).fetchall()

        return {
            "status": "success",
            "table": table_name,
            "columns_requested": columns,
            "row_count": len(result),
            "rows": [dict(row) for row in result] if result else [],
            "limit": min(limit, 1000),
            "offset": offset,
        }
    except Exception as e:
        raise ValueError(f"Query failed: {str(e)}")


def get_table_summary(db: Session, table_name: str) -> Dict[str, Any]:
    """Get summary statistics for a table."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table '{table_name}' not available")

    try:
        # Row count
        count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
        count_result = db.execute(text(count_query)).fetchone()
        row_count = count_result[0] if count_result else 0

        return {
            "status": "success",
            "table": table_name,
            "row_count": row_count,
            "columns": ALLOWED_TABLES[table_name],
            "available_for_analysis": True,
        }
    except Exception as e:
        raise ValueError(f"Summary query failed: {str(e)}")

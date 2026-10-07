from app.core.logging import logger
"""Business Intelligence Explorer - Dynamic table and column selection."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.services.bi_service import (
    get_available_tables,
    get_table_schema,
    query_table,
    get_table_summary,
)

import logging

router = APIRouter(prefix="/bi", tags=["Business Intelligence"])

@router.get(
    "/tables",
    dependencies=[Depends(require_resource_permission("bi-explorer", "view"))]
)
def list_available_tables(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get list of tables available for BI exploration."""
    try:
        tables = get_available_tables(db)
        return {
            "status": "success",
            "data": {
                "tables": tables,
                "total_tables": len(tables),
            }
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/tables/{table_name}/schema",
    dependencies=[Depends(require_resource_permission("bi-explorer", "view"))]
)
def get_table_schema_endpoint(
    table_name: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Get schema (columns) for a specific table."""
    try:
        schema = get_table_schema(table_name)
        return {
            "status": "success",
            "data": schema
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/query/{table_name}",
    dependencies=[Depends(require_resource_permission("bi-explorer", "view"))]
)
def query_table_endpoint(
    table_name: str,
    columns: Optional[List[str]] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """GET endpoint for BI queries (simpler interface)."""
    try:
        result = query_table(
            db,
            table_name=table_name,
            columns=columns,
            filters={},
            limit=limit,
            offset=offset,
        )
        return {
            "status": "success",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

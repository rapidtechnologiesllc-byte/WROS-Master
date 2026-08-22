"""
Admin SLM Management API
=========================
Endpoints for managing, monitoring, and learning from SLM patterns
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services.admin_slm_service import AdminSLMManager

router = APIRouter(prefix="/api/v1/admin/slm", tags=["admin-slm"])


# ============================================================================
# PYDANTIC MODELS (Request/Response)
# ============================================================================


class AddPatternRequest(BaseModel):
    pattern: str
    complexity: str  # 'simple', 'moderate', 'complex'
    lookup_type: str  # 'job_list', 'candidate_status', etc.


class UpdatePatternRequest(BaseModel):
    pattern: str = None
    lookup_type: str = None
    enabled: bool = None


class BulkImportRequest(BaseModel):
    patterns: List[dict]


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/dashboard")
async def get_dashboard(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get complete dashboard data for Admin SLM view"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    return manager.get_dashboard_data()


@router.get("/patterns")
async def get_patterns(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all SLM patterns organized by complexity"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    return manager.get_all_patterns()


@router.post("/patterns")
async def add_pattern(
    request: AddPatternRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new SLM pattern"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    result = manager.add_pattern(
        pattern=request.pattern,
        complexity=request.complexity,
        lookup_type=request.lookup_type,
        added_by=current_user.email,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@router.put("/patterns/{pattern_id}")
async def update_pattern(
    pattern_id: int,
    request: UpdatePatternRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing pattern"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)

    updates = {}
    if request.pattern is not None:
        updates["pattern"] = request.pattern
    if request.lookup_type is not None:
        updates["lookup_type"] = request.lookup_type
    if request.enabled is not None:
        updates["enabled"] = request.enabled

    result = manager.update_pattern(pattern_id, updates)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.delete("/patterns/{pattern_id}")
async def delete_pattern(
    pattern_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable a pattern (soft delete)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    result = manager.delete_pattern(pattern_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.get("/analytics")
async def get_analytics(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get SLM performance analytics (last 30 days)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    return manager.get_pattern_analytics()


@router.get("/patterns/{pattern_id}/performance")
async def get_pattern_performance(
    pattern_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed performance metrics for a specific pattern"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    result = manager.get_pattern_performance(pattern_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error"))

    return result


@router.get("/history")
async def get_history(
    days: int = 30,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get SLM learning/update history"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    return manager.get_learning_history(days=days)


@router.post("/patterns/bulk-import")
async def bulk_import_patterns(
    request: BulkImportRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk import patterns from CSV or JSON"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    manager = AdminSLMManager(session)
    result = manager.bulk_import_patterns(
        patterns_list=request.patterns,
        added_by=current_user.email,
    )

    return result

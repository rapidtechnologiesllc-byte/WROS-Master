"""
Hiring Manager Validation API Endpoints
HM approval checkpoint before interview scheduling
"""
from app.models.user import Jobs

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from uuid import uuid4
import logging
from typing import Optional, List

from app.models.hiring_manager_validation import HiringManagerValidation, HMValidationStatus, HMValidationResponse
from app.models.candidate import Candidate
from app.models.demand import Demand
from app.services.hiring_manager_validation_service import HiringManagerValidationService
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from sqlalchemy.orm import Session
from fastapi import Depends
from app.schemas.hm_validation_schemas import (
    HMValidationListResponse,
    HMValidationDetailResponse,
    HMValidationResponseSubmit,
    HMValidationDecisionResponse,
    CreateValidationQuestionsRequest,
    SendValidationToHMRequest,
    SendValidationToHMResponse,
)

router = APIRouter(prefix="/hiring-manager-validations", tags=["HM Validation"])
logger = logging.getLogger(__name__)

hm_service = HiringManagerValidationService()


@router.get(
    "",
    response_model=List[HMValidationListResponse],
    dependencies=[Depends(require_resource_permission("jobs", "view"))]
)
async def list_validations(
    status: Optional[str] = Query(None),
    hiring_manager_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db), current_user: Users = Depends(get_current_internal_user)
):
    """
    List pending HM validations for dashboard.
    Filters by status (PENDING, APPROVED, REJECTED, MAYBE, EXPIRED, ESCALATED)
    and hiring manager ID.
    """
    try:
        query = db.query(HiringManagerValidation)

        # Status filter
        if status:
            try:
                status_enum = HMValidationStatus[status.upper()]
                query = query.filter(HiringManagerValidation.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Hiring manager filter
        if hiring_manager_id:
            query = query.filter(HiringManagerValidation.hiring_manager_id == hiring_manager_id)

        # Default to PENDING if no status specified
        if not status:
            query = query.filter(HiringManagerValidation.status == HMValidationStatus.PENDING)

        total = query.count()
        validations = query.order_by(HiringManagerValidation.created_at.desc()).offset(offset).limit(limit).all()

        return [HMValidationListResponse.from_orm(v) for v in validations]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error listing validations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch validations")


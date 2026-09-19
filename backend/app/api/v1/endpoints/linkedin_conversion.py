"""
LinkedIn-to-Thunder Conversion Endpoints

REST API for LinkedIn candidate import with dual-path workflow:
- Fast path: Auto-convert if email/phone available
- Slow path: Manual collection if no contact info

Both paths converge at Thunder autonomous outreach loop.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import Users
from app.services import linkedin_conversion_service
from app.services.linkedin_conversion_service import (
    convert_linkedin_to_candidate_auto,
    convert_linkedin_to_candidate_manual,
    import_pipeline_candidate_to_thunder,
    LinkedInConversionError,
    InvalidLinkedInURL,
    CandidateNotOpenToWork,
    DuplicateCandidateExists,
    ApolloCandidateNotFound,
    NoAvailableRecruitersError,
    LinkedInPipelineError,
    ApolloMCPNotConfigured,
)

router = APIRouter(prefix="/linkedin/conversion", tags=["linkedin-conversion"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LinkedInConvertAutoRequest(BaseModel):
    """Fast path: Auto-convert if email/phone available"""
    linkedin_url: str = Field(..., description="Full LinkedIn profile URL")


class LinkedInConvertAutoResponse(BaseModel):
    """Response from fast path conversion"""
    status: str = Field("SUCCESS", description="Status: SUCCESS, SKIPPED_GATE, or error")
    candidate_id: str = Field(..., description="UUID of created candidate")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    path: str = Field("fast", description="Import path")
    message: str = Field(..., description="Status message")
    slm_trace_id: str = Field(..., description="SLM trace ID for correlation")


class LinkedInConvertManualRequest(BaseModel):
    """Slow path: Assign to recruiter for manual collection"""
    linkedin_url: str = Field(..., description="Full LinkedIn profile URL")
    notes: Optional[str] = Field(None, description="Notes for recruiter")
    bu_id: Optional[str] = Field(None, description="Business Unit ID (auto-detected if not provided)")


class LinkedInConvertManualResponse(BaseModel):
    """Response from slow path conversion"""
    status: str = Field("SUCCESS", description="Status of assignment")
    task_id: Optional[int] = Field(None, description="Task ID assigned to recruiter")
    pipeline_item_id: str = Field(..., description="LinkedIn pipeline item UUID")
    assigned_recruiter: str = Field(..., description="Recruiter email/name")
    message: str = Field(..., description="Status message")


class LinkedInImportRequest(BaseModel):
    """Import pipeline item to candidate (slow path → Thunder)"""
    phone_number: Optional[str] = Field(None, description="Phone number from recruiter")
    email_from_recruiter: Optional[str] = Field(None, description="Email from LinkedIn message")


class LinkedInImportResponse(BaseModel):
    """Response from pipeline import"""
    status: str = Field("SUCCESS", description="Import status")
    candidate_id: str = Field(..., description="UUID of created candidate")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    path: str = Field("slow", description="Import path")
    message: str = Field(..., description="Status message")
    slm_trace_id: str = Field(..., description="SLM trace ID for correlation")


class LinkedInUpdatePhoneRequest(BaseModel):
    """Update pipeline item with collected phone number"""
    phone_number: str = Field(..., description="Phone number collected from recruiter")


class LinkedInUpdatePhoneResponse(BaseModel):
    """Response from phone update"""
    status: str = Field("SUCCESS", description="Update status")
    pipeline_item_id: str = Field(..., description="Pipeline item UUID")
    updated_at: str = Field(..., description="ISO timestamp of update")
    message: str = Field(..., description="Status message")


class RecruiterWorkload(BaseModel):
    """Recruiter workload metrics"""
    recruiter_id: str = Field(..., description="User ID of recruiter")
    recruiter_name: Optional[str] = Field(None, description="Recruiter name")
    candidate_count: int = Field(..., description="Number of assigned candidates")
    pipeline_count: int = Field(..., description="Number of pipeline items in progress")
    total_load: float = Field(..., description="Weighted workload (candidates + pipeline*0.5)")


class LinkedInWorkloadResponse(BaseModel):
    """Response from workload endpoint"""
    status: str = Field("SUCCESS", description="Request status")
    workloads: list = Field(..., description="List of recruiter workload metrics")
    timestamp: str = Field(..., description="ISO timestamp")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/auto", response_model=LinkedInConvertAutoResponse)
async def convert_linkedin_auto(
    request: LinkedInConvertAutoRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Fast Path: Auto-convert LinkedIn candidate if email/phone available

    - Validates LinkedIn URL
    - Calls Apollo MCP for enrichment
    - Checks "Open to Work" gate (rejects if false)
    - Detects duplicates
    - Creates Candidate record
    - Queues to Thunder for autonomous outreach

    Returns 200 on success, appropriate error code on failure.

    Errors:
    - 400: Invalid URL format
    - 403: Candidate not marked "Open to Work"
    - 404: Apollo enrichment returned no results
    - 409: Duplicate candidate already exists
    - 500: Apollo MCP not configured or unexpected error
    """
    try:
        # Call fast path conversion (returns candidate without committing)
        candidate, metadata = await convert_linkedin_to_candidate_auto(
            db,
            request.linkedin_url,
            current_user=current_user,
        )

        # Commit after successful conversion and queueing
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist candidate: {str(e)}",
            )

        return LinkedInConvertAutoResponse(
            status=metadata.get('status', 'SUCCESS'),
            candidate_id=metadata.get('candidate_id'),
            email=metadata.get('email'),
            phone=metadata.get('phone'),
            path='fast',
            message=metadata.get('message'),
            slm_trace_id=metadata.get('slm_trace_id'),
        )

    except InvalidLinkedInURL as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid LinkedIn URL: {str(e)}",
        )
    except CandidateNotOpenToWork as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Candidate not open to work: {str(e)}",
        )
    except ApolloCandidateNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Apollo enrichment failed: {str(e)}",
        )
    except DuplicateCandidateExists as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate candidate: {str(e)}",
        )
    except ApolloMCPNotConfigured as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Apollo MCP not configured: {str(e)}",
        )
    except LinkedInConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post("/manual", response_model=LinkedInConvertManualResponse)
async def convert_linkedin_manual(
    request: LinkedInConvertManualRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Slow Path: Assign LinkedIn candidate to recruiter for manual collection

    - Validates LinkedIn URL
    - Creates pipeline item (status: PENDING_CONNECTION)
    - Assigns to least-loaded recruiter (round-robin by workload)
    - Creates task for recruiter
    - Returns task and pipeline IDs

    Errors:
    - 400: Invalid URL format or duplicate
    - 500: No recruiters available
    """
    try:
        # Get BU from current user if not provided
        bu_id = request.bu_id

        # Call slow path conversion
        task, pipeline_item = await convert_linkedin_to_candidate_manual(
            db,
            request.linkedin_url,
            notes=request.notes,
            current_user=current_user,
            bu_id=bu_id,
        )

        return LinkedInConvertManualResponse(
            status="SUCCESS",
            task_id=task.id if task and hasattr(task, 'id') else None,
            pipeline_item_id=str(pipeline_item.id),
            assigned_recruiter=pipeline_item.assigned_to_user_id or "Unknown",
            message="Candidate assigned to recruiter for manual collection",
        )

    except InvalidLinkedInURL as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid LinkedIn URL: {str(e)}",
        )
    except DuplicateCandidateExists as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate candidate: {str(e)}",
        )
    except NoAvailableRecruitersError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No recruiters available: {str(e)}",
        )
    except LinkedInPipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LinkedInConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.post("/{pipeline_item_id}/import", response_model=LinkedInImportResponse)
async def import_pipeline_to_candidate(
    pipeline_item_id: str,
    request: LinkedInImportRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Import Pipeline Item → Candidate → Thunder Queue

    Transitions slow path pipeline item to candidate after recruiter collects contact info.

    - Validates pipeline item exists
    - Uses provided phone or stored value
    - Detects any duplicates created since pipeline assignment
    - Creates Candidate record
    - Marks task as COMPLETED
    - Queues to Thunder for autonomous outreach

    Errors:
    - 404: Pipeline item not found
    - 400: Missing contact information or invalid state
    """
    try:
        candidate, metadata = await import_pipeline_candidate_to_thunder(
            db,
            pipeline_item_id,
            phone_number=request.phone_number,
            email_from_recruiter=request.email_from_recruiter,
            current_user=current_user,
        )

        return LinkedInImportResponse(
            status=metadata.get('status', 'SUCCESS'),
            candidate_id=metadata.get('candidate_id'),
            email=metadata.get('email'),
            phone=metadata.get('phone'),
            path='slow',
            message=metadata.get('message'),
            slm_trace_id=metadata.get('slm_trace_id'),
        )

    except LinkedInPipelineError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except LinkedInConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.patch("/{pipeline_item_id}/phone", response_model=LinkedInUpdatePhoneResponse)
async def update_pipeline_phone(
    pipeline_item_id: str,
    request: LinkedInUpdatePhoneRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Update pipeline item with phone collected by recruiter

    - Updates phone_number field
    - Sets status to PHONE_COLLECTED
    - Updates timestamp

    Used by recruiter when collecting phone before importing to candidate.
    """
    try:
        from app.models.linkedin_candidate_pipeline import (
            LinkedInCandidatePipeline,
            LinkedInPipelineStatus,
        )

        pipeline = db.query(LinkedInCandidatePipeline).filter(
            LinkedInCandidatePipeline.id == pipeline_item_id
        ).first()

        if not pipeline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline item not found: {pipeline_item_id}",
            )

        # Update phone and status
        pipeline.phone_number = request.phone_number
        pipeline.status = LinkedInPipelineStatus.PHONE_COLLECTED

        db.commit()

        return LinkedInUpdatePhoneResponse(
            status="SUCCESS",
            pipeline_item_id=str(pipeline_item_id),
            updated_at=pipeline.updated_at.isoformat(),
            message=f"Phone updated for pipeline item {pipeline_item_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update phone: {str(e)}",
        )


@router.get("/workload", response_model=LinkedInWorkloadResponse)
async def get_recruiter_workload(
    bu_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
):
    """
    Get recruiter workload metrics

    Shows candidate count, pipeline count, and weighted total load for all recruiters.
    Used for monitoring round-robin assignment distribution.

    Query Parameters:
    - bu_id: Optional Business Unit ID to filter by

    Returns list of recruiters sorted by total_load ascending (least loaded first).
    """
    try:
        from app.services import linkedin_recruiter_workload_service
        from datetime import datetime

        workloads = linkedin_recruiter_workload_service.get_all_recruiter_workloads(
            db, bu_id=bu_id
        )

        workload_dicts = [
            RecruiterWorkload(
                recruiter_id=recruiter_id,
                recruiter_name=recruiter_id,  # Would fetch actual name from Users if needed
                candidate_count=candidate_count,
                pipeline_count=pipeline_count,
                total_load=total_load,
            ).dict()
            for recruiter_id, candidate_count, pipeline_count, total_load in workloads
        ]

        return LinkedInWorkloadResponse(
            status="SUCCESS",
            workloads=workload_dicts,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workload metrics: {str(e)}",
        )

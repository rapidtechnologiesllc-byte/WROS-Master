"""
Onboarding Orchestrator - Coordinates multi-step hiring workflows.

This module serves as the orchestration layer that coordinates
workflows across multiple microservices:
- candidates/crud.py (candidate CRUD)
- candidates/conversions.py (candidate workflows)
- interviews/* (interview orchestration)
- offers/* (offer orchestration)
- employees/* (employee management)

CRUD operations are delegated to specialized microservices.
Onboarding.py focuses only on workflow coordination.

For backward compatibility with legacy routes:
- /onboarding/hr/create_candidate → delegates to /candidates/create
- /onboarding/hr/get_all_candidates → delegates to /candidates/all
- /onboarding/hr/candidate/{id} → delegates to /candidates/{id}
- /onboarding/candidates/{id}/convert-to-employee → delegates to conversion service
- /onboarding/hr/candidate/{id}/contacts → delegates to contacts service
"""

from fastapi import APIRouter, Depends, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_resource_permission, get_current_hr_or_admin

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# Legacy backward-compatibility routes - delegate to new microservices
@router.post(
    "/hr/create_candidate",
    summary="DEPRECATED: Use POST /candidates/create instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
def create_candidate_legacy(
    request_body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use POST /candidates/create instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.crud import create_candidate
    from app.schemas.candidate import CandidateCreateRequest

    request = CandidateCreateRequest(**request_body)
    return create_candidate(request=request, background_tasks=None, db=db, user=user)


@router.get(
    "/hr/get_all_candidates",
    summary="DEPRECATED: Use GET /candidates/all instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_all_candidates_legacy(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/all instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.crud import get_all_candidates
    return get_all_candidates(db=db, user=user)


@router.get(
    "/hr/candidate/{candidate_id}",
    summary="DEPRECATED: Use GET /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_candidate_by_id_legacy(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.crud import get_candidate_by_id
    return get_candidate_by_id(candidate_id=candidate_id, db=db, user=user)


@router.put(
    "/hr/update_candidate/{candidate_id}",
    summary="DEPRECATED: Use PUT /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
def update_candidate_legacy(
    candidate_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use PUT /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.crud import update_candidate
    from app.schemas.candidate import CandidateUpdateRequest

    request = CandidateUpdateRequest(**request_body)
    return update_candidate(candidate_id=candidate_id, request=request, db=db, user=user)


@router.delete(
    "/hr/delete_candidate/{candidate_id}",
    summary="DEPRECATED: Use DELETE /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "delete"))],
)
def delete_candidate_legacy(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use DELETE /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.crud import delete_candidate
    return delete_candidate(candidate_id=candidate_id, db=db, user=user)


@router.post(
    "/candidates/{candidate_id}/convert-to-employee",
    summary="DEPRECATED: Use POST /candidates/{candidate_id}/convert-to-employee instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
def convert_candidate_legacy(
    candidate_id: str,
    request_body: dict = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use POST /candidates/{candidate_id}/convert-to-employee instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.conversions import convert_candidate_to_employee
    from app.schemas.candidate import ConvertToEmployeeRequest

    request = ConvertToEmployeeRequest(**request_body)
    return convert_candidate_to_employee(candidate_id=candidate_id, request=request, db=db, user=user)


@router.get(
    "/hr/candidate/{candidate_id}/contacts",
    summary="DEPRECATED: Use GET /candidates/{candidate_id}/contacts instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_candidate_contacts_legacy(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin)
):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/{candidate_id}/contacts instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    from app.api.v1.endpoints.candidates.conversions import get_candidate_contacts
    return get_candidate_contacts(candidate_id=candidate_id, db=db, user=user)


# Orchestration workflows (to be implemented)
# These will coordinate multi-step processes across microservices:
# - Hire complete: candidate → interview → offer → hire → onboard
# - Rehire: employee → candidate → hire → onboard
# - Hiring pipeline status: aggregate status from all stages

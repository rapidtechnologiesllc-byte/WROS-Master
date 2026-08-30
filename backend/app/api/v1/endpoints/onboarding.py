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

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from app.core.dependencies import require_resource_permission

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# Legacy backward-compatibility routes - redirect to new microservices
@router.api_route(
    "/hr/create_candidate",
    methods=["POST"],
    summary="DEPRECATED: Use POST /candidates/create instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "create"))],
)
def create_candidate_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use POST /candidates/create instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    return RedirectResponse(url="/candidates/create", status_code=307)


@router.api_route(
    "/hr/get_all_candidates",
    methods=["GET"],
    summary="DEPRECATED: Use GET /candidates/all instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_all_candidates_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/all instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    return RedirectResponse(url="/candidates/all", status_code=307)


@router.api_route(
    "/hr/candidate/{candidate_id}",
    methods=["GET"],
    summary="DEPRECATED: Use GET /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_candidate_by_id_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    candidate_id = kwargs.get("candidate_id")
    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=307)


@router.api_route(
    "/hr/update_candidate/{candidate_id}",
    methods=["PUT"],
    summary="DEPRECATED: Use PUT /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
def update_candidate_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use PUT /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    candidate_id = kwargs.get("candidate_id")
    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=307)


@router.api_route(
    "/hr/delete_candidate/{candidate_id}",
    methods=["DELETE"],
    summary="DEPRECATED: Use DELETE /candidates/{candidate_id} instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "delete"))],
)
def delete_candidate_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use DELETE /candidates/{candidate_id} instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    candidate_id = kwargs.get("candidate_id")
    return RedirectResponse(url=f"/candidates/{candidate_id}", status_code=307)


@router.api_route(
    "/candidates/{candidate_id}/convert-to-employee",
    methods=["POST"],
    summary="DEPRECATED: Use POST /candidates/{candidate_id}/convert-to-employee instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
)
def convert_candidate_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use POST /candidates/{candidate_id}/convert-to-employee instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    candidate_id = kwargs.get("candidate_id")
    return RedirectResponse(url=f"/candidates/{candidate_id}/convert-to-employee", status_code=307)


@router.api_route(
    "/hr/candidate/{candidate_id}/contacts",
    methods=["GET"],
    summary="DEPRECATED: Use GET /candidates/{candidate_id}/contacts instead",
    deprecated=True,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
)
def get_candidate_contacts_legacy(**kwargs):
    """
    DEPRECATED: This endpoint has been moved to the candidates microservice.
    Please use GET /candidates/{candidate_id}/contacts instead.

    This redirect is provided for backward compatibility only.
    It will be removed in a future version.
    """
    candidate_id = kwargs.get("candidate_id")
    return RedirectResponse(url=f"/candidates/{candidate_id}/contacts", status_code=307)


# Orchestration workflows (to be implemented)
# These will coordinate multi-step processes across microservices:
# - Hire complete: candidate → interview → offer → hire → onboard
# - Rehire: employee → candidate → hire → onboard
# - Hiring pipeline status: aggregate status from all stages

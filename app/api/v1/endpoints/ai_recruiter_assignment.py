"""
S-011/HRMS-0411 -- AI Recruiter Assignment Engine
====================================================
Tag: ai-recruiter-assignment

Routes:
  GET   /candidates/{candidate_id}/ai-assignment
      Any internal user -- current active Thunder assignment for a candidate.

  GET   /admin/tenant/ai-config
  PATCH /admin/tenant/ai-config
      Super User only (tenant.ai_config permission) -- Thunder's
      configurable name/persona for the caller's own org. "Tenant" in
      this subsystem is the org-owner Users row (see
      app.services.ai_conversation_service.resolve_thunder_config's
      docstring on this codebase's real tenant_id semantics), so this
      reads/writes the caller's own Users row.

  GET   /admin/tenant/thunder-enabled
  PATCH /admin/tenant/thunder-enabled
      Super User only (tenant.ai_config permission) -- S-075/HRMS-0475
      global Thunder kill switch for the caller's own org, same
      "caller's own Users row is the tenant" semantics as ai-config above.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_permission
from app.models.user import Users
from app.schemas.ai_recruiter_assignment import (
    AIAssignmentResponse,
    TenantAIConfigResponse,
    TenantAIConfigUpdateRequest,
    TenantThunderEnabledResponse,
    TenantThunderEnabledUpdateRequest,
)
from app.services.ai_conversation_service import (
    DEFAULT_THUNDER_DISPLAY_NAME,
    DEFAULT_THUNDER_PERSONA_TEXT,
    get_active_ai_assignment,
    resolve_thunder_config,
)

router = APIRouter(tags=["ai-recruiter-assignment"])


@router.get(
    "/candidates/{candidate_id}/ai-assignment",
    response_model=AIAssignmentResponse,
    summary="Get a candidate's current active Thunder assignment",
)
def get_candidate_ai_assignment(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    # A candidate has exactly one org owner (their assignment's own
    # tenant_id) -- look up their active assignment directly rather
    # than requiring the caller to already know which tenant owns them.
    from app.models.candidate_ai import CandidateAIAssignment
    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate_id, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail=f"No active AI assignment found for candidate '{candidate_id}'.")

    return AIAssignmentResponse(
        ai_agent_name=assignment.ai_agent_name or DEFAULT_THUNDER_DISPLAY_NAME,
        ai_agent_persona=assignment.ai_agent_persona,
        assigned_at=assignment.assigned_at,
        is_active=assignment.is_active,
    )


@router.get(
    "/admin/tenant/ai-config",
    response_model=TenantAIConfigResponse,
    summary="Get this org's Thunder name/persona config — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
)
def get_tenant_ai_config(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    config = resolve_thunder_config(db, current_user.UserID)
    return TenantAIConfigResponse(ai_agent_name=config["name"], ai_agent_persona=config["persona"])


@router.patch(
    "/admin/tenant/ai-config",
    response_model=TenantAIConfigResponse,
    summary="Update this org's Thunder name/persona — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
    description=(
        "BR-03: persona changes affect every future Thunder prompt for this "
        "org's candidates. Lead BA written sign-off is a process control outside "
        "this API, not something this endpoint enforces mechanically."
    ),
)
def update_tenant_ai_config(
    body: TenantAIConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    current_user.ai_agent_name = body.ai_agent_name.strip() or DEFAULT_THUNDER_DISPLAY_NAME
    current_user.ai_agent_persona = body.ai_agent_persona.strip() or DEFAULT_THUNDER_PERSONA_TEXT
    db.add(current_user)
    db.commit()

    return TenantAIConfigResponse(ai_agent_name=current_user.ai_agent_name, ai_agent_persona=current_user.ai_agent_persona)


@router.get(
    "/admin/tenant/thunder-enabled",
    response_model=TenantThunderEnabledResponse,
    summary="Get this org's Thunder global kill switch — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
    description=(
        "S-075/HRMS-0475 BR-03 -- global pause takes precedence over "
        "every individual conversation's own pause flag. Same "
        "'tenant is the caller's own Users row' semantics as "
        "GET/PATCH /admin/tenant/ai-config above."
    ),
)
def get_tenant_thunder_enabled(
    current_user: Users = Depends(get_current_hr_or_admin),
):
    return TenantThunderEnabledResponse(thunder_enabled=current_user.thunder_enabled)


@router.patch(
    "/admin/tenant/thunder-enabled",
    response_model=TenantThunderEnabledResponse,
    summary="Set this org's Thunder global kill switch — Super User only",
    dependencies=[Depends(require_permission("tenant.ai_config"))],
    description="S-075/HRMS-0475 Step 2 -- disabling this halts every automated Thunder send across the whole org.",
)
def update_tenant_thunder_enabled(
    body: TenantThunderEnabledUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_hr_or_admin),
):
    current_user.thunder_enabled = body.enabled
    db.add(current_user)
    db.commit()
    return TenantThunderEnabledResponse(thunder_enabled=current_user.thunder_enabled)

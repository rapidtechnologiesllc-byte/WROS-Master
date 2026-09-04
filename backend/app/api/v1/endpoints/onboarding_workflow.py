"""
import logging
S-324/HRMS-ONBOARDING-WORKFLOW -- REST API Endpoints.

Provides REST endpoints for onboarding workflow operations:
- POST /onboarding-workflow/start
- POST /onboarding-workflow/assign-buddy
- POST /onboarding-workflow/send-welcome-kit
- POST /onboarding-workflow/schedule-training
- GET /onboarding-workflow/{workflow_id}
- GET /onboarding-workflow/employee/{employee_id}
"""
import logging
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import json

import app.schemas as schema
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.core.tenant_context import get_current_tenant_id

from app.models.onboarding_workflow import (
    OnboardingWorkflow,
    OnboardingBuddy,
    WelcomeKit,
    TrainingSession,
    OnboardingTask,
)
from app.services.onboarding_workflow_service import (
    start_onboarding,
    assign_buddy,
    send_welcome_kit,
    schedule_training,
)

router = APIRouter(prefix="/onboarding-workflow", tags=["onboarding-workflow"])

# ============================================================================
# SCHEMAS
# ============================================================================
logger = logging.getLogger(__name__)

class StartOnboardingRequest(schema.BaseModel):
    employee_id: str
    candidate_id: Optional[str] = None
    reporting_manager_id: Optional[str] = None
    expected_completion_days: int = 30

class AssignBuddyRequest(schema.BaseModel):
    workflow_id: int
    buddy_user_id: str
    activation_date: Optional[date] = None
    notes: Optional[str] = None

class SendWelcomeKitRequest(schema.BaseModel):
    workflow_id: int
    kit_type: str  # EMAIL, PHYSICAL, DIGITAL, HYBRID
    kit_name: str
    kit_contents: Optional[List[str]] = None
    sent_by_user_id: Optional[str] = None
    delivery_channel: str = "EMAIL"  # EMAIL, PHYSICAL_MAIL, SMS, IN_PERSON

class ScheduleTrainingRequest(schema.BaseModel):
    workflow_id: int
    training_name: str
    scheduled_date: date
    scheduled_time: str  # HH:MM format
    trainer_user_id: Optional[str] = None
    delivery_mode: str = "IN_PERSON"  # IN_PERSON, VIRTUAL, HYBRID, SELF_PACED
    meeting_link: Optional[str] = None
    duration_minutes: int = 60
    training_description: Optional[str] = None
    is_mandatory: bool = True

class OnboardingWorkflowResponse(schema.BaseModel):
    workflow_id: int
    employee_id: str
    status: str
    joining_date: date
    expected_completion_date: Optional[date]
    total_tasks: int
    completed_tasks: int
    progress_percentage: int

    class Config:
        from_attributes = True

class OnboardingBuddyResponse(schema.BaseModel):
    buddy_id: int
    buddy_user_id: str
    status: str
    activation_date: Optional[date]
    check_ins_completed: int

    class Config:
        from_attributes = True

class WelcomeKitResponse(schema.BaseModel):
    kit_id: int
    kit_type: str
    kit_name: str
    delivery_status: str
    sent_date: Optional[datetime]

    class Config:
        from_attributes = True

class TrainingSessionResponse(schema.BaseModel):
    session_id: int
    training_name: str
    scheduled_date: date
    scheduled_time: str
    delivery_mode: str
    status: str
    attendance_status: Optional[str]

    class Config:
        from_attributes = True

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/start",
    dependencies=[Depends(require_resource_permission("onboarding", "edit"))],
    summary="Start onboarding workflow for new employee"
)
def start_onboarding_endpoint(
    request: StartOnboardingRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Initiates onboarding workflow for a new employee.

    Prerequisites:
    - Employee record must exist
    - No existing workflow for this employee

    Creates default onboarding tasks and tracks progress.
    """
    try:
        tenant_id = get_current_tenant_id()
        result = start_onboarding(
            db,
            calling_context_tenant_id=tenant_id,
            employee_id=request.employee_id,
            candidate_id=request.candidate_id,
            reporting_manager_id=request.reporting_manager_id,
            expected_completion_days=request.expected_completion_days,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] start failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to start onboarding: {str(exc)}")

@router.post(
    "/assign-buddy",
    dependencies=[Depends(require_resource_permission("onboarding", "edit"))],
    summary="Assign buddy to new employee"
)
def assign_buddy_endpoint(
    request: AssignBuddyRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Assigns a buddy to guide new employee through onboarding.

    Buddy becomes the primary point of contact for the first 30 days.
    Sends notifications to both buddy and employee.
    """
    try:
        tenant_id = get_current_tenant_id()
        result = assign_buddy(
            db,
            calling_context_tenant_id=tenant_id,
            workflow_id=request.workflow_id,
            buddy_user_id=request.buddy_user_id,
            activation_date=request.activation_date,
            notes=request.notes,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] assign_buddy failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to assign buddy: {str(exc)}")

@router.post(
    "/send-welcome-kit",
    dependencies=[Depends(require_resource_permission("onboarding", "edit"))],
    summary="Send welcome kit to new employee"
)
def send_welcome_kit_endpoint(
    request: SendWelcomeKitRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Dispatches welcome kit/materials to new employee.

    Supports multiple delivery channels:
    - EMAIL: Digital welcome package
    - PHYSICAL_MAIL: Printed materials
    - SMS: Quick welcome message
    - IN_PERSON: Hand-delivered at office

    Tracks delivery status and acknowledgement.
    """
    try:
        tenant_id = get_current_tenant_id()
        result = send_welcome_kit(
            db,
            calling_context_tenant_id=tenant_id,
            workflow_id=request.workflow_id,
            kit_type=request.kit_type,
            kit_name=request.kit_name,
            kit_contents=request.kit_contents,
            sent_by_user_id=request.sent_by_user_id or user.UserID,
            delivery_channel=request.delivery_channel,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] send_welcome_kit failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to send welcome kit: {str(exc)}")

@router.post(
    "/schedule-training",
    dependencies=[Depends(require_resource_permission("onboarding", "edit"))],
    summary="Schedule training session for new employee"
)
def schedule_training_endpoint(
    request: ScheduleTrainingRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Schedules a training session for new employee onboarding.

    Supports multiple delivery modes:
    - IN_PERSON: On-site training
    - VIRTUAL: Online via Zoom/Teams
    - HYBRID: Both in-person and virtual
    - SELF_PACED: Asynchronous learning

    Creates calendar invite and tracking task.
    """
    try:
        tenant_id = get_current_tenant_id()
        result = schedule_training(
            db,
            calling_context_tenant_id=tenant_id,
            workflow_id=request.workflow_id,
            training_name=request.training_name,
            scheduled_date=request.scheduled_date,
            scheduled_time=request.scheduled_time,
            trainer_user_id=request.trainer_user_id,
            delivery_mode=request.delivery_mode,
            meeting_link=request.meeting_link,
            duration_minutes=request.duration_minutes,
            training_description=request.training_description,
            is_mandatory=request.is_mandatory,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] schedule_training failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule training: {str(exc)}")

@router.get(
    "/{workflow_id}",
    response_model=OnboardingWorkflowResponse,
    dependencies=[Depends(require_resource_permission("onboarding", "view"))],
    summary="Get onboarding workflow details"
)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> OnboardingWorkflow:
    """
    Returns full onboarding workflow including:
    - Workflow status and timeline
    - Task progress
    - Buddy assignment
    - Welcome kits
    - Training sessions
    """
    try:
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        return workflow

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] get_workflow failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow: {str(exc)}")

@router.get(
    "/employee/{employee_id}",
    dependencies=[Depends(require_resource_permission("onboarding", "view"))],
    summary="Get onboarding workflow by employee ID"
)
def get_workflow_by_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Returns onboarding workflow for specific employee including all related data:
    - Workflow status
    - Task list and progress
    - Buddy details
    - Welcome kits sent
    - Scheduled training sessions
    """
    try:
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.employee_id == employee_id
        ).first()

        if not workflow:
            raise HTTPException(status_code=404, detail=f"No onboarding workflow for employee {employee_id}")

        # Fetch related data
        buddy = db.query(OnboardingBuddy).filter(
            OnboardingBuddy.workflow_id == workflow.id
        ).first()

        tasks = db.query(OnboardingTask).filter(
            OnboardingTask.workflow_id == workflow.id
        ).all()

        welcome_kits = db.query(WelcomeKit).filter(
            WelcomeKit.workflow_id == workflow.id
        ).all()

        training_sessions = db.query(TrainingSession).filter(
            TrainingSession.workflow_id == workflow.id
        ).all()

        return {
            "workflow": {
                "workflow_id": workflow.id,
                "employee_id": workflow.employee_id,
                "status": workflow.status,
                "joining_date": workflow.joining_date,
                "expected_completion_date": workflow.expected_completion_date,
                "total_tasks": workflow.total_tasks,
                "completed_tasks": workflow.completed_tasks,
                "progress_percentage": workflow.progress_percentage,
            },
            "buddy": {
                "buddy_id": buddy.id,
                "buddy_user_id": buddy.buddy_user_id,
                "status": buddy.status,
                "activation_date": buddy.activation_date,
            } if buddy else None,
            "tasks": [
                {
                    "task_id": t.id,
                    "task_name": t.task_name,
                    "status": t.status,
                    "due_date": t.due_date,
                    "completed_date": t.completed_date,
                } for t in tasks
            ],
            "welcome_kits": [
                {
                    "kit_id": k.id,
                    "kit_type": k.kit_type,
                    "kit_name": k.kit_name,
                    "delivery_status": k.delivery_status,
                } for k in welcome_kits
            ],
            "training_sessions": [
                {
                    "session_id": s.id,
                    "training_name": s.training_name,
                    "scheduled_date": s.scheduled_date,
                    "status": s.status,
                } for s in training_sessions
            ],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] get_workflow_by_employee failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflow: {str(exc)}")

@router.get(
    "/{workflow_id}/tasks",
    dependencies=[Depends(require_resource_permission("onboarding", "view"))],
    summary="Get all onboarding tasks for workflow"
)
def get_workflow_tasks(
    workflow_id: int,
    status: Optional[str] = Query(None, description="Filter by status (PENDING, IN_PROGRESS, COMPLETED, etc.)"),
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Returns all onboarding tasks for a workflow with optional status filter.
    """
    try:
        query = db.query(OnboardingTask).filter(OnboardingTask.workflow_id == workflow_id)

        if status:
            query = query.filter(OnboardingTask.status == status)

        tasks = query.all()

        return {
            "workflow_id": workflow_id,
            "total_tasks": len(tasks),
            "tasks": [
                {
                    "task_id": t.id,
                    "task_type": t.task_type,
                    "task_name": t.task_name,
                    "status": t.status,
                    "due_date": t.due_date,
                    "assigned_to_user_id": t.assigned_to_user_id,
                    "completed_date": t.completed_date,
                    "is_mandatory": t.is_mandatory,
                } for t in tasks
            ],
        }

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] get_workflow_tasks failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve tasks: {str(exc)}")

@router.get(
    "/{workflow_id}/training",
    dependencies=[Depends(require_resource_permission("onboarding", "view"))],
    summary="Get all training sessions for workflow"
)
def get_workflow_training_sessions(
    workflow_id: int,
    status: Optional[str] = Query(None, description="Filter by status (SCHEDULED, IN_PROGRESS, COMPLETED, etc.)"),
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
) -> dict:
    """
    Returns all training sessions scheduled for an onboarding workflow.
    """
    try:
        query = db.query(TrainingSession).filter(TrainingSession.workflow_id == workflow_id)

        if status:
            query = query.filter(TrainingSession.status == status)

        sessions = query.order_by(TrainingSession.scheduled_date).all()

        return {
            "workflow_id": workflow_id,
            "total_sessions": len(sessions),
            "training_sessions": [
                {
                    "session_id": s.id,
                    "training_name": s.training_name,
                    "scheduled_date": s.scheduled_date,
                    "scheduled_time": s.scheduled_time,
                    "delivery_mode": s.delivery_mode,
                    "status": s.status,
                    "trainer_name": s.trainer_name,
                    "duration_minutes": s.duration_minutes,
                } for s in sessions
            ],
        }

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow API] get_workflow_training_sessions failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve training sessions: {str(exc)}")

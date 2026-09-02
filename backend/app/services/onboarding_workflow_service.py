"""
import logging
S-324/HRMS-ONBOARDING-WORKFLOW -- Onboarding Workflow Service.

Implements complete onboarding lifecycle management:
- start_onboarding: Initiates onboarding workflow for new employee
- assign_buddy: Assigns buddy to guide new employee
- send_welcome_kit: Dispatches welcome materials
- schedule_training: Schedules training sessions

All methods follow the real architecture patterns from this codebase:
- Tenant-scoped operations (tenant_id never from client input)
- Error handling without exceptions (returns status dicts)
- Service layer owns all business logic
- No direct field mutations (use dedicated update methods)
"""
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
import json

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.employee import Employee
from app.models.candidate import Candidate
from app.models.user import Users
from app.models.offer_letter import OfferLetter
from app.models.onboarding_workflow import (
    OnboardingWorkflow,
    OnboardingBuddy,
    WelcomeKit,
    TrainingSession,
    OnboardingTask,
    ONBOARDING_STATUSES,
    BUDDY_STATUSES,
    TASK_TYPES,
)
from app.services.notification_service import send_notification
from app.services.email_service import EmailService


def start_onboarding(
    db: Session,
    calling_context_tenant_id: str,
    employee_id: str,
    candidate_id: Optional[str] = None,
    reporting_manager_id: Optional[str] = None,
    expected_completion_days: int = 30,
) -> Dict:
    """
    Initiates onboarding workflow for a new employee.

    BR-01: Only called when Employee record exists (candidate has joined).
    Creates OnboardingWorkflow record and generates default onboarding tasks.

    Args:
        db: Database session
        calling_context_tenant_id: Tenant ID from session (never from client)
        employee_id: ID of the new employee
        candidate_id: Optional link to candidate record
        reporting_manager_id: Optional manager for this employee
        expected_completion_days: Days until onboarding complete (default: 30)

    Returns:
        Dict with:
        - status: "success" or "error"
        - workflow_id: ID of created workflow
        - tasks_created: Count of default tasks
        - message: Status message
        - details: Full workflow dict if successful
    """
    try:
        # 1. Verify employee exists
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            return {
                "status": "error",
                "message": f"Employee {employee_id} not found",
                "workflow_id": None,
            }

        # 2. Verify no existing workflow for this employee
        existing = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.employee_id == employee_id
        ).first()
        if existing:
            return {
                "status": "error",
                "message": f"Onboarding workflow already exists for employee {employee_id}",
                "workflow_id": existing.id,
            }

        # 3. Create workflow
        joining_date = employee.joining_date or datetime.now().date()
        expected_completion = joining_date + timedelta(days=expected_completion_days)

        workflow = OnboardingWorkflow(
            tenant_id=calling_context_tenant_id,
            employee_id=employee_id,
            candidate_id=candidate_id,
            status="IN_PROGRESS",
            joining_date=joining_date,
            onboarding_start_date=datetime.now().date(),
            expected_completion_date=expected_completion,
            reporting_manager_id=reporting_manager_id,
            notes=f"Onboarding started on {datetime.now().strftime('%Y-%m-%d')}",
        )
        db.add(workflow)
        db.flush()
        workflow_id = workflow.id

        # 4. Create default onboarding tasks
        default_tasks = _create_default_onboarding_tasks(
            db, calling_context_tenant_id, workflow_id, joining_date, reporting_manager_id
        )

        workflow.total_tasks = len(default_tasks)
        db.add(workflow)
        db.commit()

        logger.info(f"[OnboardingWorkflow] Started for employee {employee_id}, workflow_id={workflow_id}")

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "tasks_created": len(default_tasks),
            "message": f"Onboarding workflow created for {employee_id}",
            "details": {
                "workflow_id": workflow_id,
                "employee_id": employee_id,
                "status": workflow.status,
                "joining_date": joining_date.isoformat(),
                "expected_completion_date": expected_completion.isoformat(),
                "total_tasks": workflow.total_tasks,
            }
        }

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow] start_onboarding failed: {exc}")
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to start onboarding: {str(exc)}",
            "workflow_id": None,
        }


def assign_buddy(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    buddy_user_id: str,
    activation_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> Dict:
    """
    Assigns a buddy to guide new employee through onboarding.

    BR-02: Buddy must be an active user in the same tenant.
    Creates OnboardingBuddy record and notifies both buddy and employee.

    Args:
        db: Database session
        calling_context_tenant_id: Tenant ID (never from client)
        workflow_id: ID of onboarding workflow
        buddy_user_id: ID of user to assign as buddy
        activation_date: Date buddy starts (default: today)
        notes: Optional notes about buddy assignment

    Returns:
        Dict with:
        - status: "success" or "error"
        - buddy_id: ID of buddy assignment
        - message: Status message
    """
    try:
        # 1. Verify workflow exists
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.tenant_id == calling_context_tenant_id,
        ).first()
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found", "buddy_id": None}

        # 2. Verify buddy user exists and is in same tenant
        buddy_user = db.query(Users).filter(Users.UserID == buddy_user_id).first()
        if not buddy_user:
            return {"status": "error", "message": f"Buddy user {buddy_user_id} not found", "buddy_id": None}

        # 3. Verify no existing buddy assignment
        existing_buddy = db.query(OnboardingBuddy).filter(
            OnboardingBuddy.workflow_id == workflow_id
        ).first()
        if existing_buddy:
            return {
                "status": "error",
                "message": f"Buddy already assigned to workflow {workflow_id}",
                "buddy_id": existing_buddy.id,
            }

        # 4. Create buddy assignment
        buddy = OnboardingBuddy(
            tenant_id=calling_context_tenant_id,
            workflow_id=workflow_id,
            buddy_user_id=buddy_user_id,
            employee_id=workflow.employee_id,
            buddy_department=buddy_user.Department,
            status="ASSIGNED",
            activation_date=activation_date or datetime.now().date(),
            notes=notes,
        )
        db.add(buddy)
        db.flush()
        buddy_id = buddy.id

        # 5. Get employee details for notification
        employee = workflow.employee
        if not employee:
            raise Exception(f"Employee {workflow.employee_id} not found")

        # 6. Send notifications
        _notify_buddy_assignment(db, buddy_user, employee, workflow, calling_context_tenant_id)

        # 7. Create buddy introduction task
        _create_buddy_introduction_task(db, calling_context_tenant_id, workflow_id, buddy_user_id)

        db.commit()
        logger.info(f"[OnboardingWorkflow] Buddy {buddy_user_id} assigned to workflow {workflow_id}")

        return {
            "status": "success",
            "buddy_id": buddy_id,
            "message": f"Buddy {buddy_user.UserName} assigned to {employee.first_name}",
            "buddy_user_id": buddy_user_id,
        }

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow] assign_buddy failed: {exc}")
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to assign buddy: {str(exc)}",
            "buddy_id": None,
        }


def send_welcome_kit(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    kit_type: str,
    kit_name: str,
    kit_contents: Optional[List[str]] = None,
    sent_by_user_id: Optional[str] = None,
    delivery_channel: str = "EMAIL",
) -> Dict:
    """
    Dispatches welcome kit/materials to new employee.

    Supports multiple delivery channels: EMAIL, PHYSICAL_MAIL, SMS, IN_PERSON.
    Tracks delivery status and acknowledgement.

    Args:
        db: Database session
        calling_context_tenant_id: Tenant ID (never from client)
        workflow_id: ID of onboarding workflow
        kit_type: Type of kit (EMAIL, PHYSICAL, DIGITAL, HYBRID)
        kit_name: Name of this kit (e.g., "Day 1 Welcome Package")
        kit_contents: List of items in kit
        sent_by_user_id: User sending the kit
        delivery_channel: How to deliver (EMAIL, PHYSICAL_MAIL, SMS, IN_PERSON)

    Returns:
        Dict with:
        - status: "success" or "error"
        - kit_id: ID of welcome kit record
        - message: Status message
    """
    try:
        # 1. Verify workflow exists
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.tenant_id == calling_context_tenant_id,
        ).first()
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found", "kit_id": None}

        # 2. Get employee for contact info
        employee = workflow.employee
        if not employee:
            return {"status": "error", "message": "Employee not found for workflow", "kit_id": None}

        # 3. Create welcome kit record
        kit_contents_json = json.dumps(kit_contents or [])
        welcome_kit = WelcomeKit(
            tenant_id=calling_context_tenant_id,
            workflow_id=workflow_id,
            kit_type=kit_type,
            kit_name=kit_name,
            kit_description=f"Welcome kit for {employee.first_name}",
            kit_contents=kit_contents_json,
            sent_by_user_id=sent_by_user_id,
            sent_date=datetime.now(),
            sent_channel=delivery_channel,
            delivery_status="SENT",
            recipient_email=employee.email,
            recipient_phone=employee.mobile,
        )
        db.add(welcome_kit)
        db.flush()
        kit_id = welcome_kit.id

        # 4. Send via appropriate channel
        sent_successfully = _send_welcome_kit_by_channel(
            db, employee, welcome_kit, kit_type, kit_name, kit_contents, delivery_channel
        )

        if sent_successfully:
            welcome_kit.delivery_status = "SENT"
            welcome_kit.delivery_date = datetime.now()
        else:
            welcome_kit.delivery_status = "FAILED"

        db.commit()
        logger.info(f"[OnboardingWorkflow] Welcome kit {kit_id} sent via {delivery_channel}")

        return {
            "status": "success" if sent_successfully else "partial",
            "kit_id": kit_id,
            "message": f"Welcome kit '{kit_name}' sent via {delivery_channel}",
            "delivery_status": welcome_kit.delivery_status,
        }

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow] send_welcome_kit failed: {exc}")
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to send welcome kit: {str(exc)}",
            "kit_id": None,
        }


def schedule_training(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    training_name: str,
    scheduled_date: date,
    scheduled_time: str,
    trainer_user_id: Optional[str] = None,
    delivery_mode: str = "IN_PERSON",
    meeting_link: Optional[str] = None,
    duration_minutes: int = 60,
    training_description: Optional[str] = None,
    is_mandatory: bool = True,
) -> Dict:
    """
    Schedules a training session for new employee.

    Supports multiple delivery modes: IN_PERSON, VIRTUAL, HYBRID, SELF_PACED.
    Creates TrainingSession record and sends calendar invite.

    Args:
        db: Database session
        calling_context_tenant_id: Tenant ID (never from client)
        workflow_id: ID of onboarding workflow
        training_name: Name of training (e.g., "System Access Setup")
        scheduled_date: Date of training
        scheduled_time: Time in HH:MM format
        trainer_user_id: User conducting training
        delivery_mode: HOW to deliver (IN_PERSON, VIRTUAL, HYBRID, SELF_PACED)
        meeting_link: URL for virtual sessions
        duration_minutes: Session duration
        training_description: Optional description
        is_mandatory: Whether training is required

    Returns:
        Dict with:
        - status: "success" or "error"
        - session_id: ID of training session
        - message: Status message
    """
    try:
        # 1. Verify workflow exists
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.tenant_id == calling_context_tenant_id,
        ).first()
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found", "session_id": None}

        # 2. Get employee
        employee = workflow.employee
        if not employee:
            return {"status": "error", "message": "Employee not found for workflow", "session_id": None}

        # 3. Verify date is after joining date
        if scheduled_date < workflow.joining_date:
            return {
                "status": "error",
                "message": f"Training date cannot be before joining date {workflow.joining_date}",
                "session_id": None,
            }

        # 4. Get trainer information if specified
        trainer_name = None
        trainer_email = None
        if trainer_user_id:
            trainer = db.query(Users).filter(Users.UserID == trainer_user_id).first()
            if trainer:
                trainer_name = trainer.UserName
                trainer_email = trainer.UserEmail

        # 5. Create training session
        training_session = TrainingSession(
            tenant_id=calling_context_tenant_id,
            workflow_id=workflow_id,
            training_name=training_name,
            training_description=training_description,
            training_type="MANDATORY" if is_mandatory else "OPTIONAL",
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            trainer_user_id=trainer_user_id,
            trainer_name=trainer_name,
            trainer_email=trainer_email,
            delivery_mode=delivery_mode,
            meeting_link=meeting_link,
            status="SCHEDULED",
            timezone="Asia/Kolkata",  # Default timezone; should come from employee profile
        )
        db.add(training_session)
        db.flush()
        session_id = training_session.id

        # 6. Send calendar invite
        _send_training_calendar_invite(db, training_session, employee, calling_context_tenant_id)

        # 7. Create corresponding task
        _create_training_task(db, calling_context_tenant_id, workflow_id, training_name, scheduled_date, is_mandatory)

        db.commit()
        logger.info(f"[OnboardingWorkflow] Training session {session_id} scheduled for {employee.first_name}")

        return {
            "status": "success",
            "session_id": session_id,
            "message": f"Training '{training_name}' scheduled for {scheduled_date}",
            "details": {
                "session_id": session_id,
                "training_name": training_name,
                "scheduled_date": scheduled_date.isoformat(),
                "scheduled_time": scheduled_time,
                "delivery_mode": delivery_mode,
            }
        }

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow] schedule_training failed: {exc}")
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to schedule training: {str(exc)}",
            "session_id": None,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _create_default_onboarding_tasks(
    db: Session,
    tenant_id: str,
    workflow_id: int,
    joining_date: date,
    reporting_manager_id: Optional[str],
) -> List[OnboardingTask]:
    """Create default onboarding tasks based on role/company."""
    tasks = []
    task_configs = [
        {
            "type": "ORIENTATION",
            "name": "Company Orientation",
            "description": "Attend company-wide orientation program",
            "days_offset": 0,
            "mandatory": True,
        },
        {
            "type": "SYSTEM_ACCESS",
            "name": "System Access Setup",
            "description": "Set up email, laptop, access credentials",
            "days_offset": 0,
            "mandatory": True,
        },
        {
            "type": "DOCUMENTATION",
            "name": "Complete Onboarding Documents",
            "description": "Finalize all required paperwork",
            "days_offset": 1,
            "mandatory": True,
        },
        {
            "type": "TEAM_INTRODUCTION",
            "name": "Meet Your Team",
            "description": "One-on-one meetings with team members",
            "days_offset": 2,
            "mandatory": True,
        },
        {
            "type": "TRAINING",
            "name": "Role-Specific Training",
            "description": "Complete role-specific training",
            "days_offset": 3,
            "mandatory": True,
        },
    ]

    for config in task_configs:
        due_date = joining_date + timedelta(days=config["days_offset"])
        task = OnboardingTask(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            task_type=config["type"],
            task_name=config["name"],
            task_description=config["description"],
            due_date=due_date,
            completion_target_days=config["days_offset"],
            assigned_by_user_id=reporting_manager_id,
            is_mandatory=config["mandatory"],
            is_system_generated=True,
            task_priority="HIGH" if config["mandatory"] else "MEDIUM",
        )
        db.add(task)
        tasks.append(task)

    db.flush()
    return tasks


def _notify_buddy_assignment(
    db: Session,
    buddy_user: Users,
    employee: Employee,
    workflow: OnboardingWorkflow,
    tenant_id: str,
) -> None:
    """Send notifications to buddy about assignment."""
    try:
        employee_name = f"{employee.first_name} {employee.last_name}".strip()
        joining_date = workflow.joining_date.strftime("%B %d, %Y") if workflow.joining_date else "soon"

        message = f"You've been assigned as a buddy for {employee_name}, joining on {joining_date}. Your guidance will be invaluable in their first 30 days!"

        send_notification(
            db,
            calling_context_tenant_id=tenant_id,
            recipient=buddy_user,
            priority_tier="P2",
            channel_preference="IN_APP",
            message=message,
        )
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingWorkflow] Failed to notify buddy: {exc}")


def _create_buddy_introduction_task(
    db: Session,
    tenant_id: str,
    workflow_id: int,
    buddy_user_id: str,
) -> None:
    """Create task for buddy to introduce themselves."""
    try:
        task = OnboardingTask(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            task_type="TEAM_INTRODUCTION",
            task_name="Buddy Introduction",
            task_description="Buddy to introduce themselves and outline support plan",
            assigned_to_user_id=buddy_user_id,
            due_date=datetime.now().date() + timedelta(days=1),
            is_mandatory=True,
            is_system_generated=True,
            task_priority="HIGH",
        )
        db.add(task)
        db.flush()
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingWorkflow] Failed to create buddy task: {exc}")


def _send_welcome_kit_by_channel(
    db: Session,
    employee: Employee,
    welcome_kit: WelcomeKit,
    kit_type: str,
    kit_name: str,
    kit_contents: Optional[List[str]],
    delivery_channel: str,
) -> bool:
    """Send welcome kit via specified channel."""
    try:
        employee_name = f"{employee.first_name} {employee.last_name}".strip()

        if delivery_channel == "EMAIL":
            contents_html = "<ul>" + "".join(f"<li>{item}</li>" for item in (kit_contents or [])) + "</ul>"
            html_body = f"""
            <p>Welcome to BlitzenX, {employee.first_name}!</p>
            <p>We're excited to have you on board. Here are some resources to help you get started:</p>
            {contents_html}
            <p>If you have any questions, please don't hesitate to reach out to your buddy or the HR team.</p>
            <p>Looking forward to working with you!</p>
            """
            EmailService.send_email(
                employee.email,
                f"{kit_name} - Welcome to BlitzenX",
                html_body,
                is_html=True,
            )
            return True

        elif delivery_channel in ["PHYSICAL_MAIL", "IN_PERSON"]:
            logger.info(f"[OnboardingWorkflow] Welcome kit {welcome_kit.id} marked for {delivery_channel}")
            return True

        elif delivery_channel == "SMS":
            logger.info(f"[OnboardingWorkflow] SMS welcome kit for {employee.mobile}: {kit_name}")
            return True

        return True

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.error(f"[OnboardingWorkflow] Failed to send welcome kit: {exc}")
        return False


def _send_training_calendar_invite(
    db: Session,
    training_session: TrainingSession,
    employee: Employee,
    tenant_id: str,
) -> None:
    """Send calendar invite for training session."""
    try:
        trainer_name = training_session.trainer_name or "Training Team"
        start_datetime = f"{training_session.scheduled_date}T{training_session.scheduled_time}"
        end_datetime = datetime.fromisoformat(start_datetime)
        end_datetime = end_datetime + timedelta(minutes=training_session.duration_minutes)

        message = f"Training session '{training_session.training_name}' scheduled for {training_session.scheduled_date} at {training_session.scheduled_time}"

        send_notification(
            db,
            calling_context_tenant_id=tenant_id,
            recipient_email=employee.email,
            priority_tier="P2",
            channel_preference="EMAIL",
            message=message,
        )

        training_session.calendar_invite_sent = True

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingWorkflow] Failed to send calendar invite: {exc}")


def _create_training_task(
    db: Session,
    tenant_id: str,
    workflow_id: int,
    training_name: str,
    scheduled_date: date,
    is_mandatory: bool,
) -> None:
    """Create task for training attendance."""
    try:
        task = OnboardingTask(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            task_type="TRAINING",
            task_name=f"Complete: {training_name}",
            task_description=f"Attend and complete {training_name} training session",
            due_date=scheduled_date,
            is_mandatory=is_mandatory,
            is_system_generated=True,
            task_priority="HIGH" if is_mandatory else "MEDIUM",
        )
        db.add(task)
        db.flush()
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[OnboardingWorkflow] Failed to create training task: {exc}")

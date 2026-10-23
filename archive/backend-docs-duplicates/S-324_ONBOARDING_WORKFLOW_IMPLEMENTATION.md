# S-324: Onboarding Workflow Implementation

## Overview

S-324 implements a comprehensive onboarding workflow management system for new employees. It provides complete lifecycle management from joining date through 30+ day onboarding completion.

**Implementation Status:** Complete with service layer, REST APIs, models, and tests.

## Architecture

### Models

#### OnboardingWorkflow
Master record tracking the entire onboarding journey for one employee.

```
Fields:
- id: Primary key
- tenant_id: Multi-tenant isolation
- employee_id: Link to Employee record (unique)
- candidate_id: Optional link to Candidate for hire tracking
- status: NOT_STARTED | IN_PROGRESS | COMPLETED | ON_HOLD | DEFERRED
- joining_date: Employee's start date
- onboarding_start_date: When onboarding process began
- onboarding_end_date: When onboarding completed
- expected_completion_date: Target completion (typically joining_date + 30 days)
- total_tasks: Count of assigned tasks
- completed_tasks: Count of completed tasks
- progress_percentage: 0-100 completion rate
```

Relationships:
- 1:1 with Employee
- 1:1 with OnboardingBuddy
- 1:N with OnboardingTask
- 1:N with WelcomeKit
- 1:N with TrainingSession

#### OnboardingBuddy
Tracks buddy assignment to guide new employee.

```
Fields:
- id: Primary key
- workflow_id: FK to OnboardingWorkflow (unique - one buddy per workflow)
- buddy_user_id: FK to Users (the assigned buddy)
- employee_id: FK to Employee
- status: ASSIGNED | ACTIVE | COMPLETED | DECLINED | UNAVAILABLE
- activation_date: When buddy officially starts
- check_ins_scheduled: Count of scheduled check-ins
- check_ins_completed: Count of completed check-ins
- last_interaction_date: Last buddy-employee contact
```

#### OnboardingTask
Individual onboarding tasks to be completed (system-generated or manual).

```
Fields:
- id: Primary key
- workflow_id: FK to OnboardingWorkflow
- task_type: ORIENTATION | TRAINING | DOCUMENTATION | SYSTEM_ACCESS | TEAM_INTRODUCTION | CUSTOM
- task_name: Human-readable task name
- status: PENDING | IN_PROGRESS | COMPLETED | SKIPPED | DEFERRED
- task_priority: HIGH | MEDIUM | LOW
- assigned_to_user_id: FK to Users (who performs task)
- due_date: When task should complete
- completion_target_days: Days from joining date
- started_date: When task actually began
- completed_date: When task actually completed
- is_mandatory: Required vs optional
- is_system_generated: Auto-created vs manually added
```

#### WelcomeKit
Tracks welcome materials/packages sent to employee.

```
Fields:
- id: Primary key
- workflow_id: FK to OnboardingWorkflow
- kit_type: EMAIL | PHYSICAL | DIGITAL | HYBRID
- kit_name: Name of package (e.g., "Day 1 Welcome")
- kit_contents: JSON array of items
- sent_by_user_id: FK to Users (who sent)
- sent_date: When package was sent
- sent_channel: EMAIL | PHYSICAL_MAIL | SMS | IN_PERSON
- delivery_status: PENDING | SENT | DELIVERED | FAILED | ACKNOWLEDGED
```

#### TrainingSession
Scheduled training for new employee.

```
Fields:
- id: Primary key
- workflow_id: FK to OnboardingWorkflow
- training_name: Name of training (e.g., "System Access Setup")
- scheduled_date: When training occurs
- scheduled_time: Time in HH:MM format
- trainer_user_id: FK to Users (who conducts)
- delivery_mode: IN_PERSON | VIRTUAL | HYBRID | SELF_PACED
- meeting_link: URL for virtual sessions
- status: SCHEDULED | IN_PROGRESS | COMPLETED | CANCELLED | RESCHEDULED
- attendance_status: ATTENDED | ABSENT | EXCUSED | RESCHEDULED
- duration_minutes: Session length (default: 60)
- feedback_score: 1-5 rating after completion
```

## Service Layer

### start_onboarding()

Initiates onboarding workflow for new employee.

```python
def start_onboarding(
    db: Session,
    calling_context_tenant_id: str,
    employee_id: str,
    candidate_id: Optional[str] = None,
    reporting_manager_id: Optional[str] = None,
    expected_completion_days: int = 30,
) -> Dict:
```

**Behavior:**
- Verifies employee exists
- Prevents duplicate workflows
- Creates OnboardingWorkflow record
- Auto-generates default onboarding tasks:
  - Company Orientation (D+0)
  - System Access Setup (D+0)
  - Complete Onboarding Documents (D+1)
  - Meet Your Team (D+2)
  - Role-Specific Training (D+3)
- Returns workflow_id and task count

**Returns:**
```json
{
  "status": "success" | "error",
  "workflow_id": 123,
  "tasks_created": 5,
  "message": "...",
  "details": {...}
}
```

**Business Rules:**
- BR-01: Only called when Employee record exists (candidate has joined)
- BR-02: Duplicate workflows prevented via unique constraint
- BR-03: Default tasks are system-generated and mandatory

### assign_buddy()

Assigns buddy to guide new employee.

```python
def assign_buddy(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    buddy_user_id: str,
    activation_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> Dict:
```

**Behavior:**
- Verifies workflow exists
- Verifies buddy user exists
- Prevents duplicate buddy assignments
- Creates OnboardingBuddy record
- Sends notification to buddy
- Creates "Buddy Introduction" task
- Returns buddy_id

**Returns:**
```json
{
  "status": "success" | "error",
  "buddy_id": 456,
  "message": "Buddy [name] assigned to [employee]",
  "buddy_user_id": "user_id"
}
```

**Business Rules:**
- BR-04: One buddy per workflow (unique constraint)
- BR-05: Buddy must be active user in same tenant
- BR-06: Buddy introduction task auto-created as mandatory

### send_welcome_kit()

Dispatches welcome materials to new employee.

```python
def send_welcome_kit(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    kit_type: str,  # EMAIL, PHYSICAL, DIGITAL, HYBRID
    kit_name: str,
    kit_contents: Optional[List[str]] = None,
    sent_by_user_id: Optional[str] = None,
    delivery_channel: str = "EMAIL",
) -> Dict:
```

**Behavior:**
- Verifies workflow exists
- Gets employee contact info
- Creates WelcomeKit record
- Sends via specified channel:
  - **EMAIL**: HTML email with kit contents
  - **PHYSICAL_MAIL**: Marked for shipping
  - **SMS**: Text message notification
  - **IN_PERSON**: Hand-delivery at office
- Tracks delivery status and acknowledgement
- Returns kit_id

**Returns:**
```json
{
  "status": "success" | "partial" | "error",
  "kit_id": 789,
  "message": "Welcome kit sent via [channel]",
  "delivery_status": "SENT" | "FAILED"
}
```

**Business Rules:**
- BR-07: Multiple kits can be sent to same employee
- BR-08: Delivery channel determines sending mechanism
- BR-09: Email channel uses EmailService for HTML rendering

### schedule_training()

Schedules training session for new employee.

```python
def schedule_training(
    db: Session,
    calling_context_tenant_id: str,
    workflow_id: int,
    training_name: str,
    scheduled_date: date,
    scheduled_time: str,  # HH:MM format
    trainer_user_id: Optional[str] = None,
    delivery_mode: str = "IN_PERSON",
    meeting_link: Optional[str] = None,
    duration_minutes: int = 60,
    training_description: Optional[str] = None,
    is_mandatory: bool = True,
) -> Dict:
```

**Behavior:**
- Verifies workflow exists
- Validates date >= joining_date
- Creates TrainingSession record
- Sends calendar invite to employee
- Creates corresponding OnboardingTask
- Supports multiple delivery modes:
  - **IN_PERSON**: On-site training
  - **VIRTUAL**: Requires meeting_link (Zoom, Teams, etc.)
  - **HYBRID**: Both in-person and virtual
  - **SELF_PACED**: Asynchronous learning
- Returns session_id

**Returns:**
```json
{
  "status": "success" | "error",
  "session_id": 101,
  "message": "Training '[name]' scheduled for [date]",
  "details": {
    "session_id": 101,
    "training_name": "...",
    "scheduled_date": "2026-08-20",
    "scheduled_time": "10:00",
    "delivery_mode": "IN_PERSON"
  }
}
```

**Business Rules:**
- BR-10: Training date cannot be before employee joining date
- BR-11: Virtual sessions must include meeting_link
- BR-12: Calendar invite sent automatically
- BR-13: Corresponding task auto-created (mandatory if is_mandatory=true)

## REST API Endpoints

### 1. POST /onboarding-workflow/start

Start onboarding workflow.

**Request:**
```json
{
  "employee_id": "string",
  "candidate_id": "string (optional)",
  "reporting_manager_id": "string (optional)",
  "expected_completion_days": 30
}
```

**Response:**
```json
{
  "status": "success",
  "workflow_id": 123,
  "tasks_created": 5,
  "message": "Onboarding workflow created for [employee]",
  "details": {...}
}
```

**Required Permission:** `onboarding.manage`

### 2. POST /onboarding-workflow/assign-buddy

Assign buddy to employee.

**Request:**
```json
{
  "workflow_id": 123,
  "buddy_user_id": "string",
  "activation_date": "2026-08-15 (optional)",
  "notes": "string (optional)"
}
```

**Response:**
```json
{
  "status": "success",
  "buddy_id": 456,
  "message": "Buddy [name] assigned to [employee]",
  "buddy_user_id": "user_id"
}
```

**Required Permission:** `onboarding.manage`

### 3. POST /onboarding-workflow/send-welcome-kit

Send welcome materials.

**Request:**
```json
{
  "workflow_id": 123,
  "kit_type": "EMAIL|PHYSICAL|DIGITAL|HYBRID",
  "kit_name": "Day 1 Welcome Package",
  "kit_contents": ["Item 1", "Item 2"],
  "sent_by_user_id": "string (optional, defaults to current user)",
  "delivery_channel": "EMAIL|PHYSICAL_MAIL|SMS|IN_PERSON"
}
```

**Response:**
```json
{
  "status": "success",
  "kit_id": 789,
  "message": "Welcome kit sent via [channel]",
  "delivery_status": "SENT"
}
```

**Required Permission:** `onboarding.manage`

### 4. POST /onboarding-workflow/schedule-training

Schedule training session.

**Request:**
```json
{
  "workflow_id": 123,
  "training_name": "System Access Setup",
  "scheduled_date": "2026-08-20",
  "scheduled_time": "10:00",
  "trainer_user_id": "string (optional)",
  "delivery_mode": "IN_PERSON|VIRTUAL|HYBRID|SELF_PACED",
  "meeting_link": "https://zoom.us/... (required if VIRTUAL)",
  "duration_minutes": 60,
  "training_description": "string (optional)",
  "is_mandatory": true
}
```

**Response:**
```json
{
  "status": "success",
  "session_id": 101,
  "message": "Training scheduled for [date]",
  "details": {...}
}
```

**Required Permission:** `onboarding.manage`

### 5. GET /onboarding-workflow/{workflow_id}

Get workflow details.

**Response:**
```json
{
  "workflow_id": 123,
  "employee_id": "emp_123",
  "status": "IN_PROGRESS",
  "joining_date": "2026-08-15",
  "expected_completion_date": "2026-09-14",
  "total_tasks": 5,
  "completed_tasks": 2,
  "progress_percentage": 40
}
```

**Required Permission:** `onboarding.view`

### 6. GET /onboarding-workflow/employee/{employee_id}

Get complete onboarding data for employee.

**Response:**
```json
{
  "workflow": {...},
  "buddy": {...},
  "tasks": [
    {
      "task_id": 1,
      "task_name": "...",
      "status": "PENDING",
      "due_date": "2026-08-15"
    }
  ],
  "welcome_kits": [...],
  "training_sessions": [...]
}
```

**Required Permission:** `onboarding.view`

### 7. GET /onboarding-workflow/{workflow_id}/tasks

Get all tasks for workflow.

**Query Parameters:**
- `status` (optional): Filter by status (PENDING, IN_PROGRESS, COMPLETED, etc.)

**Response:**
```json
{
  "workflow_id": 123,
  "total_tasks": 5,
  "tasks": [...]
}
```

**Required Permission:** `onboarding.view`

### 8. GET /onboarding-workflow/{workflow_id}/training

Get all training sessions for workflow.

**Query Parameters:**
- `status` (optional): Filter by status (SCHEDULED, COMPLETED, etc.)

**Response:**
```json
{
  "workflow_id": 123,
  "total_sessions": 3,
  "training_sessions": [...]
}
```

**Required Permission:** `onboarding.view`

## Data Flow

### Workflow Lifecycle

```
Employee Created
       ↓
start_onboarding()
       ├─ Create OnboardingWorkflow (status: IN_PROGRESS)
       ├─ Create default tasks (5 mandatory)
       └─ Return workflow_id
       ↓
assign_buddy() [Optional]
       ├─ Create OnboardingBuddy
       ├─ Send notification
       └─ Create introduction task
       ↓
send_welcome_kit() [Optional, Multiple]
       ├─ Create WelcomeKit record
       ├─ Send via channel (EMAIL/PHYSICAL/SMS/IN_PERSON)
       └─ Track delivery status
       ↓
schedule_training() [Multiple Sessions]
       ├─ Create TrainingSession
       ├─ Send calendar invite
       └─ Create corresponding task
       ↓
Tasks Completion [Async Process]
       ├─ update_task_status()
       ├─ Track progress_percentage
       └─ Check for completion
       ↓
Workflow Completion [Automatic or Manual]
       ├─ All tasks completed
       └─ Update workflow.status to COMPLETED
```

## Integration Points

### Tenant Isolation
- All operations scoped by `tenant_id` via context
- Never accepts tenant_id from client input
- Session-level enforced via middleware

### Employee Model
- Links to existing Employee table
- Unique constraint on (tenant_id, employee_id)
- Created automatically when candidate joins

### User Model (Buddy, Trainer, Assignees)
- ForeignKey to Users table
- Validates users exist before assignment
- Sends notifications via notification_service

### Email Service
- Used for welcome kit EMAIL channel
- Used for calendar invite HTML rendering
- Optional SMS support (framework present, implementation pending)

### Notification Service
- Notifies buddy of assignment
- Sends training calendar invites
- Handles async message delivery

## Testing

### Service Layer Tests (test_onboarding_workflow_service.py)
- 40+ test cases covering all four main methods
- Tests for success paths
- Tests for error conditions
- Tests for business rule enforcement
- Fixtures for test employee, user, workflow setup

### API Endpoint Tests (test_onboarding_workflow_endpoints.py)
- Tests for all 8 REST endpoints
- Tests for authentication/authorization
- Tests for request validation
- Tests for response format
- Tests for error handling

### Test Coverage
- Happy path scenarios
- Error conditions
- Duplicate prevention
- Date validation
- Status transitions
- Task creation
- Notification sending
- Calendar invite generation

## Usage Examples

### Python (Service Layer)

```python
from app.services.onboarding_workflow_service import (
    start_onboarding, assign_buddy, send_welcome_kit, schedule_training
)
from sqlalchemy.orm import Session

def onboard_employee(db: Session, employee_id: str):
    # 1. Start onboarding
    result = start_onboarding(
        db,
        calling_context_tenant_id="tenant_123",
        employee_id=employee_id,
        expected_completion_days=30,
    )
    workflow_id = result["workflow_id"]
    
    # 2. Assign buddy
    assign_buddy(
        db,
        calling_context_tenant_id="tenant_123",
        workflow_id=workflow_id,
        buddy_user_id="buddy_user_id",
    )
    
    # 3. Send welcome kit
    send_welcome_kit(
        db,
        calling_context_tenant_id="tenant_123",
        workflow_id=workflow_id,
        kit_type="EMAIL",
        kit_name="Day 1 Welcome",
        kit_contents=["Letter", "Handbook"],
        delivery_channel="EMAIL",
    )
    
    # 4. Schedule training
    from datetime import date, timedelta
    scheduled_date = date.today() + timedelta(days=3)
    schedule_training(
        db,
        calling_context_tenant_id="tenant_123",
        workflow_id=workflow_id,
        training_name="System Setup",
        scheduled_date=scheduled_date,
        scheduled_time="10:00",
        delivery_mode="IN_PERSON",
    )
```

### REST API (FastAPI)

```bash
# 1. Start onboarding
curl -X POST http://localhost:8000/api/v1/onboarding-workflow/start \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "emp_123",
    "expected_completion_days": 30
  }'

# 2. Assign buddy
curl -X POST http://localhost:8000/api/v1/onboarding-workflow/assign-buddy \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": 1,
    "buddy_user_id": "buddy_user_id"
  }'

# 3. Send welcome kit
curl -X POST http://localhost:8000/api/v1/onboarding-workflow/send-welcome-kit \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": 1,
    "kit_type": "EMAIL",
    "kit_name": "Day 1 Welcome",
    "kit_contents": ["Letter", "Handbook"],
    "delivery_channel": "EMAIL"
  }'

# 4. Schedule training
curl -X POST http://localhost:8000/api/v1/onboarding-workflow/schedule-training \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": 1,
    "training_name": "System Setup",
    "scheduled_date": "2026-08-20",
    "scheduled_time": "10:00",
    "delivery_mode": "IN_PERSON",
    "duration_minutes": 60
  }'

# 5. Get workflow details
curl -X GET http://localhost:8000/api/v1/onboarding-workflow/1 \
  -H "Authorization: Bearer token"

# 6. Get all tasks
curl -X GET http://localhost:8000/api/v1/onboarding-workflow/1/tasks \
  -H "Authorization: Bearer token"
```

## Error Handling

All service methods return Dict with `status` field:
- **"success"**: Operation completed successfully
- **"partial"**: Operation partially succeeded (e.g., email failed but kit created)
- **"error"**: Operation failed completely

Clients should check `status` field and handle accordingly:

```python
result = start_onboarding(db, tenant_id, employee_id)
if result["status"] == "error":
    # Handle error: result["message"] contains details
    log_error(result["message"])
elif result["status"] == "success":
    # Success: result["workflow_id"] available
    workflow_id = result["workflow_id"]
else:
    # Partial success: check result["details"]
    log_warning(result["message"])
```

## Security & Isolation

### Tenant Isolation
- All queries filtered by `tenant_id`
- Tenant resolved from session context, never from client input
- Prevents cross-tenant data access

### Authorization
- All endpoints require permission check
- `onboarding.manage` for write operations
- `onboarding.view` for read operations
- Permission validation via FastAPI dependency

### Data Validation
- Email format validation
- Date range validation
- FK relationship validation
- Status enum enforcement
- Unique constraint enforcement

## Performance Considerations

### Database Indexes
- `onboarding_workflows(tenant_id, employee_id)`
- `onboarding_buddies(workflow_id)`
- `onboarding_tasks(workflow_id, status)`
- `training_sessions(workflow_id, scheduled_date)`
- `welcome_kits(workflow_id)`

### Query Optimization
- Lazy loading on relationships
- Batch loading via `selectinload` for N+1 prevention
- Efficient status queries with indexed fields

### Background Tasks
- Email sending deferred via BackgroundTasks
- Calendar invite generation async
- Notification sending async (via notification_service)

## Future Enhancements

1. **Onboarding Progress Dashboard**
   - Real-time task completion tracking
   - Visual progress timeline
   - Buddy engagement metrics

2. **Automated Task Assignments**
   - AI-driven task generation based on role/department
   - Automatic trainer matching

3. **Mobile App Integration**
   - Mobile-friendly training sessions
   - Mobile checklist tracking

4. **Advanced Analytics**
   - Onboarding effectiveness metrics
   - Time-to-productivity tracking
   - Retention correlation analysis

5. **Document Management**
   - Electronic signature collection
   - Document upload tracking
   - Compliance verification

## Database Migration

Run Alembic migrations to create tables:

```bash
alembic upgrade head
```

Migration files will create:
- `onboarding_workflows` table
- `onboarding_buddies` table
- `welcome_kits` table
- `training_sessions` table
- `onboarding_tasks` table

## Configuration

No explicit configuration needed. Service uses:
- Database connection from `app.core.database`
- Tenant context from `app.core.tenant_context`
- Logging from `app.core.logging`
- Email service from `app.services.email_service`
- Notification service from `app.services.notification_service`

All hardcoded values (timezones, defaults) can be moved to `settings.py` for environment-specific configuration.

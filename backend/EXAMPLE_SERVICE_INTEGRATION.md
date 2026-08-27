# Example Service Integrations - Message Queue

This document shows how to add message queue enqueue calls to existing services.

## Example 1: Candidate Service

**File:** `backend/app/services/candidates_service.py`

### Original Code
```python
def create_candidate(db: Session, candidate_data: dict, tenant_id: int, current_user_id: str):
    """Create a new candidate."""
    
    candidate = Candidate(
        id=str(uuid.uuid4()),
        name=candidate_data['name'],
        email=candidate_data['email'],
        phone=candidate_data.get('phone'),
        # ... other fields
        tenant_id=tenant_id,
        created_by=current_user_id,
        created_at=datetime.utcnow(),
    )
    
    db.add(candidate)
    db.commit()
    
    return candidate
```

### With Message Queue Integration
```python
from app.services.message_queue_service import MessageQueueService

def create_candidate(db: Session, candidate_data: dict, tenant_id: int, current_user_id: str):
    """Create a new candidate and queue for processing."""
    
    # Create candidate
    candidate = Candidate(
        id=str(uuid.uuid4()),
        name=candidate_data['name'],
        email=candidate_data['email'],
        phone=candidate_data.get('phone'),
        # ... other fields
        tenant_id=tenant_id,
        created_by=current_user_id,
        created_at=datetime.utcnow(),
    )
    
    db.add(candidate)
    db.commit()
    
    # ADDED: Queue message for automation
    try:
        MessageQueueService.enqueue_message(
            db=db,
            message_type="candidate_added",
            payload={
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "candidate_email": candidate.email,
                "candidate_phone": candidate.phone,
                "source": candidate_data.get('source', 'manual'),
            },
            tenant_id=tenant_id,
            resource_id=candidate.id,
            created_by=current_user_id,
        )
    except Exception as e:
        logger.error(f"Failed to queue candidate_added message: {str(e)}")
        # Don't fail candidate creation if queueing fails
        # But do log it for monitoring
    
    return candidate
```

### Handler Implementation

**File:** `backend/app/workers/message_queue_worker.py`

```python
async def handle_candidate_added(payload: Dict[str, Any], resource_id: Optional[str], db: Session) -> bool:
    """
    Handle candidate_added messages.
    
    Triggered when a candidate is created.
    Responsibility: Trigger Thunder autonomous recruitment.
    """
    candidate_id = payload.get("candidate_id")
    candidate_name = payload.get("candidate_name")
    candidate_email = payload.get("candidate_email")
    source = payload.get("source", "manual")
    
    logger.info(f"Processing candidate_added: {candidate_id} ({candidate_name} from {source})")
    
    try:
        # Get candidate from database
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")
        
        # Trigger Thunder autonomous recruitment
        from app.services.thunder_service import ThunderService
        
        result = await ThunderService.assign_candidate_to_thunder(db, candidate)
        
        if not result:
            raise Exception("Thunder assignment failed")
        
        logger.info(f"Successfully triggered Thunder for candidate: {candidate_id}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to handle candidate_added: {str(e)}", exc_info=True)
        raise  # Fail-fast: let worker handle retry/failure

# Register handler
register_handler("candidate_added", handle_candidate_added)
```

## Example 2: Thunder Email Service

**File:** `backend/app/services/thunder_service.py`

### With Message Queue Integration
```python
from app.services.message_queue_service import MessageQueueService

def send_candidate_email(db: Session, candidate_email: str, subject: str, body: str, 
                        candidate_id: str, tenant_id: int, current_user_id: str) -> bool:
    """Send email to candidate and queue for tracking."""
    
    try:
        # Send email via email service
        result = email_service.send(
            to_email=candidate_email,
            subject=subject,
            body=body,
            from_email="recruitment@company.com",
        )
        
        if not result:
            raise Exception("Email service returned failure")
        
        # ADDED: Queue message for tracking
        MessageQueueService.enqueue_message(
            db=db,
            message_type="thunder_email",
            payload={
                "candidate_id": candidate_id,
                "recipient_email": candidate_email,
                "subject": subject,
                "body_length": len(body),
                "sent_at": datetime.utcnow().isoformat(),
            },
            tenant_id=tenant_id,
            resource_id=candidate_id,
            created_by=current_user_id,
        )
        
        logger.info(f"Email sent and queued: {candidate_id} -> {candidate_email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        raise

# Handler
def handle_thunder_email(payload, resource_id, db):
    """Handle email sent notifications - update delivery status."""
    candidate_id = payload.get("candidate_id")
    recipient = payload.get("recipient_email")
    
    logger.info(f"Email delivery tracked: {candidate_id} -> {recipient}")
    
    # TODO: Update email delivery tracking
    # - Mark as sent in database
    # - Update engagement metrics
    # - Log communication history
    
    return True

register_handler("thunder_email", handle_thunder_email)
```

## Example 3: Flash Agent Service

**File:** `backend/app/services/flash_service.py`

### With Message Queue Integration
```python
from app.services.message_queue_service import MessageQueueService

def execute_flash_agent_action(db: Session, agent_id: str, action: str, 
                               targets: List[str], tenant_id: int) -> bool:
    """Execute Flash agent action and queue for audit trail."""
    
    try:
        # Execute action
        from app.agents.flash_agent import FlashAgent
        
        agent = FlashAgent(agent_id=agent_id)
        result = agent.execute_action(action, targets)
        
        if not result:
            raise Exception(f"Agent action failed: {action}")
        
        # ADDED: Queue message for audit trail
        MessageQueueService.enqueue_message(
            db=db,
            message_type="flash_agent_action",
            payload={
                "agent_id": agent_id,
                "action": action,
                "target_count": len(targets),
                "targets": targets[:10],  # First 10 for logging
                "executed_at": datetime.utcnow().isoformat(),
            },
            tenant_id=tenant_id,
            resource_id=agent_id,
            created_by=None,  # System action
        )
        
        logger.info(f"Agent action executed: {agent_id} - {action}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to execute agent action: {str(e)}", exc_info=True)
        raise

# Handler
def handle_flash_agent_action(payload, resource_id, db):
    """Handle Flash agent execution - update agent state."""
    agent_id = payload.get("agent_id")
    action = payload.get("action")
    target_count = payload.get("target_count", 0)
    
    logger.info(f"Agent action completed: {agent_id} - {action} ({target_count} targets)")
    
    # TODO: Update agent execution log
    # - Record execution metrics
    # - Update agent last_executed_at
    # - Calculate performance metrics
    
    return True

register_handler("flash_agent_action", handle_flash_agent_action)
```

## Example 4: User Creation Service

**File:** `backend/app/services/users_service.py`

### With Message Queue Integration
```python
from app.services.message_queue_service import MessageQueueService

def create_user(db: Session, user_data: dict, tenant_id: int, current_user_id: str):
    """Create new user and queue for onboarding."""
    
    user = Users(
        UserID=str(uuid.uuid4()),
        UserEmail=user_data['email'],
        UserName=user_data['name'],
        UserRole=user_data.get('role', 'Employee'),
        # ... other fields
        tenant_id=tenant_id,
        created_by=current_user_id,
    )
    
    db.add(user)
    db.commit()
    
    # ADDED: Queue message for onboarding workflow
    MessageQueueService.enqueue_message(
        db=db,
        message_type="user_created",
        payload={
            "user_id": user.UserID,
            "user_email": user.UserEmail,
            "user_name": user.UserName,
            "user_role": user.UserRole,
            "created_at": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        resource_id=user.UserID,
        created_by=current_user_id,
    )
    
    return user

# Handler
def handle_user_created(payload, resource_id, db):
    """Handle new user creation - trigger onboarding workflow."""
    user_id = payload.get("user_id")
    user_email = payload.get("user_email")
    user_name = payload.get("user_name")
    
    logger.info(f"New user created: {user_id} ({user_name} - {user_email})")
    
    # TODO: Trigger onboarding
    # - Send welcome email
    # - Create onboarding tasks
    # - Set up workspace
    # - Assign buddy/mentor
    
    return True

register_handler("user_created", handle_user_created)
```

## Example 5: Job Posting Service

**File:** `backend/app/services/jobs_service.py`

### With Message Queue Integration
```python
from app.services.message_queue_service import MessageQueueService

def create_job(db: Session, job_data: dict, tenant_id: int, current_user_id: str):
    """Create job posting and queue for recruitment flow."""
    
    job = Jobs(
        id=str(uuid.uuid4()),
        title=job_data['title'],
        description=job_data['description'],
        # ... other fields
        tenant_id=tenant_id,
        created_by=current_user_id,
    )
    
    db.add(job)
    db.commit()
    
    # ADDED: Queue message for recruitment start
    MessageQueueService.enqueue_message(
        db=db,
        message_type="job_posted",
        payload={
            "job_id": job.id,
            "job_title": job.title,
            "job_status": "ACTIVE",
            "posted_at": datetime.utcnow().isoformat(),
        },
        tenant_id=tenant_id,
        resource_id=job.id,
        created_by=current_user_id,
    )
    
    return job

# Handler
def handle_job_posted(payload, resource_id, db):
    """Handle job posting - notify recruiters and activate Thunder."""
    job_id = payload.get("job_id")
    job_title = payload.get("job_title")
    
    logger.info(f"Job posted: {job_id} - {job_title}")
    
    # TODO: Activate recruitment
    # - Notify recruiters
    # - Post to job boards
    # - Activate Thunder for matching
    # - Send notification emails
    
    return True

register_handler("job_posted", handle_job_posted)
```

## Integration Checklist

For each service, follow this pattern:

1. **Identify Key Operations**
   - CREATE: Resource created
   - UPDATE: Resource modified
   - DELETE: Resource deleted (optional)
   - Special actions: Email sent, status changed, etc.

2. **Add Enqueue Call**
   ```python
   MessageQueueService.enqueue_message(
       db=db,
       message_type="operation_type",
       payload={...},
       tenant_id=tenant_id,
       resource_id=resource_id,
       created_by=current_user_id,
   )
   ```

3. **Handle Errors Gracefully**
   - Don't fail main operation if queueing fails
   - Log error for monitoring
   - Let exceptions propagate in handlers (fail-fast)

4. **Register Handler**
   ```python
   def handle_operation_type(payload, resource_id, db):
       # Process the operation
       return True
   
   register_handler("operation_type", handle_operation_type)
   ```

5. **Test End-to-End**
   - Create resource → check message in queue
   - Verify handler executes
   - Check logs for success/failure

## Priority Services for Integration

**High Priority** (Core workflow):
1. Candidates service - `candidate_added`, `candidate_updated`
2. Thunder service - `thunder_email`, `thunder_sms`, `thunder_whatsapp`
3. Users service - `user_created`
4. Interviews service - `interview_scheduled`

**Medium Priority** (Important operations):
1. Jobs service - `job_posted`
2. Offers service - `offer_generated`
3. Flash service - `flash_agent_action`

**Low Priority** (Nice-to-have):
1. Allocations service - `allocation_created`
2. Timesheets service - `timesheet_submitted`
3. Invoices service - `invoice_generated`

## Testing Your Integration

```bash
# 1. Trigger the operation (e.g., create candidate)
curl -X POST http://localhost:8000/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'

# 2. Check message was queued
curl http://localhost:8000/api/v1/admin/message-queue \
  ?message_type=candidate_added

# 3. Run worker to process
python -m app.workers.message_queue_worker

# 4. Verify message was processed
curl http://localhost:8000/api/v1/admin/message-queue/{message_id}
# Should show status=COMPLETED

# 5. Check logs
tail -f logs/app.log | grep "Processing candidate_added"
```

## Notes

- All enqueue calls should be wrapped in try-catch to not fail main operation
- Handlers must use fail-fast pattern (raise exceptions)
- Keep payload small and focused on identifying the resource
- Don't store large binary data in payload (just store IDs/references)
- Test handlers with various error scenarios (network failures, missing data, etc.)

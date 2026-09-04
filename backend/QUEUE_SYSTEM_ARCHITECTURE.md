# Message Queue System Architecture

**Version:** 2.0 (Complete Channel-Based Rebuild)  
**Status:** Production Ready  
**Last Updated:** 2026-08-28  

## Overview

The queue system is the central nervous system of WROS, handling all asynchronous operations through a **channel-based architecture**. Instead of domain-specific queues, messages flow through SLM (Small Language Model) orchestration which decides which **channels** (EMAIL, WHATSAPP, THUNDER, etc.) should handle each operation.

```
Module Action
    ↓
MessageQueue (PENDING)
    ↓
SLM Orchestration (SLM_PROCESSING)
    ↓
SLM creates ChannelQueueItems (CHANNEL_QUEUED)
    ↓
Channel Processors (EMAIL, WHATSAPP, THUNDER, etc.)
    ↓
COMPLETED/FAILED
```

## Core Concept

**Instead of:** "Candidate module, interview module, timesheet module each have their own queues"

**We have:** "A unified message queue where SLM decides which channels to trigger"

### Example Flow

**Candidate Created:**
```
1. Recruitment.create_candidate() calls:
   QueueIntegrations.queue_candidate_created(candidate_id, ...)

2. MessageQueueService.enqueue() creates entry:
   {
     id: "msg-123",
     type: "candidate_created",
     status: "PENDING",
     payload: {candidate_id, candidate_email, ...}
   }

3. Message Queue Worker (runs every 2 min) fetches PENDING messages

4. SLMOrchestrationService.orchestrate_message() analyzes:
   "New candidate should be contacted by Thunder"
   Creates: ChannelQueueItem {
     channel_type: "THUNDER",
     status: "PENDING",
     payload: {candidate_id, action: "initiate_qualification"}
   }

5. Channel Processor Worker (runs every 1 min) fetches THUNDER queue items

6. ChannelProcessors.process_thunder() executes:
   - Call Thunder service
   - Log execution
   - Mark as COMPLETED

Result: Candidate automatically contacted by Thunder without any manual recruiter action.
```

## Database Schema

### message_queue Table

Central inbox for all operations.

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| type | String(100) | Message type (candidate_created, interview_scheduled, etc.) |
| status | String(50) | PENDING → SLM_PROCESSING → CHANNEL_QUEUED → COMPLETED/FAILED |
| payload | JSON | Message data (candidate_id, email, etc.) |
| resource_id | UUID | Resource ID for tracking (candidate_id, interview_id, etc.) |
| queue_type | String(100) | Primary queue type for routing |
| retry_count | Integer | Number of retry attempts |
| error | Text | Error message if failed |
| created_at | DateTime | When message was created |
| updated_at | DateTime | Last update time |

### channel_queue_item Table

Items in specific channel queues waiting for processing.

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| message_id | UUID | FK to message_queue |
| channel_type | String(100) | EMAIL, WHATSAPP, SMS, SLACK, THUNDER, APPROVAL, etc. |
| status | String(50) | PENDING → PROCESSING → COMPLETED/FAILED |
| payload | JSON | Channel-specific data |
| recipient | String(200) | Email, phone, user_id, etc. |
| retry_count | Integer | Number of retries |
| error | Text | Error message |
| created_at | DateTime | When created |
| updated_at | DateTime | Last update |

### channel_queue_log Table

Audit trail for channel processing.

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Primary key |
| channel_item_id | UUID | FK to channel_queue_item |
| status | String(50) | Status change (PENDING, PROCESSING, COMPLETED, FAILED) |
| message | Text | Log message |
| processing_time_ms | Integer | How long it took |
| timestamp | DateTime | When this happened |

## Queue Types

### Primary Message Types
- **CANDIDATE** - Candidate creation/update
- **INTERVIEW** - Interview scheduling
- **OFFER** - Offer generation
- **TIMESHEET** - Timesheet submission
- **KPI** - KPI updates
- **SALES** - Sales deal actions
- **CLIENT** - Client contact updates

### Channel Types
- **EMAIL** - Email delivery (SendGrid, SES, etc.)
- **WHATSAPP** - WhatsApp messages (Twilio, MessageBird)
- **SMS** - SMS delivery (Twilio)
- **SLACK** - Slack team notifications
- **THUNDER** - Thunder autonomous actions
- **APPROVAL** - Approval workflow routing
- **COMMISSION** - Commission calculations
- **CRM** - CRM data synchronization
- **DASHBOARD** - Real-time dashboard updates
- **CALENDAR** - Calendar event creation (Google Calendar)
- **SIGNATURE** - E-signature requests (DocuSign)

## SLM Orchestration Rules

SLM (Small Language Model) orchestration service decides which channels to create for each message type.

### Candidate Created → THUNDER_QUEUE
Every new candidate gets added to Thunder queue for autonomous qualification and outreach.

```python
SLMOrchestrationService._orchestrate_candidate_created()
# Creates: CHANNEL_QUEUE_ITEM { channel: THUNDER, action: initiate_qualification }
```

### Interview Scheduled → EMAIL + WHATSAPP + CALENDAR_QUEUE
When interview is scheduled, send confirmations to candidate and add to calendars.

```python
SLMOrchestrationService._orchestrate_interview_scheduled()
# Creates:
#   - EMAIL: candidate interview confirmation + panel members
#   - WHATSAPP: quick reminder (if consent given)
#   - CALENDAR: add to candidate and panel calendars
```

### Offer Generated → EMAIL + SIGNATURE_QUEUE
Send offer letter and request signature.

```python
SLMOrchestrationService._orchestrate_offer_generated()
# Creates:
#   - EMAIL: offer letter
#   - SIGNATURE: e-signature request
```

### Timesheet Submitted → APPROVAL_QUEUE
Route to manager for approval.

```python
SLMOrchestrationService._orchestrate_timesheet_submitted()
# Creates: APPROVAL_QUEUE item for manager review
```

### KPI Updated → DASHBOARD + EMAIL (if threshold breached)
Update dashboard and send alert if KPI falls below threshold.

```python
SLMOrchestrationService._orchestrate_kpi_updated()
# Creates:
#   - DASHBOARD: real-time update
#   - EMAIL: alert (only if threshold_triggered)
```

### Sales Deal → SALES + COMMISSION (if closed)
Process deal and calculate commission.

```python
SLMOrchestrationService._orchestrate_sales_deal()
# Creates:
#   - SALES: deal processing
#   - COMMISSION: commission calculation (if deal_closed)
```

### Client Contact → CRM + EMAIL (if new)
Sync with CRM and send follow-up.

```python
SLMOrchestrationService._orchestrate_client_contact()
# Creates:
#   - CRM: client data sync
#   - EMAIL: welcome email (if is_new_contact)
```

## Service Layer

### MessageQueueService
Core message queue operations.

```python
from app.services.message_queue_service import MessageQueueService

# Enqueue a message
message_id = MessageQueueService.enqueue(
    message_type="candidate_created",
    payload={"candidate_id": "...", "email": "..."},
    resource_id="candidate-123",
    created_by="recruiter@example.com",
    db=db
)

# Get pending messages
messages = MessageQueueService.get_pending(limit=100, db=db)

# Mark status
MessageQueueService.mark_processing(message_id, db)
MessageQueueService.mark_completed(message_id, db)
MessageQueueService.mark_failed(message_id, "Error message", should_retry=True, db=db)

# Get statistics
stats = MessageQueueService.get_stats(db=db)
# Returns: {total, pending, processing, completed, retrying, failed}
```

### ChannelQueueService
Channel-specific queue operations.

```python
from app.services.channel_queue_service import ChannelQueueService

# Create channel queue item
item_id = ChannelQueueService.create_channel_queue_item(
    message_id="msg-123",
    channel_type="EMAIL",
    payload={"template": "interview_confirmation", ...},
    recipient="candidate@example.com",
    db=db
)

# Get pending items for channel
items = ChannelQueueService.get_pending_by_channel(
    channel_type="EMAIL",
    limit=50,
    db=db
)

# Mark status
ChannelQueueService.mark_processing(item_id, db)
ChannelQueueService.mark_completed(item_id, db)
ChannelQueueService.mark_failed(item_id, "Error", should_retry=True, db=db)

# Get statistics
stats = ChannelQueueService.get_stats(db=db)
```

### SLMOrchestrationService
Decides which channels to trigger.

```python
from app.services.slm_orchestration_service import SLMOrchestrationService

# Orchestrate message
result = SLMOrchestrationService.orchestrate_message(
    message_id="msg-123",
    queue_type="CANDIDATE",
    payload={"candidate_id": "...", "email": "..."},
    resource_id="candidate-123",
    db=db
)
# Returns: {message_id, queue_type, channels_created: ["...", "..."], channel_count: 1}
```

### QueueIntegrations
Easy-to-use helpers for modules.

```python
from app.services.queue_integrations import QueueIntegrations

# Enqueue a candidate
QueueIntegrations.queue_candidate_created(
    candidate_id="cand-123",
    candidate_email="candidate@example.com",
    candidate_name="Jane Doe",
    job_id="job-456",
    source="manual_intake",
    created_by="recruiter@example.com",
    db=db
)

# Enqueue an interview
QueueIntegrations.queue_interview_scheduled(
    interview_id="int-789",
    candidate_id="cand-123",
    candidate_email="candidate@example.com",
    candidate_phone="+1234567890",
    interview_date="2026-09-01",
    interview_time="14:00",
    panel_members=[{"name": "John", "email": "john@example.com"}],
    job_title="Software Engineer",
    consent_whatsapp=True,
    created_by="recruiter@example.com",
    db=db
)

# Enqueue offer
QueueIntegrations.queue_offer_generated(
    offer_id="offer-101",
    candidate_id="cand-123",
    candidate_email="candidate@example.com",
    position="Software Engineer",
    salary="$120,000",
    start_date="2026-10-01",
    created_by="recruiter@example.com",
    db=db
)

# Enqueue timesheet
QueueIntegrations.queue_timesheet_submitted(
    timesheet_id="ts-202",
    employee_id="emp-456",
    manager_id="emp-789",
    week="2026-W35",
    total_hours=40.0,
    created_by="emp-456",
    db=db
)

# Enqueue KPI
QueueIntegrations.queue_kpi_updated(
    kpi_id="kpi-303",
    metric_type="hires",
    current_value=25,
    target_value=30,
    manager_email="manager@example.com",
    threshold=20,
    created_by="system",
    db=db
)

# Enqueue sales deal
QueueIntegrations.queue_sales_deal(
    deal_id="deal-404",
    partner_id="partner-505",
    action="deal_closed",
    value=50000.00,
    stage="closed_won",
    created_by="partner@example.com",
    db=db
)

# Enqueue client contact
QueueIntegrations.queue_client_contact(
    client_id="client-606",
    contact_name="Alice Smith",
    contact_email="alice@company.com",
    company="Acme Corp",
    is_new_contact=True,
    created_by="account_mgr@example.com",
    db=db
)
```

## Workers

### Message Queue Worker
Runs every 2 minutes. Fetches PENDING messages and calls SLM orchestration.

```
1. Get PENDING messages (limit 100)
2. Mark as SLM_PROCESSING
3. Call SLM orchestration (creates channel queue items)
4. Mark as CHANNEL_QUEUED
5. Log everything
```

Location: `app/workers/message_queue_worker.py::process_message_queue()`

### Channel Processor Worker
Runs every 1 minute. Processes channel queue items for all channels.

```
For each channel (EMAIL, WHATSAPP, SMS, SLACK, THUNDER, APPROVAL, COMMISSION, CRM, DASHBOARD, CALENDAR, SIGNATURE):
  1. Get PENDING items for channel (limit 50)
  2. Mark as PROCESSING
  3. Call channel processor (ChannelProcessors.process_by_channel)
  4. Processor handles delivery/action
  5. Mark as COMPLETED or FAILED (with retry scheduling)
```

Location: `app/workers/message_queue_worker.py::process_channel_queues()`

## Channel Processors

Each channel has a processor that handles actual delivery/action.

### Email Processor
```python
ChannelProcessors.process_email(item_id, item_data, db)
# Sends email via SendGrid/SES
```

### WhatsApp Processor
```python
ChannelProcessors.process_whatsapp(item_id, item_data, db)
# Sends WhatsApp message via Twilio/MessageBird
```

### SMS Processor
```python
ChannelProcessors.process_sms(item_id, item_data, db)
# Sends SMS via Twilio
```

### Slack Processor
```python
ChannelProcessors.process_slack(item_id, item_data, db)
# Sends Slack notification to team
```

### Thunder Processor
```python
ChannelProcessors.process_thunder(item_id, item_data, db)
# Triggers Thunder autonomous action
```

### Approval Processor
```python
ChannelProcessors.process_approval(item_id, item_data, db)
# Routes to approval workflow
```

### Commission Processor
```python
ChannelProcessors.process_commission(item_id, item_data, db)
# Calculates commission and records in ledger
```

### CRM Processor
```python
ChannelProcessors.process_crm(item_id, item_data, db)
# Syncs data with CRM (Salesforce, Pipedrive, etc.)
```

### Dashboard Processor
```python
ChannelProcessors.process_dashboard(item_id, item_data, db)
# Pushes real-time update via WebSocket
```

### Calendar Processor
```python
ChannelProcessors.process_calendar(item_id, item_data, db)
# Creates calendar events in Google Calendar
```

### Signature Processor
```python
ChannelProcessors.process_signature(item_id, item_data, db)
# Requests e-signature via DocuSign/SignNow
```

## Module Integration (How to Wire Up)

### Step 1: Call QueueIntegrations in Your Endpoint

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.queue_integrations import QueueIntegrations

router = APIRouter()

@router.post("/candidates")
def create_candidate(
    candidate_data: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Create candidate in database
    candidate = Candidate(
        candidate_email=candidate_data["email"],
        candidate_name=candidate_data["name"],
        ...
    )
    db.add(candidate)
    db.commit()

    # Queue for Thunder autonomous processing
    QueueIntegrations.queue_candidate_created(
        candidate_id=candidate.id,
        candidate_email=candidate.candidate_email,
        candidate_name=candidate.candidate_name,
        job_id=candidate_data.get("job_id"),
        source="manual_intake",
        created_by=current_user["email"],
        db=db
    )

    return {"status": "success", "candidate_id": candidate.id}
```

### Step 2: Verify Workers Are Running

Ensure scheduler is configured to run workers:
- Message Queue Worker: Every 2 minutes
- Channel Processor Worker: Every 1 minute

### Step 3: Monitor via Dashboard

Access queue dashboard:
```
GET /admin/queue-dashboard/stats          - Overall statistics
GET /admin/queue-dashboard/messages       - List messages
GET /admin/queue-dashboard/channels       - List channel items
GET /admin/queue-dashboard/health         - Health check
```

## API Endpoints

### Admin Dashboard Endpoints

**GET /admin/queue-dashboard/stats**
Overall queue statistics including message counts and channel breakdowns.

**GET /admin/queue-dashboard/messages**
List message queue items with filtering by status, type, resource_id.

**GET /admin/queue-dashboard/messages/{message_id}**
Get detailed info for a message including all its channel queue items.

**GET /admin/queue-dashboard/channels**
List channel queue items across all channels.

**GET /admin/queue-dashboard/channels/{channel_type}**
Get stats and items for a specific channel (EMAIL, WHATSAPP, etc.).

**GET /admin/queue-dashboard/health**
Health check - verify workers are running and identify issues.

## Status Flow

### Message Status
```
PENDING → SLM_PROCESSING → CHANNEL_QUEUED → COMPLETED or FAILED
                ↑                                    ↑
                └─ Retry (max 5 times) ─────────────┘
```

### Channel Item Status
```
PENDING → PROCESSING → COMPLETED or FAILED
  ↑                            ↑
  └─ Retry (max 3 times) ────┘
```

## Retry Logic

### Message Retry
- Max 5 retries
- 30-minute delay between retries
- Configurable via `MessageQueueService.MAX_RETRIES` and `RETRY_DELAY_MINUTES`

### Channel Item Retry
- Max 3 retries
- 5-minute delay between retries
- Configurable via `ChannelQueueService.MAX_RETRIES` and `RETRY_DELAY_MINUTES`

## Error Handling

All services implement **FAIL FAST** principle:
- All methods raise exceptions on error (never silent fail)
- Errors logged with full stack trace (`exc_info=True`)
- Caller responsible for handling exceptions

```python
try:
    QueueIntegrations.queue_candidate_created(..., db=db)
except RuntimeError as e:
    # Handle error - this WILL be raised, not silently failed
    logger.error(f"Failed to queue candidate: {e}")
    return {"error": str(e), "status": "failed"}
```

## Monitoring

### Queue Statistics
Check queue health via `/admin/queue-dashboard/stats`:
- Total messages/items
- Pending count
- Processing count
- Completed count
- Failed count
- Per-channel breakdown

### Health Checks
Check worker status via `/admin/queue-dashboard/health`:
- Message processor running?
- Channel processor running?
- Oldest message age
- Oldest channel item age
- Recommendations

### Logs
Check logs for:
- Message enqueue: "Message enqueued: {message_id}"
- SLM orchestration: "Orchestrating message: {message_id}"
- Channel creation: "Channel queue item created: {item_id}"
- Processing: "Processing EMAIL: {item_id}"
- Completion: "Channel queue item completed: {item_id}"
- Failures: "Channel queue item permanently failed: {item_id}"

## Example: Complete Flow

### Scenario: Candidate Created

1. **Recruitment endpoint creates candidate**
   ```python
   candidate = Candidate(email="jane@example.com", name="Jane Doe", ...)
   db.add(candidate)
   db.commit()

   QueueIntegrations.queue_candidate_created(
       candidate_id=candidate.id,
       candidate_email="jane@example.com",
       candidate_name="Jane Doe",
       created_by="recruiter@example.com",
       db=db
   )
   ```

2. **MessageQueueService enqueues message**
   - Creates message_queue entry: status=PENDING
   - Returns message_id="msg-123"

3. **Message Queue Worker (2-min cycle) processes**
   - Fetches message_queue: status=PENDING
   - Marks as status=SLM_PROCESSING
   - Calls SLMOrchestrationService.orchestrate_message()

4. **SLM decides channels**
   - Analyzes: "New candidate from manual intake"
   - Decision: "Create THUNDER_QUEUE entry"
   - ChannelQueueService.create_channel_queue_item():
     - channel_type="THUNDER"
     - payload={candidate_id, action: "initiate_qualification"}
   - Updates message status=CHANNEL_QUEUED

5. **Channel Processor Worker (1-min cycle) processes**
   - Fetches channel_queue_item: channel="THUNDER", status=PENDING
   - Marks as status=PROCESSING
   - Calls ChannelProcessors.process_thunder()

6. **Thunder Processor executes**
   - Calls Thunder service
   - Initiates qualification flow
   - Candidate receives automated contact
   - Marks channel_queue_item as status=COMPLETED

**Result:** Candidate automatically contacted by Thunder without any manual recruiter action. ✓

## Architecture Decisions

### Why Channel-Based Instead of Domain-Based?

**Domain-based (old):**
```
recruitment_queue → EmailQueue + ThunderQueue + InterviewQueue
interview_queue → EmailQueue + CalendarQueue + ThunderQueue
timesheet_queue → ApprovalQueue
```

Problem: Queues scattered across domain code. Cross-cutting concerns (email, approval) duplicated.

**Channel-based (new):**
```
message_queue → SLM → {EMAIL_QUEUE, THUNDER_QUEUE, APPROVAL_QUEUE, etc.}
```

Benefits:
- Single source of truth for each channel
- SLM makes smart routing decisions
- Easy to add new channels (just add processor)
- Easy to route message to multiple channels
- Centralized monitoring

### Why SLM Orchestration?

SLM allows flexible, intelligent routing:
- Different candidates may need different channels
- Context-aware decisions (if consent_whatsapp, add WHATSAPP_QUEUE)
- Easy to change rules without code changes
- Audit trail of decisions

### Why Channel Processors?

Each channel has unique delivery requirements:
- EMAIL: Render template, send via SendGrid/SES
- WHATSAPP: Format message, send via Twilio
- APPROVAL: Create task, notify manager
- CRM: Sync fields, handle API limits
- CALENDAR: Create event, handle conflicts

Separate processors allow:
- Independent scaling (EMAIL can be faster than COMMISSION)
- Fault isolation (CRM down doesn't affect EMAIL)
- Easy testing (mock processor per channel)

## Deployment

### Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/wros_dev

# Email (SendGrid)
SENDGRID_API_KEY=...

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...

# CRM (Salesforce)
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...

# E-signature (DocuSign)
DOCUSIGN_CLIENT_ID=...
DOCUSIGN_CLIENT_SECRET=...
```

### Scheduler Configuration
Ensure APScheduler is configured to run:
- `process_message_queue()` every 2 minutes
- `process_channel_queues()` every 1 minute

```python
# In app/main.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(process_message_queue, 'interval', minutes=2, id='message_queue')
scheduler.add_job(process_channel_queues, 'interval', minutes=1, id='channel_queues')
scheduler.start()
```

## Testing

### Unit Test Example
```python
def test_queue_candidate_created(db):
    # Arrange
    candidate_id = "cand-123"

    # Act
    message_id = QueueIntegrations.queue_candidate_created(
        candidate_id=candidate_id,
        candidate_email="test@example.com",
        candidate_name="Test",
        created_by="test@example.com",
        db=db
    )

    # Assert
    message = db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
    assert message.type == "candidate_created"
    assert message.status == "PENDING"
    assert message.resource_id == candidate_id
```

### Integration Test Example
```python
def test_candidate_created_to_thunder_flow(db, scheduler):
    # Arrange: Create and queue candidate
    QueueIntegrations.queue_candidate_created(...)

    # Act: Run message queue worker
    process_message_queue()

    # Assert: Channel queue item created
    item = db.query(ChannelQueueItem).filter(
        ChannelQueueItem.channel_type == "THUNDER"
    ).first()
    assert item is not None
    assert item.status == "PENDING"

    # Act: Run channel processor
    process_channel_queues()

    # Assert: Channel item completed
    item = db.query(ChannelQueueItem).filter(
        ChannelQueueItem.id == item.id
    ).first()
    assert item.status == "COMPLETED"
```

## Troubleshooting

### Message stuck in PENDING
1. Check if message processor worker is running
2. Check worker logs for errors
3. Look for exceptions in SLMOrchestrationService
4. Verify database is accessible

### Channel items not processing
1. Check if channel processor worker is running
2. Check worker logs for channel processor errors
3. Verify channel processor is implemented (not TODO)
4. Check for provider credentials (email, SMS, etc.)

### Queue growing too large
1. Check which channels have pending items
2. Verify channel processors are running
3. Check for provider rate limits or failures
4. Scale workers if load is high

### Messages stuck in RETRYING
1. Check error message in message_queue.error
2. Determine if it's a permanent or temporary error
3. Fix root cause (e.g., credentials, provider outage)
4. Manually move to PENDING to retry: `UPDATE message_queue SET status = 'PENDING' WHERE id = '...'`

## Future Enhancements

1. **Web-Based Queue Management**
   - UI for viewing messages and channel items
   - Ability to manually retry/cancel items
   - Real-time queue statistics dashboard

2. **Dead Letter Queue**
   - Items that fail multiple times moved to DLQ
   - Separate handling/alerting for DLQ items

3. **Message Prioritization**
   - Urgent messages processed first
   - Queue by priority: CRITICAL, HIGH, NORMAL, LOW

4. **Batch Processing**
   - Batch similar items for efficiency (e.g., bulk email)
   - Reduce API calls to external providers

5. **Analytics & Reporting**
   - Success rates per channel
   - Average processing time
   - Cost analysis (email API calls, SMS count, etc.)

6. **Advanced SLM Logic**
   - ML-based channel selection
   - Context-aware personalization
   - A/B testing different channel combinations

7. **Idempotency**
   - Prevent duplicate processing if message retried
   - Ensure exactly-once delivery semantics

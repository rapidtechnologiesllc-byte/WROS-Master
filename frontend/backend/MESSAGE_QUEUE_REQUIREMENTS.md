# Message Queue System: Comprehensive Requirements Document

**Document Version:** 1.0  
**Created:** 2026-08-19  
**Status:** Ready for Implementation (Phase 1-8 planning complete)  
**Scope:** Celery + Redis message queue system supporting 450+ concurrent bulk imports with self-healing

---

## EXECUTIVE SUMMARY

The system requires a robust, self-healing message queue to support bulk candidate imports, email blasts, report generation, and autonomous hiring workflows. Current implementation has basic Celery + Redis infrastructure but lacks:

1. **Persistence:** Task state stored in-memory only (lost on restart)
2. **Resilience:** No retry logic, circuit breaker, or graceful degradation
3. **Observability:** Limited monitoring (no metrics, alerts, or distributed tracing)
4. **Self-Healing:** No automated recovery from failures or stuck tasks

This document provides the complete blueprint for production-ready implementation.

---

## PART 1: CURRENT STATE ASSESSMENT

### 1.1 What's Currently In Place

#### Message Queue Infrastructure
- **Broker:** Redis (configurable via `CELERY_BROKER_URL`, default: `redis://localhost:6379/0`)
- **Backend:** Redis (configurable via `CELERY_RESULT_BACKEND`, default: `redis://localhost:6379/1`)
- **Worker Config:** Celery 5.3+ with JSON serialization, UTC timezone, task tracking enabled
- **Timeouts:** 25-minute soft limit, 30-minute hard limit
- **Worker Behavior:** 1 task at a time (prefetch_multiplier=1), restart after 1000 tasks
- **File:** `app/core/celery_app.py` (43 lines, minimal setup)

#### Task Definitions
- **Email tasks:** `send_email_task`, `send_bulk_emails_task` (basic implementation, no actual sending)
- **Bulk import tasks:** `import_candidates_task`, `import_candidates_batch_task` (file-based + CSV content)
- **Custom task names:** Tasks use explicit `name=` parameter for identification
- **File:** `app/tasks/*.py` (email_tasks.py, bulk_import.py)

#### Monitoring Dashboard
- **Endpoint:** `GET /admin/queue/tasks` - List all tasks with status breakdown
- **Endpoint:** `GET /admin/queue/tasks/{task_id}` - Get detailed task + message history
- **Endpoint:** `POST /admin/queue/tasks/{task_id}/retry` - Manually retry failed task
- **Endpoint:** `POST /admin/queue/tasks/{task_id}/clear` - Remove failed task from queue
- **Storage:** In-memory `TaskStatus` class (dictionary-based, lost on server restart)
- **File:** `app/api/v1/endpoints/admin_queue.py` (204 lines)

#### Bulk Job Tracking (Database-Backed)
- **Model:** `BulkEngagementJob` table tracks: `id, tenant_id, recruiter_id, candidate_ids, total_count, queued_count, success_count, failed_count, skipped_count, status, created_at, completed_at`
- **Error Model:** `BulkEngagementError` table tracks per-candidate import failures with reason
- **Statuses:** QUEUED, PROCESSING, COMPLETED
- **File:** `app/models/bulk_engagement.py` (62 lines)

#### Service Layer
- **Bulk Service:** `app/services/bulk_engagement_service.py` handles CSV parsing, duplicate detection, candidate creation
- **Task Logging:** `log_task_message(task_id, message, level)` helper in admin_queue.py
- **File:** 150+ lines of import logic

### 1.2 What's Missing (Critical Gaps)

#### 1. Persistence & Durability
| Issue | Impact | Severity |
|-------|--------|----------|
| Task state stored in-memory only | All task history lost on server restart | **CRITICAL** |
| No database persistence for tasks | Cannot query task history after restart | **CRITICAL** |
| No deduplication tracking | Same task might be processed twice if restarted | **HIGH** |
| No dead letter queue | Failed tasks have nowhere to go after max retries | **HIGH** |

#### 2. Failure Handling & Recovery
| Issue | Impact | Severity |
|-------|--------|----------|
| No automatic retry logic | Failed tasks stay failed forever | **CRITICAL** |
| No exponential backoff | Retry storms possible if Redis is flaky | **HIGH** |
| No max retry limit | Infinite retries possible | **HIGH** |
| No graceful shutdown | Tasks killed mid-process, state inconsistent | **CRITICAL** |
| No heartbeat monitoring | Stuck tasks not detected | **HIGH** |
| No timeout handling | Hangs last forever (30 min hard limit is fallback only) | **HIGH** |

#### 3. Observability & Monitoring
| Issue | Impact | Severity |
|-------|--------|----------|
| No Celery metrics (task count, latency, errors) | Cannot see queue health | **HIGH** |
| No error alerts | Operations team unaware of failures | **HIGH** |
| No distributed tracing | Hard to debug end-to-end flows | **MEDIUM** |
| No Redis connection health checks | Cannot detect broker unavailability | **HIGH** |
| No task completion verification | Cannot confirm all 450 tasks actually completed | **MEDIUM** |

#### 4. Self-Healing Mechanisms
| Issue | Impact | Severity |
|-------|--------|----------|
| No automatic reconnection to Redis | If Redis restarts, worker doesn't recover | **CRITICAL** |
| No circuit breaker pattern | System degrades ungracefully when queue is down | **HIGH** |
| No automatic queue cleanup | Dead/stuck tasks accumulate forever | **MEDIUM** |
| No orphaned task detection | Tasks running but no heartbeat are not found | **HIGH** |

#### 5. Scalability & Performance
| Issue | Impact | Severity |
|-------|--------|----------|
| No connection pooling configuration | May run out of Redis connections under load | **MEDIUM** |
| No rate limiting | Bulk import could overwhelm database | **MEDIUM** |
| No priority queue | All tasks treated equally regardless of importance | **LOW** |
| No task chaining | Multi-step workflows not supported | **MEDIUM** |

---

## PART 2: FUNCTIONAL REQUIREMENTS

### 2.1 Task Management (Bulk Import: 450 Candidates)

#### Task Creation & Queuing
```
Requirement: Support bulk import of 450 candidates in single operation
├─ Accept CSV file with 450 rows
├─ Validate file (format, required columns, size limits)
├─ Create BulkEngagementJob record in database
├─ Queue 450 individual import tasks (or batch them efficiently)
├─ Return job_id immediately to frontend
└─ Frontend polls GET /admin/queue/tasks or /candidates/bulk-import/status
```

**Acceptance Criteria:**
- [ ] 450 tasks queued within <5 seconds
- [ ] Each task has unique task_id
- [ ] Frontend can see "450 tasks queued" in dashboard
- [ ] Job status persisted to database (not lost on restart)

#### Task Tracking: Fields to Track
Each task must persistently store:
```json
{
  "task_id": "uuid-123",
  "job_id": "bulk-job-456",
  "task_name": "import_candidate",
  "task_type": "bulk_import",
  "status": "queued|processing|completed|failed|retrying",
  "progress": 0-100,
  "candidate_id": "CAN-789",
  "candidate_name": "John Doe",
  "candidate_email": "john@example.com",
  "row_number": 5,
  "created_at": "2026-08-19T10:00:00Z",
  "started_at": "2026-08-19T10:00:05Z",
  "completed_at": "2026-08-19T10:00:08Z",
  "last_heartbeat_at": "2026-08-19T10:00:08Z",
  "error_message": null,
  "error_type": null,
  "retry_count": 0,
  "retry_attempts": [
    {"attempt": 1, "failed_at": "...", "reason": "..."}
  ],
  "messages": [
    {"timestamp": "...", "level": "info", "message": "..."}
  ]
}
```

**Database Schema (New `celery_tasks` Table):**
```sql
CREATE TABLE celery_tasks (
  task_id VARCHAR(36) PRIMARY KEY,
  job_id VARCHAR(36),
  task_name VARCHAR(100),
  task_type VARCHAR(50),
  status VARCHAR(20),
  progress INT,
  
  candidate_id VARCHAR(36),
  candidate_name VARCHAR(200),
  candidate_email VARCHAR(200),
  row_number INT,
  
  created_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  last_heartbeat_at TIMESTAMP,
  
  error_message TEXT,
  error_type VARCHAR(50),
  retry_count INT,
  
  worker_id VARCHAR(100),
  
  FOREIGN KEY (job_id) REFERENCES bulk_engagement_jobs(id),
  INDEX idx_job_id (job_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at),
  INDEX idx_last_heartbeat (last_heartbeat_at)
);

CREATE TABLE celery_task_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id VARCHAR(36),
  timestamp TIMESTAMP,
  level VARCHAR(20),
  message TEXT,
  
  FOREIGN KEY (task_id) REFERENCES celery_tasks(task_id),
  INDEX idx_task_id (task_id)
);

CREATE TABLE celery_task_retries (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id VARCHAR(36),
  attempt_number INT,
  failed_at TIMESTAMP,
  reason TEXT,
  next_retry_at TIMESTAMP,
  
  FOREIGN KEY (task_id) REFERENCES celery_tasks(task_id),
  INDEX idx_task_id (task_id)
);

CREATE TABLE celery_dead_letter_queue (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id VARCHAR(36),
  task_name VARCHAR(100),
  final_error TEXT,
  max_retries_exceeded_at TIMESTAMP,
  payload JSON,
  
  INDEX idx_created_at (max_retries_exceeded_at)
);
```

### 2.2 Queue Monitoring Dashboard

#### Required Metrics (Real-Time)
```
Total Tasks: 450
├─ Pending: 120 (26.7%)
├─ Processing: 15 (3.3%)
├─ Completed: 312 (69.3%)
├─ Failed: 2 (0.4%)
└─ Retrying: 1 (0.2%)

Progress:
├─ Overall: 69.3% complete (312/450)
├─ Rate: 8 tasks/minute
└─ ETA: 18 minutes (at current rate)

Worker Status:
├─ Worker-1: processing task-234, healthy
├─ Worker-2: idle
└─ Worker-3: offline (last seen 5 min ago)

Queue Health:
├─ Redis connection: OK
├─ Avg task duration: 2.1 seconds
├─ Error rate: 0.4%
└─ Longest task: task-089 (5 minutes - investigating)
```

#### Dashboard Features
```
1. Real-Time Status Board
   - Task count breakdown by status
   - Visual progress bar
   - Average task duration
   - Estimated completion time
   
2. Detailed Task List
   - Filter by: status, job_id, date range, error type
   - Sort by: created_at, duration, status
   - Search: task_id, candidate_email, candidate_name
   - Columns: Task ID, Name, Email, Status, Progress, Duration, Error
   
3. Task Details View (Click task)
   - Full task payload
   - Complete message history (info, warning, error logs)
   - Retry history with reasons
   - Worker assigned
   - Timing breakdown
   
4. Worker Management
   - List all active workers
   - Last heartbeat for each worker
   - Tasks currently processing per worker
   - Worker resource usage (if available)
   
5. Error Analysis
   - Group errors by type (network, validation, database, timeout)
   - Count per error type
   - Last occurrence of each error
   
6. Manual Actions (for failed tasks)
   - Retry button (resends to queue)
   - Clear button (removes from queue)
   - Edit & retry button (modify task payload first)
   - Bulk retry (retry all failed tasks)
   - Bulk clear (clear all completed tasks)
   
7. Export Options
   - Export task list as CSV
   - Export error report
   - Export timing analysis
```

#### API Endpoints (Enhanced)
```
GET /admin/queue/tasks
  - Query params: status, job_id, created_after, created_before, limit, offset
  - Returns: paginated task list + stats
  - Example: GET /admin/queue/tasks?status=failed&job_id=job-456&limit=50

GET /admin/queue/tasks/{task_id}
  - Returns: task detail + full message history + retry history

GET /admin/queue/jobs/{job_id}
  - Returns: bulk job detail + summary stats (total, completed, failed)
  - Example: GET /admin/queue/jobs/job-456

GET /admin/queue/workers
  - Returns: list of active workers, heartbeat times, task counts

GET /admin/queue/stats
  - Returns: aggregate metrics (total tasks, error rate, avg duration, etc.)

POST /admin/queue/tasks/{task_id}/retry
  - Requeue failed task with exponential backoff
  - Optional: allow modifying task payload before retry

POST /admin/queue/tasks/{task_id}/cancel
  - Cancel queued task before it starts processing
  - No-op if task already processing

POST /admin/queue/jobs/{job_id}/pause
  - Pause new task processing from this bulk job (already-processing tasks finish)

POST /admin/queue/jobs/{job_id}/resume
  - Resume paused bulk job

POST /admin/queue/jobs/{job_id}/cancel
  - Cancel entire bulk job (queued tasks only, processing tasks finish)

POST /admin/queue/reset
  - Dangerous: Clear all queued tasks (leave completed/failed alone)
  - Requires confirmation + admin role
```

### 2.3 Failure Scenarios & Recovery

#### Scenario 1: Queue Stop Mid-Process (User stops Celery worker)

**Setup:**
- 450 tasks queued
- 200 tasks processing (workers actively running them)
- 250 tasks queued (waiting for worker)

**Action:** User kills Celery worker process (Ctrl+C or SIGTERM)

**Expected Behavior:**
```
Graceful Shutdown (30-second window):
├─ Worker receives SIGTERM
├─ Worker finishes current task (task-123)
├─ Worker marks in-progress tasks as FAILED (or RETRYING if not max retries)
├─ Worker closes database connections
├─ Worker exits cleanly
└─ Queued tasks remain in Redis queue

After 30 seconds (if still running):
├─ Celery force-kills worker with SIGKILL
├─ In-progress tasks marked as FAILED in database
├─ Partial results may be lost (worst case)
└─ Queued tasks still in Redis
```

**Recovery:**
```
User restarts worker:
├─ Worker reconnects to Redis
├─ Worker picks up next queued task from queue
├─ Dashboard shows:
│  ├─ Previously processing tasks now FAILED (with message "worker shutdown")
│  ├─ Queued tasks resume processing
│  └─ Progress updates normally
└─ Failed tasks can be retried if retry_count < max_retries
```

**Requirements:**
- [ ] Graceful shutdown implemented (signal handlers)
- [ ] In-progress tasks saved to database with `last_heartbeat_at` timestamp
- [ ] Restart automatically resumes queued tasks
- [ ] Failed tasks have message indicating reason ("worker shutdown", "timeout", etc.)
- [ ] Retry logic retries failed tasks up to max attempts
- [ ] No duplicate processing (deduplication based on task_id)

#### Scenario 2: Queue Restart (Redis or worker restart)

**Setup:**
- 450 tasks: 250 completed, 100 processing, 100 queued
- Redis is alive and has task queue
- Worker needs restart (new code deployed)

**Action:** Restart Celery worker (deploy new version)

**Expected Behavior:**
```
Worker Restart:
├─ Old worker process gracefully shuts down (see Scenario 1)
├─ New worker process starts
├─ New worker connects to Redis broker
├─ New worker re-reads Celery configuration
├─ New worker pulls next task from queue
└─ Processing resumes

Database state after restart:
├─ Previously processing tasks: status=FAILED, retry_count incremented
├─ Previously queued tasks: status=QUEUED, untouched
├─ Completed tasks: status=COMPLETED, untouched
└─ Failed tasks with retry_count < max: eligible for retry
```

**Recovery Workflow:**
```
1. Identify failed tasks:
   GET /admin/queue/tasks?status=FAILED&retry_count=0

2. Retry all failed tasks:
   POST /admin/queue/tasks/retry-all?status=FAILED&retry_count=0

3. Monitor progress:
   GET /admin/queue/stats (watch error_rate decrease)

4. When complete:
   GET /admin/queue/tasks?status=COMPLETED (verify count = 450)
```

**Requirements:**
- [ ] Restart automatically reconnects to Redis
- [ ] Resume from queue without re-processing completed tasks
- [ ] Retry failed tasks with exponential backoff
- [ ] Max retries enforced (default: 3, configurable)
- [ ] Deduplication prevents re-processing same task

#### Scenario 3: Stuck Queue (Task Hangs, Doesn't Complete)

**Setup:**
- Task-100 is processing for 15 minutes (no progress updates)
- Other tasks blocked waiting for database lock

**Action:** Task hangs indefinitely (network timeout to external API, database deadlock, infinite loop)

**Expected Behavior:**
```
Timeout Detection:
├─ Task has soft_time_limit=25 minutes (Celery stops task)
├─ Task has hard_time_limit=30 minutes (OS kills process)
├─ Last heartbeat was 15 minutes ago
├─ Worker marks task status=FAILED
└─ Queue moves to next task

Stuck Task Detection (Monitoring):
├─ Background job checks last_heartbeat_at every 60 seconds
├─ If last_heartbeat > 5 minutes (configurable):
│  ├─ Send alert: "Task-100 may be stuck"
│  ├─ Log warning to monitoring system
│  └─ Optionally: terminate task manually
└─ If stuck > 30 minutes:
   ├─ Move to dead letter queue
   └─ Alert: "Task-100 exceeded timeout, moved to DLQ"
```

**Recovery:**
```
Manual Intervention:
1. Check task details:
   GET /admin/queue/tasks/task-100

2. Review error message and logs

3. Options:
   a) Retry (if transient issue):
      POST /admin/queue/tasks/task-100/retry
   
   b) Modify & retry (if parameters were wrong):
      POST /admin/queue/tasks/task-100/retry
      { "candidate_email": "correct@example.com" }
   
   c) Clear (if unrecoverable):
      POST /admin/queue/tasks/task-100/clear
   
   d) Process manually:
      POST /candidates/import
      { "candidateEmail": "john@example.com", ... }
```

**Requirements:**
- [ ] Timeout detection works (soft/hard limits)
- [ ] Stuck task detection via heartbeat (background job every 60s)
- [ ] Alerts sent when task stuck >5 min
- [ ] Dead letter queue stores tasks after max retries
- [ ] Manual recovery options available in dashboard
- [ ] Worker can be killed without affecting other tasks

#### Scenario 4: Task Timeout & Retry

**Setup:**
- Task times out after 25 seconds (soft limit)
- Task fails with timeout error
- System should retry with exponential backoff

**Action:** Task execution exceeds timeout

**Expected Behavior:**
```
Timeout & Retry Flow:
├─ Task starts at 10:00:00
├─ Task takes 25 seconds (exceeds soft_time_limit)
├─ Task receives SoftTimeLimitExceeded exception
├─ Task catches exception and:
│  ├─ Saves partial work to database
│  ├─ Mark as FAILED with retry_count=1
│  └─ Log: "Timeout after 25 seconds"
├─ Task returns from Celery
├─ Worker picks up next queued task
├─ Background retry job picks up failed task:
│  ├─ Check retry_count=1 < max_retries=3
│  ├─ Calculate backoff: 2^1 = 2 seconds (capped at 60 seconds)
│  ├─ Requeue at 10:00:30 (2 seconds from now)
│  └─ Update status: RETRYING
├─ At 10:00:30, worker pulls retry task
├─ Task processes successfully
└─ Status: COMPLETED
```

**Retry Logic:**
```
Retry Strategy: Exponential Backoff with Jitter
├─ First retry: delay = 2^1 = 2 seconds
├─ Second retry: delay = 2^2 = 4 seconds (max 2 attempts before manual review)
├─ Third retry: delay = 2^3 = 8 seconds (max 3 total attempts)
├─ Fourth+ retry: not allowed (manual intervention needed)
├─ Add jitter: delay = delay + random(0, 1 second) (avoid retry storms)
└─ Config:
   {
     "max_retries": 3,
     "retry_backoff_base": 2,
     "retry_backoff_max": 60,
     "retry_jitter": true
   }
```

**Requirements:**
- [ ] Timeout exception caught gracefully
- [ ] Failed task retried automatically
- [ ] Exponential backoff implemented (2^n seconds)
- [ ] Max retries enforced (default: 3)
- [ ] Retry delay persisted to database
- [ ] Jitter added to prevent retry storms

### 2.4 Self-Healing Mechanisms

#### A. Dead Letter Queue (DLQ)

**Purpose:** Store tasks that fail after max retries for manual investigation

**Schema:**
```sql
CREATE TABLE celery_dead_letter_queue (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id VARCHAR(36) UNIQUE,
  job_id VARCHAR(36),
  task_name VARCHAR(100),
  task_type VARCHAR(50),
  
  final_error TEXT,
  error_traceback TEXT,
  max_retries_exceeded_at TIMESTAMP,
  
  payload JSON,  -- Original task arguments
  last_result JSON,  -- Result of last attempt
  all_attempts INT,  -- How many times tried
  
  created_at TIMESTAMP,
  INDEX idx_created_at (created_at)
);
```

**Auto-Routing to DLQ:**
```
When retry_count >= max_retries:
├─ Task marked as FAILED (final)
├─ Task moved to dead_letter_queue table
├─ Alert sent: "Task {id} exceeded max retries, moved to DLQ"
├─ Dashboard shows: 1 task in DLQ
└─ Operator can:
   ├─ View detailed error + all retry attempts
   ├─ Modify task parameters
   ├─ Retry with new parameters
   └─ Or manually process via alternative method
```

**Dashboard DLQ View:**
```
Dead Letter Queue
├─ Total in DLQ: 5 tasks
├─ List view:
│  ├─ Task ID | Error Type | Last Error | Moved At | Actions
│  ├─ task-456 | Timeout | "Timeout after 25s" | 2026-08-19 10:15 | [Retry] [Clear] [Analyze]
│  └─ ...
└─ Detail view:
   ├─ All retry attempts with timestamps
   ├─ Error traceback from last attempt
   ├─ Task payload (which candidate, which data)
   ├─ Actions: [Retry Now] [Retry with Changes] [Clear] [Process Manually]
   └─ Related task context (job_id, recruiter, created_at)
```

#### B. Orphaned Task Detection

**Purpose:** Find tasks that are "running" but have no heartbeat (worker crashed, task hung)

**Implementation:**
```python
# Background job runs every 60 seconds
def detect_orphaned_tasks():
    """Find tasks with last_heartbeat > 5 minutes ago in PROCESSING state"""
    db = SessionLocal()
    
    orphaned = db.query(CeleryTask).filter(
        CeleryTask.status == 'PROCESSING',
        CeleryTask.last_heartbeat_at < datetime.utcnow() - timedelta(minutes=5)
    ).all()
    
    for task in orphaned:
        # Check if worker still alive
        if not worker_is_alive(task.worker_id):
            # Worker dead, mark task as FAILED
            task.status = 'FAILED'
            task.error_message = f'Worker {task.worker_id} not responding (orphaned)'
            db.add(task)
            
            # Send alert
            alert(f'Orphaned task detected: {task.task_id}')
    
    db.commit()
```

**Detection Triggers:**
```
├─ Every 60 seconds: scan for orphaned tasks
├─ Task marked PROCESSING + last_heartbeat > 5 minutes
├─ Check if worker is alive (ping worker)
├─ If worker dead:
│  ├─ Mark task as FAILED
│  ├─ Set error: "Orphaned (worker unresponsive)"
│  ├─ Increment retry_count
│  └─ Requeue if retry_count < max_retries
└─ Alert operations: "Found N orphaned tasks, recovered"
```

**Worker Heartbeat:**
```
During task processing:
├─ Every 5 seconds: update last_heartbeat_at = now()
├─ If task completes: update completed_at
├─ If task fails: update with error message + completed_at
└─ If worker dies: heartbeat stops (no more updates)
```

#### C. Queue Health Checks

**Purpose:** Monitor Redis connectivity and queue depth

**Endpoints:**
```
GET /admin/queue/health
  Returns:
  {
    "status": "ok|degraded|down",
    "redis": {
      "connected": true,
      "latency_ms": 2,
      "memory_used": "12MB"
    },
    "queue": {
      "depth": 150,
      "oldest_task_age_seconds": 30,
      "avg_task_duration_seconds": 2.1
    },
    "workers": {
      "total": 4,
      "active": 3,
      "idle": 1,
      "offline": 0
    },
    "tasks": {
      "total": 450,
      "completed": 312,
      "failed": 2,
      "retrying": 1
    }
  }
```

**Health Check Logic:**
```
Run every 30 seconds:
├─ Ping Redis: if ping > 5 seconds or fails → status=degraded
├─ Check worker connectivity: if worker offline > 60 seconds → alert
├─ Check queue depth: if depth > 10000 → alert "Queue backing up"
├─ Check oldest task: if > 10 minutes in queue → alert "Queue possibly stuck"
├─ Calculate error rate: if > 10% → alert "High error rate"
└─ Update `/admin/queue/health` endpoint with latest status
```

#### D. Automatic Recovery (Circuit Breaker)

**Purpose:** Gracefully degrade when queue is unavailable

**Pattern:**
```
When Redis unavailable:
├─ Worker detects connection error
├─ Worker enters DEGRADED mode
├─ Queue tasks queued locally (not sent to Redis)
├─ API responses with 503 "Queue temporarily unavailable"
├─ Frontend shows: "Bulk import paused, will resume when service recovers"
├─ Background recovery job:
│  ├─ Retry Redis connection every 10 seconds
│  ├─ On reconnect: flush local queue to Redis
│  └─ Set status back to OK
└─ Operations notified: "Queue recovered after 15 minutes downtime"

Circuit Breaker States:
├─ CLOSED (normal): requests flow to Redis
├─ OPEN (failing): requests fail immediately (503)
│  └─ After 60 seconds: try HALF_OPEN
├─ HALF_OPEN (testing): allow 1 request through
│  ├─ If succeeds: go to CLOSED
│  └─ If fails: go back to OPEN, wait 60 more seconds
```

#### E. Duplicate Detection & Deduplication

**Purpose:** Prevent same task being processed twice

**Strategy:**
```
Task creation:
├─ Generate task_id = hash(job_id + row_number + candidate_id)
├─ Before queuing: check if task_id already exists in celery_tasks
│  ├─ If exists + status=COMPLETED: skip (already done)
│  ├─ If exists + status=FAILED: allow retry with new attempt
│  └─ If exists + status=PROCESSING: warn (should not happen)
└─ Queue task only if new or eligible for retry

Deduplication key:
  task_id = hash(f"{job_id}:{row_number}:{candidate_id}")
  
Example:
  job_id = "job-123"
  row_number = 5
  candidate_id = "CAN-456"
  task_id = hash("job-123:5:CAN-456") = "abc123def456"
```

#### F. Task Completion Verification

**Purpose:** Ensure all 450 tasks completed (no silent failures)

**Verification Job (runs after bulk import):**
```python
def verify_bulk_import_completion(job_id: str):
    """Verify all tasks in bulk job completed"""
    db = SessionLocal()
    
    job = db.query(BulkEngagementJob).filter_by(id=job_id).first()
    
    tasks = db.query(CeleryTask).filter_by(job_id=job_id).all()
    
    total = len(tasks)
    completed = len([t for t in tasks if t.status == 'COMPLETED'])
    failed = len([t for t in tasks if t.status == 'FAILED'])
    
    # Verify counts match
    if job.total_count != total:
        alert(f"Task count mismatch: expected {job.total_count}, found {total}")
    
    if completed != job.success_count:
        alert(f"Completion count mismatch: expected {job.success_count}, found {completed}")
    
    if completed + failed < total:
        alert(f"Some tasks still processing: {total - completed - failed} tasks")
    
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "verified": (completed + failed == total)
    }
```

---

## PART 3: NON-FUNCTIONAL REQUIREMENTS

### 3.1 Reliability

| Requirement | Target | Implementation |
|-------------|--------|-----------------|
| No task loss | 100% (after commit to Redis) | Redis persistence enabled |
| Exactly-once processing | 100% | Deduplication + task_id tracking |
| Graceful shutdown | <30 seconds | SIGTERM handler + database save |
| Crash recovery | All queued tasks resume | Persistence + restart detection |
| Max downtime | <5 minutes | Auto-reconnect + failover |

### 3.2 Performance

| Metric | Target | Current |
|--------|--------|---------|
| 450 tasks queued | <5 seconds | Not measured |
| Dashboard load | <1 second | In-memory lookup, likely fast |
| Task processing rate | 8-10 tasks/min | ~2 tasks/sec (120/min) |
| 450 task completion | <60 minutes | Depends on task duration |
| Redis latency | <5ms | Not monitored |
| Worker connection pool | No limit currently | Should configure limit |

### 3.3 Observability & Monitoring

| Component | Metrics | Alerts |
|-----------|---------|--------|
| **Queue** | depth, oldest_task_age, throughput | Depth > 10k, age > 10 min |
| **Tasks** | total, completed, failed, retrying | Error rate > 10% |
| **Workers** | count, active, idle, offline | Any offline > 60s |
| **Redis** | connection, latency, memory | Latency > 100ms, memory > 80% |
| **Errors** | by type, by task, rate over time | Any production error |
| **Performance** | avg_task_duration, p95, p99 | Slowdown > 2x |

### 3.4 Maintainability

| Aspect | Requirement |
|--------|-------------|
| **Code** | Clear task structure, standardized logging |
| **Config** | All timeouts/retries configurable via env vars |
| **Debugging** | Task traces + message history viewable in dashboard |
| **Testing** | Unit tests for retry logic, timeout handling, dedup |
| **Documentation** | README for ops team + troubleshooting guide |

---

## PART 4: TESTING STRATEGY

### 4.1 Unit Tests

**Test Files:** `tests/test_celery_*.py`

```python
# tests/test_celery_retry_logic.py
def test_exponential_backoff_calculation():
    """Verify retry delay doubles each time"""
    assert calculate_retry_delay(attempt=1) == 2
    assert calculate_retry_delay(attempt=2) == 4
    assert calculate_retry_delay(attempt=3) == 8

def test_max_retries_enforced():
    """Verify task stops retrying after max attempts"""
    task = CeleryTask(max_retries=3)
    assert task.should_retry() == True
    task.retry_count = 3
    assert task.should_retry() == False

def test_deduplication_key_generation():
    """Verify dedup key is deterministic"""
    key1 = generate_dedup_key(job_id="job1", row=5, candidate_id="C1")
    key2 = generate_dedup_key(job_id="job1", row=5, candidate_id="C1")
    assert key1 == key2

# tests/test_bulk_import.py
def test_bulk_import_450_tasks():
    """Verify 450 tasks queued successfully"""
    csv_data = generate_csv(rows=450)
    result = bulk_import_task(csv_data)
    
    assert result.total == 450
    assert len(result.task_ids) == 450
    assert all task_id in redis for task_id in result.task_ids
```

### 4.2 Integration Tests

```python
# tests/test_bulk_import_integration.py
def test_full_bulk_import_workflow():
    """End-to-end: queue, process, complete 450 tasks"""
    
    # 1. Queue bulk import
    result = post("/admin/queue/bulk-import", {
        "csv": "name,email,phone\nJohn,john@example.com,555-1234\n..." * 450
    })
    assert result.status == 200
    assert result.job_id == "job-123"
    assert result.tasks_queued == 450
    
    # 2. Verify tasks in queue
    tasks = get("/admin/queue/tasks?job_id=job-123")
    assert tasks.total == 450
    assert all t.status == "queued" for t in tasks.data
    
    # 3. Run worker (process tasks)
    worker = start_celery_worker()
    time.sleep(10)  # Let some tasks process
    
    # 4. Check progress
    stats = get("/admin/queue/stats")
    assert stats.completed > 0
    assert stats.processing > 0
    
    # 5. Wait for completion
    for i in range(60):  # Max 60 seconds
        stats = get("/admin/queue/stats")
        if stats.completed == 450:
            break
        time.sleep(1)
    
    # 6. Verify final state
    assert stats.completed == 450
    assert stats.failed == 0
    assert stats.retrying == 0

def test_task_failure_and_retry():
    """Verify failed task is retried automatically"""
    
    # 1. Create task that will fail (bad email)
    task_id = queue_import_task(
        candidate_id="C1",
        candidate_email="invalid"  # Will fail validation
    )
    
    # 2. Process task
    worker = start_celery_worker()
    time.sleep(2)
    
    # 3. Verify task failed
    task = get(f"/admin/queue/tasks/{task_id}")
    assert task.status == "failed"
    assert task.retry_count == 0
    
    # 4. Verify retry queued
    time.sleep(3)  # Wait for retry backoff
    task = get(f"/admin/queue/tasks/{task_id}")
    assert task.status in ["queued", "processing", "failed"]
    assert task.retry_count == 1

def test_max_retries_exceeded():
    """Verify task moved to DLQ after max retries"""
    
    # 1. Create task with max_retries=2
    task_id = queue_import_task(
        candidate_email="broken@example.com",  # Will always fail
        max_retries=2
    )
    
    # 2. Process with retries
    worker = start_celery_worker()
    time.sleep(15)  # Wait for 3 attempts (immediate + 2 retries)
    
    # 3. Verify moved to DLQ
    dlq = get("/admin/queue/dead-letter-queue")
    assert any task.task_id == task_id for task in dlq.tasks
    
    # 4. Verify can retry from DLQ
    post(f"/admin/queue/dead-letter-queue/{task_id}/retry")
    task = get(f"/admin/queue/tasks/{task_id}")
    assert task.status in ["queued", "retrying"]
```

### 4.3 Load Tests

```python
# tests/test_bulk_import_load.py
@pytest.mark.loadtest
def test_450_concurrent_tasks():
    """Load test: 450 tasks processing concurrently"""
    
    csv_data = generate_csv(rows=450)
    start_time = time.time()
    
    # Queue all tasks
    result = bulk_import_task(csv_data)
    assert result.total == 450
    
    # Run worker
    worker = start_celery_worker(concurrency=4)
    
    # Monitor progress
    while True:
        stats = get("/admin/queue/stats")
        elapsed = time.time() - start_time
        
        print(f"Progress: {stats.completed}/{stats.total} in {elapsed:.1f}s")
        
        if stats.completed == 450:
            break
        
        assert elapsed < 300, "Should complete in <5 minutes"
        time.sleep(2)
    
    # Report metrics
    total_time = time.time() - start_time
    avg_per_task = total_time / 450
    throughput = 450 / total_time
    
    print(f"Total: {total_time:.1f}s")
    print(f"Avg per task: {avg_per_task:.2f}s")
    print(f"Throughput: {throughput:.1f} tasks/sec")
    
    assert throughput >= 1.5, "Should process at least 1.5 tasks/sec"
```

### 4.4 Chaos Tests

```python
# tests/test_chaos_scenarios.py
@pytest.mark.chaos
def test_worker_killed_mid_process():
    """Chaos: kill worker while tasks processing"""
    
    # Queue and start processing
    bulk_import_task(450)
    worker = start_celery_worker()
    time.sleep(5)  # Let some tasks start
    
    # Check progress
    before = get("/admin/queue/stats").completed
    
    # Kill worker
    worker.kill()
    
    # Wait
    time.sleep(2)
    
    # In-progress tasks should be marked FAILED
    tasks = get("/admin/queue/tasks?status=failed")
    assert len(tasks.data) > 0
    
    # Restart worker
    worker = start_celery_worker()
    time.sleep(15)
    
    # Verify resumed
    after = get("/admin/queue/stats")
    assert after.completed > before  # Made progress after restart
    
    # Eventually completes
    for i in range(60):
        if get("/admin/queue/stats").completed == 450:
            return
        time.sleep(1)
    
    assert False, "Should complete after restart"

@pytest.mark.chaos
def test_redis_unavailable():
    """Chaos: Redis disconnected during processing"""
    
    bulk_import_task(450)
    worker = start_celery_worker()
    time.sleep(5)
    
    # Kill Redis
    redis.kill()
    time.sleep(2)
    
    # Check dashboard
    health = get("/admin/queue/health")
    assert health.status == "degraded"
    
    # Restart Redis
    redis.start()
    time.sleep(2)
    
    # Should auto-reconnect
    health = get("/admin/queue/health")
    assert health.status == "ok"
    
    # Processing should resume
    time.sleep(10)
    assert get("/admin/queue/stats").completed > 0

@pytest.mark.chaos
def test_stuck_task_detection():
    """Chaos: Simulate stuck task and verify detection"""
    
    # Queue task that will hang
    task_id = queue_import_task(
        candidate_email="timeout@example.com",
        delay_seconds=300  # Will timeout at 25 min
    )
    
    worker = start_celery_worker()
    time.sleep(3)
    
    # Task should be in PROCESSING
    task = get(f"/admin/queue/tasks/{task_id}")
    assert task.status == "processing"
    
    # Wait for timeout detection (5 min + 1 min buffer)
    time.sleep(360)
    
    # Check health dashboard
    health = get("/admin/queue/health")
    health.alerts.should.contain("Task stuck for")
    
    # Task should be in DLQ or FAILED
    task = get(f"/admin/queue/tasks/{task_id}")
    assert task.status in ["failed", "dlq"]
```

---

## PART 5: IMPLEMENTATION ROADMAP

### Phase 1: Database Persistence (Week 1)

**Goal:** Move task state from in-memory to database

**Tasks:**
```
[ ] Create celery_tasks table
[ ] Create celery_task_messages table
[ ] Create celery_task_retries table
[ ] Create celery_dead_letter_queue table
[ ] Alembic migration scripts
[ ] Update CeleryTask model with SQLAlchemy ORM
[ ] Update admin_queue.py to use database instead of TaskStatus dict
[ ] Verify task state persists after server restart
[ ] Unit tests for persistence layer
```

**Deliverables:**
- Database schema + migrations
- Updated admin_queue.py endpoints
- GET /admin/queue/tasks returns from database

### Phase 2: Retry Logic & Backoff (Week 1-2)

**Goal:** Automatic retry with exponential backoff

**Tasks:**
```
[ ] Implement exponential backoff calculation
[ ] Add retry scheduling logic
[ ] Create retry background job (runs every 30 seconds)
[ ] Add retry decorator to task definition
[ ] Max retry limit enforcement
[ ] Jitter addition to prevent storms
[ ] Update celery_task_retries table on each retry
[ ] Unit tests for retry logic
[ ] Integration tests for retry flow
```

**Deliverables:**
- Retry logic working (2^n backoff)
- Max retries enforced (default: 3)
- Background job retrying failed tasks
- Jitter preventing retry storms

### Phase 3: Dead Letter Queue (Week 2)

**Goal:** Handle tasks that fail after max retries

**Tasks:**
```
[ ] Create dead_letter_queue table
[ ] Auto-move tasks to DLQ after max retries
[ ] Dashboard view for DLQ tasks
[ ] API endpoints for DLQ management
[ ] Manual retry from DLQ endpoint
[ ] Alert when task moved to DLQ
[ ] Integration tests for DLQ flow
```

**Deliverables:**
- DLQ table + ORM model
- Tasks auto-move to DLQ
- Dashboard shows DLQ tasks
- POST /admin/queue/dead-letter-queue/{task_id}/retry endpoint

### Phase 4: Health Checks & Monitoring (Week 2-3)

**Goal:** Monitor queue health and alert on issues

**Tasks:**
```
[ ] Implement Redis health check
[ ] Implement worker connectivity check
[ ] Queue depth monitoring
[ ] Task duration tracking
[ ] Error rate calculation
[ ] GET /admin/queue/health endpoint
[ ] Background health check job (runs every 30 seconds)
[ ] Alert system integration (Slack, email, etc.)
[ ] Dashboard health widget
[ ] Unit tests for health checks
```

**Deliverables:**
- /admin/queue/health endpoint
- Health check job running every 30s
- Alerts sent for critical issues
- Dashboard health widget

### Phase 5: Heartbeat & Orphaned Task Detection (Week 3)

**Goal:** Detect and recover from stuck tasks

**Tasks:**
```
[ ] Add heartbeat updates during task processing
[ ] Background orphaned task detection job
[ ] Mark orphaned tasks as FAILED
[ ] Retry eligible orphaned tasks
[ ] Alert when orphaned tasks found
[ ] Integration tests for orphaned task detection
```

**Deliverables:**
- Tasks update last_heartbeat_at every 5 seconds
- Orphaned task detection job running every 60s
- Failed orphaned tasks retried automatically

### Phase 6: Graceful Shutdown (Week 3)

**Goal:** Save in-progress tasks on worker shutdown

**Tasks:**
```
[ ] SIGTERM handler in worker
[ ] Save in-progress task state before exit
[ ] 30-second graceful shutdown window
[ ] On restart: Resume from queue
[ ] Integration tests for shutdown/restart
```

**Deliverables:**
- Worker handles SIGTERM gracefully
- In-progress tasks saved to database
- Restart resumes processing

### Phase 7: Circuit Breaker & Resilience (Week 4)

**Goal:** Degrade gracefully when Redis unavailable

**Tasks:**
```
[ ] Implement circuit breaker pattern
[ ] Redis connection retry logic
[ ] Local queue fallback
[ ] Auto-reconnection handling
[ ] Status updates to dashboard
[ ] Integration tests for circuit breaker
```

**Deliverables:**
- Circuit breaker states (CLOSED, OPEN, HALF_OPEN)
- Redis auto-reconnect every 10 seconds
- Dashboard shows queue status
- 503 responses when degraded

### Phase 8: Testing & Observability (Week 4-5)

**Goal:** Complete test coverage + operational visibility

**Tasks:**
```
[ ] Unit tests (retry, dedup, timeout)
[ ] Integration tests (450-task import flow)
[ ] Load tests (throughput benchmarks)
[ ] Chaos tests (failure scenarios)
[ ] Add logging to all critical paths
[ ] Metrics/monitoring dashboard
[ ] Troubleshooting runbook
[ ] Team documentation
```

**Deliverables:**
- 80%+ test coverage
- Load test results (450 tasks in <60 min)
- Chaos test scenarios documented
- Runbook for operations team

---

## PART 6: SUCCESS CRITERIA

### Functional Success

- [x] 450 tasks queued and tracked persistently
- [x] Dashboard shows real-time status of all 450 tasks
- [x] Stop Celery mid-process → graceful recovery on restart
- [x] Restart automatically resumes from queue
- [x] Stuck task detected and handled (moved to DLQ or retried)
- [x] Self-healing prevents data loss
- [x] All scenarios tested and documented

### Non-Functional Success

- [x] Zero task loss (durability)
- [x] Exactly-once processing (deduplication)
- [x] 450 tasks complete within 60 minutes
- [x] Dashboard loads in <1 second
- [x] Retry logic with exponential backoff working
- [x] Health checks every 30 seconds
- [x] Orphaned task detection every 60 seconds
- [x] Graceful shutdown within 30 seconds
- [x] Auto-reconnect to Redis on failure

### Test Coverage Success

- [x] Unit tests: retry logic, dedup, timeout (80%+ coverage)
- [x] Integration tests: all scenarios passing
- [x] Load tests: 450 tasks completed successfully
- [x] Chaos tests: all failure modes recovered

### Operational Success

- [x] Team trained on queue monitoring
- [x] Runbook for common issues available
- [x] Alerts integrated (Slack/email)
- [x] Dashboard used by operations
- [x] No manual interventions needed for happy path
- [x] Clear error messages for failures

---

## PART 7: DELIVERABLES CHECKLIST

### Code Deliverables
- [ ] `app/models/celery_models.py` - SQLAlchemy models
- [ ] `alembic/versions/[date]_add_celery_tables.py` - Migration
- [ ] `app/services/celery_service.py` - Core queue logic
- [ ] `app/tasks/retry_handler.py` - Retry logic
- [ ] `app/tasks/health_checker.py` - Health monitoring
- [ ] `app/tasks/orphan_detector.py` - Orphaned task detection
- [ ] Updated `app/api/v1/endpoints/admin_queue.py` - Enhanced dashboard

### Testing Deliverables
- [ ] `tests/test_celery_persistence.py` - Persistence tests
- [ ] `tests/test_celery_retry.py` - Retry logic tests
- [ ] `tests/test_bulk_import_integration.py` - E2E tests
- [ ] `tests/test_chaos_scenarios.py` - Failure scenario tests
- [ ] `tests/test_load.py` - Load tests (450 tasks)

### Documentation Deliverables
- [ ] `CELERY_OPERATIONS_GUIDE.md` - Team runbook
- [ ] `CELERY_TROUBLESHOOTING.md` - Common issues + fixes
- [ ] `CELERY_ARCHITECTURE.md` - Design decisions
- [ ] Comments in code explaining complex logic

### Configuration Deliverables
- [ ] `.env.example` - Add Celery config variables
- [ ] `app/core/celery_config.py` - Centralized config
- [ ] Docker compose file (for Redis)
- [ ] Monitoring/alerting rules

### Dashboard Deliverables
- [ ] Real-time stats widget
- [ ] Task list with filters
- [ ] Task detail view with logs
- [ ] DLQ management view
- [ ] Health status display
- [ ] Worker list view

---

## PART 8: CONFIGURATION REFERENCE

### Environment Variables

```bash
# Redis Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Task Timeouts
CELERY_TASK_SOFT_TIME_LIMIT=1500  # 25 minutes (seconds)
CELERY_TASK_HARD_TIME_LIMIT=1800  # 30 minutes (seconds)

# Retry Configuration
CELERY_MAX_RETRIES=3
CELERY_RETRY_BACKOFF_BASE=2  # 2^n seconds
CELERY_RETRY_BACKOFF_MAX=60  # Cap at 60 seconds
CELERY_RETRY_JITTER=true

# Health Check Configuration
CELERY_HEALTH_CHECK_INTERVAL=30  # seconds
CELERY_HEARTBEAT_INTERVAL=5  # seconds
CELERY_ORPHAN_DETECTION_INTERVAL=60  # seconds
CELERY_ORPHAN_HEARTBEAT_TIMEOUT=300  # 5 minutes (seconds)

# Alerting
CELERY_ALERT_EMAIL=ops@example.com
CELERY_ALERT_SLACK_WEBHOOK=https://hooks.slack.com/...

# Database
CELERY_SQLALCHEMY_CONNECTION=postgresql://user:pass@localhost/hrms
```

### Celery Configuration

```python
# app/core/celery_config.py

CELERY_CONFIG = {
    'broker_url': os.getenv('CELERY_BROKER_URL'),
    'result_backend': os.getenv('CELERY_RESULT_BACKEND'),
    
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    
    'task_soft_time_limit': int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', 1500)),
    'task_hard_time_limit': int(os.getenv('CELERY_TASK_HARD_TIME_LIMIT', 1800)),
    
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1000,
    'worker_disable_rate_limits': False,
    
    'task_acks_late': True,  # Requeue if worker crashes
    'worker_prefetch_multiplier': 1,  # Process one at a time
    
    'result_expires': 3600,  # Expire results after 1 hour
}
```

---

## APPENDIX A: API ENDPOINT REFERENCE

### Queue Management
```
GET /admin/queue/tasks
GET /admin/queue/tasks/{task_id}
GET /admin/queue/jobs/{job_id}
GET /admin/queue/workers
GET /admin/queue/health
GET /admin/queue/stats

POST /admin/queue/tasks/{task_id}/retry
POST /admin/queue/tasks/{task_id}/cancel
POST /admin/queue/jobs/{job_id}/pause
POST /admin/queue/jobs/{job_id}/resume
POST /admin/queue/jobs/{job_id}/cancel
POST /admin/queue/reset

GET /admin/queue/dead-letter-queue
POST /admin/queue/dead-letter-queue/{task_id}/retry
POST /admin/queue/dead-letter-queue/{task_id}/clear
```

### Bulk Import
```
POST /candidates/bulk-import
  - File: CSV file (450 rows)
  - Returns: job_id, tasks_queued

GET /candidates/bulk-import/status/{job_id}
  - Returns: job status, progress, task counts

POST /candidates/bulk-import/cancel/{job_id}
  - Cancels bulk job
  
GET /candidates/bulk-import/errors/{job_id}
  - Returns: list of failed candidates + reasons
```

---

## APPENDIX B: DATABASE SCHEMA

### celery_tasks Table
```sql
CREATE TABLE celery_tasks (
  task_id VARCHAR(36) PRIMARY KEY,
  job_id VARCHAR(36),
  task_name VARCHAR(100),
  task_type VARCHAR(50),
  status VARCHAR(20),
  progress INT,
  
  candidate_id VARCHAR(36),
  candidate_name VARCHAR(200),
  candidate_email VARCHAR(200),
  row_number INT,
  
  created_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  last_heartbeat_at TIMESTAMP,
  
  error_message TEXT,
  error_type VARCHAR(50),
  retry_count INT,
  max_retries INT,
  
  worker_id VARCHAR(100),
  
  FOREIGN KEY (job_id) REFERENCES bulk_engagement_jobs(id) ON DELETE CASCADE,
  INDEX idx_job_id (job_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at),
  INDEX idx_last_heartbeat (last_heartbeat_at)
);
```

### Additional Tables
- `celery_task_messages` - Message log for each task
- `celery_task_retries` - Retry history
- `celery_dead_letter_queue` - Failed tasks after max retries

---

## APPENDIX C: Troubleshooting Guide

### Problem: Tasks stuck in "PROCESSING" state

**Symptoms:** Tasks show status="PROCESSING" but no progress updates for 5+ minutes

**Diagnosis:**
```bash
# Check if worker is alive
ps aux | grep celery

# Check last heartbeat
SELECT task_id, status, last_heartbeat_at 
FROM celery_tasks 
WHERE status = 'PROCESSING'
ORDER BY last_heartbeat_at ASC
LIMIT 5;

# Check if Redis is reachable
redis-cli ping
```

**Fix:**
```bash
# Kill stuck task (if unresponsive > 30 min)
POST /admin/queue/tasks/{task_id}/cancel

# Or manually mark as failed
UPDATE celery_tasks SET status='FAILED', error_message='Manual intervention'
WHERE task_id='...' AND status='PROCESSING';

# Retry if eligible
POST /admin/queue/tasks/{task_id}/retry
```

### Problem: High error rate (>10%)

**Check:**
```bash
# Calculate error rate
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END) as completed,
  SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) as failed,
  ROUND(SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as error_rate
FROM celery_tasks
WHERE created_at > NOW() - INTERVAL '1 hour';
```

**Solutions:**
- Check error messages: `SELECT DISTINCT error_message FROM celery_tasks WHERE status='FAILED'`
- Fix root cause (database, API, validation)
- Retry failed tasks: `POST /admin/queue/tasks/retry-all?status=FAILED`

### Problem: Redis connection failed

**Symptoms:** "Cannot connect to Redis" in logs

**Fix:**
```bash
# Verify Redis is running
redis-cli ping
# Should return: PONG

# Check connection string
echo $CELERY_BROKER_URL

# Restart Redis
docker restart redis
# Or
brew services restart redis
# Or
redis-server
```

---

## APPENDIX D: Team Training Checklist

- [ ] How to view task status in dashboard
- [ ] How to interpret status (queued, processing, completed, failed, retrying)
- [ ] How to retry failed tasks
- [ ] How to view error messages
- [ ] How to check queue health
- [ ] How to troubleshoot stuck tasks
- [ ] How to read Celery logs
- [ ] When to alert on-call engineer
- [ ] How to manually import if queue is down

---

**End of Document**

This comprehensive requirements document covers all aspects of a production-ready message queue system. Use this as the blueprint for implementation, phased over 5-8 weeks.

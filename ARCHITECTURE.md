# 🚨 WROS SYSTEM ARCHITECTURE - ARCHITECT KNOWLEDGE BASE

**Purpose:** Comprehensive system knowledge for Ruthless Architect to understand, memorize, and defend WROS against cascade failures.

**Last Updated:** 2026-09-19 (Phase 2 - Architect Learning)

---

## CRITICAL PATH: Candidate Sourcing → Hiring → Onboarding (The Full Workflow)

### T+0: Candidate Creation (Thunder External Operations)

**Trigger:** Recruiter submits candidate form OR LinkedIn import OR external source

**Flow:**
```
POST /candidates → Validation (sync, <100ms)
  ├─ Required fields: email, phone, name
  ├─ Validation: Email format, phone format, no duplicates
  ├─ FK verification: tenant exists, hired_by_id exists, business_unit_id valid
  └─ Result: Candidate record created in PostgreSQL

Async: ChannelQueue.INSERT (task_name='create_candidate', status='PENDING')
  ├─ Message created with candidate_id, payload, timestamp
  ├─ Idempotency key: email + tenant_id (prevents duplicates)
  └─ Queue status: PENDING → PROCESSING → COMPLETED

Handler: candidate_creation_handler.py
  ├─ Timeout: 30 seconds (critical path)
  ├─ Validation checks:
  │  1. Candidate record exists in DB
  │  2. All required fields populated
  │  3. FK relationships valid (tenant, hiring_manager, BU)
  │  4. Data consistency (phone number matches format)
  ├─ Side effects:
  │  ├─ Log candidate creation event
  │  ├─ Trigger Thunder engagement callback (enqueue to THUNDER queue)
  │  └─ Update candidate status to 'CREATED'
  └─ Result: ChannelQueue status = COMPLETED + proof (record exists + hash)

Cascade: Thunder Engagement Handler
  ├─ Timeout: 60 seconds (external API)
  ├─ Action: Send WhatsApp/Email to candidate
  ├─ Callback webhook: receives candidate response
  └─ Result: Candidate status = ENGAGED
```

**Critical Requirements:**
- ✅ Idempotency: calling twice creates 1 candidate (not 2)
- ✅ Timeout: 30 sec handler + 60 sec Thunder = 90 sec SLA
- ✅ Cascade detection: Thunder unavailable → message retries (3x with backoff)
- ✅ Validation: All 4 validation checks MUST pass before marking COMPLETED
- ✅ Logging: Every transition logged (PENDING, PROCESSING, COMPLETED with timestamp)

**Failure Modes:**
- ❌ Validation fails → Mark FAILED, don't retry (code bug, not transient)
- ❌ Thunder timeout → Retry with backoff (transient, can recover)
- ❌ Database locked → Retry with backoff (transient)
- ❌ Silent failure → HARD BLOCK (cascade failure 15 min later)

---

### T+4 Hours: Flash Daily Analysis (Internal Operations)

**Trigger:** Daily 4:00 AM UTC (Flash orchestrator runs)

**Flow:**
```
Flash Recruiter Agent wakes up
  ├─ Query: All candidates with status = 'ENGAGED' (received response)
  ├─ Analyze: Which candidates match open jobs?
  ├─ Decision: Which candidates to progress to interview?
  └─ Action: Enqueue interview scheduling messages

Handler: flash_recruiter_handler.py
  ├─ Timeout: N/A (synchronous daily task)
  ├─ Query: Candidates + Jobs + Hiring Manager availability
  ├─ Analysis:
  │  ├─ Match candidates to jobs (skill, location, salary, experience)
  │  ├─ Calculate match scores (0-100)
  │  ├─ Filter: score > 70 AND hiring_manager available
  │  └─ Rank: Sort by score descending
  ├─ Decision:
  │  ├─ Select top N candidates per job (based on capacity)
  │  ├─ Create interview schedule candidates
  │  └─ Enqueue: interview_scheduled message per candidate-job pair
  └─ Result: Candidates progress to interview stage
```

**Cascade Effect:**
- Thunder candidates must arrive by T+4 to be included in Flash analysis
- If candidate arrives at T+5 (after Flash ran) → must wait for next day (24 hour delay)
- Cascade: Late arrival → missed interview window → lost candidate

**Scaling Constraint:**
- Flash must complete in < 15 minutes at 1500 HC
- Baseline: 100 engaged candidates + 50 open jobs = 5000 match calculations
- At 1500 HC: 1500 engaged candidates + 300 open jobs = 450,000 calculations
- Must be parallelized or risk 30+ minute runtime (breaks hiring SLA)

---

### T+4:30: Interview Scheduling (Interview Service)

**Trigger:** Flash enqueues interview_scheduled messages

**Flow:**
```
Handler: interview_scheduled_handler.py
  ├─ Timeout: 30 seconds
  ├─ Input: candidate_id, job_id, hiring_manager_id, interview_date
  ├─ Validation:
  │  1. Candidate exists AND status = 'ENGAGED'
  │  2. Job exists AND is open
  │  3. Hiring manager exists AND available on date
  │  4. Date is in future (not past)
  ├─ Side effects:
  │  ├─ Create Interview record
  │  ├─ Send interview reminder email (1 hour before)
  │  ├─ Block hiring manager's calendar
  │  └─ Update candidate status to 'INTERVIEW_SCHEDULED'
  └─ Result: Candidate waiting for interview

Cascade: No-show Detection
  ├─ If candidate doesn't show → mark FAILED
  ├─ Auto-reschedule to next available slot
  ├─ Send follow-up SMS
  └─ If 3 no-shows → mark candidate REJECTED
```

**Critical Path Timing:**
- Message enqueued at T+4:30
- Handler processes by T+5:00
- Interview can be scheduled for T+24 to T+168 (same week to next week)

---

### T+24: Offer Generation (Offer Service)

**Trigger:** Interview completed + hiring manager approved

**Flow:**
```
Handler: offer_generated_handler.py
  ├─ Timeout: 45 seconds
  ├─ Input: candidate_id, job_id, salary, benefits, start_date
  ├─ Validation:
  │  1. Candidate exists AND status = 'INTERVIEW_PASSED'
  │  2. Job still open (not filled)
  │  3. Salary within budget
  │  4. Start date > 2 weeks from now (legal notice)
  ├─ Side effects:
  │  ├─ Generate offer document (DocuSign template)
  │  ├─ Send offer via email + SMS
  │  ├─ Block candidate from other interviews
  │  ├─ Set offer expiration (72 hours default)
  │  └─ Update candidate status to 'OFFER_SENT'
  └─ Result: Candidate can accept/reject offer

Cascade: Offer Signature
  ├─ Candidate must e-sign within 72 hours
  ├─ If signed → status = 'OFFER_ACCEPTED'
  ├─ If not signed by deadline → offer expires, candidate rejected
  └─ Hiring manager can extend by 48 hours (once)
```

**Business SLA:**
- Candidate→Interview→Offer should take < 24 hours (aggressive hiring)
- Industry standard: 3-7 days
- WROS target: 24 hours = competitive advantage at 1500 HC

---

### T+24:30: Employee Conversion (Workforce Service)

**Trigger:** Offer accepted + e-signed

**Flow:**
```
Handler: candidate_conversion_handler.py (call it candidate_to_employee_handler)
  ├─ Timeout: 40 seconds
  ├─ Input: candidate_id, signed_offer_id, start_date
  ├─ Validation:
  │  1. Offer is signed (verified via DocuSign)
  │  2. Candidate status = 'OFFER_ACCEPTED'
  │  3. No active employee record already (preventing duplicates)
  │  4. Start date valid (> today, < 365 days out)
  ├─ Side effects:
  │  ├─ Create Employee record (copy from candidate)
  │  ├─ Create payroll setup (salary, tax info, bank details)
  │  ├─ Create equipment request (laptop, phone, access badges)
  │  ├─ Assign buddy (peer mentor for first 30 days)
  │  ├─ Send onboarding email workflow
  │  └─ Update candidate status to 'EMPLOYEE' (archive from candidate table)
  └─ Result: Employee in system, ready for payroll

Cascade: Onboarding Workflow
  ├─ Equipment ordered on T+0 (arrive by T+3)
  ├─ Payroll setup on T+0 (effective T+start_date)
  ├─ IT account created on T+0 (available T+start_date)
  ├─ Email setup on T+0 (active T+start_date)
  ├─ 30-day onboarding checklist generated
  └─ Manager notified of hire
```

**Cascade Failure Risk:**
- If payroll setup fails → employee starts but unpaid (disaster)
- If IT account fails → employee can't access systems (productivity loss)
- If both fail → employee's first day is broken (reputation damage)

---

## QUEUE ARCHITECTURE: How Messages Flow Through System

### Queue System (ChannelQueueItem)

**Table Structure:**
```
ChannelQueueItem {
  id: UUID
  tenant_id: int (for sharding)
  message_type: str (candidate_creation, interview_scheduled, etc.)
  payload: JSON
  status: enum (PENDING, PROCESSING, COMPLETED, FAILED, RETRYING)
  created_at: timestamp
  started_at: timestamp  
  completed_at: timestamp
  handler_name: str (which handler processes this?)
  handler_version: str (schema version for payload)
  error_reason: str (if FAILED)
  retry_count: int
  retry_backoff: int (seconds until next retry)
  idempotency_key: str (prevents processing same message twice)
  result_hash: str (proof that handler completed successfully)
}
```

**Message Types (Handler Registry):**
```
THUNDER (Candidate external operations):
- create_candidate → candidate_creation_handler
- import_linkedin_candidate → linkedin_import_handler
- thunder_engagement → thunder_engagement_handler
- candidate_response_received → candidate_response_handler

FLASH (Internal operations):
- job_created_flash → job_creation_flash_handler
- job_updated_flash → job_update_flash_handler
- job_deleted_flash → job_delete_flash_handler
- flash_daily_analysis → flash_recruiter_handler

INTERVIEW (Interview scheduling):
- interview_scheduled → interview_scheduled_handler
- interview_completed → interview_completed_handler
- interview_no_show → interview_no_show_handler

OFFER (Offer generation):
- offer_generated_flash → offer_generation_handler
- offer_approved → offer_approved_handler
- offer_signed → offer_signed_handler

EMPLOYEE (Onboarding):
- candidate_conversion → candidate_conversion_handler
- employee_onboarding → employee_onboarding_handler
- payroll_setup → payroll_setup_handler
```

**Processing Flow:**

```
Queue Processor (runs every 1 second)
  ├─ Query: WHERE status='PENDING' LIMIT 10 (batch processing)
  ├─ For each message:
  │  ├─ Check idempotency_key (prevent duplicates)
  │  ├─ Load handler by message_type
  │  ├─ Update status → PROCESSING
  │  ├─ Call handler.process(message)
  │  ├─ Handler timeout: 30-60 seconds (per handler)
  │  ├─ If success:
  │  │  ├─ Update status → COMPLETED
  │  │  ├─ Store result_hash (proof)
  │  │  ├─ Call on_success() → enqueue downstream messages
  │  │  └─ Log transition
  │  ├─ If failure (retryable):
  │  │  ├─ Increment retry_count
  │  │  ├─ Update status → RETRYING
  │  │  ├─ Set retry_backoff (exponential: 1s, 2s, 4s, 8s, 16s, then 60s)
  │  │  ├─ Max 5 retries, then FAILED
  │  │  └─ Log retry attempt
  │  └─ If failure (non-retryable):
  │     ├─ Update status → FAILED
  │     ├─ Store error_reason
  │     ├─ Enqueue escalation alert
  │     └─ Notify human operator
  └─ Continue (loop again)
```

**Concurrency & Scaling:**

```
Single Queue Processor (current):
- Processes 2 msg/sec baseline
- Processes 5 msg/sec under load
- Thread pool: 10-20 workers (configurable)
- Database bottleneck: PostgreSQL single instance

For 1500 HC (target 20 msg/sec):
- Must shard by tenant_id
- 1 queue processor per shard (3 shards = 3 processors)
- Each processor: 10 msg/sec (throughput target)
- Total: 30 msg/sec capacity (50% overhead for spikes)
```

---

## DATABASE SCHEMA: Critical Tables & Relationships

### Core Tables (for 1500 HC)

**Candidates Table:**
```
candidates {
  id UUID, tenant_id INT, email STRING (unique per tenant), phone STRING,
  name STRING, status ENUM, created_at TIMESTAMP, updated_at TIMESTAMP,
  hiring_manager_id UUID (FK → users), business_unit_id INT (FK → business_units),
  source STRING, resume_url STRING, created_by UUID (FK → users)
}
Indexes: (tenant_id, email), (tenant_id, status), (created_at, tenant_id)
Partitioning: By (tenant_id, DATE(created_at)) - monthly partitions
Scaling: 1.5M rows at 1500 HC, query latency target: 10-50ms p99
```

**Jobs Table:**
```
jobs {
  id UUID, tenant_id INT, title STRING, status ENUM (open, filled, closed),
  hiring_manager_id UUID (FK → users), business_unit_id INT,
  salary_min INT, salary_max INT, headcount_needed INT,
  created_at TIMESTAMP, filled_date TIMESTAMP (if closed)
}
Indexes: (tenant_id, status), (tenant_id, created_at)
Scaling: 50K rows at 1500 HC, query latency target: 10ms p99
```

**ChannelQueueItem Table:**
```
channel_queue_items {
  id UUID, tenant_id INT, message_type STRING, status ENUM,
  payload JSON, created_at TIMESTAMP, started_at TIMESTAMP, completed_at TIMESTAMP,
  handler_name STRING, error_reason STRING, retry_count INT,
  idempotency_key STRING, result_hash STRING
}
Indexes: (tenant_id, status, created_at), (idempotency_key, message_type)
Partitioning: By (channel_type, DATE(created_at)) - daily partitions, auto-purge after 90 days
Scaling: 100K-1M rows/day, query latency target: 5-20ms p99, concurrent writes: 100+/sec
```

**Employees Table:**
```
employees {
  id UUID, tenant_id INT, candidate_id UUID (FK → candidates),
  email STRING (unique per tenant), phone STRING, name STRING,
  salary INT, start_date DATE, manager_id UUID (FK → employees),
  business_unit_id INT, employment_status ENUM, created_at TIMESTAMP
}
Indexes: (tenant_id, email), (tenant_id, employment_status)
Scaling: 1500 rows at 1500 HC, grows 10-15 per week
```

### Sharding Strategy (1500 HC)

```
Shard Router (load balancer)
  ├─ Shard 1 (PostgreSQL instance): Tenant 1-500
  │  ├─ Candidates: 500K rows
  │  ├─ Jobs: 10K rows
  │  ├─ Employees: 500 rows
  │  └─ Queue: 50K msg/day
  ├─ Shard 2 (PostgreSQL instance): Tenant 501-1000
  │  └─ (same structure)
  └─ Shard 3 (PostgreSQL instance): Tenant 1001-1500
     └─ (same structure)

Scaling benefit: Each shard handles 6-10 msg/sec (total 20 msg/sec)
Query latency: Reduced from 100-500ms (single DB) to 10-50ms (sharded)
Write throughput: Reduced contention, better parallelism
```

---

## FAILURE MODES: What Breaks & How to Recover

### Failure Mode #1: Cascade Failure (Most Common)

**Scenario:** Candidate creation succeeds, but Thunder engagement fails

```
T+0:00  - Candidate created ✓
T+0:05  - Thunder handler timeout (API unreachable)
T+0:10  - Handler marked RETRYING
T+0:15  - Retry attempt 1 (backoff 1s)
T+0:45  - Retry attempt 2 (backoff 2s) FAILED
T+1:00  - Handler marked FAILED (max retries exceeded)
T+1:05  - Alert sent to on-call engineer (Slack + email)
T+1:15  - Engineer investigates
  ├─ Problem: Thunder service crashed (check Datadog)
  ├─ Diagnosis: Deployment bug in Thunder service
  ├─ Recovery: Rollback Thunder to previous version
  └─ Action: Re-run handler (manually queue message to retry)
T+1:30  - Thunder service recovered
T+1:35  - Handler retried, Thunder email sent ✓
```

**Prevention Gate:** Architect must verify:
- Thunder service availability (can it handle 100 req/sec?)
- Timeout values (30s Thunder handler + 60s engagement = 90s SLA)
- Retry backoff (exponential, max 5 retries)
- Escalation to human (after max retries)

**Hard Block:** If candidate creation handler has NO timeout → cascade hangs entire queue

### Failure Mode #2: Silent Failure (Most Dangerous)

**Scenario:** Handler returns success but candidate not actually created

```
T+0:00  - Candidate API called, validation passes
T+0:05  - ChannelQueue message inserted
T+0:10  - Handler processes:
         ├─ Read candidate from DB (found!)
         ├─ Perform validation (all checks pass)
         ├─ Mark COMPLETED with hash (success!)
         └─ BUT: Thunder engagement was silently skipped (no error)
T+0:15  - Handler reports success, message status = COMPLETED
T+0:20  - Upstream code thinks candidate is engaged, moves on
T+2:00  - Flash analysis runs, doesn't see candidate (status is ENGAGED)
T+4:00  - Candidate misses interview window (because Flash never analyzed)
T+24:00 - Recruiter realizes candidate missing ("where did they go?")
T+26:00 - Problem traced back to handler (silent failure 26 hours late!)
```

**Why it's dangerous:**
- No error raised, no logs, no alerts
- System appears healthy for 26 hours
- Cascade failure discovered too late to fix

**Prevention Gate:** Architect must verify:
- No silent `except: pass` blocks
- All exceptions logged + raised (fail-fast, not silent)
- All handler transitions logged (proof: "transitioned to COMPLETED at T+0:10")
- All side effects verified (Thunder actually sent email, not just thought it did)

**Hard Block:** Any handler with silent catch blocks → REJECT at gate

### Failure Mode #3: Duplicate Processing

**Scenario:** Network glitch causes same message to queue twice

```
T+0:00  - Recruiter clicks "Create Candidate"
T+0:01  - API call #1 succeeds, returns candidate_id=123
T+0:02  - Network timeout, UI shows error (though create succeeded)
T+0:03  - Recruiter clicks "Create Candidate" again (same data)
T+0:04  - API call #2 queues another message with same email
T+0:10  - Queue processor tries to create candidate twice
         ├─ Handler #1: Creates candidate_id=123 ✓
         ├─ Handler #2: Tries to create same email → FK violation!
         └─ Result: FAILED (duplicate email error, non-retryable)
T+0:15  - Alert: "Duplicate candidate detected"
T+0:20  - Recruiter confused: "I only clicked once!"
```

**Prevention:** Architect must verify:
- Idempotency key exists: sha256(email + tenant_id)
- Handler checks idempotency_key BEFORE processing
- If already processed → return cached result (not error)

**Hard Block:** Any handler without idempotency validation → REJECT at gate

---

## PERMISSION SYSTEM: RBAC & Data Scoping

### Role Templates (Authority Hierarchy)

```
Admin (system-wide)
  ├─ Resources: all
  ├─ Permissions: read, write, delete, admin
  ├─ Data scoping: none (full access)
  └─ Examples: CTO, DevOps, system admin

Super Admin (tenant-wide)
  ├─ Resources: recruitment, workforce, finance, projects
  ├─ Permissions: read, write, delete (no admin flag)
  ├─ Data scoping: All business units in tenant
  └─ Examples: Talent director, CFO, COO

Manager (business unit + reporting hierarchy)
  ├─ Resources: recruitment (read, write), workforce (read, write), finance (read only)
  ├─ Permissions: Can manage subordinates + own BU
  ├─ Data scoping: Business unit + direct reports only
  └─ Examples: Hiring manager, department head, team lead

User (individual)
  ├─ Resources: recruitment (read only), workflow assignments (write own)
  ├─ Permissions: Can only access own work
  ├─ Data scoping: Own candidate, own interviews, own tasks
  └─ Examples: Recruiter, HR specialist, interviewer
```

### Data Scoping by Role

**CEO/Super Admin:** Access all candidates, all jobs, all employees (no scoping)

**Hiring Manager (Manager role in BU "Sales"):**
```
Can see: All candidates applied to Sales jobs
Can see: All Sales department employees
Cannot see: Finance candidates, Engineering employees
Cannot see: Other BU's data (scope enforced by BU = "Sales")
```

**Recruiter (User role):**
```
Can see: Candidates they created (created_by = user_id)
Can see: Interviews they're assigned to
Cannot see: Other recruiters' candidates
Cannot see: Financial data
```

**Gate Enforcement:** Every endpoint must check:
1. User authenticated? (login required)
2. User has role? (assigned to admin/super_admin/manager/user)
3. User has permission for resource? (read/write checks)
4. User has data scope? (BU, creator, assignment checks)

---

## SCALING CONSTRAINTS: Where System Breaks

### Baseline (Current)
- Queue throughput: 2-5 msg/sec
- Concurrent users: 10-20
- Concurrent candidate creations: 1-2 per minute
- Database: Single PostgreSQL instance
- Response time: 200-500ms p99

### At 100 Employees (10% of 1500 HC)
- Queue throughput: 5-10 msg/sec (2x baseline)
- Concurrent users: 50-100
- Concurrent candidate creations: 10 per minute
- Database: Single instance (still OK)
- Response time: 100-200ms p99 (needs optimization)
- **Breaking point:** Queue processor thread pool exhaustion (20 threads at 10 msg/sec)

### At 500 Employees (33% of 1500 HC)
- Queue throughput: 10-15 msg/sec (3x baseline)
- Concurrent users: 250-500
- Concurrent candidate creations: 50 per minute
- Database: Single instance straining (lock contention)
- Response time: 300-1000ms p99 (degraded)
- **Breaking point:** Database connection pool exhaustion, queue processor thread pool (10 msg/sec = 10 threads used, can't scale higher)

### At 1000 Employees (66% of 1500 HC)
- Queue throughput: 15-20 msg/sec (7x baseline)
- Database: **MUST SHARD** (single instance failing)
- Response time: 500-2000ms p99 (broken SLAs)
- **Breaking point:** Need sharding + multiple queue processors
- Action: Implement 3-shard architecture (tenant_id based)

### At 1500 Employees (Full Scale)
- Queue throughput: 20 msg/sec (10x baseline) - REQUIRES:
  - 3 PostgreSQL instances (sharded by tenant_id)
  - 3 Queue processors (1 per shard)
  - 30-40 handler worker threads (10-15 per shard)
- Candidate→Offer SLA: < 24 hours (requires optimization)
- Response time: 50-100ms p99 (after sharding)
- **No further breaking points** (architecture supports 1500+ indefinitely)

**Architect Responsibility:** Verify code works at baseline AND at 1500 HC (10x scale).

---

## INCIDENT HISTORY: Past Cascade Failures & Root Causes

### Incident #1: Silent Handler Completion (2026-09-06)

**What Happened:**
- Candidate created successfully ✓
- Thunder engagement handler marked COMPLETED
- BUT: Thunder email was never sent (silent failure in exception handler)
- Cascade: Candidate never engaged, Flash skipped them, lost hire

**Root Cause:** `except Exception: pass` in thunder_engagement_handler line 85

**Gate Rule That Should Have Caught It:** Gate #7 (No silent catch blocks)

**Prevention:** Architect blocks any code with silent exception handlers

---

### Incident #2: Missing Timeout, Queue Hangs (2026-09-05)

**What Happened:**
- Handler job_creation_flash_handler didn't have timeout config
- Message stuck in PROCESSING for 30+ minutes
- Queue backed up, new candidates couldn't be processed
- Recruiter escalated (SLA broken)

**Root Cause:** Handler added without TIMEOUT_SECONDS constant

**Gate Rule That Should Have Caught It:** Gate #6 (Handler timeout enforcement)

**Prevention:** Architect blocks any handler without timeout declaration

---

## ARCHITECT DECISION CHECKLIST: Questions to Ask for Every Code Change

1. **Upstream:** Does this assume a dependency exists? Can it fail gracefully?
2. **Functional:** Does this break any business workflow? Can hiring still happen?
3. **Downstream:** What breaks 3 months from now if we ship this?
4. **Cascade:** If this component fails, what else cascades? Can we recover?
5. **Scale:** Does this work at 100 HC? 500 HC? 1500 HC? Where does it break?
6. **Timing:** What's the timeout? What's the SLA? What's the backoff?
7. **Logging:** Are all state transitions logged? Can we debug failures?
8. **Testing:** Is this tested at peak load (100 req/sec)? At scale (1500 HC)?

---

## QUICK REFERENCE: Gate Criteria by Type

**Candidate Creation Handler (Template):**
- ✅ TIMEOUT_SECONDS = 30
- ✅ 4-step validation: structure, DB, FK, consistency
- ✅ No silent catch blocks (log + raise all exceptions)
- ✅ Logging: handler_start, validation checks, handler_complete
- ✅ Idempotency: check idempotency_key before processing
- ✅ Circuit breaker: track failure_rate, halt if > 5%
- ✅ Cascade: verify tenant exists before creating candidate
- ✅ Transaction safety: rollback on validation failure, commit on success
- ✅ Monitoring: emit metrics (duration, success/fail, retry_count)
- ✅ Result hash: store proof that candidate was created

**Job Creation Handler (Template):**
- Same as above, with job-specific validations

---

**This document is the Architect Knowledge Base. Ruthless Architect must master this to make autonomous decisions.**


# End-to-End Testing Plan - Production Ready

## Pre-Deployment Verification Checklist

### 1. Job Creation Flow (CRITICAL)
**Flow:** Endpoint → Queue → Handler → DB → Processor → SLM → Flash_Recruiter

**Steps:**
1. POST `/api/v1/jobs/create` with valid job data
   - Expected: HTTP 200, returns `message_id`
   - Backend: Message queued to `job_created_flash`
   - Database: No job record yet (handler creates it)

2. Wait 2-3 seconds for queue processor to run
   - Expected: Job written to database with status 'active' or 'pending_approval'
   - Verify: `SELECT * FROM jobs WHERE jobID = <job_id>` returns 1 row

3. Verify SLM analysis ran
   - Expected: `SELECT * FROM slm_decisions WHERE message_id LIKE 'job_created_flash%'` returns 1 row
   - Verify: `slm_confidence > 0`, `message_type = 'job_created_flash'`

4. Verify flash_recruiter was queued
   - Expected: `SELECT * FROM channel_queue_item WHERE task_name = 'flash_recruiter' AND data LIKE '%<job_id>%'` returns 1 row
   - Verify: Status = PENDING

5. Frontend verification
   - Navigate to Jobs page
   - Expected: Job appears ONCE (deduplication working)
   - Click job: Details load correctly
   - Count: Total jobs ≥ 1

### 2. Candidate Creation Flow
**Flow:** Endpoint → Queue → Handler → DB → Thunder

**Steps:**
1. POST `/api/v1/candidates/create` with valid candidate data
   - Expected: HTTP 200, returns `message_id`
   - Database: No candidate record yet (handler creates it)

2. Wait 2-3 seconds for queue processor
   - Expected: Candidate written to database
   - Verify: `SELECT * FROM candidates WHERE candidateEmail = <email>` returns 1 row

3. Verify Thunder agent assigned
   - Expected: `assign_thunder_agent` message queued
   - Verify: `SELECT * FROM channel_queue_item WHERE task_name = 'assign_thunder_agent'` exists

### 3. SLM Decision Storage (CRITICAL)
**Expected:** All handler operations create SLMDecision records

**Verify:**
1. After job creation: `SELECT COUNT(*) FROM slm_decisions` > 0
2. Fields are correct:
   - `message_type` NOT NULL
   - `handler_name` NOT NULL
   - `slm_confidence` >= 0 and <= 1
   - `risk_level` IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
   - `slm_analysis` contains JSON

3. SLM Dashboard query works:
   ```sql
   SELECT message_type, COUNT(*) as count 
   FROM slm_decisions 
   WHERE created_at >= NOW() - INTERVAL 24 HOUR 
   GROUP BY message_type;
   ```

### 4. Message Queue Monitor
**Verify:**
1. Frontend loads `/admin/messagequeue`
   - Expected: Page displays, no errors
   - Stats: Total, Pending, Processing, Completed, Failed counts

2. Create a job and verify queue shows:
   - `job_created_flash` message with status PENDING → COMPLETED
   - `flash_recruiter` message with status PENDING

3. Click message detail:
   - Payload displays correctly
   - Result shows job_id

### 5. Soft-Delete Verification
**Setup:**
1. Create job with title "TEST_DELETE_ME"
2. Manually soft-delete: `UPDATE jobs SET is_deleted=TRUE, deleted_at=NOW() WHERE jobID='test_id'`
3. Verify endpoint filters it:
   - GET `/api/v1/jobs/all` does NOT include deleted job
   - `SELECT COUNT(*) FROM jobs WHERE is_deleted=FALSE` excludes it

4. Frontend verification:
   - Refresh jobs page
   - Deleted job does NOT appear

### 6. Queue Processor State Machine
**Verify:** Message status transitions

1. Create job → Message shows as PENDING
2. After handler processes → Message shows as COMPLETED
3. Verify result stored: `SELECT result FROM channel_queue_item WHERE id='<message_id>'` contains `{"success": true, "data": {"job_id": "..."}}`

### 7. Handler Idempotency
**Verify:** Duplicate message processing doesn't create duplicates

1. Get a message ID from queue
2. Manually re-queue the same message (simulate retry)
3. Verify:
   - Only 1 job record created (deduplication via idempotency_key)
   - Handler returns same job_id both times

### 8. Thunder Health Monitoring (Spartan Phalanx)
**Verify:** Flash monitors Thunder as neighbor

1. Check flash_recruiter_handler logs:
   - Should show: "Thunder health: X.X% (N tasks)"
   - If < 70%: "cascade_failure_signal queued"

2. Verify cascade signal structure:
   ```sql
   SELECT data FROM channel_queue_item 
   WHERE task_name = 'cascade_failure_signal' 
   LIMIT 1;
   ```
   - Expected: Contains `thunder_health`, `success_rate`, `signal_type`

### 9. Error Handling
**Test failure scenarios:**

1. Invalid job payload:
   - POST `/api/v1/jobs/create` with missing required field
   - Expected: HTTP 400, error message

2. Handler crash simulation:
   - Message queue has error handling
   - Message should be retryable (not lost)

3. DB connection failure:
   - Message stays in queue
   - Can be retried when DB comes back up

## Success Criteria

✅ Job creation: endpoint → DB → SLM → flash_recruiter (all 4 steps verified)
✅ SLM decision storage: All decisions persisted with correct fields
✅ Message queue: Messages transition PENDING → COMPLETED
✅ Frontend: Jobs appear without duplicates
✅ Soft-delete: Deleted jobs filtered correctly
✅ Error handling: Failures don't crash system, messages are retryable
✅ Queue processor: Correct orchestration (handler → SLM → next queue)

## Rollback Plan

If any test fails:
1. Check handler logs for errors
2. Verify database constraints are met
3. Check queue message payload is correct
4. Verify SLMDecision table structure matches model
5. Roll back migration if soft-delete causes issues:
   ```bash
   alembic downgrade -1
   ```

## Production Deployment Steps

1. ✅ Run alembic migration: `alembic upgrade head`
2. ✅ Restart backend service
3. ✅ Restart queue processor
4. ✅ Run E2E tests above
5. ✅ Monitor logs for first 24 hours
6. ✅ Verify dashboard displays data correctly

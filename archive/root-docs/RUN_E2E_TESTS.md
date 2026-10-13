# END-TO-END TEST EXECUTION PLAN

## Phase 1: Job Creation Flow (CRITICAL)

### Test 1.1: Endpoint to Queue
**Action:** Run in Terminal
```bash
curl -X POST http://localhost:8080/api/v1/jobs/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "jobTitle": "Test_Job_E2E_$(date +%s)",
    "jobDescription": "End-to-end test job",
    "jobSkills": "Python,FastAPI,PostgreSQL",
    "jobExperience": "3-5 years",
    "jobLocation": "Remote"
  }'
```
**Expected Response:** HTTP 200 with `message_id`
**Evidence:** Screenshot of response JSON

### Test 1.2: Queue Contains Message
**Action:** Run Database Query
```sql
SELECT * FROM channel_queue_item 
WHERE task_name = 'job_created_flash' 
ORDER BY created_at DESC 
LIMIT 1;
```
**Expected:** 1 row with status='PENDING'
**Evidence:** Query result screenshot

### Test 1.3: Handler Processes Message
**Action:** Wait 3 seconds, then query database
```sql
SELECT * FROM jobs 
WHERE jobTitle LIKE 'Test_Job_E2E_%' 
ORDER BY jobCreatedAt DESC 
LIMIT 1;
```
**Expected:** 1 job row created with matching title
**Evidence:** Query result with jobID

### Test 1.4: SLM Analysis Recorded
**Action:** Query SLM decisions table
```sql
SELECT * FROM slm_decisions 
WHERE message_type = 'job_created_flash'
ORDER BY created_at DESC 
LIMIT 1;
```
**Expected:** 1 row with:
- `message_type` = 'job_created_flash'
- `handler_name` NOT NULL
- `slm_confidence` > 0
- `risk_level` IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
**Evidence:** Query result screenshot

### Test 1.5: Flash_Recruiter Queued
**Action:** Query queue for next message
```sql
SELECT * FROM channel_queue_item 
WHERE task_name = 'flash_recruiter' 
ORDER BY created_at DESC 
LIMIT 1;
```
**Expected:** 1 row with:
- `status` = 'PENDING'
- `data` contains `job_id` from Test 1.3
- `data` contains SLM instructions
**Evidence:** Query result screenshot

### Test 1.6: Frontend Job Display
**Action:** Navigate to Jobs page in browser
**Expected:** 
- Test job appears ONCE (deduplication working)
- No duplicates showing
- Can click to view details
**Evidence:** Browser screenshot

## Phase 2: SLM Decision Storage Verification

### Test 2.1: Decision Table Integrity
**Action:** Query for all decisions
```sql
SELECT COUNT(*) FROM slm_decisions;
```
**Expected:** Count > 0 (decisions exist)
**Evidence:** Screenshot

### Test 2.2: Field Validation
**Action:** Run validation query
```sql
SELECT id, message_type, handler_name, slm_confidence, risk_level
FROM slm_decisions
WHERE created_at >= NOW() - INTERVAL 24 HOUR
LIMIT 5;
```
**Expected:** All rows have required fields populated
**Evidence:** Query result screenshot

### Test 2.3: SLM Dashboard Query
**Action:** Run dashboard aggregation
```sql
SELECT message_type, COUNT(*) as count, AVG(slm_confidence) as avg_confidence
FROM slm_decisions 
WHERE created_at >= NOW() - INTERVAL 24 HOUR 
GROUP BY message_type;
```
**Expected:** Grouping by message_type works, counts show all jobs
**Evidence:** Query result screenshot

## Phase 3: Message Queue Monitor Verification

### Test 3.1: Admin Page Loads
**Action:** Navigate to `http://localhost:3000/admin/messagequeue`
**Expected:**
- Page displays (no errors)
- Shows queue statistics
- Displays recent messages
**Evidence:** Browser screenshot

### Test 3.2: Queue Stats
**Action:** Look for stats: Total, Pending, Processing, Completed, Failed
**Expected:** Numbers displayed and updating
**Evidence:** Browser screenshot

### Test 3.3: Create Job → Monitor Shows Message
**Action:** 
1. Create new job via API (repeat Test 1.1)
2. Watch MessageQueueMonitor in real-time
3. Should show:
   - `job_created_flash` message appears (PENDING)
   - After 2-3 seconds: status changes to COMPLETED
   - `flash_recruiter` message appears (PENDING)
**Expected:** Real-time queue updates showing flow
**Evidence:** Series of screenshots showing state transitions

## Phase 4: Soft-Delete Verification

### Test 4.1: Create Test Job
**Action:** Create job via API with specific title
```bash
curl -X POST http://localhost:8080/api/v1/jobs/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "jobTitle": "TEST_DELETE_ME_$(date +%s)",
    ...
  }'
```
**Expected:** Job created, get jobID
**Evidence:** API response screenshot

### Test 4.2: Soft-Delete in Database
**Action:** Execute update
```sql
UPDATE jobs 
SET is_deleted=TRUE, deleted_at=NOW() 
WHERE jobTitle LIKE 'TEST_DELETE_ME_%';
```
**Expected:** 1 row updated
**Evidence:** Query result screenshot

### Test 4.3: Endpoint Filters Deleted
**Action:** Query the endpoint
```bash
curl http://localhost:8080/api/v1/jobs/all \
  -H "Authorization: Bearer <JWT_TOKEN>"
```
**Expected:** Response does NOT include deleted job
**Evidence:** JSON response showing deleted job missing

### Test 4.4: Database Query Filters Deleted
**Action:** Run database query
```sql
SELECT * FROM jobs 
WHERE (is_deleted = FALSE) OR (is_deleted IS NULL);
```
**Expected:** Does NOT include TEST_DELETE_ME job
**Evidence:** Query result screenshot

### Test 4.5: Frontend Doesn't Show Deleted
**Action:** Navigate to Jobs page
**Expected:** Deleted job NOT displayed
**Evidence:** Browser screenshot

## Phase 5: Migration Verification

### Test 5.1: Soft-Delete Columns Exist
**Action:** Describe jobs table
```sql
DESCRIBE jobs;
```
**Expected:** Two new columns:
- `deleted_at` (DateTime, nullable)
- `is_deleted` (Boolean, default=FALSE)
**Evidence:** Query result screenshot

### Test 5.2: Indexes Created
**Action:** Query indexes
```sql
SHOW INDEX FROM jobs WHERE Key_name LIKE '%deleted%';
```
**Expected:** Two indexes:
- `ix_jobs_deleted_at`
- `ix_jobs_is_deleted`
**Evidence:** Query result screenshot

## Phase 6: Other Handlers Verification

### Test 6.1: Candidate Creation Handler
**Action:** Create candidate via API
```bash
curl -X POST http://localhost:8080/api/v1/candidates/create \
  -H "Content-Type: application/json" \
  -d '{"name": "Test_Candidate", "email": "test_$(date +%s)@example.com", ...}'
```
**Expected:** HTTP 200 with message_id
**Evidence:** API response

### Test 6.2: Candidate Persisted
**Action:** Query database
```sql
SELECT * FROM candidates 
WHERE name LIKE 'Test_Candidate' 
ORDER BY created_at DESC LIMIT 1;
```
**Expected:** 1 candidate row
**Evidence:** Query result

### Test 6.3: Thunder Agent Assignment Queued
**Action:** Query queue
```sql
SELECT * FROM channel_queue_item 
WHERE task_name LIKE 'assign_thunder_agent%' 
ORDER BY created_at DESC LIMIT 1;
```
**Expected:** 1 message queued
**Evidence:** Query result

## SUCCESS CRITERIA

✅ **Phase 1 Complete:** Job creation flow verified end-to-end (6/6 tests)
✅ **Phase 2 Complete:** SLM decisions stored correctly (3/3 tests)
✅ **Phase 3 Complete:** Message queue monitor working (3/3 tests)
✅ **Phase 4 Complete:** Soft-delete filtering working (5/5 tests)
✅ **Phase 5 Complete:** Migration applied correctly (2/2 tests)
✅ **Phase 6 Complete:** Other handlers working (3/3 tests)

**Total:** 22 test steps, all passing = PRODUCTION READY ✅

## EXECUTION CHECKLIST

- [ ] Phase 1 Test 1.1: Create job via API
- [ ] Phase 1 Test 1.2: Queue contains message
- [ ] Phase 1 Test 1.3: Job in database
- [ ] Phase 1 Test 1.4: SLM decision recorded
- [ ] Phase 1 Test 1.5: Flash recruiter queued
- [ ] Phase 1 Test 1.6: Job appears on frontend (once)
- [ ] Phase 2 Test 2.1: Decision table has data
- [ ] Phase 2 Test 2.2: Field validation passes
- [ ] Phase 2 Test 2.3: Dashboard query works
- [ ] Phase 3 Test 3.1: Monitor page loads
- [ ] Phase 3 Test 3.2: Stats display
- [ ] Phase 3 Test 3.3: Real-time updates
- [ ] Phase 4 Test 4.1: Create test job
- [ ] Phase 4 Test 4.2: Soft-delete in DB
- [ ] Phase 4 Test 4.3: Endpoint filters deleted
- [ ] Phase 4 Test 4.4: DB query filters deleted
- [ ] Phase 4 Test 4.5: Frontend doesn't show deleted
- [ ] Phase 5 Test 5.1: Columns exist
- [ ] Phase 5 Test 5.2: Indexes exist
- [ ] Phase 6 Test 6.1: Candidate creation works
- [ ] Phase 6 Test 6.2: Candidate in database
- [ ] Phase 6 Test 6.3: Thunder queue message

**STATUS: Ready for execution**

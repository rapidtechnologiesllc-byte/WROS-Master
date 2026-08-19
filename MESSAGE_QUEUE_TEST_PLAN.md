# Message Queue System: Complete End-to-End Test Plan
## 450 Candidates Bulk Import Test with Failure Scenarios

**Date:** 2026-08-19  
**Objective:** Test message queue system end-to-end with 450 candidates, verify resilience, and identify self-healing enhancements  
**Total Duration:** ~90 minutes  

---

## PHASE 1: SETUP (15 minutes)

### 1.1 Redis Installation

**Option A: Use Python fakeredis (In-Memory Mock)**
- Fastest for testing
- No external installation needed
- Command: Install fakeredis via pip if needed

**Option B: Use Redis Server (Recommended for real testing)**
- Requires Redis installation
- For Windows: Use Memurai or WSL2 Redis

```bash
# Option A - fakeredis (testing only)
pip install fakeredis

# Option B - Real Redis via WSL
wsl apt-get update
wsl apt-get install redis-server
wsl redis-server --daemonize yes
```

### 1.2 Backend Dependencies

```bash
# Install all backend requirements
cd C:\dev\OnboardingModule-Backend
pip install -r requirements.txt

# Verify Celery and Redis installed
pip show celery redis
```

### 1.3 Database Setup

```bash
# Ensure database is initialized
python init_wros_db.py

# Verify candidates table exists
python -c "from app.models.candidate import Candidate; from app.core.database import SessionLocal; db = SessionLocal(); print(f'Candidate model ready'); db.close()"
```

### 1.4 Backend Server Startup

```bash
# Terminal 1: Start backend
cd C:\dev\OnboardingModule-Backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 1.5 Celery Worker Startup

```bash
# Terminal 2: Start Celery worker
cd C:\dev\OnboardingModule-Backend
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

---

## PHASE 2: CREATE 450-CANDIDATE TEST SCRIPT (10 minutes)

**File:** `scripts/test_bulk_import_450.py`

Script functionality:
- Generates 450 unique candidates with realistic data
- Creates candidates in database
- Queues as async Celery tasks
- Returns task IDs for monitoring
- Tracks completion in real-time

**Key metrics:**
- Task ID list (for monitoring)
- Total candidates created
- Queue status (queued/processing/completed)
- Time tracking (start/end times)

---

## PHASE 3: EXECUTE IMPORT & MONITOR (5 minutes)

### 3.1 Run Test Script

```bash
python scripts/test_bulk_import_450.py
```

**Expected output:**
```
Starting bulk import of 450 candidates...
Generated 450 test candidates
Created candidates in database (batch processing)
Queued 450 async tasks
Task IDs: [task_1, task_2, ..., task_450]
Monitor progress at: http://localhost:8000/admin/queue/tasks
```

### 3.2 Monitor Queue Dashboard

```
GET http://localhost:8000/admin/queue/tasks
```

**Expected response:**
```json
{
  "status": "success",
  "stats": {
    "total": 450,
    "queued": 225,
    "active": 15,
    "completed": 210,
    "failed": 0
  },
  "tasks": [...]
}
```

**Dashboard features:**
- Real-time task count
- Status breakdown (queued/active/completed/failed)
- Task ID tracking
- Error messages (if any)
- Progress percentage

---

## PHASE 4: FAILURE SCENARIO TESTING (40 minutes)

### Scenario A: Stop Queue Mid-Process (10 min)

**Setup:**
1. Script running with 450 candidates
2. Wait until ~225 tasks processed (50% complete)
3. Note time, current state

**Execution:**
```bash
# Terminal 2: Kill Celery worker (Ctrl+C)
# Press Ctrl+C in Celery terminal
```

**Observations to document:**
- [ ] In-progress tasks status (still active? marked failed?)
- [ ] Queued tasks status (still pending?)
- [ ] Task state in database
- [ ] Redis queue state
- [ ] Error messages in logs
- [ ] Dashboard reflects changes?

**Expected findings:**
- Tasks in progress: Either marked as FAILED or stay ACTIVE (depends on implementation)
- Queued tasks: Should remain QUEUED (safe in Redis)
- Database: Should be consistent (no corrupted records)
- Redis: Tasks should still be in queue

**Documentation:**
Create file: `test_results/scenario_a_stop_midprocess.md`
- Time killed: HH:MM:SS
- Tasks processed before kill: XXX
- Queue state after kill: {...}
- Task states: [list of samples]
- Findings: [what we learned]

---

### Scenario B: Restart Queue After Stop (10 min)

**Setup:**
Previous state: Queue killed at 50% completion

**Execution:**
```bash
# Terminal 2: Restart Celery worker
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

**Observations to document:**
- [ ] Does queue auto-resume?
- [ ] In-progress tasks retried?
- [ ] Duplicate executions detected?
- [ ] Total completion rate
- [ ] Time to complete remaining tasks

**Expected findings:**
- Auto-resume: Tasks in QUEUED state should resume (depends on implementation)
- Retries: May or may not happen (need to document behavior)
- Duplicates: Should NOT occur (task ID deduplication)
- Completion: All 450 tasks should eventually complete
- Time: Should complete remaining 225 in ~same time as before

**Documentation:**
Create file: `test_results/scenario_b_restart_recovery.md`
- Time restart: HH:MM:SS
- Tasks resumed: XXX
- Total completion time: HH:MM:SS
- Duplicates detected: YES/NO
- Final count: XXX completed, 0 failed

---

### Scenario C: Intentional Stuck Queue (10 min)

**Setup:**
Modify task to hang:
1. Add special task ID to hang
2. Queue mix: 225 normal + 1 hanging + 224 normal
3. Observe system behavior

**Preparation:**
```bash
# Create hanging task (in task definition or via test script)
# Task should hang/timeout intentionally
```

**Execution:**
1. Queue mixed batch (225 + 1 hanging + 224)
2. Monitor queue progress
3. Observe timeout behavior
4. Verify other tasks continue

**Observations to document:**
- [ ] Hanging task detected?
- [ ] Timeout triggered (at 25 min or 30 min limit)?
- [ ] Queue continues with other tasks?
- [ ] Error message generated?
- [ ] System recovers automatically?

**Expected findings:**
- Detection: May or may not detect hanging (depends on timeout config)
- Timeout: Should occur at task_time_limit (30 min configured)
- Continuation: Other tasks should NOT be blocked
- Error handling: Task marked FAILED with timeout error
- Recovery: Remaining 224 tasks should process normally

**Documentation:**
Create file: `test_results/scenario_c_stuck_queue.md`
- Hanging task ID: task_XXX
- Time hung detected: HH:MM:SS (or timeout at HH:MM:SS)
- Other tasks blocked: YES/NO
- Queue recovered: YES/NO
- Final stats: XXX completed, 1 failed (hung), YYY pending

---

### Scenario D: Stuck Queue + Restart Recovery (10 min)

**Setup:**
Previous state: Queue with 1 hanging task, 224 remaining normal tasks

**Execution:**
1. Let queue process normally with hung task (5-10 min)
2. Verify timeout behavior
3. Kill Celery worker
4. Fix hanging task (remove from queue or code fix)
5. Restart worker
6. Verify recovery and continuation

**Process:**
```bash
# Terminal 2: Kill worker (Ctrl+C) while hung task running
# Fix issue (e.g., comment out hanging task from queue)
# Terminal 2: Restart worker
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

**Observations to document:**
- [ ] Timeout behavior during hang
- [ ] Clean kill/restart
- [ ] Queue recovery after restart
- [ ] Remaining tasks processed
- [ ] No duplicate execution of hung task
- [ ] Final completion

**Expected findings:**
- Hang: Task times out at 30-min mark (or earlier with soft limit at 25 min)
- Kill: Worker stops cleanly without queue corruption
- Fix: Removing/fixing hung task allows queue to recover
- Restart: Remaining 224 tasks resume processing
- Completion: Final count 449 completed (1 hung task removed), 0 failures
- No duplicates: Hung task not reprocessed

**Documentation:**
Create file: `test_results/scenario_d_stuck_plus_restart.md`
- Hang start time: HH:MM:SS
- Timeout detected: HH:MM:SS
- Worker kill time: HH:MM:SS
- Fix applied: [description]
- Restart time: HH:MM:SS
- Recovery time: X minutes to process remaining 224
- Final stats: 449 completed, 1 removed

---

## PHASE 5: SELF-HEALING ANALYSIS (20 minutes)

### 5.1 Current Mechanisms

**Examine infrastructure for existing self-healing:**

```bash
# Check Celery configuration
cat app/core/celery_app.py
# Look for:
# - task_time_limit (hard limit)
# - task_soft_time_limit (graceful timeout)
# - worker_prefetch_multiplier (task queueing)
# - worker_max_tasks_per_child (worker recycling)
# - Retry policies
# - Error handling
```

**Check admin queue for tracking:**

```bash
# Current TaskStatus implementation
cat app/api/v1/endpoints/admin_queue.py
# Limitations:
# - In-memory registry (lost on restart)
# - No persistence
# - No automatic recovery
# - No health checks
```

### 5.2 What Works

**Document working mechanisms:**
- [ ] Task timeout at 30 minutes (hard limit)
- [ ] Soft timeout at 25 minutes (graceful)
- [ ] Task ID tracking
- [ ] Status monitoring via API
- [ ] Manual retry via dashboard
- [ ] Message logging

### 5.3 What's Missing

**Identify gaps:**
- [ ] Persistent task state (lost on restart)
- [ ] Automatic task recovery after worker failure
- [ ] Connection loss detection to Redis
- [ ] Dead letter queue for failed tasks
- [ ] Health check monitoring
- [ ] Circuit breaker pattern
- [ ] Automatic backoff/retry
- [ ] Task heartbeat monitoring

### 5.4 Enhancement Recommendations

**Priority 1 (Critical):**
1. Persist task state to database instead of in-memory
   - Create `TaskStatus` table in database
   - Query from persistent storage
   - Survives worker restart
   
2. Automatic task recovery after worker restart
   - Mark in-progress tasks as FAILED on worker shutdown
   - Requeue FAILED tasks on worker startup
   - Prevent duplicate execution (idempotent tasks)

3. Redis connection health checks
   - Verify connection to Redis on startup
   - Detect connection loss and alert
   - Auto-reconnect with backoff

**Priority 2 (High):**
1. Dead letter queue for failed tasks
   - Move permanently failed tasks to DLQ
   - Enable admin review of failed tasks
   - Statistics on failure reasons
   
2. Task heartbeat monitoring
   - Long-running tasks send heartbeat
   - Detect stuck tasks (no heartbeat for 5 min)
   - Auto-kill stuck tasks and requeue
   
3. Circuit breaker for failing queues
   - If >50% of tasks fail, pause queue
   - Alert admin
   - Manual restart required

**Priority 3 (Medium):**
1. Exponential backoff retry
   - Automatic retry for transient errors
   - Exponential backoff (1s → 2s → 4s → 8s)
   - Max retry count

2. Database connection pooling
   - Verify DB connection before task execution
   - Auto-retry on connection loss
   
3. Detailed error tracking
   - Store full stack traces
   - Group errors by type
   - Enable pattern detection

**Documentation:**
Create file: `test_results/self_healing_analysis.md`
- Current mechanisms: [list]
- What works: [confirmed features]
- What's missing: [gaps]
- Priority 1 enhancements: [list with estimates]
- Priority 2 enhancements: [list with estimates]
- Priority 3 enhancements: [list with estimates]

---

## PHASE 6: RESULTS & RECOMMENDATIONS (10 minutes)

### Create Final Report

**File:** `test_results/COMPLETE_TEST_REPORT.md`

**Sections:**
1. Executive Summary
   - Test date and duration
   - Scenarios executed
   - Overall system health
   - Recommendations

2. Scenario Results
   - A: Stop mid-process
   - B: Restart recovery
   - C: Stuck queue detection
   - D: Stuck + restart

3. Queue Performance Metrics
   - Total tasks processed: 450
   - Success rate: X%
   - Average task time: Y seconds
   - Queue efficiency: Z%

4. Self-Healing Capabilities
   - Current: [working features]
   - Missing: [gaps]
   - Recommended enhancements: [prioritized list]

5. Dashboard Improvements
   - Current features: [list]
   - Missing features: [list]
   - Proposed updates: [specific enhancements]

6. Timeline & Effort Estimates
   - Priority 1 (critical): X hours
   - Priority 2 (high): Y hours
   - Priority 3 (medium): Z hours

---

## TEST SCRIPTS & UTILITIES

### 1. Main Test Script: test_bulk_import_450.py
- Generates 450 candidates
- Queues as async tasks
- Returns task IDs

### 2. Monitoring Script: monitor_queue.py
- Real-time queue monitoring
- Task state tracking
- Statistics collection

### 3. Scenario Execution Scripts
- scenario_a_stop_midprocess.py
- scenario_b_restart_recovery.py
- scenario_c_stuck_queue.py
- scenario_d_stuck_plus_restart.py

---

## SUCCESS CRITERIA

- [ ] All 450 candidates imported successfully (Scenario B)
- [ ] Restart recovery maintains data integrity
- [ ] Stuck task detection working
- [ ] No duplicate task executions
- [ ] Dashboard shows real-time updates
- [ ] Error messages clear and actionable
- [ ] Performance metrics meet expectations
- [ ] Self-healing gaps identified
- [ ] Enhancement roadmap created

---

## DELIVERABLES

1. **Installation Steps Document**
   - Redis setup for Windows
   - Dependency installation
   - Backend startup
   - Worker startup

2. **Test Scripts (4 files)**
   - test_bulk_import_450.py
   - monitor_queue.py
   - scenario_*.py files

3. **Test Results (5 files)**
   - scenario_a_stop_midprocess.md
   - scenario_b_restart_recovery.md
   - scenario_c_stuck_queue.md
   - scenario_d_stuck_plus_restart.md
   - COMPLETE_TEST_REPORT.md

4. **Self-Healing Analysis**
   - Current mechanisms
   - Missing features
   - Priority-ranked enhancements
   - Implementation timeline

5. **Dashboard Enhancement Plan**
   - Current vs. needed features
   - Mock-ups or specifications
   - Implementation roadmap

---

## EXECUTION CHECKLIST

- [ ] Phase 1: Setup (15 min)
- [ ] Phase 2: Test script creation (10 min)
- [ ] Phase 3: Initial import & monitoring (5 min)
- [ ] Phase 4: Failure scenarios (40 min)
  - [ ] Scenario A (10 min)
  - [ ] Scenario B (10 min)
  - [ ] Scenario C (10 min)
  - [ ] Scenario D (10 min)
- [ ] Phase 5: Self-healing analysis (20 min)
- [ ] Phase 6: Final report creation (10 min)
- [ ] All documentation complete
- [ ] All test results documented
- [ ] Recommendations prioritized

**Total Time: ~90 minutes**

---

## NOTES & OBSERVATIONS

- [ ] Redis connection stable throughout testing
- [ ] Database integrity verified (no data corruption)
- [ ] All task IDs unique (no collisions)
- [ ] Error messages clear and helpful
- [ ] No deadlocks observed
- [ ] Performance acceptable for production

---


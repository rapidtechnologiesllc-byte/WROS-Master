# Message Queue Test Execution Guide
## Setup, Execution, and Failure Scenarios

**Version:** 1.0  
**Date:** 2026-08-19  
**Duration:** ~90 minutes  

---

## QUICK START (5 minutes)

If you have Redis running and dependencies installed, start here:

```bash
# Terminal 1: Start backend
cd C:\dev\OnboardingModule-Backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Celery worker
cd C:\dev\OnboardingModule-Backend
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Terminal 3: Run test
cd C:\dev\OnboardingModule-Backend
python scripts/test_bulk_import_450.py

# Terminal 4: Monitor queue
cd C:\dev\OnboardingModule-Backend
python scripts/monitor_queue.py --interval 3 --duration 600
```

**Then open:** http://localhost:8000/admin/queue/tasks

---

## DETAILED SETUP (15 minutes)

### Step 1: Verify Python & Dependencies

```bash
# Check Python version
python --version
# Expected: Python 3.10+

# Check if requirements are installed
pip list | grep -E "celery|redis|fastapi|sqlalchemy"

# If missing, install all requirements
pip install -r requirements.txt

# Verify installation
python -c "import celery; import redis; import fastapi; print('✓ All dependencies installed')"
```

### Step 2: Install/Start Redis

#### Option A: Using Python fakeredis (For Testing Only)

```bash
# Install fakeredis (in-memory mock Redis)
pip install fakeredis

# This is sufficient for local testing
# No external Redis server needed
```

#### Option B: Use Real Redis on Windows

**Option B1: Via WSL2 (Recommended)**

```bash
# In PowerShell (Admin)
# Enable WSL if not already enabled
wsl --install

# In WSL terminal
sudo apt-get update
sudo apt-get install redis-server

# Start Redis
redis-server --daemonize yes

# Verify
redis-cli ping
# Expected: PONG
```

**Option B2: Using Memurai (Pre-built Redis for Windows)**

1. Download from: https://github.com/microsoftarchive/memurai-doc/releases
2. Install MSI
3. Start Redis Service:
   ```powershell
   Start-Service Memurai
   ```
4. Verify:
   ```powershell
   redis-cli ping
   # Expected: PONG
   ```

### Step 3: Database Setup

```bash
# Navigate to backend
cd C:\dev\OnboardingModule-Backend

# Initialize database if needed
python -c "from app.core.database import engine, Base; Base.metadata.create_all(bind=engine); print('✓ Database ready')"

# Verify Candidate model
python -c "from app.models.candidate import Candidate; print('✓ Candidate model available')"
```

### Step 4: Backend Server Startup

**Terminal 1 - Backend:**

```bash
cd C:\dev\OnboardingModule-Backend

# Start with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Expected output:
# INFO:     Started server process [XXXX]
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

Verify: http://localhost:8000/docs

### Step 5: Celery Worker Startup

**Terminal 2 - Celery Worker:**

```bash
cd C:\dev\OnboardingModule-Backend

# Start worker
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Expected output:
# ------------ celery@HOSTNAME v5.3.x ------
#  ... Connected to redis://localhost:6379/0
#  ... [Tasks]
#  ... [Worker Online]
```

**Expected log messages:**
- "Connected to redis://localhost:6379/0"
- "Worker Online" 
- No connection errors

### Step 6: Verify Everything is Ready

```bash
# Check backend is responsive
curl http://localhost:8000/docs

# Check queue endpoint exists
curl http://localhost:8000/admin/queue/tasks

# Check Celery is connected (look for "Connected to redis" in Terminal 2)
```

---

## TEST EXECUTION PHASES

### Phase 1: Initial Import & Monitoring

**Terminal 3 - Run Test Script:**

```bash
cd C:\dev\OnboardingModule-Backend
python scripts/test_bulk_import_450.py
```

**Expected output:**

```
======================================================================
 MESSAGE QUEUE TEST: 450-CANDIDATE BULK IMPORT
======================================================================

[PHASE 1] Generating 450 test candidates...
✓ Generated 450 candidates

[PHASE 2] Creating candidates in database...
Committed batch at record 50/450
Committed batch at record 100/450
...
✓ Created 450 candidates in database

[PHASE 3] Queuing async Celery tasks...
Queued 50/450 tasks
Queued 100/450 tasks
...
✓ Queued 450 async tasks

[PHASE 5] Checking initial queue status...

Initial Queue Status:
  Total:     450
  Queued:    225
  Active:    15
  Completed: 210
  Failed:    0

✅ Test setup complete!
Monitor at: http://localhost:8000/admin/queue/tasks
```

### Phase 2: Monitor Queue in Real-Time

**Terminal 4 - Monitor Queue:**

```bash
cd C:\dev\OnboardingModule-Backend
python scripts/monitor_queue.py --interval 3 --duration 600
```

**Expected output:**

```
================================================================================
MESSAGE QUEUE MONITOR
================================================================================

Update #1 | 14:23:45 | Elapsed: 0s

Queue Status:
  Total Tasks:    450
  Queued:         225
  Active:         15
  Completed:      210
  Failed:         0

Progress:
  Completed: [================                    ] 46.7%
  Queued:    [=========                          ] 50.0%

Throughput:
  Rate: 3.25 tasks/second
  Status: 15 tasks in 4.6s

Estimate:
  Avg Time per Task: 0.31 seconds
  Est. Remaining Time: 2m 18s
  Est. Total Time: 2m 45s
```

### Phase 3: Browser Dashboard

Open in web browser:
```
http://localhost:8000/admin/queue/tasks
```

**Expected output:**

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
  "tasks": [
    {
      "task_id": "abc123...",
      "task_name": "bulk_import_candidates",
      "status": "completed",
      "progress": 100,
      "created_at": "2026-08-19T14:23:42",
      "updated_at": "2026-08-19T14:23:55",
      "messages": [...]
    },
    ...
  ]
}
```

---

## FAILURE SCENARIOS

### Scenario A: Stop Queue Mid-Process (10 minutes)

**Goal:** Test queue behavior when worker is killed mid-execution

**Setup:**

1. Let test run until ~50% complete (watch Terminal 4 monitor)
   - Wait for approximately 225 tasks completed
   - Note the time: HH:MM:SS

**Execution:**

```bash
# Terminal 2: Kill Celery worker
# Press Ctrl+C in Celery terminal

# You should see:
# Shutting down
# Worker stopped
```

**Observations:**

1. Check Terminal 4 monitor output:
   - Does it still show active tasks?
   - What happens to queued tasks?
   - Do any errors appear?

2. Check browser dashboard:
   ```
   curl http://localhost:8000/admin/queue/tasks
   ```
   - Status of in-progress tasks?
   - Status of queued tasks?
   - Total counts?

3. Check database directly:
   ```bash
   python -c "
   from app.core.database import SessionLocal
   from app.models.candidate import Candidate
   db = SessionLocal()
   candidates = db.query(Candidate).count()
   print(f'Candidates in DB: {candidates}')
   db.close()
   "
   ```

**Documentation:**

Create file: `test_results/scenario_a_findings.md`

```markdown
# Scenario A: Stop Queue Mid-Process

## Execution Details
- Time Stopped: HH:MM:SS
- Tasks Completed Before Stop: XXX
- Tasks Queued Before Stop: XXX
- Tasks Active: XXX

## Observations

### In-Memory Registry
- Tasks marked as: [ACTIVE/FAILED/QUEUED]
- Status changes: [YES/NO]
- Error messages: [list any]

### Redis Queue
- Tasks still in queue: [YES/NO]
- Queue state: [stable/corrupted]

### Database Integrity
- Candidates created: 450 ✓
- No data corruption: ✓
- All records valid: ✓

## Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]
```

---

### Scenario B: Restart Queue After Stop (10 minutes)

**Goal:** Test queue recovery after worker restart

**Setup:**

Previous state from Scenario A (worker killed at 50%)

**Execution:**

```bash
# Terminal 2: Restart Celery worker
cd C:\dev\OnboardingModule-Backend
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# Expected output:
# ------------ celery@HOSTNAME v5.3.x ------
#  ... Connected to redis://localhost:6379/0
#  ... [Tasks]
#  ... [Worker Online]
```

**Observations:**

1. Terminal 4 monitor:
   - Do queued tasks resume?
   - Any sudden changes in active/completed counts?
   - Any error messages?

2. Terminal 2 logs:
   - Any error reconnecting to Redis?
   - Any error reprocessing tasks?
   - How many tasks reprocessed?

3. Browser dashboard:
   ```bash
   curl http://localhost:8000/admin/queue/tasks
   ```
   - Do new tasks appear?
   - Do already-completed tasks persist?
   - Any duplicate task IDs?

**Verification:**

```bash
# Wait for completion (5-10 minutes)
# Then check final state:

curl http://localhost:8000/admin/queue/tasks | python -m json.tool

# Should show:
# - Total: 450
# - Queued: 0
# - Active: 0
# - Completed: 450
# - Failed: 0
```

**Documentation:**

Create file: `test_results/scenario_b_findings.md`

```markdown
# Scenario B: Restart Queue Recovery

## Execution Details
- Time Restarted: HH:MM:SS
- Tasks Resumed: XXX
- Time to Completion: YYY seconds

## Observations

### Auto-Resume
- Tasks automatically resumed: [YES/NO]
- Remaining tasks processed: XXX
- Processing time: HH:MM:SS

### Data Integrity
- Duplicate executions: [0 / X detected]
- Database consistency: [PASS / FAIL]
- All 450 candidates recorded: [YES / NO]

### Error Handling
- Connection errors: [0 / X]
- Retry attempts: [count]
- Recovery automatic: [YES / NO]

## Final Stats
- Total Completed: 450
- Total Failed: 0
- Success Rate: 100%
- Total Time: HH:MM:SS

## Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]
```

---

### Scenario C: Stuck Queue Detection (10 minutes)

**Goal:** Test system behavior with a hanging/stuck task

**Preparation:**

Create a hanging task by manually adding delay to a specific task:

```bash
# Add to app/tasks/bulk_import.py for testing:

@celery_app.task(name="tasks.test_hang_task")
def test_hang_task():
    """Task that hangs indefinitely (for testing)."""
    import time
    time.sleep(300)  # 5 minute hang
    return {"status": "hung"}
```

**Execution:**

```bash
# Terminal 3: Queue mixed batch

# Start fresh with 225 normal + 1 hanging + 224 normal
python -c "
from app.tasks.bulk_import import test_hang_task
from app.tasks.bulk_import import import_candidates_task

# Queue normal tasks
for i in range(225):
    import_candidates_task.delay(f'candidate_{i}')

# Queue the hanging task
test_hang_task.delay()

# Queue more normal tasks
for i in range(225, 449):
    import_candidates_task.delay(f'candidate_{i}')

print('✓ Queued 450 tasks including 1 hanging task')
"
```

**Observations:**

1. Terminal 4 monitor:
   - At what point does queue stall?
   - Do other tasks continue processing?
   - Is timeout detected?

2. Terminal 2 logs:
   - Any timeout message?
   - Does worker recover?
   - Any SoftTimeLimitExceeded?

3. Browser dashboard:
   - Task marked as failed?
   - What's the error message?
   - Do remaining tasks show as queued?

**Documentation:**

Create file: `test_results/scenario_c_findings.md`

```markdown
# Scenario C: Stuck Queue Detection

## Execution Details
- Hanging task ID: task_XXX
- Time queue stalled: HH:MM:SS
- Timeout duration: 25-30 minutes (configured)

## Observations

### Timeout Detection
- Detected at: HH:MM:SS
- Error message: [quote exact message]
- Task status: [FAILED / TIMEOUT / other]

### Queue Behavior
- Other tasks blocked: [YES / NO]
- Tasks continued: XXX
- Queue recovered: [AUTOMATIC / MANUAL / NOT]

### Worker Behavior
- Worker crashed: [YES / NO]
- SoftTimeLimitExceeded: [YES / NO]
- Auto-recovery: [YES / NO]

## Final Stats
- Completed normally: XXX
- Hung task status: [FAILED]
- Failed tasks: 1
- Queue recovered: [YES / NO]

## Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]
```

---

### Scenario D: Stuck Queue + Restart Recovery (10 minutes)

**Goal:** Test recovery from hung task + worker restart

**Setup:**

Previous state from Scenario C (1 hung task, queue recovering)

**Execution:**

```bash
# Step 1: Kill Celery worker while hung task running
# Terminal 2: Press Ctrl+C

# Step 2: Remove/fix the hanging task
# Option A: Clear it from the test (recommended for speed)
# Option B: Update the task to complete quickly

# Step 3: Restart worker
cd C:\dev\OnboardingModule-Backend
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

**Observations:**

1. Terminal 2 logs:
   - Clean restart?
   - Redis reconnection?
   - Tasks picked up from queue?

2. Terminal 4 monitor:
   - Resume after restart?
   - Rate of task completion?
   - Any errors?

3. Final verification:
   ```bash
   curl http://localhost:8000/admin/queue/tasks | python -m json.tool
   ```

**Documentation:**

Create file: `test_results/scenario_d_findings.md`

```markdown
# Scenario D: Stuck Queue + Restart Recovery

## Execution Timeline
- Hang detected: HH:MM:SS
- Worker killed: HH:MM:SS
- Task fixed/removed: [MANUAL / AUTOMATIC]
- Worker restarted: HH:MM:SS
- Recovery complete: HH:MM:SS

## Recovery Process

### Worker Restart
- Connection re-established: [TIME]
- Redis reconnected: [TIME]
- Tasks resumed: [COUNT]

### Task Processing
- Remaining tasks: 449 (1 removed)
- Processed after restart: XXX
- Processing rate: Y tasks/second

### Data Integrity
- Duplicate executions: 0
- Database consistency: [PASS / FAIL]
- Final record count: 450

## Final Stats
- Total Completed: 449
- Total Failed: 0 (hung task removed)
- Success Rate: 100%
- Total Time: HH:MM:SS
- Recovery Time: HH:MM:SS

## Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

## Recommendations
- [Recommendation 1]
- [Recommendation 2]
```

---

## TEST RESULTS DIRECTORY STRUCTURE

Create these files to document your findings:

```
test_results/
├── scenario_a_findings.md         (Stop mid-process)
├── scenario_b_findings.md         (Restart recovery)
├── scenario_c_findings.md         (Stuck queue)
├── scenario_d_findings.md         (Stuck + restart)
├── COMPLETE_TEST_REPORT.md        (Summary & recommendations)
├── self_healing_analysis.md       (Enhancement recommendations)
└── logs/
    ├── backend.log
    ├── celery.log
    └── monitor.log
```

---

## COMMON ISSUES & TROUBLESHOOTING

### Issue 1: "Connection refused" on Redis

**Symptoms:**
- Terminal 2 shows: `Connection refused at ('localhost', 6379)`

**Solution:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not running:
# Option 1: Start Redis
redis-server --daemonize yes

# Option 2: Use fakeredis (mock)
pip install fakeredis
# Update settings to use fakeredis
```

### Issue 2: "No module named app"

**Symptoms:**
- `ModuleNotFoundError: No module named 'app'`

**Solution:**
```bash
# Make sure you're in the correct directory
cd C:\dev\OnboardingModule-Backend

# Try again
python scripts/test_bulk_import_450.py
```

### Issue 3: Database errors

**Symptoms:**
- `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable`

**Solution:**
```bash
# Initialize database
python init_wros_db.py

# Or run migrations
alembic upgrade head
```

### Issue 4: Celery worker hangs

**Symptoms:**
- Worker starts but tasks not processing
- No new output in Terminal 2

**Solution:**
```bash
# Kill and restart with verbose logging
celery -A app.core.celery_app worker --loglevel=debug --pool=solo

# Check Redis connection
redis-cli ping

# Check if tasks are in queue
redis-cli llen celery
```

---

## COLLECTION & ANALYSIS

### After all scenarios complete:

1. **Collect logs:**
   ```bash
   # Copy logs to test_results
   cp logs/*.log test_results/
   ```

2. **Generate summary report:**
   ```bash
   python scripts/generate_test_report.py
   ```

3. **Identify patterns:**
   - Success rate trends
   - Performance metrics
   - Error frequency
   - Recovery time

4. **Create enhancement roadmap:**
   - Priority 1 (Critical): [2-3 items]
   - Priority 2 (High): [2-3 items]
   - Priority 3 (Medium): [2-3 items]

---

## SUCCESS CRITERIA

- [ ] All 450 candidates imported
- [ ] Queue tasks completed
- [ ] Restart recovery works
- [ ] No duplicate executions
- [ ] Stuck task detected
- [ ] Database integrity maintained
- [ ] Dashboard shows real-time updates
- [ ] Error messages clear and helpful
- [ ] All scenarios documented
- [ ] Recommendations provided

---

## TIME ESTIMATE

| Phase | Duration | Notes |
|-------|----------|-------|
| Setup | 15 min | Redis, Python, Backend setup |
| Test Execution | 5 min | Initial import & queueing |
| Monitoring | 30 min | Real-time queue watching |
| Scenario A | 10 min | Stop mid-process |
| Scenario B | 10 min | Restart recovery |
| Scenario C | 10 min | Stuck queue |
| Scenario D | 10 min | Stuck + restart |
| Analysis | 20 min | Document findings |
| **TOTAL** | **~110 min** | **~2 hours** |

---

## NEXT STEPS

After completing all scenarios:

1. Review all findings in test_results/
2. Create COMPLETE_TEST_REPORT.md with summary
3. Document self-healing enhancements needed
4. Prioritize recommendations
5. Implement Priority 1 items in next sprint

---


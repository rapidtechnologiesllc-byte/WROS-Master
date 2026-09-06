# Local Message Queue Verification - 4-Step Setup Guide

Complete end-to-end testing of the message queue system with comprehensive verification.

**Total Time: 15-20 minutes**

---

## Table of Contents

1. [Quick Start (4 Steps)](#quick-start)
2. [Detailed Steps](#detailed-steps)
3. [Verification Points](#verification-points)
4. [Troubleshooting](#troubleshooting)
5. [What You'll See](#what-youll-see)

---

## Quick Start

```powershell
# Terminal 1: Setup Redis
./redis-setup.ps1

# Terminal 2: Start Backend Services
./backend-startup-complete.ps1

# Terminal 3: Run Verification Tests
cd backend
python test_queue_verification.py

# Terminal 4: Monitor in Real-Time
# Open: http://localhost:3000/queue-dashboard
# Watch queue items transition from PENDING → PROCESSING → COMPLETED
```

---

## Detailed Steps

### Step 1: Redis Setup (5 minutes)

**Purpose:** Ensure Redis is running - required for Celery message broker

**Command:**
```powershell
cd C:\dev\WROS-Master
./redis-setup.ps1
```

**What It Does:**
- ✅ Detects if Redis is already running
- ✅ Checks if Redis is installed (looks in standard Windows locations)
- ✅ Provides installation guidance if Redis not found
- ✅ Starts Redis if installed but not running
- ✅ Verifies Redis is listening on port 6379

**Expected Output:**
```
[STEP 1] Checking if Redis is already running...
✅ Redis is already running on port 6379

[STEP 2] Checking if Redis is installed...
✅ Found Redis at: C:\Program Files\Redis\redis-server.exe

[STEP 3] Starting Redis...
✅ Redis process started (PID: 1234)
✅ Redis is listening on port 6379

[STEP 4] Testing Redis connectivity...
✅ Redis PING successful - connection verified

==================== REDIS READY TO USE ====================

Redis is running and ready for backend services!

Next steps:
  1. Run: ./backend-startup-complete.ps1
```

**If Redis Not Installed:**
The script provides clear installation options:
- **Memurai** (recommended for Windows)
- **Chocolatey**
- **Windows Subsystem for Linux (WSL2)**
- **Docker**

Follow the provided instructions and rerun the script.

---

### Step 2: Backend Services Startup (3 minutes)

**Purpose:** Start FastAPI backend, Celery worker, and verify all 3 services are healthy

**Command:**
```powershell
cd C:\dev\WROS-Master
./backend-startup-complete.ps1
```

**What It Does:**
1. ✅ Verifies Redis is running (prerequisite)
2. ✅ Kills any stray processes on port 8080
3. ✅ Stops existing Celery workers
4. ✅ Starts Celery worker (logs to `backend/celery-worker.log`)
5. ✅ Starts FastAPI backend on port 8080
6. ✅ Shows real-time backend logs

**Expected Output:**
```
==================== BACKEND STARTUP - COMPLETE STACK ====================

[STEP 1] Verifying Redis is running on port 6379...
✅ Redis is running

[STEP 2] Cleaning up existing processes...
✅ Previous processes cleaned up

[STEP 3] Starting Celery worker...
   Launching Celery worker (logging to: C:\dev\WROS-Master\backend\celery-worker.log)...
✅ Celery worker started (PID: 5678)
   Logs: C:\dev\WROS-Master\backend\celery-worker.log

[STEP 4] Starting FastAPI backend on port 8080...
   Launching: uvicorn app.main:app --reload --host 127.0.0.1 --port 8080

INFO:     Uvicorn running on http://127.0.0.1:8080
INFO:     Application startup complete
```

**Keep This Terminal Open:**
- The backend logs will be displayed here
- You'll see messages like: `"[Worker] Processing message..."` when Celery processes queue items
- Don't close this window - the backend needs to keep running

---

### Step 3: Run Verification Tests (5 minutes)

**Purpose:** Create test candidates and verify they flow through the message queue system

**Command:**
```powershell
cd C:\dev\WROS-Master\backend
python test_queue_verification.py
```

**What It Does:**
1. ✅ Connects to PostgreSQL database
2. ✅ Verifies ChannelQueueItem table exists
3. ✅ Creates 3 test candidates
4. ✅ Verifies candidates are in database
5. ✅ Creates corresponding queue items
6. ✅ Verifies queue items are in database
7. ✅ Simulates worker processing (PENDING → COMPLETED)
8. ✅ Checks API endpoints
9. ✅ Tests error conditions
10. ✅ Displays dashboard readiness

**Expected Output:**
```
================================================================================
MESSAGE QUEUE VERIFICATION TEST SUITE
================================================================================

[TEST 1: Database Connection]
────────────────────────────────────────────────────────────────────────────────
✅ Database connection successful

[TEST 2: Verify ChannelQueueItem Table]
────────────────────────────────────────────────────────────────────────────────
✅ ChannelQueueItem table exists and is accessible

[TEST 3: Create Test Candidates]
────────────────────────────────────────────────────────────────────────────────
✅ Created candidate: Alice Johnson (ID: abc12345...)
✅ Created candidate: Bob Smith (ID: def67890...)
✅ Created candidate: Carol Williams (ID: ghi11111...)

📊 Summary: Created 3 test candidates

[TEST 4: Verify Candidates Persisted in Database]
────────────────────────────────────────────────────────────────────────────────
✅ All 3 candidates found in database

[TEST 5: Create Test Queue Items]
────────────────────────────────────────────────────────────────────────────────
ℹ️  Creating manual queue items to simulate worker processing
✅ Created queue item: Alice Johnson (Status: PENDING)
✅ Created queue item: Bob Smith (Status: PENDING)
✅ Created queue item: Carol Williams (Status: PENDING)

📊 Summary: Created 3 queue items

[TEST 6: Verify Queue Items Persisted]
────────────────────────────────────────────────────────────────────────────────
✅ Found 3+ PENDING queue items

[TEST 7: Queue Statistics]
────────────────────────────────────────────────────────────────────────────────
Queue Status Summary:
  PENDING:     3
  PROCESSING:  0
  COMPLETED:   0
  FAILED:      0
  ────────────────
  TOTAL:       3
✅ Total 3 queue items in system

[TEST 8: Manual Queue Item Processing Simulation]
────────────────────────────────────────────────────────────────────────────────
ℹ️  Simulating what the Celery worker would do...
✅ Marked queue item as PROCESSING: abc12345...
✅ Marked queue item as COMPLETED: abc12345...

[TEST 9: Verify Processing Results]
────────────────────────────────────────────────────────────────────────────────
✅ Found 1 completed item(s)
  ✓ Item abc12345... (Type: create_candidate)

[TEST 10: Verify API Endpoints Available]
────────────────────────────────────────────────────────────────────────────────
✅ API endpoint available: Queue Stats (http://localhost:8080/queues/stats)
✅ API endpoint available: Queue Messages (http://localhost:8080/queues)

[TEST 11: Error Condition Testing]
────────────────────────────────────────────────────────────────────────────────
ℹ️  Test: Invalid queue type
✅ Invalid queue item created (worker will handle it)

[TEST 12: Dashboard Data Readiness Check]
────────────────────────────────────────────────────────────────────────────────
Dashboard Data Summary:
  Total Queue Items:  3
  Candidate Queue:    3
  Email Queue:        0
✅ Dashboard will display real queue data

VERIFICATION COMPLETE
────────────────────────────────────────────────────────────────────────────────

NEXT STEPS:

1. If not already running, start the backend:
   cd backend
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080

2. Start the Celery worker:
   cd backend
   python -m celery -A app worker --loglevel=info

3. Open the dashboard:
   http://localhost:3000/queue-dashboard

4. Watch the queue items get processed in real-time:
   - PENDING → PROCESSING → COMPLETED
   - Dashboard refreshes every 10 seconds

5. Check Celery logs to see worker processing messages

TESTING SCENARIOS:
✅ Candidates created successfully
✅ Queue items created successfully
✅ Dashboard endpoints available
✅ Error handling verified
✅ Real-time status tracking works

Your message queue is ready for testing!

================================================================================
```

---

### Step 4: Monitor Dashboard in Real-Time (5+ minutes)

**Purpose:** Watch queue items flow through the system in real-time

**Command:**
Open browser:
```
http://localhost:3000/queue-dashboard
```

**What You'll See:**

1. **Queue Statistics Section:**
   - PENDING count (items waiting to be processed)
   - PROCESSING count (items currently being handled)
   - COMPLETED count (successfully processed)
   - FAILED count (errors encountered)

2. **Queue Messages Table:**
   - Real-time list of all queue items
   - Status transitions: PENDING → PROCESSING → COMPLETED
   - Shows queue type, message type, timestamps
   - Auto-refreshes every 10 seconds

3. **Real-Time Updates:**
   - Watch items move from PENDING to PROCESSING (Celery worker starts)
   - Watch items move from PROCESSING to COMPLETED (after ~1 second)
   - Dashboard updates automatically (no page refresh needed)

**Expected Progression:**
```
Initial State (from TEST 3):
  PENDING:    3
  PROCESSING: 0
  COMPLETED:  0

After 5-10 seconds (Celery worker processes):
  PENDING:    2
  PROCESSING: 1 (being processed now)
  COMPLETED:  0

After 15-20 seconds:
  PENDING:    0
  PROCESSING: 0
  COMPLETED:  3+ (all test items completed)
```

---

## Verification Points

Use this checklist to verify everything is working:

### Verification Checklist

- [ ] **Redis Running**
  - Test: `redis-cli ping` returns `PONG`
  - Port: 6379 should be in use (`netstat -ano | findstr :6379`)

- [ ] **Celery Worker Running**
  - Test: Look for "celery worker online" in logs
  - Port: Redis port 6379 connected (in logs)
  - Processes: 4 worker processes spawned

- [ ] **FastAPI Backend Running**
  - Test: `curl http://localhost:8080/queues/stats` returns JSON
  - Port: 8080 should be in use
  - Logs: Show "Application startup complete"

- [ ] **Database Connected**
  - Test: `python test_queue_verification.py` runs successfully
  - Check: Shows candidate count and queue item count

- [ ] **Queue Items Created**
  - Test: TEST 3 creates 3+ queue items
  - Check: Database shows items with PENDING status

- [ ] **Queue Items Processed**
  - Test: Wait 10-20 seconds
  - Check: Items transition to COMPLETED status

- [ ] **Dashboard Shows Real Data**
  - Test: Dashboard displays queue statistics
  - Check: Numbers match database counts

- [ ] **API Endpoints Responding**
  - Test: `http://localhost:8080/queues/stats` returns 200
  - Test: `http://localhost:8080/queues` returns message list

---

## Troubleshooting

### Problem: Redis Not Starting

**Symptoms:**
- "Redis not found in standard locations"
- Port 6379 not in use

**Solutions:**
1. Install Redis:
   ```powershell
   choco install redis-64
   # or
   # Download Memurai from https://www.memurai.com/
   ```
2. Rerun: `./redis-setup.ps1`
3. Check installation:
   ```powershell
   Get-Command redis-cli
   ```

---

### Problem: Port 8080 Already in Use

**Symptoms:**
- "Address already in use" error from uvicorn
- Backend startup fails

**Solutions:**
1. Kill existing process:
   ```powershell
   netstat -ano | findstr :8080
   # Find the PID, then:
   taskkill /PID 1234 /F
   ```
2. Or use different port:
   ```powershell
   python -m uvicorn app.main:app --port 8081
   ```

---

### Problem: Test Shows "Database Connection Failed"

**Symptoms:**
- "Test 1: Database Connection" fails
- PostgreSQL not accessible

**Solutions:**
1. Verify PostgreSQL is running:
   ```powershell
   netstat -ano | findstr :5432
   ```
2. Check database URL in `.env`:
   ```
   DATABASE_URL=postgresql://...@localhost:5432/wros_dev
   ```
3. Verify database exists:
   ```sql
   psql -U app_user -d wros_dev -c "SELECT 1"
   ```

---

### Problem: Celery Worker Not Processing Messages

**Symptoms:**
- Queue items stay in PENDING status
- Celery logs show "waiting for tasks"
- Dashboard doesn't update

**Solutions:**
1. Verify Celery is running:
   ```powershell
   Get-Process celery
   # or
   Get-Process python | Where-Object { $_.CommandLine -like "*celery*" }
   ```
2. Check Redis connection:
   ```powershell
   redis-cli ping
   ```
3. Check Celery logs:
   ```powershell
   Get-Content backend\celery-worker.log -Tail 50
   ```
4. Restart Celery:
   ```powershell
   taskkill /IM python.exe /F
   ./backend-startup-complete.ps1
   ```

---

### Problem: Dashboard Not Showing Queue Data

**Symptoms:**
- Dashboard loads but shows no queue items
- Statistics show all zeros
- API endpoints return empty data

**Solutions:**
1. Verify queue items exist:
   ```powershell
   cd backend
   python -c "from app.core.database import SessionLocal; from app.models.channel_queue import ChannelQueueItem; db = SessionLocal(); print(db.query(ChannelQueueItem).count())"
   ```
2. Check dashboard endpoint:
   ```powershell
   curl http://localhost:8080/queues/stats
   ```
3. Verify frontend can connect to backend:
   - Open browser DevTools (F12)
   - Check Network tab - calls to `http://localhost:8080/queues/*` should return data
   - Check Console for CORS errors

---

### Problem: Tests Pass but Dashboard Shows "No Data"

**Symptoms:**
- TEST 12 shows "Dashboard will display real queue data"
- But dashboard remains empty

**Possible Causes:**
- Frontend not connected to backend API
- CORS headers misconfigured
- Frontend still loading old data

**Solutions:**
1. Hard refresh dashboard:
   ```
   Ctrl+Shift+R  (or Cmd+Shift+R on Mac)
   ```
2. Clear browser cache:
   - DevTools → Application → Clear Storage
3. Check CORS headers:
   ```powershell
   curl -i http://localhost:8080/queues/stats | findstr "Access-Control"
   ```

---

## What You'll See

### Terminal 1: Redis Setup
```
✅ Redis is running
✅ Redis is listening on port 6379
✅ Redis PING successful - connection verified
```

### Terminal 2: Backend Startup
```
✅ Celery worker started (PID: 5678)
✅ Redis is running

INFO:     Uvicorn running on http://127.0.0.1:8080
INFO:     Application startup complete
```

### Terminal 3: Verification Tests
```
✅ Database connection successful
✅ Created candidate: Alice Johnson
✅ Created candidate: Bob Smith
✅ Created candidate: Carol Williams
✅ Found 3+ PENDING queue items
✅ Dashboard will display real queue data
```

### Terminal 4: Dashboard (Browser)
```
Queue Statistics
├─ PENDING:    3
├─ PROCESSING: 0
├─ COMPLETED:  0
└─ FAILED:     0

Queue Messages
├─ Alice Johnson - PENDING (2 minutes ago)
├─ Bob Smith - PENDING (2 minutes ago)
└─ Carol Williams - PENDING (2 minutes ago)
```

### After 10-20 Seconds (Worker Processes Items)
```
Queue Statistics
├─ PENDING:    0
├─ PROCESSING: 0
├─ COMPLETED:  3
└─ FAILED:     0

Queue Messages
├─ Alice Johnson - COMPLETED (1 minute ago)
├─ Bob Smith - COMPLETED (1 minute ago)
└─ Carol Williams - COMPLETED (1 minute ago)
```

---

## Complete Flow Diagram

```
START
  ↓
Redis Running? (./redis-setup.ps1)
  ├─ Yes → Continue
  └─ No → Install & Rerun
  ↓
Backend Started? (./backend-startup-complete.ps1)
  ├─ Celery Worker ✓
  ├─ FastAPI Backend ✓
  └─ Connected to Redis ✓
  ↓
Tests Passing? (python test_queue_verification.py)
  ├─ Database Connected ✓
  ├─ Candidates Created ✓
  ├─ Queue Items Created ✓
  └─ Statistics Available ✓
  ↓
Dashboard Shows Data? (http://localhost:3000/queue-dashboard)
  ├─ Queue Statistics ✓
  ├─ Real-time Updates ✓
  └─ Status Transitions ✓
  ↓
✅ MESSAGE QUEUE SYSTEM VERIFIED & WORKING
```

---

## Success Criteria

Your setup is complete and working when:

✅ All 4 terminals run without errors
✅ Test script shows 12/12 tests passing
✅ Dashboard displays queue statistics
✅ Queue items transition from PENDING → COMPLETED
✅ Dashboard updates every 10 seconds automatically
✅ API endpoints respond with real data
✅ No errors in any logs

---

## Next Steps

Now that the message queue is verified:

1. **Create More Test Data**
   ```powershell
   cd backend
   python test_queue_verification.py
   # Run multiple times to create more candidates
   ```

2. **Test with Real Candidates**
   - Use the frontend to create actual candidates
   - Watch them flow through the queue
   - Verify Thunder autonomous flow works

3. **Monitor Celery Worker**
   - Check `backend/celery-worker.log` for details
   - Watch processing times
   - Test error recovery (mark items as FAILED, then retry)

4. **Test Dashboard Features**
   - Filter by queue type
   - Filter by status
   - View message details
   - Test retry functionality

5. **Load Testing**
   - Create 100+ queue items
   - Verify performance under load
   - Monitor CPU/memory usage

---

## Files Reference

| File | Purpose |
|------|---------|
| `redis-setup.ps1` | Detects/installs/starts Redis |
| `backend-startup-complete.ps1` | Starts FastAPI + Celery |
| `test_queue_verification.py` | Creates test data & verifies flow |
| `LOCAL_TESTING.md` | This guide |
| `backend/celery-worker.log` | Celery worker logs |

---

**Happy Testing!** 🚀

For issues or questions, check the **Troubleshooting** section above.

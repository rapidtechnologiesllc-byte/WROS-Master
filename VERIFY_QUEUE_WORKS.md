# Message Queue Verification Checklist

Quick checklist to verify the message queue system is working end-to-end.

**Print this out and check off each item as you complete it.**

---

## PRE-FLIGHT CHECKS

- [ ] PostgreSQL is running on port 5432
- [ ] No processes already using port 8080 (backend)
- [ ] No processes already using port 6379 (Redis)
- [ ] Network connectivity: `ping 127.0.0.1` works
- [ ] PowerShell execution policy allows scripts

---

## STEP 1: REDIS SETUP (Expected Time: 2-5 minutes)

**Command:** `./redis-setup.ps1`

### Verification Checkpoints

- [ ] Script starts without errors
- [ ] Output shows: "✅ Redis is running"
- [ ] Output shows: "✅ Redis is listening on port 6379"
- [ ] Output shows: "✅ Redis PING successful"
- [ ] **Success message:** "REDIS READY TO USE"

### If Failed:
- [ ] Run `netstat -ano | findstr :6379` to check port
- [ ] Install Redis per script instructions
- [ ] Rerun `./redis-setup.ps1`

---

## STEP 2: BACKEND STARTUP (Expected Time: 2-3 minutes)

**Command:** `./backend-startup-complete.ps1`

### Verification Checkpoints

- [ ] Script starts without errors
- [ ] Output shows: "✅ Redis is running"
- [ ] Output shows: "✅ Previous processes cleaned up"
- [ ] Output shows: "✅ Celery worker started (PID: ...)"
- [ ] Output shows: "✅ Celery worker started" log message
- [ ] Uvicorn starts with output showing port 8080
- [ ] Backend logs show: "Application startup complete"
- [ ] **Keep this terminal open** while testing

### If Failed:
- [ ] Check if Redis is still running (use Step 1 script)
- [ ] Kill stray processes: `taskkill /IM python.exe /F`
- [ ] Rerun `./backend-startup-complete.ps1`

---

## STEP 3: VERIFICATION TESTS (Expected Time: 3-5 minutes)

**Command:** `cd backend` then `python test_queue_verification.py`

### Test Results

#### Test 1: Database Connection
- [ ] Shows: "✅ Database connection successful"

#### Test 2: ChannelQueueItem Table
- [ ] Shows: "✅ ChannelQueueItem table exists"

#### Test 3: Create Test Candidates
- [ ] Creates Alice Johnson: "✅ Created candidate..."
- [ ] Creates Bob Smith: "✅ Created candidate..."
- [ ] Creates Carol Williams: "✅ Created candidate..."
- [ ] Shows: "📊 Summary: Created 3 test candidates"

#### Test 4: Verify Candidates Persisted
- [ ] Shows: "✅ All 3 candidates found in database"

#### Test 5: Create Test Queue Items
- [ ] Creates 3 queue items: "✅ Created queue item..."
- [ ] Shows: "📊 Summary: Created 3 queue items"

#### Test 6: Verify Queue Items Persisted
- [ ] Shows: "✅ Found 3+ PENDING queue items"

#### Test 7: Queue Statistics
- [ ] Shows queue status summary
- [ ] PENDING count ≥ 3
- [ ] Shows: "✅ Total X queue items in system"

#### Test 8: Processing Simulation
- [ ] Shows: "✅ Marked queue item as PROCESSING"
- [ ] Shows: "✅ Marked queue item as COMPLETED"

#### Test 9: Verify Processing Results
- [ ] Shows: "✅ Found 1+ completed item(s)"

#### Test 10: API Endpoints Available
- [ ] Shows: "✅ API endpoint available: Queue Stats"
- [ ] Shows: "✅ API endpoint available: Queue Messages"

#### Test 11: Error Condition Testing
- [ ] Shows: "✅ Invalid queue item created"

#### Test 12: Dashboard Data Readiness
- [ ] Shows queue statistics (PENDING/PROCESSING/COMPLETED counts)
- [ ] Shows: "✅ Dashboard will display real queue data"

### Overall Test Result
- [ ] **Status:** All 12 tests passing
- [ ] **Queue Items:** 3+ created and accessible
- [ ] **Database:** Connected and working
- [ ] **API:** Endpoints responding

### If Failed:
- [ ] Verify backend is still running (check Step 2 terminal)
- [ ] Verify Redis is still running: `redis-cli ping`
- [ ] Check PostgreSQL connection in `backend/.env`
- [ ] Rerun test after fixing issues

---

## STEP 4: DASHBOARD VERIFICATION (Expected Time: 5+ minutes)

**Action:** Open `http://localhost:3000/queue-dashboard` in browser

### Initial State (Immediately After Step 3)

- [ ] Dashboard loads without errors
- [ ] Shows "Queue Statistics" card
- [ ] PENDING count shows 2 or 3
- [ ] PROCESSING count shows 0 or 1
- [ ] COMPLETED count shows 0 or 1
- [ ] FAILED count shows 0
- [ ] Shows "Queue Messages" table
- [ ] Table has columns: Type, Status, Recipient, Created At
- [ ] Table shows 3+ message rows

### Message Progression (Within 10-20 Seconds)

- [ ] Watch PENDING count decrease
- [ ] Watch COMPLETED count increase
- [ ] Messages change from "PENDING" to "PROCESSING"
- [ ] Messages change from "PROCESSING" to "COMPLETED"
- [ ] Dashboard updates automatically (every 10 seconds)

### Final State (After 30 Seconds)

- [ ] PENDING count = 0
- [ ] COMPLETED count ≥ 3
- [ ] All messages show "COMPLETED" status
- [ ] Dashboard continues refreshing (auto-update working)

### Real-Time Features Verification

- [ ] Dashboard refreshes without manual page reload
- [ ] Statistics update in real-time
- [ ] Table updates in real-time
- [ ] No console errors (F12 → Console tab)
- [ ] No network errors (F12 → Network tab)

### API Verification (from Browser)

Open new browser tab and test:
- [ ] `http://localhost:8080/queues/stats` returns JSON with queue stats
- [ ] `http://localhost:8080/queues` returns JSON with message list

### If Dashboard Shows No Data:
- [ ] Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
- [ ] Clear cache: F12 → Application → Clear all storage
- [ ] Verify backend is running (check Step 2 terminal)
- [ ] Check browser console for errors (F12)

---

## SYSTEM HEALTH CHECKS

### Check 1: Redis Health
```powershell
redis-cli ping
# Should return: PONG
```
- [ ] Returns PONG

### Check 2: Backend API Health
```powershell
curl http://localhost:8080/docs
# Should return FastAPI Swagger documentation
```
- [ ] Returns HTML (API docs page)

### Check 3: Queue Statistics API
```powershell
curl http://localhost:8080/queues/stats
# Should return JSON with queue stats
```
- [ ] Returns JSON with queue statistics

### Check 4: Celery Worker Status
```
Check Step 2 terminal for messages like:
  "[*] Ready to accept tasks"
  "[*] celery@HOSTNAME ready."
```
- [ ] Worker shows "Ready to accept tasks"

### Check 5: Database Queries
```powershell
cd backend
python -c "from app.core.database import SessionLocal; from app.models.channel_queue import ChannelQueueItem; db = SessionLocal(); print(f'Total queue items: {db.query(ChannelQueueItem).count()}')"
```
- [ ] Shows count > 0

---

## PERFORMANCE CHECKS

### Processing Speed
- [ ] Queue items process within 1-3 seconds
- [ ] No messages stuck in PROCESSING state
- [ ] All PENDING items eventually reach COMPLETED

### CPU/Memory Usage
- [ ] Python process uses < 200MB RAM
- [ ] CPU usage normal when idle
- [ ] No memory leaks (stays stable over time)

### Network
- [ ] Dashboard updates smoothly without lag
- [ ] API responses within 200ms
- [ ] No timeout errors in logs

---

## ERROR HANDLING

### Test 1: Invalid Data
Create a candidate with missing email:
- [ ] Backend accepts without crashing
- [ ] Queue item created with error handling
- [ ] Worker marks as FAILED (not hanging)

### Test 2: Database Disconnect
Stop PostgreSQL briefly (Ctrl+C in psql):
- [ ] Worker catches error and logs it
- [ ] Worker attempts retry
- [ ] Celery doesn't crash

### Test 3: Redis Disconnect
Stop Redis (`redis-cli shutdown`):
- [ ] Worker catches connection error
- [ ] Error logged clearly
- [ ] Can reconnect by restarting Redis

---

## INTEGRATION CHECKS

### Check 1: Candidate → Queue Item Flow
- [ ] Candidates created via API appear in database
- [ ] Corresponding queue items created automatically
- [ ] Queue items have correct candidate_id

### Check 2: Queue Item → Message Processing
- [ ] Worker picks up PENDING items
- [ ] Status transitions: PENDING → PROCESSING → COMPLETED
- [ ] Result stored in database

### Check 3: Message → Dashboard Display
- [ ] Dashboard fetches real data from API
- [ ] Statistics match database counts
- [ ] Messages list matches queue items
- [ ] Updates in real-time

---

## FINAL VERIFICATION SUMMARY

### Required Checks (All Must Pass)

- [ ] Redis is running on port 6379
- [ ] Backend is running on port 8080
- [ ] Celery worker is running and ready
- [ ] Database has 3+ test candidates
- [ ] Database has 3+ queue items
- [ ] All 12 verification tests pass
- [ ] Dashboard displays queue statistics
- [ ] Dashboard shows real queue items
- [ ] Queue items processing in < 20 seconds
- [ ] API endpoints responding correctly

### System Status

If all checks above are complete:

✅ **MESSAGE QUEUE SYSTEM IS WORKING CORRECTLY**

The system is ready for:
- Production deployment testing
- Load testing with real data
- Integration with Thunder autonomous loop
- Dashboard monitoring and analytics

---

## NEXT STEPS

### Immediate (Within 5 minutes)
1. Keep all 3 services running (Redis, Backend, Celery)
2. Leave dashboard open for monitoring
3. Test with new candidates created via frontend

### Short-term (Next Session)
1. Create more test data (100+ queue items)
2. Test dashboard with large dataset
3. Verify performance under load
4. Test error recovery and retry logic

### Production Readiness
- [ ] Load test with 1000+ queue items
- [ ] Monitor memory/CPU over 1 hour
- [ ] Test deployment to staging server
- [ ] Document monitoring procedures

---

## TROUBLESHOOTING QUICK REFERENCE

| Issue | Solution |
|-------|----------|
| Redis not running | Run `./redis-setup.ps1` |
| Port 8080 in use | `taskkill /IM python.exe /F` |
| Database error | Verify PostgreSQL running, check `.env` |
| Tests fail | Check all 3 services running |
| Dashboard no data | Hard refresh (Ctrl+Shift+R), check browser console |
| Worker not processing | Verify Redis connection, restart Celery |
| API returns 500 error | Check backend logs in Step 2 terminal |

---

## SIGN-OFF

**Verification Completed By:** ________________  
**Date:** ________________  
**Time Taken:** ________________  
**Issues Encountered:** ________________  
**Resolution:** ________________  

**Overall Status:** 
- [ ] ✅ All systems working
- [ ] ⚠️  Minor issues (documented above)
- [ ] ❌ Critical issues (needs investigation)

---

**For detailed troubleshooting, see `LOCAL_TESTING.md`**

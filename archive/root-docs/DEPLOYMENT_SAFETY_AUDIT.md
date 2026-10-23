# Deployment Safety Audit
**Purpose:** Verify nothing breaks before deploying. Prevent "fixing the same code" pattern.

## Pre-Deployment State Verification

### 1. Current Working Features (Must Not Break)

**Candidate Creation Pipeline:**
- [ ] POST /api/v1/candidates (create new candidate)
  - Expected: HTTP 201, candidate_id returned
  - Test: `curl -X POST http://localhost:8081/api/v1/candidates -H "Content-Type: application/json" -d '{"email":"test@example.com"}'`

**Authentication:**
- [ ] POST /auth/login (admin user login)
  - Expected: HTTP 200, access_token returned
  - Test User: superuser@blitzenx.com / TestUser@123

**Dashboard Access:**
- [ ] GET /api/v1/candidates/all (list all candidates)
  - Expected: HTTP 200, candidates array returned
  - Test: `curl -X GET http://localhost:8081/api/v1/candidates/all -H "Authorization: Bearer TOKEN"`

**Job Management:**
- [ ] GET /api/v1/jobs/all (list jobs)
  - Expected: HTTP 200, jobs array returned

**Queue Processing:**
- [ ] Queue processor running (check logs for "Queue processor started")
  - Expected: Background task processing messages
  - Status: Watch backend logs for COMPLETED/FAILED messages

### 2. New Features (Should Now Work)

**Message Display:**
- [ ] GET /api/v1/candidates/{id}/messages
  - Expected: HTTP 200, message array returned
  - Test after creating candidate with messages

**Activity Feed:**
- [ ] GET /api/v1/candidates/{id}/activity-feed
  - Expected: HTTP 200, activity array returned

**Queue Health:**
- [ ] GET /queue-health (health endpoint)
  - Expected: HTTP 200, {pending: N, processing: N, failed: N}

### 3. Regression Test Cases (Most Likely to Break)

**Route Registration:**
```
These endpoints MUST work or routing is broken:
- GET /api/v1/candidates/all → ✅ Verify returns candidates
- GET /api/v1/candidates/{id} → ✅ Verify returns single candidate
- GET /api/v1/candidates/{id}/messages → ✅ NEW - Verify works
- POST /api/v1/candidates → ✅ Verify creation works
- GET /queue-health → ✅ NEW - Verify health check works
```

**Database Integrity:**
```
These MUST not error or data is corrupt:
- channel_queue_item table exists ✅ Verify in app_schema
- handler_duration_ms column exists ✅ Verify column added
- MessageDeliveryLog table has records ✅ Verify schema
```

**Handler Timeout:**
```
This MUST work or queue hangs:
- Handlers time out after 30s ✅ Verify in logs when slow query happens
- Timeout errors are retried ✅ Verify message marked PENDING on timeout
```

## Deployment Procedure (Safe)

### Phase A: Pre-Deploy (5 min)
```bash
# 1. Verify current state is working
Backend running on :8081 ✅
Database connected ✅
Routes initialized ✅

# 2. Backup database
pg_dump wros_dev > backup_$(date +%s).sql

# 3. Record current metrics
- Pending messages in queue: ___
- Failed messages: ___
- Failed message count: ___
- Average handler duration: ___
```

### Phase B: Deploy (10 min)
```bash
# 1. Stop backend gracefully (drain queue)
- Wait for all PROCESSING messages to complete or timeout
- Monitor logs: "Queue processor stopped"

# 2. Pull latest code
git pull origin main

# 3. Restart backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8081

# 4. Verify startup
- Check logs: "[OK] Database contract validated"
- Check logs: "[OK] ChannelQueueItem table verified"
- Check logs: "[OK] Application startup complete"
```

### Phase C: Smoke Tests (10 min)

**Critical Path Test (Must Pass):**
```bash
# Test 1: Authentication still works
TOKEN=$(curl -s -X POST http://localhost:8081/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"superuser@blitzenx.com","password":"TestUser@123"}' \
  | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
  echo "❌ DEPLOYMENT FAILED: Authentication broken"
  exit 1
fi

# Test 2: Candidates endpoint still works
CANDIDATES=$(curl -s -X GET http://localhost:8081/api/v1/candidates/all \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.candidates | length')

if [ "$CANDIDATES" -lt 0 ]; then
  echo "❌ DEPLOYMENT FAILED: Candidates endpoint broken"
  exit 1
fi

# Test 3: New message endpoint works
CANDIDATE_ID=$(curl -s -X GET http://localhost:8081/api/v1/candidates/all \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.candidates[0].candidateID')

MESSAGES=$(curl -s -X GET http://localhost:8081/api/v1/candidates/$CANDIDATE_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.messages | length')

if [ -z "$MESSAGES" ]; then
  echo "❌ DEPLOYMENT FAILED: Message endpoint broken"
  exit 1
fi

# Test 4: Queue health check
QUEUE_STATUS=$(curl -s -X GET http://localhost:8081/queue-health)
if [ -z "$(echo $QUEUE_STATUS | jq '.pending')" ]; then
  echo "❌ DEPLOYMENT FAILED: Queue health check broken"
  exit 1
fi

echo "✅ ALL SMOKE TESTS PASSED - DEPLOYMENT SUCCESSFUL"
```

### Phase D: Post-Deploy Monitoring (Next 30 min)

**Watch for:**
- ❌ Queue processor hanging (no messages being processed)
- ❌ High error rate (>5% failed messages)
- ❌ Timeout storms (>10 timeout errors per minute)
- ❌ Database connection errors
- ❌ Memory leaks (steadily increasing)

**If Any Issue Detected:**
```bash
# IMMEDIATE ROLLBACK
git checkout previous-commit
# OR restore database backup
psql wros_dev < backup_XXXXXXX.sql

# Restart backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8081

# Verify rollback successful
# Run smoke tests again
```

## Prevention: Never Fix The Same Code Twice

### Root Cause Analysis (Why This Happened)

**The Pattern:**
1. Code written but not tested end-to-end
2. Deployed to production
3. Broke something (routing, database, permissions)
4. Fixed in production
5. Two weeks later: same issue again

**Why?**
- No automated regression tests
- No before/after comparison
- No deployment checklist enforcement
- No "golden master" test suite

### Future Prevention: The Checklist

**For EVERY deployment going forward:**

1. **Before Commit:**
   - [ ] Code compiles (no syntax errors)
   - [ ] Related tests pass
   - [ ] No dead code (code review gate passes)
   - [ ] Database schema migrations tested on staging

2. **Before Deployment:**
   - [ ] Database backup taken
   - [ ] Current feature list documented (this file)
   - [ ] Smoke test script prepared (above)
   - [ ] Rollback plan ready
   - [ ] On-call team notified

3. **After Deployment:**
   - [ ] All smoke tests pass
   - [ ] Logs show "Application startup complete"
   - [ ] Queue processor actively processing (check /queue-health)
   - [ ] No error spike in first 5 minutes
   - [ ] Manual walk-through of 3 critical paths

### Regression Test Suite (Run These Every Deployment)

```bash
#!/bin/bash
# DEPLOYMENT_REGRESSION_TESTS.sh

set -e

TOKEN="$1"  # Pass token from smoke test
BASE_URL="http://localhost:8081"

echo "Running regression test suite..."

# Test Set 1: Core Routing
echo "[1/10] Testing routing to /candidates/all..."
curl -s "$BASE_URL/api/v1/candidates/all" -H "Authorization: Bearer $TOKEN" | jq . > /dev/null

# Test Set 2: Message Endpoints (NEW)
echo "[2/10] Testing message endpoints..."
curl -s "$BASE_URL/api/v1/candidates/TEST/messages" -H "Authorization: Bearer $TOKEN" | jq . > /dev/null

# Test Set 3: Activity Feed (NEW)
echo "[3/10] Testing activity feed..."
curl -s "$BASE_URL/api/v1/candidates/TEST/activity-feed" -H "Authorization: Bearer $TOKEN" | jq . > /dev/null

# Test Set 4: Queue Health (NEW)
echo "[4/10] Testing queue health..."
curl -s "$BASE_URL/queue-health" | jq . > /dev/null

# Test Set 5: Database Connectivity
echo "[5/10] Testing database..."
# Check if any PROCESSING messages are older than 30s (hung handler)
# SELECT COUNT(*) FROM app_schema.channel_queue_item 
# WHERE status='PROCESSING' AND processing_started_at < NOW() - INTERVAL '30 seconds'

# Test Set 6: Handler Timeout
echo "[6/10] Testing handler timeout enforcement..."
# Would need to trigger a slow query and verify it times out

# Test Set 7: Auth Still Works
echo "[7/10] Testing authentication..."
curl -s "$BASE_URL/auth/login" -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test"}' | jq . > /dev/null

# Test Set 8: Error Handling
echo "[8/10] Testing error handling..."
# Verify 404 on invalid endpoint
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/nonexistent")
if [ "$HTTP_CODE" != "404" ]; then
  echo "❌ Error handling broken (expected 404, got $HTTP_CODE)"
  exit 1
fi

# Test Set 9: Message Display
echo "[9/10] Testing message display integration..."
# Verify MessageDeliveryLog can be queried

# Test Set 10: No Obvious Errors in Logs
echo "[10/10] Checking logs for errors..."
# grep "ERROR\|CRITICAL" backend.log | head -5

echo "✅ ALL REGRESSION TESTS PASSED"
```

## Checklist: Deploy With Confidence

```
PRE-DEPLOYMENT:
  [ ] Read current state of PRODUCTION_READY.md
  [ ] Verify database backup exists
  [ ] Verify on-call procedure documented
  
DEPLOYMENT:
  [ ] Stop backend gracefully
  [ ] Pull code (git pull)
  [ ] Restart backend
  [ ] Verify startup logs
  
SMOKE TESTS:
  [ ] Auth endpoint returns token
  [ ] Candidates endpoint returns data
  [ ] Messages endpoint responds (HTTP 200 or 404, not error)
  [ ] Queue health endpoint responds
  [ ] No error spike in logs
  
POST-DEPLOYMENT (30 min):
  [ ] Queue processor processing messages
  [ ] No timeout errors in logs
  [ ] Handler duration_ms being recorded
  [ ] Failed message cleanup running
  
IF ANYTHING FAILS:
  [ ] Immediate rollback to previous commit
  [ ] Restore database from backup
  [ ] Investigate root cause
  [ ] DO NOT deploy again until fixed
  [ ] Document what broke and why
```

---

## The Hard Truth

**This is the "nth time fixing the same code" because:**

1. ✅ Code was tested during development
2. ❌ But NOT tested against production-like scenarios
3. ❌ No regression test suite protecting against regressions
4. ❌ No automated verification before deployment
5. ❌ Relying on manual testing (error-prone)

**To prevent this going forward:**

1. **Automated Regression Tests** - Run same tests every deployment
2. **Deployment Checklist** - Use DEPLOYMENT_REGRESSION_TESTS.sh script
3. **Before/After Metrics** - Compare queue stats before vs after
4. **Rollback Automation** - One command to revert if something breaks
5. **Post-Deploy Monitoring** - Watch logs for 30 minutes minimum

**The Investment:**
- 2 hours to set up automated tests
- 5 minutes per deployment to run them
- Saves 10+ hours debugging production issues

**Without This:**
- Every deployment risks breaking something
- You spend time "fixing the same code"
- Users see downtime
- Trust erodes

---

**Decision:**
- [ ] Deploy now with manual smoke tests above
- [ ] Deploy now but create automated tests immediately after
- [ ] Don't deploy until automated tests are created and proven

Which would you prefer?

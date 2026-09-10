# Queue Processor Production Runbook - CYCLE 19

**Last Updated:** 2026-09-10  
**Status:** PRODUCTION READY  
**Critical Urgency:** Messages not processing within 5 minutes = PAGE ON-CALL  

---

## 🚨 CRITICAL ISSUES & QUICK FIXES

### Issue 1: Messages Not Processing (Stuck in PENDING)

**Symptoms:**
- Messages queued 5+ minutes ago still PENDING
- Queue processor logs show no activity
- Job creation endpoint returns success but job never appears in database

**Root Causes (in priority order):**
1. Queue processor not running (process crashed)
2. Database connection pool exhausted
3. Handler timeout (30s exceeded)
4. Circuit breaker triggered (5+ consecutive failures)

**Quick Diagnosis:**

```bash
# Check if queue processor is running
ps aux | grep "python.*queue_processor"
# Expected: 1 process running (not 0, not 2+)

# Check process logs
tail -n 100 /var/log/wros/queue_processor.log
# Expected: "Processing batch" every 2-10 seconds
# Bad sign: "Circuit breaker triggered" or long silence

# Count pending messages
psql -U app_user -d wros_prod -c "SELECT COUNT(*) FROM channel_queue_item WHERE status='PENDING';"
# Expected: < 20 (normal), > 100 (ALERT), > 1000 (CRITICAL)
```

**Fix Steps:**

| Situation | Action | Time |
|-----------|--------|------|
| Process not running | `systemctl start queue-processor` or start manually | 30s |
| Process running but silent | Kill and restart: `systemctl restart queue-processor` | 60s |
| DB connection pool exhausted | Restart backend API: `systemctl restart wros-api` | 2m |
| Circuit breaker triggered | Check logs, fix root cause, manually restart processor | 5m+ |
| Timeout (slow handler) | Increase HANDLER_TIMEOUT_SECONDS from 30→60, restart | 2m |

---

### Issue 2: Dead Letter Queue Overflowing (MAX_RETRIES Exceeded)

**Symptoms:**
- Messages stuck with status=DEAD_LETTER
- No escalation alerts received
- Job creation "succeeded" but recruitment never happens

**Root Causes:**
1. Handler dependency missing (e.g., non-existent function in Depends())
2. Database unavailable during handler execution
3. Handler bug (infinite retry loop)
4. Job deleted mid-processing

**Quick Diagnosis:**

```bash
# Count dead letter messages
psql -U app_user -d wros_prod -c "SELECT COUNT(*) FROM channel_queue_item WHERE status='DEAD_LETTER';"
# Expected: 0-5, > 10 = investigate

# Show dead letter details (oldest first)
psql -U app_user -d wros_prod -c "
  SELECT id, type, created_at, result 
  FROM channel_queue_item 
  WHERE status='DEAD_LETTER' 
  ORDER BY created_at ASC 
  LIMIT 5;
"

# Check for pattern (same type failing repeatedly)
psql -U app_user -d wros_prod -c "
  SELECT type, COUNT(*) 
  FROM channel_queue_item 
  WHERE status='DEAD_LETTER' 
  GROUP BY type 
  ORDER BY COUNT(*) DESC;
"
```

**Fix Steps:**

1. **Identify cause:** Look at `result` field JSON for error message
2. **Fix root cause:** Deploy code fix if handler bug
3. **Clear dead letters:** 
   ```sql
   -- Archive to audit table (don't delete!)
   INSERT INTO dead_letter_archive SELECT * FROM channel_queue_item WHERE status='DEAD_LETTER';
   DELETE FROM channel_queue_item WHERE status='DEAD_LETTER';
   ```
4. **Requeue if safe:** 
   ```sql
   -- Only if you fixed the underlying issue
   UPDATE channel_queue_item 
   SET status='PENDING', retry_count=0 
   WHERE id IN (SELECT id FROM dead_letter_archive WHERE type='job_created_flash')
   ORDER BY created_at DESC LIMIT 10;
   ```

---

### Issue 3: Scheduled Messages Not Triggering (SCHEDULED Status Stuck)

**Symptoms:**
- Flash_Recruiter should run every 4 hours but recruitment stops
- Messages stuck with status=SCHEDULED and scheduled_for in the past
- Logs show "Queue empty" backoff continuously

**Root Cause:**
- Queue processor not checking SCHEDULED messages
- scheduled_for timestamp wrong (in future when should be past)
- Adaptive backoff stuck (empty_batch_count accumulating)

**Quick Diagnosis:**

```bash
# Count scheduled messages ready to process
psql -U app_user -d wros_prod -c "
  SELECT COUNT(*) FROM channel_queue_item 
  WHERE status='SCHEDULED' AND scheduled_for <= NOW();
"

# Show oldest scheduled message that should have run
psql -U app_user -d wros_prod -c "
  SELECT id, type, scheduled_for, NOW() - scheduled_for as overdue 
  FROM channel_queue_item 
  WHERE status='SCHEDULED' AND scheduled_for <= NOW() 
  ORDER BY scheduled_for ASC 
  LIMIT 1;
"

# Check queue processor logs for scheduling code
tail -n 200 /var/log/wros/queue_processor.log | grep -i "scheduled\|adaptive\|backoff"
```

**Fix Steps:**

1. Restart queue processor: `systemctl restart queue-processor`
2. If still stuck, check queue processor is querying SCHEDULED messages:
   ```python
   # In queue_processor_service.py line 94-98:
   # Should query: status='SCHEDULED' AND scheduled_for <= datetime.utcnow()
   ```
3. Reset adaptive backoff counter manually (unlikely but possible):
   ```bash
   # This requires code restart, no direct DB command
   systemctl restart queue-processor
   ```

---

## 📊 MONITORING & ALERTING

### Health Check Endpoint

```bash
# Verify queue processor is healthy
curl http://localhost:8000/health/queue-processor
# Expected: { "status": "healthy", "processed_this_minute": 15, "pending_messages": 23 }
# Bad: timeout (process hung), 500 (crash), or "pending" spike

# Check all system health
curl http://localhost:8000/health
```

### Metrics to Watch

**Every 5 minutes:**
- Pending messages count: Should decrease (< 100)
- Processed rate: Should be > 1 msg/sec during load
- Error rate: Should be < 5% of total

**Every hour:**
- Dead letter messages: Should be < 5
- Slow handlers (> 10s): Should be 0-2 per hour
- Circuit breaker status: Should be "OFF" (not triggered)

**Every day:**
- Jobs with active recruitment: Count should match deployed jobs
- Recruitment outcomes: Candidates matched per job (SLM metrics)

### Alert Thresholds

| Metric | Yellow (Warn) | Red (Page) |
|--------|--------------|-----------|
| Pending msgs > | 100 | 500 |
| Error rate > | 5% | 15% |
| Dead letters > | 10 | 50 |
| Slow handlers > | 3/hr | 10/hr |
| Processor silent > | 5m | 10m |
| Circuit breaker | N/A | TRIGGERED |

---

## 🔧 COMMON SCENARIOS & FIXES

### Scenario 1: Job Created But Recruitment Never Starts

**Expected Flow:**
1. POST /jobs/create → job_id queued to FLASH
2. job_created_flash handler → Job persisted to DB
3. Handler queues flash_recruiter message
4. flash_recruiter handler → Candidates matched, Thunder queued

**Debugging:**

```sql
-- Step 1: Check if job exists
SELECT jobID, jobTitle, jobStatus FROM jobs WHERE jobID='JOB-123';
-- Expected: 1 row with status='active'

-- Step 2: Check if job_created_flash completed
SELECT id, type, status, created_at, result 
FROM channel_queue_item 
WHERE type='job_created_flash' AND message_id LIKE '%JOB-123%';
-- Expected: status='COMPLETED', result contains job_id

-- Step 3: Check if flash_recruiter was queued
SELECT id, type, status, created_at, scheduled_for 
FROM channel_queue_item 
WHERE type='flash_recruiter' AND payload::text LIKE '%JOB-123%'
ORDER BY created_at ASC;
-- Expected: status='COMPLETED' or 'SCHEDULED'

-- Step 4: Check if Thunder messages were queued
SELECT id, type, status, created_at 
FROM channel_queue_item 
WHERE type LIKE '%thunder%' OR type LIKE '%candidate%'
  AND payload::text LIKE '%JOB-123%'
ORDER BY created_at DESC;
-- Expected: Multiple rows with status='PENDING' or 'COMPLETED'
```

**Common Causes & Fixes:**

| Issue | Sign | Fix |
|-------|------|-----|
| Handler missing | FAILED status, "No handler registered" | Check MessageHandlerRegistry has all 3 handlers registered |
| Job not in DB | flash_recruiter returns RuntimeError | Verify job_created_flash handler completed successfully |
| Recruitment run but no candidates | flash_recruiter COMPLETED, candidates_matched=0 | Check candidate eligibility filters (skill match, location, notice period) |
| Job status not active | flash_recruiter SKIPPED | Job approval workflow: check job needs approval first |

---

### Scenario 2: Thunder Candidate Outreach Failing

**Expected Flow:**
1. Thunder queue has engage_candidate_with_thunder messages
2. Thunder handler sends SMS/Email/WhatsApp
3. Candidate receives message + link to apply

**Debugging:**

```sql
-- Count Thunder messages by status
SELECT status, COUNT(*) 
FROM channel_queue_item 
WHERE type='engage_candidate_with_thunder' 
GROUP BY status;
-- Expected: Mostly COMPLETED, few PENDING/RETRY

-- Show failed Thunder messages
SELECT id, type, status, created_at, result 
FROM channel_queue_item 
WHERE type='engage_candidate_with_thunder' AND status IN ('FAILED','DEAD_LETTER')
ORDER BY created_at DESC 
LIMIT 5;

-- Check if SMS gateway is working
curl -X GET http://sms-gateway:5000/health
-- Expected: { "status": "online", "credits": 1234 }
```

**Common Causes & Fixes:**

| Issue | Sign | Fix |
|-------|------|-----|
| SMS gateway down | 502/503 errors in result | Check SMS provider status, restart gateway service |
| Candidate no phone | "Phone not found" error | Check candidate profile has valid phone number |
| Message too long | "Message exceeds 160 chars" | Truncate candidate name or greeting in message |
| Rate limit hit | "Rate limit exceeded" error | Wait 5m or contact SMS provider to increase limit |

---

## 🛠️ MANUAL OPERATIONS

### Force Reprocess Message (Emergency Only)

```sql
-- Reset a stuck PENDING message
UPDATE channel_queue_item 
SET status='PENDING', retry_count=0, last_attempted_at=NULL
WHERE id=12345;

-- Restart processor after change
systemctl restart queue-processor
```

### Archive Old Completed Messages

```sql
-- Keep only last 30 days of completed messages (free up space)
INSERT INTO channel_queue_archive 
SELECT * FROM channel_queue_item 
WHERE status='COMPLETED' AND created_at < NOW() - INTERVAL '30 days';

DELETE FROM channel_queue_item 
WHERE status='COMPLETED' AND created_at < NOW() - INTERVAL '30 days';
```

### Reset Circuit Breaker (Only If Confirmed Safe)

```bash
# Check what triggered it
tail -n 50 /var/log/wros/queue_processor.log | grep -i "circuit\|failure"

# Once root cause fixed and verified:
systemctl restart queue-processor

# Verify it comes back up (should process messages within 30s)
sleep 5
psql -U app_user -d wros_prod -c "SELECT COUNT(*) FROM channel_queue_item WHERE status='PENDING';" 
# Count should decrease
```

---

## 📋 DEPLOYMENT CHECKLIST

Before deploying CYCLE 19 changes:

- [ ] Database migration applied: `migrate_add_queue_columns.sql`
- [ ] All 3 handlers registered in MessageHandlerRegistry
- [ ] Queue processor configured: HANDLER_TIMEOUT_SECONDS=30
- [ ] SLM training error handling in place (non-blocking)
- [ ] Delayed message support enabled (scheduled_for column exists)
- [ ] Adaptive backoff configured (2-16s range)
- [ ] Circuit breaker set to 5 consecutive failures
- [ ] Dead letter escalation endpoint exists
- [ ] Monitoring dashboards updated with queue depth metric
- [ ] On-call alerts configured for thresholds above
- [ ] Team trained on this runbook

---

## 🆘 ESCALATION

**Critical Issues (Page On-Call):**
- Queue processor crashed (no messages processing 10+ minutes)
- Dead letter queue overflowing (> 50 messages)
- Database connection pool exhausted (backend API hanging)
- Circuit breaker triggered (5+ consecutive failures)

**Non-Critical Issues (Slack alert):**
- Slow handlers detected (> 10s)
- Error rate elevated (> 5%)
- Adaptive backoff active (queue empty)

**Escalation Path:**
1. Run diagnosis steps above (5 minutes)
2. Attempt fix from "Quick Fixes" section (5-10 minutes)
3. If unresolved, page on-call engineer
4. Provide diagnosis output and steps attempted
5. Escalate to architect if cause unclear

---

## 📞 CONTACTS

- **Queue Processor Owner:** Platform Team
- **On-Call:** See PagerDuty schedule
- **Architect (Architecture Decisions):** Ruthless Architect Agent
- **Database Admin:** See Wiki for credentials

---

## Appendix: Full Command Reference

```bash
# Start/Stop/Restart
systemctl start queue-processor
systemctl stop queue-processor
systemctl restart queue-processor
systemctl status queue-processor

# View Logs
tail -f /var/log/wros/queue_processor.log         # Live
tail -n 200 /var/log/wros/queue_processor.log    # Last 200 lines
grep "ERROR\|CRITICAL" /var/log/wros/queue_processor.log  # Error only

# Database Queries (Common)
psql -U app_user -d wros_prod -c "SELECT COUNT(*) FROM channel_queue_item WHERE status='PENDING';"
psql -U app_user -d wros_prod -c "SELECT type, status, COUNT(*) FROM channel_queue_item GROUP BY type, status ORDER BY type, status;"
psql -U app_user -d wros_prod -c "SELECT * FROM channel_queue_item WHERE status='DEAD_LETTER' ORDER BY created_at DESC LIMIT 10;"

# Health Check
curl http://localhost:8000/health/queue-processor
curl http://localhost:8000/health

# Emergency Restart (if systemctl fails)
kill $(pgrep -f "python.*queue_processor") || true
sleep 2
python -m app.services.queue_processor_service  # Runs in foreground for debugging
```

---

**Last Reviewed:** 2026-09-10  
**Next Review:** 2026-09-24 (or after any major changes)

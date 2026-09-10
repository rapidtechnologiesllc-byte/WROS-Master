# Queue Processor Monitoring & Alerts - CYCLE 19

**Purpose:** Real-time visibility into queue health, handler performance, and system bottlenecks

---

## 🎯 Dashboard Metrics (5-Minute Refresh)

### Queue Health Indicators

**1. Message Pipeline Status**

```sql
-- Total messages in each state
SELECT 
  status,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM channel_queue_item
GROUP BY status
ORDER BY 
  CASE status
    WHEN 'PENDING' THEN 1
    WHEN 'PROCESSING' THEN 2
    WHEN 'COMPLETED' THEN 3
    WHEN 'FAILED' THEN 4
    WHEN 'RETRY' THEN 5
    WHEN 'SCHEDULED' THEN 6
    WHEN 'DEAD_LETTER' THEN 7
  END;
```

**Expected (Healthy System):**
- PENDING: 0-50 messages (< 100 is warning)
- PROCESSING: 0-10 messages (should process within 30s)
- COMPLETED: Majority (should grow continuously)
- FAILED: 0-2 messages (retried to RETRY status)
- RETRY: 0-10 messages (being retried with backoff)
- SCHEDULED: 0-100 messages (waiting for time window)
- DEAD_LETTER: 0-5 messages (max retries exceeded)

---

**2. Processing Throughput (Per Minute)**

```sql
-- Messages completed in last minute
SELECT 
  COUNT(*) as messages_completed_1m,
  COUNT(*) / 60.0 as messages_per_second,
  AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time_sec
FROM channel_queue_item
WHERE status='COMPLETED' AND updated_at > NOW() - INTERVAL '1 minute';

-- Historical throughput (last hour)
SELECT 
  DATE_TRUNC('minute', updated_at) as minute,
  COUNT(*) as completed_messages,
  COUNT(*) / 60.0 as msgs_per_sec
FROM channel_queue_item
WHERE status='COMPLETED' AND updated_at > NOW() - INTERVAL '60 minutes'
GROUP BY DATE_TRUNC('minute', updated_at)
ORDER BY minute DESC;
```

**Alert Thresholds:**
- Throughput < 0.5 msgs/sec for 5+ minutes: 🟡 WARNING
- Throughput < 0.1 msgs/sec for 5+ minutes: 🔴 ALERT (page on-call)

---

**3. Handler Performance**

```sql
-- Slow handlers (> 10 seconds)
SELECT 
  type,
  COUNT(*) as slow_count,
  ROUND(AVG(handler_duration_ms) / 1000.0, 2) as avg_sec,
  ROUND(MAX(handler_duration_ms) / 1000.0, 2) as max_sec
FROM channel_queue_item
WHERE status='COMPLETED' 
  AND handler_duration_ms > 10000
  AND updated_at > NOW() - INTERVAL '1 hour'
GROUP BY type
ORDER BY slow_count DESC;

-- Timeout handlers (reached 30s limit)
SELECT 
  type,
  COUNT(*) as timeout_count,
  ROUND(AVG(handler_duration_ms) / 1000.0, 2) as avg_sec
FROM channel_queue_item
WHERE handler_duration_ms >= 30000
  AND updated_at > NOW() - INTERVAL '1 hour'
GROUP BY type
ORDER BY timeout_count DESC;
```

**Alert Thresholds:**
- Any handler > 20s: 🟡 WARNING (slow)
- Any handler = 30s consistently: 🔴 ALERT (may be timing out)

---

**4. Error Rate & Dead Letters**

```sql
-- Current error rate (last hour)
SELECT 
  COUNT(CASE WHEN status IN ('FAILED','DEAD_LETTER') THEN 1 END)::FLOAT 
  / COUNT(*)::FLOAT * 100 as error_rate_pct,
  COUNT(CASE WHEN status IN ('FAILED','DEAD_LETTER') THEN 1 END) as error_count,
  COUNT(*) as total_processed
FROM channel_queue_item
WHERE updated_at > NOW() - INTERVAL '1 hour'
  AND status != 'PENDING';  -- Exclude still-processing

-- Dead letter backlog (by type)
SELECT 
  type,
  COUNT(*) as dead_letter_count,
  MIN(created_at) as oldest,
  MAX(created_at) as newest
FROM channel_queue_item
WHERE status='DEAD_LETTER'
GROUP BY type
ORDER BY dead_letter_count DESC;
```

**Alert Thresholds:**
- Error rate > 5%: 🟡 WARNING
- Error rate > 15%: 🔴 ALERT (page on-call)
- Dead letters > 10: 🟡 WARNING
- Dead letters > 50: 🔴 ALERT

---

**5. Retry Activity (Backoff Working?)**

```sql
-- Messages in retry queue
SELECT 
  type,
  COUNT(*) as retry_count,
  ROUND(AVG(retry_count)::NUMERIC, 2) as avg_retry_num,
  MAX(retry_count) as max_retries
FROM channel_queue_item
WHERE status='RETRY'
GROUP BY type
ORDER BY retry_count DESC;

-- Next retry timing
SELECT 
  type,
  COUNT(*) as count,
  ROUND(EXTRACT(EPOCH FROM (MIN(next_retry_at) - NOW())) / 60.0, 1) as min_wait_min,
  ROUND(EXTRACT(EPOCH FROM (MAX(next_retry_at) - NOW())) / 60.0, 1) as max_wait_min
FROM channel_queue_item
WHERE status='RETRY'
GROUP BY type
ORDER BY type;
```

**Expected (Healthy):**
- RETRY queue < 20 messages (being worked down)
- Retry backoff increasing: 10s, 20s, 40s

---

**6. Scheduled Messages (Delayed Queue)**

```sql
-- Messages waiting to be scheduled
SELECT 
  COUNT(*) as scheduled_count,
  COUNT(CASE WHEN scheduled_for <= NOW() THEN 1 END) as ready_to_process,
  COUNT(CASE WHEN scheduled_for > NOW() THEN 1 END) as waiting,
  ROUND(EXTRACT(EPOCH FROM (AVG(scheduled_for) - NOW())) / 3600.0, 1) as avg_wait_hours
FROM channel_queue_item
WHERE status='SCHEDULED';

-- Flash recruiter self-scheduling (4-hour loop)
SELECT 
  DATE_TRUNC('hour', scheduled_for) as scheduled_hour,
  COUNT(*) as count
FROM channel_queue_item
WHERE type='flash_recruiter' AND status='SCHEDULED'
GROUP BY DATE_TRUNC('hour', scheduled_for)
ORDER BY scheduled_hour ASC;
```

**Expected (Healthy):**
- SCHEDULED count < 100 (not piling up)
- All SCHEDULED with scheduled_for <= NOW() should process within 5m

---

## 🔔 Alert Configuration

### For Grafana/Datadog/CloudWatch

**Alert 1: Queue Processor Down**
```
Condition: No COMPLETED messages in last 10 minutes
Severity: CRITICAL
Action: Page on-call immediately
Runbook: Queue_Processor_Runbook.md → Issue 1
```

**Alert 2: Dead Letter Overflow**
```
Condition: Dead letters > 50
Severity: HIGH
Action: Page on-call
Runbook: Queue_Processor_Runbook.md → Issue 2
```

**Alert 3: Pending Messages Backing Up**
```
Condition: PENDING > 100 for 5+ minutes
Severity: HIGH
Action: Alert in Slack #ops, no page
Runbook: Queue_Processor_Runbook.md → Scenario 1
```

**Alert 4: Error Rate High**
```
Condition: Error rate > 15% in last hour
Severity: MEDIUM
Action: Alert in Slack #ops
Runbook: Queue_Processor_Runbook.md → Issue 2
```

**Alert 5: Scheduled Messages Overdue**
```
Condition: Messages in SCHEDULED with scheduled_for < NOW() - 5 minutes
Severity: HIGH
Action: Alert in Slack #ops
Runbook: Queue_Processor_Runbook.md → Issue 3
```

---

## 📈 SLA Metrics

### Recruitment Velocity (CYCLE 19 KPI)

```sql
-- Jobs with active recruitment
SELECT 
  COUNT(DISTINCT payload::jsonb->>'job_id') as active_jobs,
  COUNT(CASE WHEN type='flash_recruiter' AND status='COMPLETED' THEN 1 END) as recruitment_runs_completed,
  COUNT(CASE WHEN type LIKE '%thunder%' AND status='COMPLETED' THEN 1 END) as candidate_outreach_sent
FROM channel_queue_item
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Job-to-First-Candidate Time (SLA: < 4 hours)
SELECT 
  job_id,
  job_title,
  created_at as job_created,
  first_candidate_queued,
  EXTRACT(EPOCH FROM (first_candidate_queued - created_at)) / 3600 as hours_to_first_candidate
FROM (
  SELECT 
    payload::jsonb->>'job_id' as job_id,
    payload::jsonb->>'job_title' as job_title,
    (SELECT created_at FROM channel_queue_item WHERE type='job_created_flash' LIMIT 1) as created_at,
    (SELECT MIN(created_at) FROM channel_queue_item 
     WHERE type LIKE '%thunder%' 
       AND payload::jsonb->>'job_id' = job_id) as first_candidate_queued
  FROM channel_queue_item
  WHERE type='flash_recruiter'
    AND created_at > NOW() - INTERVAL '7 days'
) metrics
WHERE first_candidate_queued IS NOT NULL
ORDER BY hours_to_first_candidate DESC;
```

**SLA Targets (CYCLE 19):**
- Job to first candidate outreach: < 4 hours
- Recruitment velocity: ≥ 5 candidates/job/week
- First-pass conversion: ≥ 2% (5 interviews per 250 contacted)

---

## 🏥 Health Check Endpoint

**Implement at: `GET /health/queue-processor`**

```json
{
  "status": "healthy",
  "timestamp": "2026-09-10T12:34:56Z",
  "processor": {
    "running": true,
    "uptime_seconds": 86400,
    "last_batch_processed": "2026-09-10T12:34:55Z",
    "batches_per_minute": 6.2
  },
  "queue": {
    "pending": 12,
    "processing": 0,
    "completed_1h": 1250,
    "retry": 3,
    "dead_letter": 2,
    "scheduled": 45
  },
  "performance": {
    "avg_processing_ms": 450,
    "max_processing_ms": 28000,
    "slow_handlers_1h": 2,
    "error_rate_pct": 2.1
  },
  "sla": {
    "job_to_first_candidate_avg_hours": 1.2,
    "first_pass_conversion_pct": 2.5,
    "recruitment_velocity": 6
  },
  "alerts": []  // Empty if healthy, contains warnings/critical issues
}
```

---

## 📊 Dashboard Panels (Recommended)

1. **Queue Status (Stacked Area)** - Messages by status over time
2. **Processing Throughput (Line)** - Messages/sec with SLA threshold
3. **Handler Duration (Heatmap)** - Type vs time distribution
4. **Error Rate (Line with threshold)** - % failed messages over time
5. **Retry Activity (Stacked Bar)** - Retries by type, depth
6. **Job-to-Candidate (Line)** - Hours from job creation to first outreach SLA
7. **Recruitment Velocity (Bar)** - Candidates matched per job
8. **Dead Letter Trend (Line)** - Accumulation rate

---

## 🧪 Testing Monitors

### Load Test Scenario

```bash
# Simulate 100 job creations (100 flash_recruiter runs)
for i in {1..100}; do
  curl -X POST http://localhost:8000/jobs/create \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"job_title\": \"Load Test Job $i\",
      \"job_description\": \"Test\",
      \"job_skills\": \"Python, Node.js\",
      \"job_location\": \"San Francisco\",
      \"no_of_positions\": 3,
      \"job_experience\": \"Senior\"
    }" &
done
wait

# Monitor queue during load
watch -n 1 'psql -U app_user -d wros_dev -c "SELECT status, COUNT(*) FROM channel_queue_item GROUP BY status;"'

# Expected progression:
# 1. PENDING jumps to 100+ (job_created_flash)
# 2. COMPLETED increases (handlers finish)
# 3. flash_recruiter messages queued (PENDING THUNDER)
# 4. THUNDER COMPLETED messages increase
# 5. Final: All COMPLETED, queue back to normal
```

**Success Criteria:**
- ✅ 100% of jobs reach database
- ✅ 100% of flash_recruiter runs complete
- ✅ ≥ 50% of jobs get candidates matched
- ✅ All candidates get Thunder outreach queued
- ✅ No dead letters created
- ✅ Processing time < 2 minutes for 100 jobs

---

**Last Updated:** 2026-09-10  
**Next Review:** 2026-09-24

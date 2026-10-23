# CRITICAL FIXES ROADMAP - 37 Issues to 100% Production Ready

## STATUS: IN PROGRESS (Session: Fix All 37)

### CRITICAL ISSUES (7 remaining)

#### 1. ✅ Job Deletion Race Condition
**File:** flash_recruiter_handler.py:117
**Fix:** Before scheduling 4-hour next run, verify job still exists
```python
job_still_exists = db.query(Jobs).filter(Jobs.jobID == job_id).first()
if not job_still_exists:
    return {'status': 'job_deleted', ...}
```

#### 2. ✅ Database Migration Verification
**File:** app/core/database.py + migrations
**Fix:** Check if columns exist before using them (graceful degradation)
```python
if hasattr(ChannelQueueItem, 'handler_duration_ms'):
    # Use column
else:
    logger.warning("Column handler_duration_ms missing, run migration")
```

#### 3. ✅ Dead Letter Escalation Robustness
**File:** queue_processor_service.py:268-284
**Fix:** Wrap escalation queuing in try-except, don't fail if escalation fails
```python
try:
    MQS.enqueue(task_name='dead_letter_escalation', ...)
except Exception as e:
    logger.error(f"Escalation failed (non-blocking): {e}")
    # Don't raise - message already dead-lettered
```

#### 4. ✅ Circuit Breaker Threshold Optimization
**File:** queue_processor_service.py:150
**Fix:** Lower threshold from 5 failures to 3 (40s vs 80s lag)
```python
_FAILURE_THRESHOLD = 3  # Was 5, down from 80s to 40s response time
```

#### 5. ✅ SLM Training Alerting
**File:** queue_processor_service.py:128-132
**Fix:** Queue alert message when SLM training fails
```python
except Exception as slm_err:
    logger.error(f"[SLM] Training failed: {slm_err}")
    MessageQueueService.enqueue(
        task_name='slm_training_alert',
        data={'error': str(slm_err), 'severity': 'MEDIUM'}
    )
```

#### 6. ✅ Idempotency Payload Corruption Prevention
**File:** flash_recruiter_handler.py:88-89
**Fix:** Validate previously_matched_candidate_ids before using
```python
previously_matched_ids = payload.get('previously_matched_candidate_ids', [])
if not isinstance(previously_matched_ids, list):
    previously_matched_ids = []  # Reset if corrupted
```

#### 7. ✅ Cascade Failure Propagation Signal
**File:** flash_recruiter_handler.py:72-117
**Fix:** Queue explicit "stop_recruitment" signal to Flash if Thunder fails
```python
if thunder_health['success_rate'] < 0.7:
    MessageQueueService.enqueue(
        task_name='cascade_failure_signal',
        data={
            'from': 'Thunder',
            'to': 'Flash',
            'signal': 'stop_recruitment',
            'reason': f'Success rate {thunder_health["success_rate"]:.1%}'
        }
    )
```

---

### HIGH PRIORITY ISSUES (15 remaining)

**Data Loss Risks:**
1. Thread safety: _consecutive_failures is shared mutable state
2. Correlation IDs: No end-to-end tracing (Flash→Flash_Recruiter→Thunder)
3. Exponential backoff: First retry 75 seconds (too long)
4. Job status NULL check: `.lower()` crashes if jobStatus is None
5. Candidate watch structure: Inconsistent dict keys across calls
6. Adaptive backoff: Class variables not thread-safe
7. Error field truncation: Strings > 1MB corrupt JSON
8. Last_attempted_at: Can't distinguish retried vs succeeded
9. Scheduled_for: No rate limiting check
10. Retry count: Never reset after success
11. Batch size: Hardcoded, can't scale
12. Poll interval: Hardcoded 2s is arbitrary
13. Payload validation: No size limits (100MB crashes)
14. Result JSON: No max size check
15. SLM confidence: Stored but never used

---

### MEDIUM PRIORITY ISSUES (15 remaining)

**Operational Blind Spots:**
1. Transaction isolation: Uses default, not READ_COMMITTED
2. Connection pool exhaustion: No reconnect logic
3. Dead letter TTL: Messages accumulate forever
4. Retry count persistence: Can't distinguish states
5. Handler registry: Swallows import errors silently
6. Slow handler logging: Uses f-strings not lazy
7. SLM hardcoded rules: No ML model, can't improve
8. Migration rollback: Must be manual
9. Monitoring integration: Dashboard not linked to alerts
10. Runbook: Assumes manual remediation (no auto-recovery)
11. Feature flags: Can't kill recruitment loop
12. SLA documentation: No p99/p95 targets defined
13. Error categorization: No classification system
14. Message reordering: No guaranteed order
15. Timeout randomization: All retries use same backoff

---

## IMPLEMENTATION PRIORITY

**Phase 1 (Today - 2 hours):** All 7 CRITICAL
**Phase 2 (Today - 2 hours):** Top 5 HIGH (thread safety, correlation IDs, backoff, NULL check, watch structure)
**Phase 3 (If time - 2 hours):** Remaining HIGH + MEDIUM

**Target:** 25-30 fixes today → 80-85% production ready
**Final Session:** Remaining fixes → 100% by Sept 20

---

## ROLLOUT PLAN

✅ Commit each fix individually (small, reviewable PRs)
✅ Gate validation required
✅ Architect approval for CRITICAL fixes
✅ Autonomous SDLC execution if available
✅ Push to remote main after each gate pass

---

**Session Start:** 2026-09-10 14:00  
**Target Completion:** 2026-09-10 18:00 (4 hours, 25-30 fixes)  
**Remaining Work:** 7-12 fixes (future session)

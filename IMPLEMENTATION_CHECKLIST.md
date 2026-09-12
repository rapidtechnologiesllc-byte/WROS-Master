# Queue Handler Validation + Timeout Implementation Checklist

**Status:** 🚨 CRITICAL - Ready for implementation  
**Date:** 2026-09-12  
**Requirement:** Validation patterns + time-bound execution  
**Target Completion:** 2026-09-18 (Priority 1)

---

## PHASE 1: Priority 1 Handlers (This Week - 4 Handlers)

### Handler 1: CREATE_CANDIDATE (30-second timeout)

**File:** `backend/app/services/message_handlers/candidate_creation_handler.py`

**Changes Required:**

- [ ] **Add timeout config:**
  ```python
  TIMEOUT_SECONDS = 30
  WARN_AT_SECONDS = 25
  ```

- [ ] **Add timeout check in process():**
  - Start timeout clock at beginning
  - Check `time.time() > timeout_at` before each major operation
  - Raise `TimeoutError` if timeout exceeded

- [ ] **Update on_success() with 4-step validation:**
  1. Check result structure (required fields exist)
  2. Query database (verify candidate record exists)
  3. Check related records (status, tenant, etc.)
  4. Verify data integrity (email matches, no corruption)
  - Raise `ValueError` if non-retryable (handler code bug)
  - Raise `RuntimeError` if retryable (temporary DB issue)
  - Mark COMPLETED only if ALL checks pass

- [ ] **Test cases:**
  - Happy path: Work + validation under 30s, COMPLETED
  - Validation fails: Record not found, raises RuntimeError
  - Timeout: Handler exceeds 30s, marked FAILED

**Reference:** `handler_validation_template.py` (copy pattern, adapt fields)

---

### Handler 2: ENGAGE_CANDIDATE_WITH_THUNDER (60-second timeout)

**File:** `backend/app/services/message_handlers/candidate_creation_handler.py:on_success()`

**Changes Required:**

- [ ] **Add timeout config:**
  ```python
  TIMEOUT_SECONDS = 60
  WARN_AT_SECONDS = 50
  ```

- [ ] **Add timeout checks in process():**
  - Timeout for Thunder API call (inner timeout 30s)
  - Timeout for delivery log creation

- [ ] **Update on_success() with validation:**
  1. Check result structure (delivery_id exists)
  2. Query MessageDeliveryLog (verify entry exists)
  3. Check delivery status ('sent', 'delivered', 'queued')
  4. Verify conversation record (if created)
  5. Verify candidate still exists (no race condition)

- [ ] **Test cases:**
  - Happy path: Message delivered + verified in 60s
  - Delivery failed: Log status='failed', validation fails
  - Timeout: API call > 30s, marked FAILED

---

### Handler 3: JOB_CREATED_FLASH (45-second timeout)

**File:** `backend/app/services/flash_service.py` (or relevant job handler)

**Changes Required:**

- [ ] **Add timeout config:**
  ```python
  TIMEOUT_SECONDS = 45
  WARN_AT_SECONDS = 40
  ```

- [ ] **Add timeout checks in process():**
  - Timeout for job INSERT
  - Timeout for FK checks (hiring manager exists)

- [ ] **Update on_success() with validation:**
  1. Check result structure (job_id exists)
  2. Query Jobs table (verify job record exists)
  3. Check FK integrity (hiring manager exists)
  4. Verify business unit assignment
  5. Check job data matches payload (no corruption)

- [ ] **Test cases:**
  - Happy path: Job created + verified in 45s
  - FK broken: Hiring manager doesn't exist, validation fails
  - Timeout: INSERT takes > 45s, marked FAILED

---

### Handler 4: CANDIDATE_CONVERSION_HANDLER (40-second timeout)

**File:** `backend/app/services/message_handlers/candidate_conversion_handler.py`

**Changes Required:**

- [ ] **Add timeout config:**
  ```python
  TIMEOUT_SECONDS = 40
  WARN_AT_SECONDS = 35
  ```

- [ ] **Add timeout checks in process():**
  - Timeout for candidate lookup
  - Timeout for employee creation

- [ ] **Update on_success() at line 201 with validation:**
  1. Check result structure (candidate_id + employee_id)
  2. Query Candidate (status must be "EMPLOYEE")
  3. Query Employee (verify record exists)
  4. Verify email consistency (candidate.email == employee.email)
  5. Check no orphaned records

- [ ] **Test cases:**
  - Happy path: Employee created + verified in 40s, status updated
  - Email mismatch: Validation fails (data corruption)
  - Timeout: Conversion takes > 40s, marked FAILED

---

## PHASE 2: Configuration & Infrastructure

### Config File: handlers_timeout_config.yaml

**File:** `backend/handlers_timeout_config.yaml`

- [ ] Create file with timeout values for ALL handlers
- [ ] Include Priority 1 handlers (30-60s)
- [ ] Include Priority 2 handlers (20-45s)
- [ ] Document external dependencies (API timeouts, etc.)
- [ ] Set `warn_at_seconds` to 80% of timeout

### Handler Registry: Load Timeout Config

**File:** `backend/app/services/message_handler_registry.py`

- [ ] **Add method to load timeout config at startup:**
  ```python
  @staticmethod
  def load_timeout_config(config_path: str):
      # Load YAML file
      # Apply timeouts to handler classes
      # Log loaded config
  ```

- [ ] **Call at app startup** in `app/main.py`:
  ```python
  @app.on_event("startup")
  async def startup():
      MessageHandlerRegistry.load_timeout_config()
  ```

### Queue Processor: Enforce Timeouts

**File:** `backend/app/services/queue_processor_service.py:_process_single_message()`

- [ ] **Implement outer timeout enforcement:**
  - Get handler timeout from config
  - Run handler in thread with `timeout` parameter
  - Kill handler if exceeds timeout
  - Mark message FAILED if handler timed out
  - Schedule retry with exponential backoff

- [ ] **Track handler duration:**
  - Measure time.time() before handler
  - Calculate duration after handler completes
  - Log if handler > 10s (warning level)

---

## PHASE 3: Code Review Gate Updates

### Gate: Enforce Validation Pattern

**File:** Code review gate configuration

- [ ] **Block commits** containing:
  - `on_success()` without `db.query()` (no verification!)
  - `message.status = "COMPLETED"` without validation
  - Marking COMPLETED without raising exceptions on failure
  - Missing `db.rollback()` on validation failure

- [ ] **Allow commits** containing:
  - `on_success()` with minimum 2 database queries
  - Explicit `ValueError`/`RuntimeError` raises
  - Timeout checks in `process()` method
  - Logging for each validation step

### Gate: Enforce Timeout Config

- [ ] **Block commits** containing:
  - Handler without `TIMEOUT_SECONDS` class variable
  - Handler without timeout checks in `process()`
  - Handler without timeout checks in `on_success()`
  - Timeout values not in `handlers_timeout_config.yaml`

- [ ] **Allow commits** containing:
  - All 4 required timeout checks per handler
  - Configuration file with ALL handlers listed

---

## PHASE 4: Testing & Verification

### Unit Tests: Validation Pattern

**File:** `backend/tests/test_handler_validation.py` (new file)

- [ ] **Test 1: Happy path**
  - Handler completes work
  - on_success() validates all checks
  - Message marked COMPLETED
  - Verify record exists in database

- [ ] **Test 2: Validation fails - record missing**
  - Handler returns wrong ID
  - on_success() queries database
  - Record not found → RuntimeError
  - Message NOT marked COMPLETED

- [ ] **Test 3: Validation fails - data mismatch**
  - Handler creates record with wrong data
  - on_success() compares fields
  - Email mismatch detected → RuntimeError
  - Message NOT marked COMPLETED

- [ ] **Test 4: Validation fails - related record missing**
  - Handler creates candidate but not status
  - on_success() queries CandidateStatus
  - Record not found → RuntimeError
  - Message NOT marked COMPLETED

### Unit Tests: Timeout Behavior

**File:** `backend/tests/test_handler_timeouts.py` (new file)

- [ ] **Test 1: Work completes before timeout**
  - Handler executes in 500ms
  - Timeout is 30s
  - Message COMPLETED successfully
  - Duration under timeout

- [ ] **Test 2: Work exceeds timeout**
  - Mock slow database (sleep 35s)
  - Timeout is 30s
  - Handler raises TimeoutError
  - Message marked FAILED

- [ ] **Test 3: Validation exceeds timeout**
  - Handler completes (100ms)
  - Validation queries slow (sleep 6s)
  - 5-second validation window exceeded
  - Message marked FAILED

- [ ] **Test 4: Timeout triggers exponential backoff**
  - Handler times out on attempt 1
  - Retry scheduled for 30s
  - Attempt 2: times out
  - Retry scheduled for 60s
  - Verify exponential growth: 30s → 60s → 120s

### Integration Tests: End-to-End

**File:** `backend/tests/test_handler_integration.py`

- [ ] **Test 1: Candidate creation end-to-end**
  - POST /candidates
  - Queue processor processes message
  - Handler executes with timeout
  - Validation passes
  - Candidate verified in database

- [ ] **Test 2: Timeout recovery (retry succeeds)**
  - First attempt: DB locked (timeout)
  - Message marked FAILED
  - Wait 30s
  - Retry: DB unlocked (success)
  - Message COMPLETED

- [ ] **Test 3: Permanent failure (validation fails)**
  - Handler returns wrong ID
  - Validation fails (ValueError)
  - Message marked FAILED
  - NO RETRY (non-retryable)

---

## PHASE 5: Monitoring & Alerting Setup

### Metrics Collection

**File:** `backend/app/services/timeout_metrics.py` (new file)

- [ ] Create metrics collector class
- [ ] Track per handler:
  - `handler_timeouts_total` (Counter)
  - `handler_duration_seconds` (Histogram)
  - `validation_failures_total` (Counter)
  - `messages_completed_total` (Counter)

- [ ] Expose metrics at `/metrics/handlers/timeout`

### Alert Configuration

**File:** Alert rules (Prometheus or monitoring system)

- [ ] Create alert for high timeout rate (> 5%)
- [ ] Create alert for approaching timeout (> 10% near limit)
- [ ] Create alert for thread pool exhaustion (> 80% full)
- [ ] Create alert for permanent timeout failures (5+ repeated)

---

## Validation Checklist: Before Submitting Phase 1

### Code Changes

- [ ] All 4 Priority 1 handlers updated with validation
- [ ] All 4 handlers have TIMEOUT_SECONDS config
- [ ] All handlers have timeout checks in process() + on_success()
- [ ] handlers_timeout_config.yaml created with all values
- [ ] Queue processor loads timeout config at startup
- [ ] Queue processor enforces outer timeout

### Testing

- [ ] All 12 unit tests passing (4 handlers × 3 test cases)
- [ ] All 4 timeout tests passing
- [ ] All 3 integration tests passing
- [ ] Manual testing: timeout behavior works correctly
- [ ] Manual testing: validation catches errors

### Code Review

- [ ] Gate passes on all modified handlers
- [ ] Gate enforces validation pattern (blocks violations)
- [ ] Gate enforces timeout config (blocks missing values)
- [ ] Documentation updated (README, handler guide)
- [ ] Code review comments addressed

### Deployment Readiness

- [ ] handlers_timeout_config.yaml in production config
- [ ] Monitoring/metrics enabled and logging data
- [ ] Alert rules created and tested
- [ ] Runbook created for timeout escalation
- [ ] Team trained on new validation pattern

---

## Success Criteria for Phase 1

**Completion:** All 4 Priority 1 handlers fully implemented and tested

| Handler | Validation | Timeout | Config | Tests | Status |
|---------|-----------|---------|--------|-------|--------|
| create_candidate | 4 checks | 30s | YAML | 3 | ⏳ |
| engage_candidate | 5 checks | 60s | YAML | 3 | ⏳ |
| job_created_flash | 4 checks | 45s | YAML | 3 | ⏳ |
| candidate_conversion | 4 checks | 40s | YAML | 3 | ⏳ |

**Measurement:**
- 0% silent failures (all COMPLETED verified)
- 0% handler hangs (all respect timeout)
- 0% validation bypasses (gate enforces)
- 100% test coverage (validation + timeout paths)

---

## Timeline

```
2026-09-12 (Friday):
  ✅ Architecture + documentation created (THIS TASK)
  → Ready for implementation

2026-09-13 to 2026-09-14 (Sat-Sun):
  → Developer 1: create_candidate handler
  → Developer 2: engage_candidate handler (parallel)

2026-09-15 (Mon):
  → Developer 1: job_created_flash handler
  → Developer 2: candidate_conversion handler (parallel)
  → QA: Testing + verification

2026-09-16 (Tue):
  → Code review + gate updates
  → Manual testing
  → Documentation review

2026-09-17 (Wed):
  → Monitoring setup
  → Alert testing
  → Final verification

2026-09-18 (Thu):
  ✅ Phase 1 complete - MERGED TO MAIN
  → Begin Phase 2 (Priority 2 handlers)
```

---

## Reference Materials

### Documentation

1. **QUEUE_HANDLER_VALIDATION_PATTERN.md** (2,500 lines)
   - Complete validation pattern guide
   - Validation checklist by handler type
   - Error handling strategy
   - Testing strategy

2. **QUEUE_HANDLER_TIMEOUTS_CRITICAL.md** (2,000 lines)
   - Timeout architecture
   - Timeout config by handler
   - Queue processor integration
   - Monitoring + alerting

3. **QUEUE_HANDLER_COMPLETE_SOLUTION.md** (1,000 lines)
   - Integrated solution (validation + timeouts)
   - Handler implementation template
   - Scenario walkthroughs
   - Before/after comparison

4. **handler_validation_template.py** (400 lines)
   - Reference implementation
   - Copy this pattern to all handlers
   - All 4 methods with documentation

### Configuration Files

5. **handlers_timeout_config.yaml**
   - Timeout values per handler
   - External dependency timeouts
   - Alert thresholds

---

## Handoff to Development Team

### For Developer 1 (create_candidate + job_created_flash)

**Start with:**
1. Read `QUEUE_HANDLER_COMPLETE_SOLUTION.md` (15 min)
2. Review `handler_validation_template.py` (10 min)
3. Copy template pattern to create_candidate handler (30 min)
4. Add validation checks (45 min)
5. Add timeout enforcement (30 min)
6. Write tests (1 hour)
7. Code review + fixes (30 min)

**Total: ~4 hours per handler**

### For Developer 2 (engage_candidate + candidate_conversion)

**Start with:**
1. Read `QUEUE_HANDLER_COMPLETE_SOLUTION.md` (15 min)
2. Review `handler_validation_template.py` (10 min)
3. Copy template pattern to engage_candidate handler (30 min)
4. Add validation checks (45 min)
5. Add timeout enforcement (30 min)
6. Write tests (1 hour)
7. Code review + fixes (30 min)

**Total: ~4 hours per handler**

---

## Questions & Troubleshooting

### Q: What if handler legitimately takes > 30 seconds?
**A:** Increase timeout in handlers_timeout_config.yaml. But first investigate why handler is slow.

### Q: What if database is slow on Mondays?
**A:** Don't increase timeout. Fix database. Use different timeout per environment if needed.

### Q: What if external API is flaky?
**A:** Implement retry logic at API call level, not at timeout level.

### Q: How do I debug a timeout?
**A:** Check logs for "HANDLER TIMEOUT" message. Includes handler name, timeout value, actual duration.

---

## Sign-Off Checklist

- [ ] Architecture reviewed and approved by architect
- [ ] Implementation ready for development team
- [ ] All supporting documentation created
- [ ] Timeline agreed upon
- [ ] Resources allocated (2 developers)
- [ ] Testing strategy approved
- [ ] Monitoring + alerting plan approved

**Next Step:** Assign work to development team, begin Phase 1 implementation 2026-09-13


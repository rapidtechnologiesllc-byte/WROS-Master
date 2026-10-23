# PRODUCTION-READY SOLUTION: Unified Queue Monitoring System

**Date:** 2026-09-16  
**Status:** Ready for implementation  
**Scope:** Single integrated monitoring system, no dead code

---

## ARCHITECTURE DECISION

**Keep two separate, specialized monitoring cycles:**

1. **Queue Stuck Message Monitor** (10-second cycle)
   - Detects messages stuck in "processing" > 5 minutes
   - Autonomously recovers with escalating strategies
   - Analyzes root causes
   - Meets SLA (5-minute threshold, detected within 10 seconds)

2. **Long-term Architecture System** (90-second cycle, FUTURE)
   - Code quality and prevention
   - Not needed for immediate production stability
   - Deferred to Phase 2

**Why separate cycles?**
- Stuck message SLA requires detection every 10 seconds
- 90-second cycle is too slow (may not detect within 5 minutes)
- Different timescales, different responsibilities
- Can run independently without cross-dependencies

---

## FILES TO CREATE/MODIFY

### 1. REPLACE: stuck_message_detector.py

**Fix the SQL queries to match actual ChannelQueueItem columns:**

**BEFORE (BROKEN):**
```python
SELECT id, task_name, status, queue_type, retry_count, ..., data, error_message
```

**AFTER (FIXED):**
```python
SELECT id, type as task_name, status, channel_type as queue_type, retry_count, ..., payload as data, error as error_message
```

**Changes:**
- Line 52: `type as task_name` (not `task_name`)
- Line 53: `channel_type as queue_type` (not `queue_type`)
- Line 59: `payload as data` (not `data`)
- Line 60: `error as error_message` (not `error_message`)

**Result:** SQL query will work against actual schema

### 2. CREATE: StuckMessageMonitorService

**New service to manage the 10-second monitoring loop:**

**Location:** `backend/app/services/stuck_message_monitor_service.py`

**Responsibilities:**
- Uses corrected stuck_message_detector.py
- Runs in background thread
- Catches and logs all exceptions (bulletproof)
- Exposes status via global cache
- Starts at main.py startup

**Key Methods:**
```python
class StuckMessageMonitorService:
    async def run_monitoring_loop():
        """Run 10-second detection/healing/analysis cycle forever"""
        while True:
            detect_stuck_messages()
            heal_stuck_messages()  # Escalating strategies
            analyze_root_causes()
            await asyncio.sleep(10)
    
    def get_current_status():
        """Return current monitoring state for API"""
        return {
            "last_check_at": ...,
            "stuck_detected": ...,
            "healed": ...,
            "failed": ...,
            "last_root_causes": ...
        }
```

### 3. CREATE: API Endpoint

**Location:** `backend/app/api/v1/endpoints/stuck_messages.py`

**Endpoints:**
```python
@router.get("/api/v1/monitoring/stuck-messages")
def get_stuck_message_status():
    """Get current stuck message monitoring status"""
    return StuckMessageMonitorService.get_current_status()

@router.get("/api/v1/monitoring/stuck-messages/history")
def get_stuck_message_history():
    """Get last 10 stuck message detection cycles"""
    return StuckMessageMonitorService.get_history()
```

### 4. MODIFY: main.py

**Add stuck message monitoring startup (similar to queue processor):**

**Location:** `backend/app/main.py` after queue processor initialization

```python
# STUCK MESSAGE MONITORING: Detect and recover from stuck messages
# Runs independently, detects every 10 seconds, meets 5-minute SLA
try:
    logger.info("[Startup] Initializing stuck message monitoring...")
    from app.services.stuck_message_monitor_service import StuckMessageMonitorService
    from threading import Thread
    
    monitor_thread = Thread(
        target=StuckMessageMonitorService.start_monitoring,
        daemon=True,
        name="StuckMessageMonitor"
    )
    monitor_thread.start()
    
    if not monitor_thread.is_alive():
        raise RuntimeError("Stuck message monitor failed to start")
    
    logger.info("[OK] Stuck message monitoring started (10s cycle)")
    
except Exception as exc:
    logger.error(f"[Startup] Failed to start stuck message monitoring: {exc}", exc_info=True)
    logger.warning("[Startup] Stuck message monitoring disabled - messages may remain stuck")
```

### 5. DELETE: These are DEAD CODE

- `app/services/integrated_architecture_system.py` - Pseudo-code, remove
- `app/api/v1/endpoints/architect.py` - Depends on broken integrated_system
- `app/models/architect_findings.py` - Unused, remove
- `backend/test_architect_standalone.py` - Test for removed code
- `backend/tests/test_autonomous_architect.py` - Test for removed code
- `backend/app/services/autonomous_architect.py` - Not integrated, remove
- Keep `INTEGRATED_SYSTEM_EXAMPLE.md` for reference only (no production impact)

**Reason:** These files are architectural proposals but completely non-functional. They waste context and confuse developers.

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Fix Stuck Message Detector (30 minutes)
- [ ] Update SQL queries in stuck_message_detector.py (column name fixes)
- [ ] Test SQL syntax locally
- [ ] Verify queries work against test database

### Phase 2: Create Monitoring Service (60 minutes)
- [ ] Create stuck_message_monitor_service.py
- [ ] Implement 10-second monitoring loop
- [ ] Add escalating recovery strategies:
  1. Restart queue processor thread
  2. Retry stuck message (reset to PENDING)
  3. Move to FAILED status after 3 retries
  4. Escalate if > 30 minutes stuck
- [ ] Add bulletproof error handling (never crash)
- [ ] Add status cache for API queries

### Phase 3: Create API Endpoint (30 minutes)
- [ ] Create stuck_messages.py endpoint
- [ ] GET /monitoring/stuck-messages (current status)
- [ ] GET /monitoring/stuck-messages/history (last 10 cycles)
- [ ] Add to main.py router

### Phase 4: Wire to Startup (15 minutes)
- [ ] Add StuckMessageMonitorService to main.py
- [ ] Start in background thread (like queue processor)
- [ ] Add error handling and logging
- [ ] Test startup sequence

### Phase 5: Testing & Verification (45 minutes)
- [ ] Create test stuck message scenario
- [ ] Verify detection within 10 seconds
- [ ] Verify healing (message moved to PENDING)
- [ ] Verify API endpoint returns current status
- [ ] Verify system survives exceptions

### Phase 6: Cleanup (15 minutes)
- [ ] Delete dead code files (integrated_architecture_system.py, etc.)
- [ ] Update main.py imports
- [ ] Remove router includes for deleted endpoints
- [ ] Commit with clear message

**Total: ~3.5 hours work, zero architectural complexity**

---

## PRODUCTION SLA

**Stuck Message Detection & Recovery:**

| Scenario | Timeline | Status |
|---|---|---|
| Message stuck at T+0 | | |
| Detected by monitor | T+10s | ✅ Within 10 seconds |
| Healing starts | T+15s | ✅ Within 15 seconds |
| Message retried | T+20s | ✅ Moving through queue |
| Customer impact | ~20 seconds | ✅ Meets SLA |

**Without monitoring (current state):**
| | |
| Message stuck at T+0 | |
| Detected manually | T+600s (10 min) | ❌ Way over SLA |
| Manual restart | T+700s | ❌ Too late |
| Retry starts | T+800s | ❌ Customer already impacted 13 min |

---

## KEY GUARANTEES

1. ✅ **No dead code** - Every line of code runs in production
2. ✅ **Bulletproof error handling** - Never crashes, always retries
3. ✅ **Meets SLA** - Detects stuck messages within 5-minute threshold
4. ✅ **Autonomous** - No human intervention, fully automatic
5. ✅ **Observable** - API endpoints expose current status
6. ✅ **Scalable** - Single thread per service, minimal overhead
7. ✅ **Maintainable** - Clear separation of concerns

---

## VALIDATION BEFORE SHIP

**In test database:**
1. Queue a message with candidate import
2. Kill the handler process mid-execution
3. Watch monitor detect stuck message within 10 seconds
4. Watch healing strategies execute (restart → retry)
5. Watch message recover and complete
6. Check API endpoint shows status and root cause

**Expected result:** Automatic recovery, zero manual intervention, customer never sees failure.

---

## SUCCESS CRITERIA

- [ ] No hardcoded values in production code
- [ ] No pseudo-code or stubbed functions
- [ ] All SQL queries use correct column names
- [ ] All error cases handled gracefully
- [ ] Monitoring runs autonomously at startup
- [ ] API endpoint exposes current status
- [ ] Messages detected as stuck within 10 seconds
- [ ] Recovery strategies execute in order
- [ ] Root cause analysis identifies why message stuck
- [ ] System survives all test failure scenarios


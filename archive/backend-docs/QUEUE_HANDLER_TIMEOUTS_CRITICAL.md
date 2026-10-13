# Queue Handler Timeouts - CRITICAL REQUIREMENT

**STATUS:** 🚨 BLOCKING - All handlers must have time-bound execution  
**Requirement Source:** Coordinator (2026-09-12)  
**Impact:** Prevents infinite hangs, resource exhaustion, system deadlocks

---

## THE PROBLEM: Handlers Can Hang Indefinitely

### Current Issue

```
Handler starts work
    ↓
Database connection established
    ↓
INSERT statement issued
    ↓
🚨 DATABASE LOCKS UP (deadlock, replication lag, overload)
    ↓
Handler waits... and waits... and waits...
    ↓
5 minutes later: Still waiting (blocking queue processor thread)
    ↓
Queue processor thread pool exhausted (all threads hung)
    ↓
New messages can't be processed
    ↓
System cascade failure (cannot create candidates, send messages, etc.)
```

### Why This Happens

- Database locks on high-traffic tables
- Network timeouts to external services (Thunder, delivery APIs)
- Deadlock situations (rare but possible)
- Resource exhaustion on slow database servers
- No timeout enforcement

**Result:** Handlers hang indefinitely, blocking entire queue processor, cascading to system failure.

---

## THE SOLUTION: Time-Bound Execution with Timeouts

### Core Principle

**EVERY handler must complete within a configurable timeout or FAIL FAST.**

```
Handler starts work (T+0)
    ↓
[TIMEOUT CLOCK STARTS: 30-second window]
    ↓
Work completes OR timeout expires
    ↓
If work completes before timeout:
    → Validation runs (must complete before timeout)
    → Message marked COMPLETED
    → Done ✅

If timeout expires:
    → Work interrupted (thread killed if needed)
    → Message marked FAILED
    → Scheduled for retry (exponential backoff)
    → Prevent same handler from hanging again ⚠️
    → Done in < timeout ✅
```

---

## Timeout Configuration by Handler Type

### Priority 1 Handlers

#### 1. CREATE_CANDIDATE Handler

**Timeout:** 30 seconds (work + validation must complete)

**Why 30s:**
- Database INSERT typically 50-200ms
- Validation queries 100-300ms  
- Total expected: 500-1000ms
- **Buffer:** 30x safety margin for DB overload
- **Hard limit:** Prevent DB resource starvation

**Timeout Breakdown:**
```
0-5s:   Validate payload structure
5-15s:  INSERT candidate record (DB work)
15-20s: Flush to database
20-25s: Refresh candidate from DB (confirmation)
25-28s: Create status record
28-30s: Validation queries (4 checks)
30s:    TIMEOUT EXPIRES → FAIL if not completed
```

**Configuration:**
```python
class CreateCandidateHandler:
    TIMEOUT_SECONDS = 30  # Hard limit
    WARN_AT_SECONDS = 25  # Start warning at 25s
    
    @staticmethod
    def process(message, db):
        start_time = time.time()
        timeout_at = start_time + CreateCandidateHandler.TIMEOUT_SECONDS
        
        # All work must complete by timeout_at
        # If time.time() > timeout_at before returning → FAIL
```

**What Happens When Timeout Expires:**
```python
if time.time() > timeout_at:
    db.rollback()  # Abandon any partial work
    message.status = "FAILED"
    message.error = "Handler exceeded 30-second timeout"
    db.commit()
    return  # Message queued for retry
```

---

#### 2. ENGAGE_CANDIDATE_WITH_THUNDER Handler

**Timeout:** 60 seconds (external service dependency)

**Why 60s:**
- Thunder API call: 500-2000ms typical
- Message delivery service: 1000-5000ms typical
- Network latency: 100-500ms
- **Buffer:** 10x safety margin for service slowdown
- **Hard limit:** Prevent API call hangs blocking queue

**Timeout Breakdown:**
```
0-10s:  Validate candidate exists
10-40s: Call Thunder engagement API (with internal timeout)
40-50s: Log delivery attempt to MessageDeliveryLog
50-55s: Create or update conversation record
55-60s: Validation queries
60s:    TIMEOUT EXPIRES → FAIL if not completed
```

**Configuration:**
```python
class EngageCandidateWithThunderHandler:
    TIMEOUT_SECONDS = 60
    WARN_AT_SECONDS = 50
    API_CALL_TIMEOUT = 30  # Inner timeout for Thunder API call
    
    @staticmethod
    def process(message, db):
        start_time = time.time()
        timeout_at = start_time + EngageCandidateWithThunderHandler.TIMEOUT_SECONDS
        
        # Candidate must be contacted and delivery logged by timeout_at
        try:
            response = call_thunder_api(
                candidate_id=message.payload['candidate_id'],
                timeout=EngageCandidateWithThunderHandler.API_CALL_TIMEOUT
            )
        except TimeoutError:
            raise RuntimeError("Thunder API timeout - will retry")
        
        if time.time() > timeout_at:
            raise RuntimeError("Handler exceeded 60-second timeout")
```

**What Happens When Timeout Expires:**
```
Message marked FAILED (not COMPLETED)
Scheduled for retry with exponential backoff:
  Retry 1: Wait 30s
  Retry 2: Wait 60s
  Retry 3: Wait 120s
  Retry 4: Wait 240s
  Retry 5: Escalate to ops
```

---

#### 3. JOB_CREATED_FLASH Handler

**Timeout:** 45 seconds

**Why 45s:**
- Job INSERT: 100-500ms
- FK validation (hiring manager exists): 50-200ms
- Status/metadata creation: 100-300ms
- Related record creation: 500-1000ms
- **Buffer:** 10x safety margin

**Configuration:**
```python
class JobCreatedFlashHandler:
    TIMEOUT_SECONDS = 45
    WARN_AT_SECONDS = 40
```

---

#### 4. CANDIDATE_CONVERSION_HANDLER

**Timeout:** 40 seconds

**Why 40s:**
- Candidate lookup: 50-100ms
- Employee record creation: 100-500ms
- Status update: 100-200ms
- Validation queries: 200-500ms
- **Buffer:** 10x safety margin

**Configuration:**
```python
class CandidateConversionHandler:
    TIMEOUT_SECONDS = 40
    WARN_AT_SECONDS = 35
```

---

## Implementation Pattern: Time-Bound Execution

### Handler Structure with Timeout

```python
class ExampleHandler:
    # Configuration
    TIMEOUT_SECONDS = 30
    WARN_AT_SECONDS = 25
    
    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Execute handler work within timeout."""
        import time
        
        # Start timeout clock
        start_time = time.time()
        timeout_at = start_time + ExampleHandler.TIMEOUT_SECONDS
        
        try:
            # ========== PHASE 1: Do work ==========
            if time.time() > timeout_at:
                raise TimeoutError("Handler exceeded timeout before starting work")
            
            # Create record
            record = db.add(Record(...))
            db.flush()
            record_id = record.id
            
            # Check if we're approaching timeout
            elapsed = time.time() - start_time
            remaining = ExampleHandler.TIMEOUT_SECONDS - elapsed
            if remaining < 5:  # Less than 5 seconds remaining
                raise TimeoutError(f"Approaching timeout: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining")
            
            # ========== PHASE 2: Validation ==========
            result = {
                'status': 'success',
                'record_id': record_id,
                'email': message.payload.get('email')
            }
            
            return result
            
        except TimeoutError as e:
            db.rollback()
            logger.error(f"[Handler] Timeout: {e}")
            # Raise RuntimeError so queue processor retries
            raise RuntimeError(f"Handler timeout: {str(e)}") from e
        
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Work failed: {e}", exc_info=True)
            raise
    
    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Validate work before marking COMPLETED - with timeout."""
        import time
        
        # Start validation timeout (should complete quickly, < 5s)
        start_time = time.time()
        validation_timeout_at = start_time + 5  # 5-second validation window
        
        try:
            # Validation Step 1: Check result
            if time.time() > validation_timeout_at:
                raise TimeoutError("Validation timeout during step 1")
            
            record_id = result.get('record_id')
            if not record_id:
                raise ValueError("Missing record_id")
            
            # Validation Step 2: Database verification
            if time.time() > validation_timeout_at:
                raise TimeoutError("Validation timeout during step 2")
            
            record = db.query(Model).filter(Model.id == record_id).first()
            if not record:
                raise RuntimeError("Record not found in database")
            
            # Validation Step 3: Related records
            if time.time() > validation_timeout_at:
                raise TimeoutError("Validation timeout during step 3")
            
            status = db.query(Status).filter(...).first()
            if not status:
                raise RuntimeError("Status record missing")
            
            # Validation Step 4: Data integrity (quick checks only)
            if time.time() > validation_timeout_at:
                raise TimeoutError("Validation timeout during step 4")
            
            if record.email != result.get('email'):
                raise RuntimeError("Email mismatch")
            
            # Mark COMPLETED only after validation passes
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = json.dumps(result)
            db.commit()
            
            logger.info(f"✅ COMPLETED within timeout")
            
        except TimeoutError as e:
            db.rollback()
            logger.error(f"[Handler] Validation timeout: {e}")
            raise RuntimeError(f"Validation timeout: {str(e)}") from e
        except (ValueError, RuntimeError) as e:
            db.rollback()
            logger.error(f"[Handler] Validation failed: {e}")
            raise
```

---

## Queue Processor Integration

### Timeout Enforcement at Queue Processor Level

```python
class QueueProcessorService:
    @staticmethod
    def _process_single_message(db: Session, message: ChannelQueueItem) -> Dict[str, Any]:
        """Process message with outer timeout enforcement."""
        import time
        import threading
        
        # Get handler and its timeout config
        handler = MessageHandlerRegistry.get_handler(message.type)
        handler_timeout = getattr(handler, 'TIMEOUT_SECONDS', 30)  # Default 30s
        
        message.status = "PROCESSING"
        message.processing_started_at = datetime.utcnow()
        db.commit()
        
        # ========== OUTER TIMEOUT: Prevent handler from hanging ==========
        handler_result = None
        handler_exception = None
        handler_timed_out = False
        
        def _execute_handler_with_timeout():
            nonlocal handler_result, handler_exception
            try:
                handler_result = handler(message, db)
            except Exception as e:
                handler_exception = e
        
        # Run handler in thread with timeout
        handler_thread = threading.Thread(
            target=_execute_handler_with_timeout,
            daemon=True
        )
        handler_start_time = time.time()
        handler_thread.start()
        handler_thread.join(timeout=handler_timeout)
        handler_duration_ms = int((time.time() - handler_start_time) * 1000)
        
        # ========== TIMEOUT CHECK: Did handler complete before timeout? ==========
        if handler_thread.is_alive():
            handler_timed_out = True
            logger.critical(
                f"[QueueProcessor] ⚠️ HANDLER TIMEOUT: {message.type} "
                f"exceeded {handler_timeout}s limit (took {handler_duration_ms}ms)"
            )
            
            # Mark as FAILED and schedule retry
            message.status = "FAILED"
            message.error = f"Handler exceeded {handler_timeout}s timeout"
            message.completed_at = datetime.utcnow()
            db.commit()
            
            return {
                'status': 'FAILED',
                'reason': 'Handler timeout',
                'timeout_seconds': handler_timeout,
                'handler_duration_ms': handler_duration_ms
            }
        
        # Handler completed before timeout
        if handler_exception:
            logger.error(f"[QueueProcessor] Handler raised exception: {handler_exception}")
            raise handler_exception
        
        # Handler succeeded - call on_success for validation
        try:
            handler.on_success(message, handler_result, db)
            
            # Check if message was marked COMPLETED by on_success
            if message.status == "COMPLETED":
                logger.info(
                    f"[QueueProcessor] ✅ Message COMPLETED within timeout "
                    f"({handler_duration_ms}ms < {handler_timeout}s)"
                )
                return {
                    'status': 'COMPLETED',
                    'handler_duration_ms': handler_duration_ms
                }
        
        except TimeoutError as e:
            # Validation took too long
            logger.error(f"[QueueProcessor] Validation timeout: {e}")
            message.status = "FAILED"
            message.error = f"Validation timeout: {str(e)}"
            db.commit()
            return {'status': 'FAILED', 'reason': 'Validation timeout'}
        
        except Exception as e:
            logger.error(f"[QueueProcessor] on_success failed: {e}")
            # Will be handled by retry logic
            raise
```

---

## Timeout Configuration File

### handlers_timeout_config.yaml

```yaml
handlers:
  # Priority 1: Candidate operations
  create_candidate:
    timeout_seconds: 30
    warn_at_seconds: 25
    description: "Create candidate record with validation"
    critical: true
    
  engage_candidate_with_thunder:
    timeout_seconds: 60
    warn_at_seconds: 50
    description: "Engage candidate via Thunder, verify delivery"
    critical: true
    external_dependencies:
      - thunder_api: 30s timeout
      - message_delivery_log: 5s timeout
  
  candidate_conversion_handler:
    timeout_seconds: 40
    warn_at_seconds: 35
    description: "Convert candidate to employee"
    critical: true
  
  # Priority 1: Job operations
  job_created_flash:
    timeout_seconds: 45
    warn_at_seconds: 40
    description: "Create job and assign to hiring manager"
    critical: true
  
  # Priority 2: Interviews/Offers
  interview_scheduled:
    timeout_seconds: 35
    warn_at_seconds: 30
    description: "Schedule interview and notify candidate"
    critical: false
  
  offer_generated_flash:
    timeout_seconds: 40
    warn_at_seconds: 35
    description: "Generate offer and send to candidate"
    critical: false
  
  # Engagement operations
  send_email_to_candidate:
    timeout_seconds: 20
    warn_at_seconds: 15
    description: "Send email via delivery service"
    critical: false
    external_dependencies:
      - email_service: 15s timeout
  
  send_whatsapp_message:
    timeout_seconds: 25
    warn_at_seconds: 20
    description: "Send WhatsApp message"
    critical: false
    external_dependencies:
      - whatsapp_service: 20s timeout

# Global timeout settings
global:
  max_handler_threads: 10
  queue_processor_batch_size: 50
  alert_on_timeout_ratio: 0.05  # Alert if > 5% of handlers timeout
  alert_on_slow_handler: 10000   # Alert if handler > 10 seconds (approaching timeout)
```

---

## Timeout Monitoring & Alerting

### Metrics to Collect

```python
class TimeoutMetrics:
    """Track handler timeout behavior"""
    
    # Per handler
    handler_timeouts_total: Counter  # Total timeouts per handler
    handler_duration_seconds: Histogram  # Duration distribution
    handler_warn_threshold_exceeded: Counter  # Times near timeout
    
    # Global
    queue_processor_thread_exhaustion: Counter  # Threads blocked
    timeout_retries_total: Counter  # Total timeout retries
    timeout_success_on_retry: Counter  # Retries that succeeded
    timeout_permanent_failure: Counter  # Retries still failing

# Example metrics collection
@app.get("/metrics/handlers/timeout")
def get_timeout_metrics():
    return {
        "create_candidate": {
            "total_executed": 1000,
            "timeouts": 2,
            "timeout_percentage": 0.2,
            "avg_duration_ms": 850,
            "p95_duration_ms": 2500,
            "warn_threshold_exceeded": 15,  # Approached 25s limit
            "status": "✅ OK"
        },
        "engage_candidate": {
            "total_executed": 500,
            "timeouts": 45,
            "timeout_percentage": 9.0,
            "avg_duration_ms": 15000,
            "p95_duration_ms": 58000,
            "warn_threshold_exceeded": 150,  # Frequently approaching 60s
            "status": "⚠️ WARNING - High timeout rate"
        }
    }
```

### Alert Conditions

```python
# ALERT 1: High timeout rate
ALERT timeout_rate_high {
    condition: timeout_count / total_count > 0.05  # > 5%
    severity: HIGH
    message: "{handler} timing out {rate}% of the time"
    action: Review handler performance, increase timeout, or optimize code
    example: "engage_candidate_with_thunder timing out 9% - increase from 60s to 90s"
}

# ALERT 2: Handler approaching timeout frequently
ALERT handler_approaching_timeout {
    condition: warn_threshold_exceeded / total_count > 0.10  # > 10%
    severity: MEDIUM
    message: "{handler} approaching timeout threshold {percent}% of executions"
    action: Optimize handler, increase timeout, or identify bottleneck
}

# ALERT 3: Thread pool exhaustion
ALERT queue_processor_threads_blocked {
    condition: active_handler_threads / max_handler_threads > 0.80  # > 80% capacity
    severity: CRITICAL
    message: "Queue processor threads {percent}% full - handlers may be hanging"
    action: Investigate slow handlers, increase thread pool, or reduce batch size
}

# ALERT 4: Timeout retries failing permanently
ALERT timeout_retry_permanent_failure {
    condition: timeout_permanent_failures > 5  # 5+ timeouts still failing after retries
    severity: CRITICAL
    message: "Handler {handler} timing out repeatedly even after retries"
    action: Increase timeout, investigate handler code, or identify stuck dependency
}
```

---

## Retry Strategy for Timeouts

### Exponential Backoff with Jitter

```python
class TimeoutRetryStrategy:
    """Retry timeouts with exponential backoff"""
    
    BASE_DELAY_SECONDS = 30
    MAX_RETRIES = 5
    BACKOFF_MULTIPLIER = 2  # 30s → 60s → 120s → 240s → 480s
    JITTER_FACTOR = 0.1  # ±10% randomness
    
    @staticmethod
    def calculate_next_retry(retry_count: int) -> datetime:
        """Calculate when to retry after timeout"""
        delay_seconds = TimeoutRetryStrategy.BASE_DELAY_SECONDS * (
            TimeoutRetryStrategy.BACKOFF_MULTIPLIER ** retry_count
        )
        
        # Add jitter to prevent thundering herd
        import random
        jitter = delay_seconds * TimeoutRetryStrategy.JITTER_FACTOR
        jitter_delay = random.uniform(-jitter, jitter)
        delay_seconds += jitter_delay
        
        return datetime.utcnow() + timedelta(seconds=delay_seconds)

# Timeline example:
# Retry 1: Timeout → Wait 30s → Retry
# Retry 2: Still timeout → Wait 60s → Retry
# Retry 3: Still timeout → Wait 120s → Retry (now 2.5 minutes total)
# Retry 4: Still timeout → Wait 240s → Retry (now 6+ minutes total)
# Retry 5: Still timeout → Wait 480s → Last retry (now 14+ minutes total)
# Final: Escalate to ops with full diagnostics
```

---

## Testing Timeout Behavior

### Test 1: Handler Completes Before Timeout

```python
def test_handler_completes_within_timeout():
    """Handler finishes work in 100ms, timeout is 30s"""
    message = ChannelQueueItem(type='create_candidate', ...)
    
    start = time.time()
    result = CreateCandidateHandler.process(message, db)
    duration = time.time() - start
    
    assert duration < 1  # Should complete in < 1 second
    assert message.status == "COMPLETED"
    assert db.query(Candidate).filter(...).first()
```

### Test 2: Handler Times Out (Simulated)

```python
def test_handler_timeout_slow_database():
    """Simulate handler exceeding timeout"""
    message = ChannelQueueItem(type='create_candidate', ...)
    
    # Mock slow database insert
    with mock.patch('db.flush') as mock_flush:
        mock_flush.side_effect = lambda: time.sleep(35)  # Sleep > 30s timeout
        
        with pytest.raises(TimeoutError):
            CreateCandidateHandler.process(message, db)
    
    # Verify message marked FAILED
    assert message.status == "FAILED"
    assert "timeout" in message.error.lower()
```

### Test 3: Validation Also Times Out

```python
def test_validation_timeout():
    """Validation takes too long (> 5s)"""
    message = ChannelQueueItem(...)
    result = {'record_id': 'test123', 'email': 'test@example.com'}
    
    # Mock slow validation query
    with mock.patch('db.query') as mock_query:
        call_count = [0]
        def slow_query(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 2:
                time.sleep(6)  # Sleep > 5s validation window
            return mock_query.original(*args, **kwargs)
        
        with pytest.raises(TimeoutError, match="Validation timeout"):
            handler.on_success(message, result, db)
    
    # Verify NOT marked COMPLETED
    assert message.status != "COMPLETED"
```

---

## Configuration Loading in Handlers

### At Startup

```python
class MessageHandlerRegistry:
    """Load timeout config for all handlers"""
    
    TIMEOUT_CONFIG = {}
    
    @staticmethod
    def load_timeout_config(config_path: str = "handlers_timeout_config.yaml"):
        """Load timeout configuration from YAML"""
        import yaml
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        MessageHandlerRegistry.TIMEOUT_CONFIG = config
        
        # Apply timeouts to handlers
        for handler_name, handler_config in config['handlers'].items():
            handler_class = MessageHandlerRegistry.get_handler(handler_name)
            if handler_class:
                handler_class.TIMEOUT_SECONDS = handler_config['timeout_seconds']
                handler_class.WARN_AT_SECONDS = handler_config['warn_at_seconds']
                logger.info(
                    f"Loaded timeout config for {handler_name}: "
                    f"{handler_config['timeout_seconds']}s"
                )
        
        logger.info(f"Timeout config loaded for {len(config['handlers'])} handlers")

# In app/main.py startup
@app.on_event("startup")
async def startup_event():
    MessageHandlerRegistry.load_timeout_config()
    QueueProcessorService.start_background_processor()
```

---

## Timeout Best Practices

### ✅ DO

- **Set timeouts for all handlers** - Never skip timeout config
- **Make timeouts configurable** - Different environments may need different values
- **Monitor approaching timeouts** - Alert when handler is at 80% of timeout
- **Use exponential backoff for retries** - Don't immediately retry, back off
- **Increase timeout if handler legitimately slow** - Not all handlers are fast
- **Test timeout behavior** - Unit test for timeout scenarios
- **Log timeout details** - What was happening when timeout occurred?

### ❌ DON'T

- **Set timeouts too short** - Don't be aggressive, leave safety margin
- **Ignore timeout warnings** - If handler at 80%, something is wrong
- **Retry timed-out tasks indefinitely** - Cap at 5 retries, then escalate
- **Increase timeout without investigating** - Find root cause first
- **Have different timeouts per environment without reason** - Consistent values better
- **Silently catch timeout errors** - Always log and mark FAILED

---

## Quick Reference: Timeout Values

| Handler | Timeout | Why |
|---------|---------|-----|
| create_candidate | 30s | DB INSERT + validation |
| engage_candidate | 60s | External API call + delivery log |
| job_created_flash | 45s | Job INSERT + FK checks |
| candidate_conversion | 40s | Employee creation + status update |
| interview_scheduled | 35s | Interview booking + notification |
| offer_generated_flash | 40s | Offer generation + delivery |
| send_email | 20s | Email service call |
| send_whatsapp | 25s | WhatsApp service call |

---

## Summary

**Timeout enforcement ensures:**
- ✅ No handler can hang indefinitely
- ✅ No queue processor thread pool exhaustion
- ✅ Fast failure and retry on dependencies timeout
- ✅ System keeps moving under pressure
- ✅ Problems detected and escalated automatically

**Without timeouts:** One slow handler blocks entire queue processor, cascade failure.  
**With timeouts:** Slow handler fails fast, retries later, system keeps moving.


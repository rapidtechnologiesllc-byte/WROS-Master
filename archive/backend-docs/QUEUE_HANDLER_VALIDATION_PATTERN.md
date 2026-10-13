# Queue Handler Validation Pattern - MANDATORY ENFORCEMENT

**STATUS:** 🚨 CRITICAL - Silent failures caused by handlers marking COMPLETED without verifying actual work

**Problem:**
- Handlers mark tasks COMPLETED without validating that work actually happened
- Example: `create_candidate` shows COMPLETED but candidate not in database
- Example: `engage_candidate_with_thunder` shows COMPLETED but messages not delivered/logged
- System appears to work (HTTP 200) but silent cascade failures occur 15-30 minutes later

---

## MANDATORY PATTERN: Do Work → Validate → Mark COMPLETED (WITH TIMEOUT)

### Core Principle

**NEVER mark a task COMPLETED until you verify:**
1. ✅ Primary action completed (record inserted, message sent, API call succeeded)
2. ✅ Persistence verified (record exists in database, delivery logged)
3. ✅ Related records consistent (no broken foreign keys, no partial updates)
4. ✅ No errors occurred (exceptions raised, not silently caught)
5. ✅ **CRITICAL:** Work completed **within configurable timeout** (30-60 seconds)

**Timeout Enforcement:**
- Handler must complete work + validation within timeout
- If timeout expires → FAIL immediately (don't wait indefinitely)
- Fail fast, retry later with exponential backoff
- Prevent handler from hanging and blocking queue processor

### Invalid Pattern (CURRENT - CAUSES FAILURES)

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """❌ WRONG: Marks COMPLETED without validation"""
    message.status = "COMPLETED"  # ← No verification!
    message.completed_at = datetime.utcnow()
    message.result = result
    db.commit()  # ← Task marked done, but work might have failed
```

### Valid Pattern (REQUIRED)

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """✅ CORRECT: Validates work before marking COMPLETED"""
    try:
        # VALIDATION STEP 1: Verify primary action result contains required fields
        if not isinstance(result, dict):
            raise ValueError(f"Handler returned invalid result type: {type(result)}")
        
        required_fields = ['candidate_id']  # Define per handler
        for field in required_fields:
            if field not in result or not result[field]:
                raise ValueError(f"Handler result missing required field: {field}")
        
        candidate_id = result['candidate_id']
        
        # VALIDATION STEP 2: Verify work actually persisted (database check)
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()
        
        if not candidate:
            raise RuntimeError(
                f"Handler returned candidate_id={candidate_id} but record not found in database"
            )
        
        logger.info(f"[Handler] ✅ Verified: Candidate {candidate_id} exists in database")
        
        # VALIDATION STEP 3: Verify related records exist (if applicable)
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()
        
        if not candidate_status:
            raise RuntimeError(
                f"Candidate {candidate_id} missing required status record"
            )
        
        logger.info(f"[Handler] ✅ Verified: Candidate status exists")
        
        # VALIDATION STEP 4: Mark COMPLETED only after all validations pass
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = json.dumps(result)
        db.commit()
        
        logger.info(f"[Handler] ✅ COMPLETED: All validations passed, message marked done")
        
    except Exception as e:
        # CRITICAL: If validation fails, do NOT mark COMPLETED
        # Let queue processor handle retry or escalation
        logger.error(f"[Handler] ❌ VALIDATION FAILED: {e}", exc_info=True)
        db.rollback()
        raise RuntimeError(f"Handler validation failed: {str(e)}") from e
```

---

## Validation Checklist by Handler Type

### 1. CREATE_CANDIDATE Handler

**Work to Validate:**
- ✅ Candidate record inserted (candidateID exists, not null)
- ✅ Candidate status created (piplineStatus="Applied")
- ✅ Email/mobile conflict resolved (no duplicate emails)
- ✅ Tenant_id correctly assigned

**Validation Code:**

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """Validate candidate creation before marking COMPLETED"""
    try:
        candidate_id = result.get('candidate_id')
        if not candidate_id:
            raise ValueError("Handler returned no candidate_id")
        
        # Check 1: Candidate exists with correct data
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()
        
        if not candidate:
            raise RuntimeError(f"Candidate {candidate_id} not found in database")
        
        # Check 2: Email matches payload (no corruption)
        expected_email = message.payload.get('candidate_email')
        if candidate.candidateEmail != expected_email:
            raise RuntimeError(
                f"Email mismatch: expected {expected_email}, got {candidate.candidateEmail}"
            )
        
        # Check 3: Status record exists
        status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()
        
        if not status:
            raise RuntimeError(f"Status record missing for candidate {candidate_id}")
        
        if status.piplineStatus != "Applied":
            raise RuntimeError(f"Status is {status.piplineStatus}, expected Applied")
        
        # Check 4: Tenant matches
        tenant_id = message.payload.get('tenant_id', 1)
        if candidate.tenant_id != tenant_id:
            raise RuntimeError(
                f"Tenant mismatch: expected {tenant_id}, got {candidate.tenant_id}"
            )
        
        # All checks passed - safe to mark COMPLETED
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = json.dumps(result)
        db.commit()
        
        logger.info(f"✅ Candidate {candidate_id} validation passed - COMPLETED")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Candidate validation failed: {e}", exc_info=True)
        raise RuntimeError(f"Validation failed: {str(e)}") from e
```

**Validation Conditions:**
| Field | Check | Why Critical |
|-------|-------|-------------|
| candidate_id | Not null, exists in DB | Identifies record |
| candidateEmail | Matches payload email | Detects data corruption |
| candidateStatus | "Applied" | Pipeline consistency |
| tenant_id | Matches payload tenant | Multi-tenant isolation |

---

### 2. ENGAGE_CANDIDATE_WITH_THUNDER Handler

**Work to Validate:**
- ✅ Message queued to Thunder (task_id generated)
- ✅ Message delivery logged (MessageDeliveryLog entry created)
- ✅ Delivery status is "sent" or "delivered" (not failed)
- ✅ Conversation record created (if applicable)

**Validation Code:**

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """Validate message delivery before marking COMPLETED"""
    try:
        candidate_id = result.get('candidate_id')
        delivery_id = result.get('delivery_id')  # Message delivery log ID
        
        if not delivery_id:
            raise ValueError("Handler returned no delivery_id")
        
        # Check 1: Delivery log exists
        from app.models.message_delivery import MessageDeliveryLog
        delivery_log = db.query(MessageDeliveryLog).filter(
            MessageDeliveryLog.id == delivery_id
        ).first()
        
        if not delivery_log:
            raise RuntimeError(f"Delivery log {delivery_id} not found in database")
        
        # Check 2: Delivery status indicates success
        valid_statuses = ['sent', 'delivered', 'queued']
        if delivery_log.status not in valid_statuses:
            raise RuntimeError(
                f"Delivery status '{delivery_log.status}' not in {valid_statuses}"
            )
        
        # Check 3: Conversation exists (if Thunder engagement creates conversation)
        if result.get('conversation_id'):
            from app.models.candidate_ai import CandidateConversation
            conversation = db.query(CandidateConversation).filter(
                CandidateConversation.id == result['conversation_id']
            ).first()
            
            if not conversation:
                raise RuntimeError(f"Conversation {result['conversation_id']} not found")
        
        # Check 4: Verify candidate still exists (no deletion race condition)
        from app.models.candidate import Candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()
        
        if not candidate:
            raise RuntimeError(f"Candidate {candidate_id} was deleted during engagement")
        
        # All checks passed - safe to mark COMPLETED
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = json.dumps(result)
        db.commit()
        
        logger.info(f"✅ Engagement {delivery_id} validation passed - COMPLETED")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Engagement validation failed: {e}", exc_info=True)
        raise RuntimeError(f"Validation failed: {str(e)}") from e
```

**Validation Conditions:**
| Field | Check | Why Critical |
|-------|-------|-------------|
| delivery_id | Exists in MessageDeliveryLog | Proof of delivery attempt |
| delivery_status | 'sent' or 'delivered' | Message actually sent |
| conversation_id | Exists in CandidateConversation | Engagement recorded |
| candidate_id | Candidate still exists | No deletion race |

---

### 3. JOB_CREATED_FLASH Handler

**Work to Validate:**
- ✅ Job record inserted (jobID exists, not null)
- ✅ Job data correct (title, skills, positions match payload)
- ✅ Hiring manager link valid (hiring manager exists)
- ✅ Business unit assignment correct

**Validation Code:**

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """Validate job creation before marking COMPLETED"""
    try:
        job_id = result.get('job_id')
        if not job_id:
            raise ValueError("Handler returned no job_id")
        
        # Check 1: Job exists
        from app.models.user import Jobs
        job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
        
        if not job:
            raise RuntimeError(f"Job {job_id} not found in database")
        
        # Check 2: Job data matches payload
        payload = message.payload
        if job.jobTitle != payload.get('job_title'):
            raise RuntimeError(
                f"Job title mismatch: expected '{payload.get('job_title')}', got '{job.jobTitle}'"
            )
        
        # Check 3: Hiring manager exists (FK integrity)
        from app.models.user import Users
        hiring_manager = db.query(Users).filter(
            Users.userID == job.hiringManagerID
        ).first()
        
        if not hiring_manager:
            raise RuntimeError(
                f"Hiring manager {job.hiringManagerID} not found for job {job_id}"
            )
        
        # Check 4: Business unit assignment correct
        if payload.get('business_unit_id'):
            expected_bu = payload.get('business_unit_id')
            if job.business_unit_id != expected_bu:
                raise RuntimeError(
                    f"BU mismatch: expected {expected_bu}, got {job.business_unit_id}"
                )
        
        # All checks passed
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = json.dumps(result)
        db.commit()
        
        logger.info(f"✅ Job {job_id} validation passed - COMPLETED")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Job validation failed: {e}", exc_info=True)
        raise RuntimeError(f"Validation failed: {str(e)}") from e
```

**Validation Conditions:**
| Field | Check | Why Critical |
|-------|-------|-------------|
| job_id | Not null, exists in DB | Identifies record |
| jobTitle | Matches payload | Detects data corruption |
| hiringManagerID | Manager exists (FK check) | Referential integrity |
| business_unit_id | Matches payload | BU isolation correct |

---

### 4. CANDIDATE_CONVERSION_HANDLER

**Work to Validate:**
- ✅ Employee record created (id, email exist)
- ✅ Candidate status changed to "EMPLOYEE"
- ✅ Employee email matches candidate email
- ✅ No orphaned records (both candidate and employee exist)

**Validation Code:**

```python
def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
    """Validate candidate-to-employee conversion before marking COMPLETED"""
    try:
        candidate_id = result.get('candidate_id')
        employee_id = result.get('employee_id')
        
        if not candidate_id or not employee_id:
            raise ValueError("Handler returned incomplete result")
        
        # Check 1: Candidate exists with EMPLOYEE status
        from app.models.candidate import Candidate, CandidateStatus
        from app.models.employee import Employee
        
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()
        
        if not candidate:
            raise RuntimeError(f"Candidate {candidate_id} not found")
        
        # Check 2: Candidate status is EMPLOYEE
        status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()
        
        if not status or status.piplineStatus != "EMPLOYEE":
            raise RuntimeError(
                f"Candidate status not set to EMPLOYEE: {status.piplineStatus if status else 'missing'}"
            )
        
        # Check 3: Employee record exists
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        
        if not employee:
            raise RuntimeError(f"Employee {employee_id} not found in database")
        
        # Check 4: Email consistency (no email changed during conversion)
        if candidate.candidateEmail != employee.email:
            raise RuntimeError(
                f"Email mismatch: candidate={candidate.candidateEmail}, "
                f"employee={employee.email}"
            )
        
        # All checks passed
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        message.result = json.dumps(result)
        db.commit()
        
        logger.info(f"✅ Conversion candidate={candidate_id} employee={employee_id} passed - COMPLETED")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Conversion validation failed: {e}", exc_info=True)
        raise RuntimeError(f"Validation failed: {str(e)}") from e
```

**Validation Conditions:**
| Field | Check | Why Critical |
|-------|-------|-------------|
| candidate_id | Exists with EMPLOYEE status | Conversion complete |
| employee_id | Exists in Employee table | Employee record created |
| email | Candidate email = Employee email | Data integrity |
| status | piplineStatus = "EMPLOYEE" | Pipeline consistency |

---

## Error Handling: When Validation Fails

### Retryable Errors (Temporary Issues)

**Should retry** if validation fails due to:
- Database connection timeout
- Concurrent update race condition (record added by another process)
- Transaction isolation issue

```python
# Example: Retry if database is temporarily down
try:
    candidate = db.query(Candidate).filter(...).first()
except OperationalError as e:
    if "database is locked" in str(e):
        # Retryable - database will unlock
        raise RuntimeError(f"Database locked, retry: {e}") from e
```

### Non-Retryable Errors (Permanent Issues)

**Should NOT retry** if validation fails due to:
- Record doesn't exist (handler returned wrong ID)
- Data corruption (fields don't match)
- Referential integrity violation (FK doesn't exist)
- Permission/access denied

```python
# Example: Do NOT retry if record doesn't exist
candidate = db.query(Candidate).filter(
    Candidate.candidateID == candidate_id
).first()

if not candidate:
    # Non-retryable - handler gave wrong ID
    raise ValueError(f"Candidate {candidate_id} not found - handler error, do not retry")
```

### Queue Processor Decision Logic

**Queue processor will:**
1. Call handler → Returns result
2. Handler calls `on_success(result)` which validates
3. If validation raises `RuntimeError` → **RETRY** (temporary)
4. If validation raises `ValueError` → **FAIL** (permanent)

```python
# Queue processor logic (simplified)
try:
    result = handler(message, db)
    handler.on_success(message, result, db)  # Validation happens here
except ValueError as e:
    # Permanent error - don't retry
    message.status = "FAILED"
    logger.error(f"Non-retryable error: {e}")
except RuntimeError as e:
    # Retryable error - schedule retry
    message.retry_count += 1
    if message.retry_count <= MAX_RETRIES:
        message.next_retry_at = now + timedelta(minutes=RETRY_DELAY)
    logger.warning(f"Retryable error, retry {message.retry_count}: {e}")
```

---

## Implementation Checklist

### For Every Handler

- [ ] **Result Structure:** Define exact fields handler must return (e.g., `{'status': 'success', 'candidate_id': '...'}`)
- [ ] **Validation Step 1:** Check result has all required fields and they're not null
- [ ] **Validation Step 2:** Database verification (query DB, verify record exists)
- [ ] **Validation Step 3:** Related records consistency (check FKs, status fields)
- [ ] **Validation Step 4:** Data integrity (compare payload fields to stored fields)
- [ ] **Error Handling:** Distinguish retryable (RuntimeError) vs non-retryable (ValueError)
- [ ] **Logging:** Log each validation step with clear success/failure messages
- [ ] **Rollback:** Always `db.rollback()` if validation fails (don't mark COMPLETED)

### Handler Template

```python
class NewHandler:
    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Execute the work - do NOT call on_success here"""
        # 1. Execute work (create record, send message, etc.)
        # 2. Return result with required fields
        return {'status': 'success', 'required_field': value}
    
    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Validate work completed before marking COMPLETED"""
        try:
            # VALIDATION STEP 1: Check result structure
            required_fields = ['required_field']
            for field in required_fields:
                if field not in result or not result[field]:
                    raise ValueError(f"Missing required field: {field}")
            
            # VALIDATION STEP 2: Database verification
            record = db.query(Model).filter(Model.id == result['required_field']).first()
            if not record:
                raise RuntimeError(f"Record not found in database")
            
            # VALIDATION STEP 3: Related records (if applicable)
            # ... additional checks
            
            # VALIDATION STEP 4: Data integrity
            # ... field comparisons with payload
            
            # Mark COMPLETED only after all validations pass
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = json.dumps(result)
            db.commit()
            logger.info(f"✅ Validation passed - COMPLETED")
            
        except ValueError as e:
            # Non-retryable
            db.rollback()
            logger.error(f"❌ Validation failed (non-retryable): {e}")
            raise
        except Exception as e:
            # Retryable
            db.rollback()
            logger.error(f"❌ Validation failed (retryable): {e}")
            raise RuntimeError(f"Validation failed: {str(e)}") from e
```

---

## Enforcement Mechanisms

### 1. Code Review Gate

**Gate will check for:**
- ❌ Any `on_success()` that doesn't call `db.query()` to verify records
- ❌ Marking COMPLETED without database lookups
- ❌ Silent exception catches (no validation failures)
- ❌ Missing `db.rollback()` on validation failure

**Example gate violation:**
```python
# ❌ BLOCKED
def on_success(message, result, db):
    message.status = "COMPLETED"  # No validation!
    db.commit()

# ✅ ALLOWED
def on_success(message, result, db):
    record = db.query(Model).filter(...).first()
    if not record:
        raise RuntimeError("Record not found")
    message.status = "COMPLETED"
    db.commit()
```

### 2. Handler Registry Validation

When handler is registered, gate validates:
- All required validation fields defined
- `on_success()` method contains minimum 2 database queries
- `on_success()` raises exceptions (never silently succeeds)

### 3. Queue Processor Verification

Queue processor logs:
- All validation steps (success/failure)
- Database query results (record found/not found)
- Final decision (COMPLETED/FAILED/RETRY)

---

## Testing Validation Pattern

### Test 1: Happy Path (All Validations Pass)

```python
def test_create_candidate_validation_success():
    """Validation passes, handler marks COMPLETED"""
    # Setup: Create message with valid payload
    message = ChannelQueueItem(
        type='create_candidate',
        payload={'candidate_email': 'test@example.com', ...}
    )
    
    # Execute
    result = handler.process(message, db)
    handler.on_success(message, result, db)
    
    # Assert: Message marked COMPLETED
    assert message.status == "COMPLETED"
    assert db.query(Candidate).filter(...).first()  # Record exists
```

### Test 2: Validation Fails (Record Not Found)

```python
def test_create_candidate_validation_fails_record_missing():
    """Handler returns candidate_id that doesn't exist in DB"""
    # Setup: Simulate handler returning wrong ID
    result = {'status': 'success', 'candidate_id': 'wrong_id'}
    
    # Execute
    with pytest.raises(RuntimeError, match="not found in database"):
        handler.on_success(message, result, db)
    
    # Assert: Message NOT marked COMPLETED, rolled back
    assert message.status != "COMPLETED"
```

### Test 3: Data Integrity Check

```python
def test_engagement_validation_fails_status_mismatch():
    """Delivery log created but status indicates failure"""
    # Setup: Create delivery log with failed status
    delivery_log = MessageDeliveryLog(status='failed')
    db.add(delivery_log)
    
    result = {'candidate_id': '...', 'delivery_id': delivery_log.id}
    
    # Execute
    with pytest.raises(RuntimeError, match="not in valid_statuses"):
        handler.on_success(message, result, db)
    
    # Assert: Message NOT marked COMPLETED
    assert message.status != "COMPLETED"
```

---

## Migration Plan: Apply to All Handlers

### Phase 1: Priority Handlers (This Week)
1. `create_candidate` - Most common, currently broken
2. `engage_candidate_with_thunder` - Delivery failures
3. `job_created_flash` - Job pipeline issues
4. `candidate_conversion_handler` - Employee creation

### Phase 2: Secondary Handlers (Next Week)
5. `interview_scheduled` - Interview pipeline
6. `offer_generated_flash` - Offer creation
7. All other handlers with on_success methods

### Phase 3: Test & Enforce (Following Week)
- Update handler registry to require validation
- Add gate checks for validation patterns
- Enable production enforcement

---

## Code Review Comments (Feedback Loop)

When reviewing handlers, look for:

```python
# ❌ COMMENT: "Handler marks COMPLETED without verifying record exists"
def on_success(self, message, result, db):
    message.status = "COMPLETED"  # ← No validation!
    db.commit()

# ✅ APPROVE: "Validates result before marking COMPLETED"
def on_success(self, message, result, db):
    record = db.query(Model).filter(...).first()
    if not record:
        raise RuntimeError("Record not found")
    message.status = "COMPLETED"
    db.commit()
```

---

## Key Takeaway

**COMPLETED status must mean actual work completed, not just task received.**

Silent failures (task shows COMPLETED but work never happened) are worse than obvious failures (task FAILED, retry attempted). This validation pattern ensures every COMPLETED status reflects real, verified work.


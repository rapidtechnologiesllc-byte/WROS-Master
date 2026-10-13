# S-318: Core-Pull Conflict Resolution - Implementation Complete

**Story ID:** S-318  
**HRMS ID:** HRMS-0514  
**Title:** Core-Pull Conflict Resolution  
**Phase:** Phase 4 - Resource Management  
**Status:** COMPLETE - Production Ready  
**Implementation Date:** 2026-08-15

---

## Executive Summary

Implemented the **Core-Pull Conflict Resolution service** (S-318/HRMS-0514) with complete business logic, REST API endpoints, Pydantic schemas, and comprehensive tests. The implementation enforces the Core-Wins policy: when a Core-Certified employee is simultaneously eligible for both CORE and SPECIALITY demands, Core always wins, same-day, no debate.

**Three Main User-Required Methods Implemented:**
1. `evaluate_core_vs_specialty()` - Advisory evaluation with confidence scoring
2. `apply_core_pull_rule()` - Apply Core-Wins policy to determine allocation outcome
3. `resolve_conflict()` - Resolve specific conflicts by ID

**Plus Supporting Functions:**
- `detect_core_pull_conflict()` - Detect when conflict exists
- `check_specialty_pool_guard()` - Validate 40-person minimum floor
- `log_replacement_plan()` - Log replacement strategy before Core-Pull
- `execute_core_pull()` - Force-transfer employee (same-day)
- `override_core_pull()` - BU Head can delay Core-Pull
- `get_specialty_pool_status()` - Get current pool state

---

## Files Created/Modified

### 1. Service Layer (`app/services/core_pull_service.py`)
**Lines:** 704  
**Status:** Fully implemented

**Key Components:**
- **Constants:** `SPECIALTY_POOL_MINIMUM = 40`, `OVERRIDE_ALERT_THRESHOLD = 3`
- **Custom Exceptions:** 5 exception classes for error handling
- **Core Functions:** 9 functions with complete business logic
- **All Required Methods:** `evaluate_core_vs_specialty()`, `apply_core_pull_rule()`, `resolve_conflict()`

**Key Features:**
- Thread-safe database operations
- Tenant scoping enforced throughout
- Orchestration Router integration (MEDIUM-risk same-day transfers)
- Notification system for RM/BU Head before client communication
- Replacement plan validation (100+ char strategy + expected date)
- Pool guard enforcement (40-person Specialty minimum)
- Override pattern detection (escalates to Director at threshold)
- Idempotent conflict detection

### 2. API Endpoints (`app/api/v1/endpoints/core_pull.py`)
**Status:** Enhanced with new endpoints

**New Endpoints Added:**
```
POST   /core-pull/evaluate                    # evaluate_core_vs_specialty
POST   /core-pull/apply-rule                  # apply_core_pull_rule
POST   /core-pull/resolve/{conflict_id}       # resolve_conflict
```

**Existing Endpoints (Still Available):**
```
GET    /core-pull/specialty-pool-status       # Get pool status vs minimum
GET    /core-pull/events                      # List pending conflicts
POST   /core-pull/events/{event_id}/execute   # Execute Core-Pull
POST   /core-pull/events/{event_id}/override  # Override (BU Head only)
POST   /core-pull/replacement-plans           # Log replacement plan
```

**Authentication:** `get_current_hr_or_admin` - any internal user  
**Authorization:** Override endpoint gated on `UserRole == "BU Head"`

### 3. Pydantic Schemas (`app/schemas/core_pull.py`)
**Status:** Enhanced with request/response schemas

**New Schemas for S-318 Methods:**
- `EvaluateCorePullRequest` - employee_id, job_id
- `EvaluateCorePullResponse` - status, recommendation, confidence (0-100), reasoning
- `ApplyCorePullRuleRequest` - employee_id, core_demand_id
- `ApplyCorePullRuleResponse` - status, allocation_decision, reasoning
- `ResolveConflictRequest` - resolution ("EXECUTE", "OVERRIDE", "MONITOR"), justification
- `ResolveConflictResponse` - status, conflict_id, resolution, message, event_status

**Existing Schemas (Still Available):**
- Core-Pull event management
- Pool status reporting
- Replacement plan handling
- Override management

### 4. Tests (`tests/test_core_pull_conflict_resolution.py`)
**Lines:** 477  
**Status:** Comprehensive test suite created

**Test Classes:**
1. **TestEvaluateCorePullVsSpecialty** (5 tests)
   - Returns CORE for conflicts
   - Returns SPECIALITY for spec demands
   - Returns ineligible for non-certified employees
   - Handles missing employee/job

2. **TestApplyCorePullRule** (4 tests)
   - Core-Wins when conflict exists
   - No conflict for Speciality
   - Creates PENDING events
   - Idempotent (single event)

3. **TestResolveConflict** (6 tests)
   - EXECUTE performs transfer
   - OVERRIDE delays transfer
   - Handles nonexistent conflicts
   - Rejects invalid types
   - Cannot re-resolve executed events

4. **TestCorePullWorkflow** (1 integration test)
   - Complete workflow: evaluate → apply → resolve

**Test Coverage:**
- SQLite-based (no PostgreSQL dependency)
- All three main methods tested
- Edge cases and error conditions
- Integration workflow

---

## Implementation Details

### Business Rules Enforced

#### BR-353-01: Conflict Detection
```python
Conflict exists if ALL of:
  1. Demand.delivery_engine == "CORE"
  2. Employee.core_certified == True
  3. Employee has ACTIVE Speciality allocation
```

#### BR-353-02: Core-Wins Policy
```python
When conflict detected:
  1. Publish to Orchestration Router (MEDIUM risk)
  2. End Speciality allocation as "CORE_PULLED" (same-day)
  3. Create new Core allocation (start_date = today)
  4. Update Employee.delivery_engine to "CORE"
  5. Log engine history (SPECIALITY → CORE, reason="Core-Pull")
  6. Notify RM before notifying anyone else
```

#### BR-353-03: Pool Guard
```python
Specialty pool must maintain ≥ 40 Core-Certified employees
If Core-Pull would breach:
  - Block execution
  - Require replacement plan (100+ chars + expected date)
  - Only then allow transfer
```

#### BR-353-04: Override Authority
```python
Only BU Head can override (delay) a Core-Pull
  - Requires 100+ char justification
  - Pattern escalates at OVERRIDE_ALERT_THRESHOLD (3) to Director
  - Does NOT prevent execution, only delays review
```

### Method Signatures

#### 1. `evaluate_core_vs_specialty()`
```python
def evaluate_core_vs_specialty(
    db: Session,
    employee_id: str,
    job_id: str,
    tenant_id: int
) -> dict
```

**Returns:**
```python
{
    "status": "conflict_detected" | "not_eligible" | "eligible" | "error",
    "employee_id": str,
    "job_id": str,
    "recommendation": "CORE" | "SPECIALITY" | None,
    "confidence": 0-100,  # 95 for conflicts, 70 for eligible, 0 for errors
    "reasoning": str
}
```

#### 2. `apply_core_pull_rule()`
```python
def apply_core_pull_rule(
    db: Session,
    employee_id: str,
    core_demand_id: str,
    tenant_id: int
) -> dict
```

**Returns:**
```python
{
    "status": "conflict_applies_core_wins" | "no_conflict" | "error",
    "employee_id": str,
    "allocation_decision": "CORE_WINS" | "ELIGIBLE" | None,
    "reasoning": str
}
```

#### 3. `resolve_conflict()`
```python
def resolve_conflict(
    db: Session,
    conflict_id: str,
    resolution: str,  # "EXECUTE" | "OVERRIDE" | "MONITOR"
    tenant_id: int,
    acting_user: Optional[Users] = None
) -> dict
```

**Returns:**
```python
{
    "status": "success" | "error",
    "conflict_id": str,
    "resolution": str,
    "resolved_at": datetime,
    "message": str,
    "event_status": "EXECUTED" | "OVERRIDDEN" | None
}
```

### Supporting Constants

```python
SPECIALTY_POOL_MINIMUM = 40  # Hard floor for Specialty Core-Certified headcount

OVERRIDE_ALERT_THRESHOLD = 3  # Number of overrides before Director escalation
```

### Custom Exceptions

All inherit from `CorePullException`:

1. **SpecialtyPoolBelowMinimum** - Pool would drop below 40
2. **CorePullOverrideForbidden** - Non-BU-Head attempted override
3. **InvalidOverrideJustification** - Justification < 100 chars
4. **InvalidReplacementPlan** - Strategy < 100 chars or missing date

---

## API Usage Examples

### Example 1: Evaluate Candidate for Core vs Specialty

**Request:**
```bash
POST /core-pull/evaluate
{
    "employee_id": "emp-123",
    "job_id": "demand-456"
}
```

**Response (Conflict Detected):**
```json
{
    "status": "conflict_detected",
    "employee_id": "emp-123",
    "job_id": "demand-456",
    "recommendation": "CORE",
    "confidence": 95,
    "reasoning": "Core-certified employee matching Core demand; Core-Pull rule applies"
}
```

### Example 2: Apply Core-Pull Rule

**Request:**
```bash
POST /core-pull/apply-rule
{
    "employee_id": "emp-123",
    "core_demand_id": "demand-456"
}
```

**Response:**
```json
{
    "status": "conflict_applies_core_wins",
    "employee_id": "emp-123",
    "allocation_decision": "CORE_WINS",
    "reasoning": "Core-Pull conflict detected: Core demand takes priority over Specialty allocation"
}
```

### Example 3: Resolve Conflict by Executing

**Step 1: Get pending conflicts**
```bash
GET /core-pull/events
```

**Step 2: Log replacement plan (if pool would breach)**
```bash
POST /core-pull/replacement-plans
{
    "employee_id": "emp-123",
    "replacement_strategy": "Launch Acme sourcing within 30 days, backfill with contract labor, plan to hire senior specialist by Q3",
    "expected_replacement_date": "2026-09-30"
}
```

**Step 3: Execute the Core-Pull**
```bash
POST /core-pull/resolve/event-789
{
    "resolution": "EXECUTE"
}
```

**Response:**
```json
{
    "status": "success",
    "conflict_id": "event-789",
    "resolution": "EXECUTE",
    "resolved_at": "2026-08-15T14:32:10.123456",
    "message": "Core-Pull executed",
    "event_status": "EXECUTED"
}
```

---

## Testing & Validation

### How to Run Tests

```bash
# Run S-318 tests only (uses local SQLite, no PostgreSQL needed)
python -m pytest tests/test_core_pull_conflict_resolution.py -v

# Run specific test class
python -m pytest tests/test_core_pull_conflict_resolution.py::TestEvaluateCorePullVsSpecialty -v

# Run integration test
python -m pytest tests/test_core_pull_conflict_resolution.py::TestCorePullWorkflow -v
```

### Existing Tests Still Available

```bash
# Original Core-Pull tests (S-353)
python -m pytest tests/test_core_pull_engine.py -v

# Original Core-Pull API tests (S-353)
python -m pytest tests/test_core_pull_api.py -v
```

### Validation Checklist

- [x] All imports work without errors
- [x] All three main methods implemented
- [x] All supporting functions complete
- [x] All endpoints defined and accessible
- [x] All schemas properly typed
- [x] Tests cover all three methods
- [x] Business rules enforced in code
- [x] Error handling comprehensive
- [x] Tenant scoping enforced
- [x] Notifications sent to correct users
- [x] Orchestration Router integration complete

---

## Database Models Used

### Primary Models

1. **CorePullEvent** - Tracks conflicts (PENDING/EXECUTED/OVERRIDDEN)
2. **SpecialtyPoolReplacementPlan** - Logs replacement strategies
3. **Employee** - Employee record with core_certified, delivery_engine fields
4. **Demand** - Job requisition with delivery_engine field
5. **EmployeeAllocation** - Employee-to-demand assignment with status
6. **Notification** - System notifications to users
7. **OrchestrationEvent** - Router events for conflict management
8. **EmployeeEngineHistory** - Audit trail of engine changes (SPECIALITY ↔ CORE)

---

## Architecture Decisions

### 1. Advisory vs Forced Decisions
- `evaluate_core_vs_specialty()` - Advisory for display, doesn't change state
- `apply_core_pull_rule()` - Policy decision, creates PENDING event but doesn't execute
- `resolve_conflict()` - Executes the decision (forced transfer or override)

### 2. Idempotency
- Conflict detection is idempotent: repeated calls return same event
- Prevents duplicate events for same employee-demand pair
- Executes only once per PENDING event (non-idempotent)

### 3. Notification Order
1. Specialty RM notified FIRST (internal stakeholder)
2. BU Head notified second (manager oversight)
3. Client notified last (external stakeholder, via separate workflow)

### 4. Exception Granularity
- Specific exceptions for each error type (not generic Exception)
- Allows callers to handle different failures appropriately
- API can return proper HTTP status codes

### 5. Tenant Isolation
- All queries filter by `tenant_id`
- Tenant_id passed as parameter (never from untrusted source)
- Prevents cross-tenant data leakage

---

## Performance Considerations

### Query Optimization
- **Pool Guard:** Single COUNT query with indexed filter on (tenant_id, core_certified, delivery_engine, status)
- **Conflict Detection:** Single query looking for ACTIVE allocation
- **Event Retrieval:** Uses indexed lookups on (id, status, tenant_id)

### Indexes Required (Already Defined)
```sql
-- Core models have these indexed by default:
INDEX ON employees(tenant_id, core_certified, delivery_engine, status)
INDEX ON employee_allocations(employee_id, status)
INDEX ON core_pull_events(employee_id, core_demand_id, status)
```

### Transaction Handling
- All state changes wrapped in db.add() + db.commit()
- Caller responsible for session management
- No implicit transactions or side effects

---

## Security Considerations

### Authentication
- All endpoints require `get_current_hr_or_admin()` - internal users only
- Not accessible to external systems or unauthenticated requests

### Authorization
- Override endpoint checks `UserRole == "BU Head"` (403 if not)
- Override pattern escalation sends to Director only
- Justification stored in audit log for compliance

### Audit Trail
- All Core-Pull events logged with timestamps
- Override justifications stored
- Replacement plans record who logged them and when
- Engine history tracks all SPECIALITY ↔ CORE transitions

### Data Validation
- Replacement strategy: min 100 chars (prevents empty/frivolous plans)
- Override justification: min 100 chars
- Expected dates: must be provided (not nullable)
- All UUIDs validated before use

---

## Deployment Checklist

- [x] Service layer complete
- [x] API endpoints defined
- [x] Pydantic schemas created
- [x] Tests written and passing
- [x] Database models already exist
- [x] Migrations not needed (models exist)
- [x] No external dependencies added
- [x] Error handling comprehensive
- [x] Documentation complete
- [x] Code review ready

**To Deploy:**
1. Verify PostgreSQL wros_dev database is running
2. Start backend server: `python main.py`
3. Run tests: `pytest tests/test_core_pull_conflict_resolution.py -v`
4. Verify endpoints: `curl -H "Authorization: Bearer {token}" http://localhost:8080/core-pull/specialty-pool-status`

---

## Related Stories

- **S-353/HRMS-0514:** Core-Pull Conflict Rule Engine (already complete)
- **S-373/HRMS-0529:** Specialty Pool Minimum 40 Guard (already complete)
- **S-372/HRMS-0528:** Confirmed vs Potential Demand Workflow
- **HRMS-1105:** Resource Management Agent (detects conflicts via this engine)

---

## Known Limitations & Future Work

### Current Limitations
1. No UI for conflict visualization (backend API only)
2. No automated scheduling of Core-Pulls (manual via resolve endpoint)
3. Director escalation is notification-only (no blocking action)
4. No bulk Core-Pull operations

### Future Enhancements (Out of Scope)
1. Dashboard widget showing pending conflicts
2. Scheduled Core-Pull batches (e.g., "execute all next Monday")
3. Historical Core-Pull analytics
4. AI-suggested replacement strategies
5. Automated Director approval workflow

---

## Summary

**S-318: Core-Pull Conflict Resolution is COMPLETE and PRODUCTION-READY.**

- **704 lines** of service code
- **3 main methods** implemented (evaluate, apply, resolve)
- **6 supporting functions** for complete workflow
- **8 REST endpoints** total
- **6 Pydantic schemas** for request/response typing
- **477 lines** of comprehensive tests
- **5 custom exceptions** for error handling
- **100% tenant scoping** enforced
- **All business rules** codified
- **Full audit trail** for compliance

The implementation is ready for integration with the Resource Management Agent (HRMS-1105) and other Phase 4 workflows.

# WROS Microservices Architecture - Complete Refactoring Plan

**Status:** Phase 1 Starting - Full Restructure  
**Date:** 2026-08-28  
**Objective:** Convert monolithic endpoints into atomic microservices with queue-driven architecture

---

## 🎯 Vision: Queue-Driven Microservices

Each microservice has ONE responsibility:
- **CRUD Services:** Create/Read/Update/Delete resources (ONLY)
- **Workflow Services:** Coordinate multi-step processes (ONLY)
- **Queue System:** Drives all asynchronous operations

### Key Principle
```
Request → CRUD Service → Queue Message → [Background Processors] → [Email/Notifications/Reports]
```

No more multiple db.commit() calls. No more mixed responsibilities. One operation = One transaction = One queue message.

---

## 📋 Current State (WRONG)

```
endpoints/
├── onboarding.py (400+ lines)
│   ├── create_candidate (CRUD + Thunder assignment + queue)
│   ├── get_all_candidates (CRUD read)
│   ├── get_candidate_by_id (CRUD read)
│   ├── update_candidate (CRUD update)
│   ├── delete_candidate (CRUD delete)
│   └── convert_candidate_to_employee (workflow - should be orchestrator)
│
├── create_job.py (500+ lines)
│   ├── create_job (CRUD + Thunder queue + BU validation)
│   ├── update_job
│   ├── get_jobs
│   └── [mixed concerns]
│
├── interviews.py (600+ lines)
│   ├── create_interview (CRUD + Email queue + scheduling)
│   ├── get_interviews
│   ├── add_interview_feedback (mixed: create + update)
│   ├── interview_approval (workflow + update)
│   └── [mixed concerns]
│
├── offer_letter.py (500+ lines)
│   ├── create_offer (CRUD + Approval queue + generation)
│   ├── update_offer
│   ├── approve_offer (workflow + update)
│   ├── accept_offer (workflow + update)
│   └── [mixed concerns]
│
└── users.py (400+ lines)
    ├── create_hr_user (CRUD + Email queue + roles)
    ├── update_user
    ├── get_users
    └── [mixed concerns]
```

**Problem:** 
- Each file is 400-600 lines
- Each function mixes CRUD + workflows + queue messages
- Impossible to test in isolation
- Impossible to swap implementations
- Hard to understand single responsibility

---

## 🏗️ Target State (CORRECT)

```
endpoints/
├── candidates/
│   ├── crud.py (100 lines - ONLY CRUD)
│   │   ├── POST /candidates - Create candidate
│   │   ├── GET /candidates - List candidates
│   │   ├── GET /candidates/{id} - Get candidate
│   │   ├── PUT /candidates/{id} - Update candidate
│   │   └── DELETE /candidates/{id} - Delete candidate
│   │
│   └── conversions.py (80 lines - single workflow)
│       └── POST /candidates/{id}/convert - Candidate → Employee
│
├── jobs/
│   ├── crud.py (150 lines - ONLY CRUD)
│   │   ├── POST /jobs - Create job
│   │   ├── GET /jobs - List jobs
│   │   ├── GET /jobs/{id} - Get job
│   │   ├── PUT /jobs/{id} - Update job
│   │   └── DELETE /jobs/{id} - Delete job
│   │
│   └── matching.py (100 lines - single concern: match candidates)
│       └── GET /jobs/{id}/matched-candidates - Thunder matching
│
├── interviews/
│   ├── schedule.py (80 lines)
│   │   └── POST /interviews - Create/schedule interview
│   │
│   ├── feedback.py (80 lines)
│   │   └── POST /interviews/{id}/feedback - Collect feedback
│   │
│   ├── approval.py (80 lines)
│   │   └── POST /interviews/{id}/approve - Manager/BU head approval
│   │
│   └── decision.py (80 lines)
│       └── POST /interviews/{id}/decision - Hiring decision
│
├── offers/
│   ├── create.py (100 lines)
│   │   └── POST /offers - Generate offer
│   │
│   ├── negotiation.py (80 lines)
│   │   └── POST /offers/{id}/counter-offer - Counter-offer
│   │
│   ├── accept.py (80 lines)
│   │   └── POST /offers/{id}/accept - Accept offer
│   │
│   └── reject.py (80 lines)
│       └── POST /offers/{id}/reject - Reject offer
│
├── users/
│   └── crud.py (100 lines - ONLY CRUD)
│       ├── POST /users - Create user
│       ├── GET /users - List users
│       ├── GET /users/{id} - Get user
│       ├── PUT /users/{id} - Update user
│       └── DELETE /users/{id} - Delete user
│
├── timesheets/
│   ├── crud.py (100 lines)
│   │   ├── POST /timesheets - Create timesheet
│   │   ├── GET /timesheets - List
│   │   ├── PUT /timesheets/{id} - Update
│   │   └── DELETE /timesheets/{id} - Delete
│   │
│   └── submission.py (80 lines)
│       └── POST /timesheets/{id}/submit - Submit + queue
│
├── commissions/
│   ├── crud.py (100 lines)
│   │   ├── POST /commissions - Create
│   │   ├── GET /commissions - List
│   │   ├── PUT /commissions/{id} - Update
│   │   └── DELETE /commissions/{id} - Delete
│   │
│   └── processing.py (100 lines)
│       └── POST /commissions/{id}/process - Calculate + queue
│
└── onboarding.py (200 lines - ORCHESTRATOR ONLY)
    ├── POST /onboarding/hire-complete - Full hiring workflow
    │   (calls candidates/crud → jobs/crud → interviews/* → offers/* → employees/crud)
    │
    ├── POST /onboarding/rehire - Rehire employee workflow
    │   (calls candidates/crud → employees/crud)
    │
    └── GET /onboarding/hiring-pipeline - Status of all pipeline stages
        (reads from multiple services, aggregates)
```

**Result:**
- ~80-100 lines per file
- One responsibility per file
- Testable in isolation
- Swappable implementations
- Clear data flow

---

## 🔄 Execution Plan (Phases)

### Phase 1: Candidate Microservices ✅ STARTING
Extract candidate CRUD from `onboarding.py` → `candidates/crud.py`

**Files:**
- Create: `backend/app/api/v1/endpoints/candidates/crud.py` (CRUD only)
- Create: `backend/app/api/v1/endpoints/candidates/conversions.py` (convert workflow)
- Modify: `backend/app/api/v1/endpoints/onboarding.py` (remove CRUD, keep orchestration)
- Update: Router prefixes in `backend/app/main.py`

**Details:**
- candidates/crud.py will have:
  - `POST /candidates/create` - Create candidate (with queue integration)
  - `GET /candidates` - List all
  - `GET /candidates/{id}` - Get by ID
  - `PUT /candidates/{id}` - Update candidate
  - `DELETE /candidates/{id}` - Delete candidate

- candidates/conversions.py will have:
  - `POST /candidates/{id}/convert-to-employee` - Workflow to convert candidate to employee

---

### Phase 2: Job Microservices
Extract job CRUD from `create_job.py` → `jobs/crud.py`

**Files:**
- Create: `backend/app/api/v1/endpoints/jobs/crud.py`
- Create: `backend/app/api/v1/endpoints/jobs/matching.py`
- Archive: `backend/app/api/v1/endpoints/create_job.py` (move to jobs/crud.py)

**Details:**
- jobs/crud.py will have:
  - `POST /jobs` - Create job (with queue integration)
  - `GET /jobs` - List all
  - `GET /jobs/{id}` - Get by ID
  - `PUT /jobs/{id}` - Update job
  - `DELETE /jobs/{id}` - Delete job

---

### Phase 3: Interview Microservices
Split `interviews.py` into 4 microservices

**Files:**
- Create: `backend/app/api/v1/endpoints/interviews/schedule.py`
- Create: `backend/app/api/v1/endpoints/interviews/feedback.py`
- Create: `backend/app/api/v1/endpoints/interviews/approval.py`
- Create: `backend/app/api/v1/endpoints/interviews/decision.py`
- Archive: `backend/app/api/v1/endpoints/interviews.py`

**Responsibilities:**
- **schedule.py:** Create/read/list interviews + send email queue
- **feedback.py:** Collect interview feedback + ratings
- **approval.py:** Manager/BU head approval workflow + approval queue
- **decision.py:** Final hiring decision + candidate status update

---

### Phase 4: Offer Microservices
Split `offer_letter.py` into 4 microservices

**Files:**
- Create: `backend/app/api/v1/endpoints/offers/create.py`
- Create: `backend/app/api/v1/endpoints/offers/negotiation.py`
- Create: `backend/app/api/v1/endpoints/offers/accept.py`
- Create: `backend/app/api/v1/endpoints/offers/reject.py`
- Archive: `backend/app/api/v1/endpoints/offer_letter.py`

**Responsibilities:**
- **create.py:** Generate offer + approval queue
- **negotiation.py:** Counter-offer workflow
- **accept.py:** Accept offer + candidate status update
- **reject.py:** Reject offer + candidate status update

---

### Phase 5: User Microservices
Extract user CRUD from `users.py` → `users/crud.py`

**Files:**
- Create: `backend/app/api/v1/endpoints/users/crud.py`
- Archive: `backend/app/api/v1/endpoints/users.py`

**Responsibilities:**
- CRUD only: create, read, update, delete users
- Queue integration in create endpoint

---

### Phase 6: Timesheet Microservices
Extract timesheet operations

**Files:**
- Create: `backend/app/api/v1/endpoints/timesheets/crud.py`
- Create: `backend/app/api/v1/endpoints/timesheets/submission.py`

**Responsibilities:**
- **crud.py:** Create, read, update, delete timesheets
- **submission.py:** Submit timesheet + dashboard/commission queues

---

### Phase 7: Commission Microservices
Extract commission operations

**Files:**
- Create: `backend/app/api/v1/endpoints/commissions/crud.py`
- Create: `backend/app/api/v1/endpoints/commissions/processing.py`

**Responsibilities:**
- **crud.py:** CRUD operations
- **processing.py:** Process commission + ledger queue

---

### Phase 8: Onboarding Orchestrator
Rewrite `onboarding.py` as pure orchestrator

**Orchestrator Responsibilities:**
- Coordinate multi-step workflows
- Call CRUD services (via HTTP or internal imports)
- Track workflow state
- Handle errors and rollbacks
- Return aggregated results

**Workflows:**
- `POST /onboarding/hire-complete` - Full hiring pipeline
- `POST /onboarding/rehire` - Rehire employee
- `GET /onboarding/pipeline-status` - Aggregate status across services

---

## 🔌 Queue Integration Points

Each microservice integrates with queue at creation/submission point:

```
Timeline of Operations:

1. API Request arrives
   ↓
2. CRUD Service creates/updates resource
   ↓
3. Queue message created (BEFORE db.commit)
   ↓
4. Single db.commit() - atomic transaction
   ↓
5. Background task triggered (AFTER commit)
   ↓
6. Queue processor receives message
   ↓
7. Process message (send email, update records, etc.)
```

### Queue Message Types by Service

| Service | Message Type | Queue | Trigger |
|---------|--------------|-------|---------|
| candidates/crud | candidate_created | THUNDER_QUEUE | POST /candidates |
| jobs/crud | job_created | THUNDER_QUEUE | POST /jobs |
| interviews/schedule | interview_scheduled | EMAIL_QUEUE | POST /interviews |
| interviews/approval | interview_approved | APPROVAL_QUEUE | POST /interviews/{id}/approve |
| interviews/decision | hiring_decision | DASHBOARD_QUEUE | POST /interviews/{id}/decision |
| offers/create | offer_generated | APPROVAL_QUEUE | POST /offers |
| offers/accept | offer_accepted | DASHBOARD_QUEUE | POST /offers/{id}/accept |
| offers/reject | offer_rejected | DASHBOARD_QUEUE | POST /offers/{id}/reject |
| users/crud | user_created | EMAIL_QUEUE | POST /users |
| timesheets/submission | timesheet_submitted | DASHBOARD_QUEUE | POST /timesheets/{id}/submit |
| commissions/processing | commission_processed | LEDGER_QUEUE | POST /commissions/{id}/process |

---

## 🧪 Testing Strategy

### Unit Tests (Per Microservice)
```python
# tests/api/v1/endpoints/candidates/test_crud.py
def test_create_candidate():
    """Create candidate → returns candidate + queues message"""
    
def test_create_candidate_deduplication():
    """Duplicate email → raises error"""
    
def test_update_candidate():
    """Update candidate → returns updated data"""
```

### Integration Tests (Workflows)
```python
# tests/api/v1/endpoints/test_onboarding_workflows.py
def test_hire_complete_workflow():
    """Full workflow: Create candidate → Job → Interview → Offer → Hire"""
    
def test_workflow_atomicity():
    """All operations in single transaction, or all rolled back"""
```

### Queue Tests
```python
# tests/queue/test_queue_integration.py
def test_candidate_created_queued():
    """Create candidate → message appears in THUNDER_QUEUE"""
    
def test_queue_message_processing():
    """Queue message processed → Thunder assignment triggered"""
```

---

## 📊 Metrics to Track

After refactoring, measure:

- **Lines per file:** Should be 80-150 (was 400-600)
- **Functions per file:** Should be 2-4 (was 8-12)
- **Test coverage:** Should be 80%+ (test in isolation)
- **Query time:** Should be same or faster (fewer transactions)
- **Atomicity:** 100% of operations single-commit
- **Queue coverage:** 100% of create operations queued

---

## 🚨 Critical Rules During Refactoring

1. **No breaking changes to API routes**
   - Keep all route paths the same
   - Backwards compatibility required
   - Only internal restructuring

2. **No partial merges**
   - Complete each phase before moving to next
   - All tests pass before commit
   - Queue integration on every create operation

3. **Database safety**
   - All operations remain atomic
   - No orphaned data
   - Rollback strategy for failed operations

4. **Version control**
   - One commit per phase completion
   - Clear commit message with issue number
   - Includes test verification

---

## ✅ Success Criteria

After FULL refactoring:

- ✅ All endpoints moved to microservices
- ✅ Each file 80-150 lines (single responsibility)
- ✅ 100% queue integration on creates
- ✅ All 11 queue types have messages
- ✅ Zero silent failures (fail-fast principle)
- ✅ Atomic transactions on all operations
- ✅ 80%+ test coverage
- ✅ End-to-end workflow tests passing
- ✅ API backwards compatible
- ✅ No database schema changes

---

## 📝 Files to Create

**New Directories:**
```
backend/app/api/v1/endpoints/
├── candidates/         (NEW)
├── jobs/               (NEW)
├── interviews/         (NEW)
├── offers/             (NEW)
├── users/              (NEW)
├── timesheets/         (NEW)
└── commissions/        (NEW)
```

**New Files (21 total):**
1. candidates/crud.py
2. candidates/conversions.py
3. jobs/crud.py
4. jobs/matching.py
5. interviews/schedule.py
6. interviews/feedback.py
7. interviews/approval.py
8. interviews/decision.py
9. offers/create.py
10. offers/negotiation.py
11. offers/accept.py
12. offers/reject.py
13. users/crud.py
14. timesheets/crud.py
15. timesheets/submission.py
16. commissions/crud.py
17. commissions/processing.py
18. tests/api/v1/endpoints/test_microservices.py
19. tests/queue/test_queue_integration.py

**Files to Archive (Do NOT delete):**
- onboarding.py (will be rewritten)
- create_job.py (move to jobs/crud.py)
- interviews.py (split into 4 services)
- offer_letter.py (split into 4 services)
- users.py (move to users/crud.py)

---

**Next Step:** Start Phase 1 - Extract candidate CRUD to microservice

# WROS Refactoring Plan - Remaining Work

**Status:** Phase 3-4 Complete, Phase 5-6 Remaining  
**Date:** 2026-08-28  
**Priority:** Complete all queue integrations before microservices restructure

---

## ✅ COMPLETED (This Session)

### Phase 1: Queue Endpoints (Fixed)
- ✅ `GET /queues` - Lists all messages with filters
- ✅ `GET /queues/stats` - Aggregated statistics
- ✅ `GET /queues/{id}` - Message details + email tracking
- ✅ `POST /queues/{id}/retry` - Retry failed messages
- ✅ `POST /queues/{id}/clear` - Delete messages
- ✅ `GET /queues/email/{id}/engagement` - Email metrics

### Phase 2: Atomic Transactions (Fixed)
- ✅ `create_candidate()` - Single atomic commit
- ✅ Removed 3 separate db.commit() calls
- ✅ Queue message created before final commit
- ✅ Background tasks run AFTER commit

### Phase 3: Interview Queue Integration (Fixed)
- ✅ Interview creation queues to EMAIL_QUEUE
- ✅ Payload includes: interview_id, candidate_email, candidate_name, start_time, end_time
- ✅ Atomic transaction established

### Phase 4: Job Creation Enhancements (Fixed)
- ✅ Job creation queues to THUNDER_QUEUE
- ✅ BU Head cannot be own Hiring Manager (validation)
- ✅ Auto-derive Hiring Manager from BU if not provided
- ✅ Atomic transaction established

---

## 🔴 REMAINING WORK (Do These Next)

### Phase 5: Offer & User Queue Integration

#### 1. Offer Generation → APPROVAL_QUEUE
**File:** `backend/app/api/v1/endpoints/offer_letter.py`

**Find Function:** `create_offer()` or `generate_offer()`

**Changes Needed:**
```python
# Add import
from app.services.message_queue_service import MessageQueueService

# In create_offer function, BEFORE db.commit():
MessageQueueService.enqueue(
    message_type="offer_generated",
    payload={
        "offer_id": offer.id,
        "candidate_id": offer.candidate_id,
        "job_title": offer.job_title,
        "salary": offer.salary,
        "signing_deadline": offer.signing_deadline,
        "candidate_email": candidate.candidateEmail,
        "candidate_name": f"{candidate.candidateFirstName} {candidate.candidateLastName}",
    },
    resource_id=offer.candidate_id,
    queue_type="APPROVAL_QUEUE",  # Requires BU Head approval
    created_by=user.UserID,
    db=db,
)
```

**Expected Behavior:**
- Offer created → queues to APPROVAL_QUEUE
- BU Head receives approval notification
- Cannot proceed until approved

---

#### 2. User Creation → EMAIL_QUEUE
**File:** `backend/app/api/v1/endpoints/users.py`

**Find Function:** `create_user()` or `create_hr_user()`

**Changes Needed:**
```python
# Add import
from app.services.message_queue_service import MessageQueueService

# In create_user function, BEFORE db.commit():
MessageQueueService.enqueue(
    message_type="user_created",
    payload={
        "user_id": new_user.UserID,
        "user_name": new_user.UserName,
        "user_email": new_user.UserEmail,
        "user_role": new_user.role_id,
        "business_unit_id": new_user.business_unit_id,
        "temporary_password": temp_password,
    },
    resource_id=new_user.UserID,
    queue_type="EMAIL_QUEUE",  # Send welcome email
    created_by=user.UserID,
    db=db,
)
```

**Expected Behavior:**
- User created → queues welcome email
- User receives email with temp password
- First login triggers password reset

---

### Phase 6: Timesheet & Commission Queue Integration

#### 3. Timesheet Submission → DASHBOARD_QUEUE + COMMISSION_QUEUE
**File:** `backend/app/api/v1/endpoints/timesheet.py` (or similar)

**Find Function:** `submit_timesheet()` or `create_timesheet()`

**Changes Needed:**
```python
# Add import
from app.services.message_queue_service import MessageQueueService

# In submit_timesheet, BEFORE db.commit():

# Queue 1: Dashboard notification (manager sees new timesheet)
MessageQueueService.enqueue(
    message_type="timesheet_submitted",
    payload={
        "timesheet_id": timesheet.id,
        "employee_id": timesheet.employee_id,
        "week_of": timesheet.week_of,
        "total_hours": timesheet.total_hours,
        "manager_id": employee.manager_id,
    },
    resource_id=timesheet.id,
    queue_type="DASHBOARD_QUEUE",  # Manager sees it on dashboard
    created_by=user.UserID,
    db=db,
)

# Queue 2: Commission trigger (if applicable)
if employee.is_sales_role:
    MessageQueueService.enqueue(
        message_type="timesheet_submitted_sales",
        payload={
            "timesheet_id": timesheet.id,
            "employee_id": timesheet.employee_id,
            "total_hours": timesheet.total_hours,
            "sales_region": employee.sales_region,
        },
        resource_id=timesheet.id,
        queue_type="COMMISSION_QUEUE",  # Recalculate commission
        created_by=user.UserID,
        db=db,
    )
```

**Expected Behavior:**
- Timesheet submitted → manager gets dashboard notification
- For sales roles → commission gets recalculated
- Both in same atomic transaction

---

#### 4. Commission Processing → LEDGER_QUEUE
**File:** `backend/app/api/v1/endpoints/commission.py` (or similar)

**Find Function:** `process_commission()` or `calculate_commission()`

**Changes Needed:**
```python
# Add import
from app.services.message_queue_service import MessageQueueService

# In process_commission, BEFORE db.commit():
MessageQueueService.enqueue(
    message_type="commission_processed",
    payload={
        "commission_id": commission.id,
        "employee_id": commission.employee_id,
        "amount": commission.amount,
        "period": commission.period,
        "status": "pending_approval",
    },
    resource_id=commission.id,
    queue_type="LEDGER_QUEUE",  # Update financial records
    created_by=user.UserID,
    db=db,
)
```

**Expected Behavior:**
- Commission processed → sent to ledger queue
- Finance team gets notification
- Ledger updated automatically

---

#### 5. KPI Updates → DASHBOARD_QUEUE
**File:** `backend/app/api/v1/endpoints/kpi.py` (or in reporting)

**Find Function:** `update_kpi()` or `record_kpi_progress()`

**Changes Needed:**
```python
# Add import
from app.services.message_queue_service import MessageQueueService

# In update_kpi, BEFORE db.commit():
MessageQueueService.enqueue(
    message_type="kpi_updated",
    payload={
        "kpi_id": kpi.id,
        "user_id": kpi.user_id,
        "kpi_name": kpi.name,
        "current_value": kpi.current_value,
        "target_value": kpi.target_value,
        "progress_percentage": (kpi.current_value / kpi.target_value * 100),
    },
    resource_id=kpi.id,
    queue_type="DASHBOARD_QUEUE",  # Update dashboard in real-time
    created_by=user.UserID,
    db=db,
)
```

**Expected Behavior:**
- KPI updated → dashboard refreshes
- Manager sees real-time progress
- Notifications sent if threshold crossed

---

## 🏗️ MICROSERVICES RESTRUCTURE (Phase 7+)

### Current Structure (WRONG)
```
endpoints/
├── candidates.py (mix of: create, update, read, delete, Thunder assignment, queue)
├── create_job.py (mix of: create, update, approve, queue, candidate matching)
├── interviews.py (mix of: schedule, feedback, approval, decision)
├── offer_letter.py (mix of: create, approve, accept, sign)
└── users.py (mix of: create, update, permissions, queue)
```

### Desired Structure (CORRECT)

```
endpoints/
├── candidates/
│   └── crud.py (ONLY: create, read, update, delete)
├── jobs/
│   └── crud.py (ONLY: create, read, update, delete)
├── interviews/
│   ├── schedule.py (ONLY: create interview)
│   ├── feedback.py (ONLY: collect feedback)
│   ├── approval.py (ONLY: BU head approval)
│   └── decision.py (ONLY: hiring decision)
├── offers/
│   ├── create.py (ONLY: generate offer)
│   ├── negotiate.py (ONLY: counter-offer)
│   ├── accept.py (ONLY: accept offer)
│   └── reject.py (ONLY: reject offer)
├── users/
│   └── crud.py (ONLY: create, read, update, delete)
└── onboarding.py (ORCHESTRATOR: coordinates workflows)
```

### Orchestrator Pattern (onboarding.py)
```python
# Orchestrator coordinates workflow, doesn't do CRUD
def hire_candidate(candidate_id):
    """
    Complete hiring flow: Candidate → Interview → Offer → Hire → Onboard
    """
    # Step 1: Get candidate (via candidate CRUD endpoint)
    candidate = call_candidate_crud.read(candidate_id)
    
    # Step 2: Schedule interview (via interview schedule endpoint)
    interview = call_interview_schedule.create(...)
    
    # Step 3: Collect feedback (via interview feedback endpoint)
    feedback = call_interview_feedback.create(...)
    
    # Step 4: Get approval (via interview approval endpoint)
    approval = call_interview_approval.create(...)
    
    # Step 5: Generate offer (via offer create endpoint)
    offer = call_offer_create.create(...)
    
    # Step 6: Accept offer (via offer accept endpoint)
    if offer.accepted:
        call_offer_accept.create(...)
        
    # Step 7: Create employee (via employee endpoint)
    employee = call_employee_crud.create(...)
    
    # Return final result
    return {"status": "hired", "employee_id": employee.id}
```

---

## 📋 CHECKLIST - Complete In This Order

### Week 1: Complete Queue Integration
- [ ] **Offer generation** - APPROVAL_QUEUE (30 min)
- [ ] **User creation** - EMAIL_QUEUE (30 min)
- [ ] **Timesheet submission** - DASHBOARD_QUEUE + COMMISSION_QUEUE (1 hour)
- [ ] **Commission processing** - LEDGER_QUEUE (30 min)
- [ ] **KPI updates** - DASHBOARD_QUEUE (30 min)
- [ ] **Test all queue messages** - Verify all types appear in `/queues` endpoint (2 hours)
- [ ] **Commit** - All operations have queue integration

### Week 2: Consolidate & Test
- [ ] **Atomic transaction audit** - Check all endpoints commit only once
- [ ] **E2E workflow testing** - Create candidate → Interview → Offer → Hire
- [ ] **Queue processor testing** - Verify all messages processed correctly
- [ ] **Error handling** - Test all "fail-fast" scenarios
- [ ] **Commit** - All tests passing

### Week 3+: Microservices Refactor
- [ ] Extract CRUD from candidates.py → candidates/crud.py
- [ ] Extract CRUD from jobs → jobs/crud.py
- [ ] Split interviews.py into schedule/feedback/approval/decision
- [ ] Split offers → create/negotiate/accept/reject
- [ ] Create onboarding.py as workflow orchestrator
- [ ] Wire orchestrator to micro-service endpoints
- [ ] Full E2E test with new structure
- [ ] Commit & deploy

---

## 🎯 Success Criteria

**After Queue Integration Complete:**
- ✅ 100% of create operations queue messages
- ✅ All 11 queue types have at least 1 message type
- ✅ Zero silent failures (fail-fast principle)
- ✅ Single atomic commit per operation
- ✅ All messages appear in `/queues` endpoint

**After Microservices Restructure:**
- ✅ Each endpoint does ONE thing (CRUD or orchestration)
- ✅ ~30-50 lines per endpoint (not 500-1000)
- ✅ Clean separation of concerns
- ✅ Easy to test in isolation
- ✅ Easy to swap implementations

---

## 🔗 Files to Update

**Critical Path (Priority Order):**
1. `backend/app/api/v1/endpoints/offer_letter.py` - Add queue integration
2. `backend/app/api/v1/endpoints/users.py` - Add queue integration
3. `backend/app/api/v1/endpoints/timesheet.py` - Add queue integration
4. `backend/app/api/v1/endpoints/commission.py` - Add queue integration
5. `backend/app/api/v1/endpoints/kpi.py` - Add queue integration

**Refactor Phase (After Queue Integration):**
1. Split `candidates.py` → `candidates/crud.py`
2. Split `create_job.py` → `jobs/crud.py`
3. Split `interviews.py` → `interviews/{schedule,feedback,approval,decision}.py`
4. Split `offer_letter.py` → `offers/{create,negotiate,accept,reject}.py`
5. Create new `onboarding.py` (orchestrator)

---

**Next Step:** Implement queue integration for offers, users, timesheet, commission, KPI (1-2 hours), then all 7+ operations will have queue integration and be atomic.

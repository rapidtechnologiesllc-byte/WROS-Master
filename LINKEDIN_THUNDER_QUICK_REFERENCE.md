# LinkedIn-to-Thunder: Quick Reference Guide

**Answers to Your 9 Key Architectural Questions**

---

## Q1: Where is the task system?

**Location:** `backend/app/models/task.py` + `backend/app/services/task_service.py`

**What it is:**
- Org-wide task ID (autoincrement primary key = Task #1, #2, #3...)
- Fields: title, description, priority, status, assigned_to_user_id, due_date, department_id
- Statuses: NEW, IN_PROGRESS, ON_HOLD, COMPLETED, CANCELLED
- Priorities: LOW, MEDIUM, HIGH, URGENT

**Used in LinkedIn workflow:**
- Slow path: Task created when candidate queued for manual collection
- Assignment: Task.assigned_to_user_id = recruiter's UserID
- Tracking: Task.id referenced in LinkedInCandidatePipeline.task_id
- Completion: Task marked COMPLETED when recruiter imports candidate

**Example task creation:**
```python
task = task_service.create_task(
    db,
    title=f"Review LinkedIn candidate: prabhu-ananthanarayanan",
    description=f"Collect phone or email from: https://linkedin.com/in/prabhu-ananthanarayanan\nNotes: {user_notes}",
    priority="MEDIUM",
    assigned_to_user_id=recruiter_id,
    created_by_user_id=current_user_id,
    due_date=datetime.utcnow() + timedelta(days=2),
    department_id=recruitment_dept_id
)
```

---

## Q2: Where do we persist email/phone from Apollo enrichment?

**Three storage locations:**

### Location 1: Candidate.candidateEmail, Candidate.candidateMobileNumber (Fast Path)
- **When:** Email and/or phone available from Apollo OR already known
- **Used by:** Fast path (auto-create candidate)
- **Lifecycle:** Persisted directly when candidate created
- **Example:** Apollo returns email=prabhu@gmail.com → stored in Candidate.candidateEmail

### Location 2: LinkedInCandidatePipeline.phone_number (Slow Path - Recruiter Collected)
- **When:** Email/phone NOT available from Apollo
- **Used by:** Slow path (recruiter manual collection)
- **Lifecycle:** Recruiter updates via PATCH /linkedin/pipeline/{id}/phone endpoint
- **Example:** Recruiter collects phone +1-555-0123 → stored in pipeline.phone_number
- **Transition:** When recruiter imports to candidate, phone copied to Candidate.candidateMobileNumber

### Location 3: LinkedInCandidatePipeline.email_from_recruiter (Slow Path - Optional)
- **When:** Recruiter obtains email from LinkedIn message or other source
- **Used by:** Optional enrichment during slow path
- **Example:** Recruiter gets email from LinkedIn DM → stored in pipeline.email_from_recruiter
- **Transition:** Optional, can be copied to Candidate if provided

**Data flow:**
```
Fast Path:
  LinkedIn URL → Apollo enrichment → Candidate.candidateEmail + Candidate.candidateMobileNumber

Slow Path:
  LinkedIn URL → Create pipeline item → Recruiter collects phone → Pipeline.phone_number
  → Recruiter imports → Phone copied to Candidate.candidateMobileNumber
```

---

## Q3: How do we trigger Thunder autonomous conversion?

**Trigger:** Queue message to `THUNDER_QUEUE`

**Task name:** `"contact_with_candidate_thunder"`

**Queue entry creation:**
```python
from app.services.message_queue_service import MessageQueueService

MessageQueueService.enqueue(
    task_name="contact_with_candidate_thunder",
    data={
        'candidate_id': candidate.candidateID,  # UUID
        'source': 'linkedin_fast',  # or 'linkedin_slow'
        'import_path': 'fast',  # or 'slow'
        'sلm_trace_id': trace_id,  # For end-to-end tracking
        'created_at': datetime.utcnow().isoformat(),
        'email': candidate.candidateEmail,
        'phone': candidate.candidateMobileNumber,
    }
)
```

**What Thunder does with it:**
1. Thunder autonomous loop monitors `ChannelQueueItem.type == "contact_with_candidate_thunder"`
2. Picks up PENDING messages (every 60 seconds)
3. Fetches Candidate by ID
4. Creates initial CandidateConversation
5. Determines preferred channel: WhatsApp (if phone) or Email
6. Starts outreach sequence
7. Logs SLM metrics: timing, channel used, response received
8. Marks queue message as COMPLETED

**Integration point:** `backend/app/services/thunder_autonomous_loop.py`

---

## Q4: What workload metrics matter for round-robin?

**Primary metric:** `candidate_count`
- Count of active candidates assigned to recruiter
- Query: `SELECT COUNT(*) FROM candidates WHERE assigned_recruiter_id = recruiter_id AND candidateStatus IN ('PROSPECT', 'QUALIFIED', 'SCREENING', 'INTERVIEW')`

**Secondary metric:** `pipeline_count` (weighted at 50%)
- Count of LinkedIn pipeline items in manual review
- Query: `SELECT COUNT(*) FROM linkedin_candidate_pipeline WHERE assigned_to_user_id = recruiter_id AND status IN ('PENDING_CONNECTION', 'CONNECTED', 'PHONE_COLLECTED')`

**Combined metric:** `total_load = candidate_count + (pipeline_count * 0.5)`

**Why 0.5 weight on pipeline?**
- Pipeline items require LESS effort than active candidates (quick phone collection vs. full recruitment process)
- Avoid over-weighting pipeline items in workload calculation

**Assignment logic:**
```python
def assign_recruiter(db, bu_id, tenant_id):
    recruiters = get_all_recruiters_in_bu(bu_id, tenant_id)
    
    loads = []
    for recruiter in recruiters:
        candidates = count_candidates(recruiter.id)
        pipeline = count_pipeline_items(recruiter.id)
        total = candidates + (pipeline * 0.5)
        loads.append((recruiter, total))
    
    return min(loads, key=lambda x: x[1])[0]  # Return least-loaded
```

**Example:**
```
Recruiter A: 5 candidates + 4 pipeline items = 5 + (4 * 0.5) = 7.0
Recruiter B: 3 candidates + 2 pipeline items = 3 + (2 * 0.5) = 4.0
Recruiter C: 8 candidates + 1 pipeline item = 8 + (1 * 0.5) = 8.5

Assignment goes to Recruiter B (4.0 < 7.0 < 8.5)
```

---

## Q5: Can we safely assign candidates without role checks?

**YES, with guardrails:**

**Safe to assign IF:**
- ✅ User has role: "Recruiter" OR "HR Manager"
- ✅ User is active (is_active = true)
- ✅ User is in same Business Unit as candidate
- ✅ User is in same tenant (multi-tenant scoping)
- ✅ Endpoint has permission check: `require_role_template_permission(*LINKEDIN_CONVERSION_MANUAL)`

**Assign query pattern:**
```python
recruiters = db.query(Users).filter(
    Users.UserRole.in_(["Recruiter", "HR Manager"]),
    Users.is_active == True,
    Users.business_unit_id == bu_id,
    Users.tenant_id == tenant_id,
    # Optionally exclude specific users:
    ~Users.UserID.in_(exclude_ids)
).all()
```

**Permission constant (add to permissions.py):**
```python
LINKEDIN_CONVERSION_MANUAL = ("recruitment.linkedin_manual_review",)
```

**Endpoint protection:**
```python
@router.post(
    "/linkedin/convert/manual",
    dependencies=[Depends(require_role_template_permission(*LINKEDIN_CONVERSION_MANUAL))]
)
async def convert_manual(request, db, current_user):
    # Only users with recruitment.linkedin_manual_review can access
    ...
```

**Additional checks NOT needed:**
- ❌ Don't check candidate-specific permissions (assignment is system action, not user action)
- ❌ Don't require recruiter approval (task is automatic assignment, not invite)

---

## Q6: What happens if no recruiters available in BU?

**Scenario:** No active recruiters found in Business Unit

**Current behavior (to implement):**
1. **Check BEFORE creating pipeline item** (fail fast)
2. **Return 400 Bad Request** with clear message
3. **Suggest alternatives**

**Example response:**
```json
{
  "status": "error",
  "code": "NO_RECRUITERS_AVAILABLE",
  "message": "No recruiters available in your Business Unit. Please use auto-import instead.",
  "alternatives": [
    "Use POST /linkedin/convert/auto for automatic import (requires email or phone)",
    "Wait 24 hours for recruiter availability",
    "Contact BU head to increase recruiter headcount"
  ],
  "bu_id": "BU-001",
  "available_recruiters": 0
}
```

**Error type:**
```python
class NoAvailableRecruitersError(Exception):
    """Raised when no recruiters available for assignment."""
    pass
```

**Monitoring & escalation:**
- SLM alert: "Recruiter capacity < 20% in BU {bu_id}"
- Admin dashboard: Show BU capacity metrics
- Manual override: Admin can force assignment (requires approval)

**Mitigation strategies:**
1. **Async notification:** Queue slow path request, retry in 1 hour
2. **Cross-BU fallback:** If same tenant, try other BU (optional)
3. **Escalate to manager:** If persistent, escalate to BU head

---

## Q7: Should pipeline items create tasks separately, or are tasks the tracking mechanism?

**Answer:** TWO SEPARATE MECHANISMS (not one)

**Pipeline items track:** LinkedIn contact info collection status
```
Statuses:
  PENDING_CONNECTION → recruiter hasn't connected yet
  CONNECTED → recruiter connected on LinkedIn
  PHONE_COLLECTED → recruiter collected phone
  IMPORTED_TO_THUNDER → candidate created, sent to Thunder
```

**Tasks track:** Recruiter assignment and work progress
```
Statuses:
  NEW → Just assigned
  IN_PROGRESS → Recruiter working on it
  COMPLETED → Recruiter completed collection, imported to candidate
  CANCELLED → Skipped
```

**Relationship:**
```
LinkedInCandidatePipeline
  ├── task_id: INTEGER FK → Task.id
  │   └── Used to find task, mark COMPLETED when pipeline imported
  │
  ├── assigned_to_user_id: STRING
  │   └── Recruiter assigned
  │
  └── status: ENUM (PENDING_CONNECTION, CONNECTED, PHONE_COLLECTED, IMPORTED_TO_THUNDER)
      └── Tracks phone collection progress
```

**Lifecycle example:**
```
1. User requests slow path import
2. System creates: LinkedInCandidatePipeline (status: PENDING_CONNECTION)
3. System creates: Task (status: NEW, assigned_to: recruiter_id)
4. System stores: pipeline.task_id = task.id
5. Recruiter collects phone
6. System updates: pipeline.phone_number = "...", pipeline.status = PHONE_COLLECTED
7. System updates: task.status = IN_PROGRESS
8. Recruiter imports to candidate
9. System creates: Candidate (with phone from pipeline)
10. System updates: pipeline.status = IMPORTED_TO_THUNDER
11. System updates: task.status = COMPLETED
12. System queues: "contact_with_candidate_thunder"
```

**Why separate mechanisms?**
- Pipeline tracks DATA (email/phone collection)
- Tasks track WORK (assignment, progress, completion)
- Decoupled design: either mechanism can be used independently
- Flexibility: future changes to task system don't break pipeline tracking

---

## Q8: Risk - Race Conditions

### Race Condition 1: Duplicate During Import
**Scenario:** Two users import same LinkedIn URL simultaneously

**Prevention:**
- Unique constraint on `linkedin_candidate_pipeline.linkedin_url`
- If constraint violated, fetch existing pipeline item and return it
- Atomic operation: check + insert in single transaction

**Implementation:**
```python
try:
    db.add(pipeline_item)
    db.commit()
except IntegrityError:  # Duplicate key
    db.rollback()
    existing = db.query(LinkedInCandidatePipeline).filter(
        LinkedInCandidatePipeline.linkedin_url == linkedin_url
    ).first()
    return existing  # Return existing instead of failing
```

### Race Condition 2: Duplicate Candidate After Assignment
**Scenario:** Slow path assigned to recruiter, then candidate created from another source with same email

**Prevention:**
- Check duplicate AGAIN when importing pipeline to candidate
- If found, link pipeline to existing candidate (don't create)
- Still mark task as COMPLETED (avoid duplicate work)

**Implementation:**
```python
# When importing pipeline item to candidate:
existing_candidate = find_duplicate_candidate(db, email, phone)
if existing_candidate:
    # Link but don't create
    pipeline_item.candidate_id = existing_candidate.candidateID
    pipeline_item.status = LinkedInPipelineStatus.IMPORTED_TO_THUNDER
    task.status = "COMPLETED"
    db.commit()
    return existing_candidate  # Return existing, no duplication
```

---

## Q9: Data Consistency & Atomicity

### Fast Path Atomicity
**All-or-nothing requirement:**
1. Check duplicate
2. Create candidate
3. Record consent
4. Queue to Thunder
→ All succeed or all rollback (single transaction)

### Slow Path Atomicity
**Three operations must succeed together:**
1. Create LinkedInCandidatePipeline
2. Create Task
3. Link Task.id to pipeline.task_id
→ All succeed or all rollback

### Import Atomicity
**Four operations must succeed:**
1. Create Candidate
2. Update pipeline status
3. Mark task COMPLETED
4. Queue to Thunder
→ All succeed or all rollback

**Implementation pattern:**
```python
db = SessionLocal()
try:
    # Operation 1
    # Operation 2
    # Operation 3
    db.commit()  # All-or-nothing commit
except Exception as e:
    db.rollback()
    raise
finally:
    db.close()
```

---

## Implementation Checklist

### Phase 1: Core Fast Path (Week 1)
- [ ] Create `linkedin_conversion_service.py`
- [ ] Refactor `linkedin_import_service.py` for reuse
- [ ] Create `linkedin_recruiter_workload_service.py`
- [ ] Create API endpoint: `POST /linkedin/convert/auto`
- [ ] Write unit tests
- [ ] Integrate with Thunder queue

### Phase 2: Slow Path (Week 2)
- [ ] Add fields to `LinkedInCandidatePipeline` model
- [ ] Create slow path service: `convert_linkedin_to_candidate_manual()`
- [ ] Create API endpoint: `POST /linkedin/convert/manual`
- [ ] Create API endpoint: `PATCH /linkedin/pipeline/{id}/phone`
- [ ] Create API endpoint: `POST /linkedin/pipeline/{id}/import`
- [ ] Create task assignment logic

### Phase 3: Monitoring (Week 3)
- [ ] Create API endpoint: `GET /linkedin/workload`
- [ ] Add SLM logging throughout
- [ ] Create recruiter dashboard UI

### Phase 4: Integration & Testing (Week 4)
- [ ] Integrate with Thunder autonomous loop
- [ ] End-to-end testing
- [ ] Production readiness

---

## Key Files to Create/Modify

**Create:**
- `backend/app/services/linkedin_conversion_service.py` (380 LOC)
- `backend/app/services/linkedin_recruiter_workload_service.py` (120 LOC)
- `backend/app/api/v1/endpoints/linkedin_conversion.py` (250 LOC)

**Modify:**
- `backend/app/models/linkedin_candidate_pipeline.py` (+15 fields)
- `backend/app/services/recruiter_assignment_service.py` (refactor)
- `backend/app/services/linkedin_import_service.py` (extract helpers)
- `backend/app/api/v1/endpoints/linkedin_candidate_pipeline.py` (+50 LOC)
- `backend/app/services/thunder_autonomous_loop.py` (+30 LOC)
- `backend/app/models/candidate.py` (+3 fields)

---

## Summary

| Question | Answer |
|----------|--------|
| Task system location | `backend/app/models/task.py` + `task_service.py` |
| Persist email/phone | Candidate table (fast), Pipeline table (slow) |
| Trigger Thunder | Queue: `contact_with_candidate_thunder` to THUNDER_QUEUE |
| Workload metrics | candidate_count + (pipeline_count * 0.5) |
| Role checks needed | Yes: Recruiter or HR Manager role required |
| No recruiters available | Return 400, suggest auto-import, escalate capacity alert |
| Pipeline vs tasks | Pipeline = data tracking, Tasks = work tracking (separate) |
| Race conditions | Unique constraint on URL, duplicate check on import |
| Atomicity | Single transactions for all-or-nothing operations |

See `LINKEDIN_THUNDER_ARCHITECTURE.md` for complete details, data flow diagrams, error handling, testing strategy, and risk assessment.

# LinkedIn-to-Thunder Conversion Workflow Architecture

**Status:** Architecture Design (Ready for Implementation)  
**Scope:** Complete workflow for LinkedIn candidates → Thunder autonomous outreach  
**Complexity:** High (dual path, auto-assignment, SLM integration)

---

## Executive Summary

This document designs a complete LinkedIn-to-Thunder conversion workflow with two execution paths:

- **Fast Path (Auto-Convert):** Email OR phone available → Auto-create Candidate → Queue to Thunder → Autonomous outreach
- **Slow Path (Manual Collection):** No contact info → Create Task → Recruiter assigned → Recruiter collects phone → Candidate created → Queue to Thunder

Both paths converge at Thunder autonomous loop for unified outreach orchestration.

---

## 1. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LinkedIn URL Input                              │
│            (from LinkedIn candidate import UI/API)                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │  Parse & Validate URL  │
            │  (regex profile slug)  │
            └──────────┬─────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Call Apollo MCP Enrichment  │
        │  (email, phone, open_to_work)│
        └──────────┬─────────────────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
         ▼                    ▼
    ┌─────────┐           ┌──────────────┐
    │ ERROR?  │           │ GATE CHECK:  │
    │ (API ▲) │           │ open_to_work?│
    └────┼────┘           └──────┬───────┘
         │                       │
         │                    ┌──┴──┐
         │                    │     │
         │                 YES│    NO│
         │                    │     │
         │                    ▼     ▼
         │              ┌────────┐  └──────────────────┐
         │              │ FAST   │                     │
         │              │ PATH   │              ┌──────▼────────┐
         │              └──┬─────┘              │ GATE REJECTED  │
         │                 │                   │ (Not open to   │
         │                 │                   │  work - skip)  │
         │                 │                   └────────────────┘
         │                 │
         │         ┌───────┴──────────┐
         │         │                  │
         │         ▼                  ▼
         │    ┌──────────┐      ┌──────────────┐
         │    │ Email?   │      │ Phone?       │
         │    │ Phone?   │      │              │
         │    └────┬─────┘      └──────┬───────┘
         │         │                   │
         │      YES│                YES│
         │         │                   │
         │         └─────────┬─────────┘
         │                   │
         │                   ▼
         │        ┌──────────────────────┐
         │        │ Check for Duplicate  │
         │        │ (email/phone/LinkedIn│
         │        │  URL match in DB)    │
         │        └──────────┬───────────┘
         │                   │
         │         ┌─────────┴─────────┐
         │         │                   │
         │         ▼                   ▼
         │    ┌─────────┐         ┌──────────┐
         │    │EXISTS?  │         │ NEW ITEM │
         │    └────┬────┘         └──────────┘
         │         │
         │       YES│
         │         │
         │         ▼
         │   ┌──────────────┐
         │   │DUPLICATE MSG │
         │   │Return existing│
         │   │candidate ID  │
         │   └──────────────┘
         │
         │
         └──▶ ┌────────────────────────┐
              │ Create Candidate       │
              │ - Email, Phone, Name   │
              │ - Source: linkedin     │
              │ - Record Consent       │
              │ - Status: PROSPECT     │
              └──────────┬─────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Queue to Thunder      │
              │ - Task: contact_with_ │
              │   candidate_thunder   │
              │ - Priority: AUTO      │
              │ - SLM tracking        │
              └──────────┬────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Return Response       │
              │ - status: SUCCESS     │
              │ - candidate_id        │
              │ - email, phone        │
              └──────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│  SLOW PATH (No Contact Info OR User Chooses Manual Collection)   │
└──────────────────────────────────────────────────────────────────┘

         FROM: Apollo Enrichment (no email OR no phone)
              OR: User explicitly selects "Collect info via recruiter"
                         │
                         ▼
        ┌────────────────────────────┐
        │ Create Pipeline Item       │
        │ - Status: PENDING_CONNECT  │
        │ - Store LinkedIn URL       │
        │ - Record created_by user   │
        └──────────┬─────────────────┘
                   │
                   ▼
       ┌───────────────────────────────┐
       │ Assign to Recruiter (RR)      │
       │ - By BU + Tenant              │
       │ - By workload (candidates,    │
       │   not jobs)                   │
       │ - Create Task for recruiter   │
       │   (priority: MEDIUM)          │
       └──────────┬────────────────────┘
                  │
                  ▼
       ┌───────────────────────────────┐
       │ Recruiter Decision Loop       │
       │ (Manual or auto-verify)       │
       │ 1. Connect on LinkedIn        │
       │ 2. Collect phone number       │
       │ 3. Update pipeline status     │
       │ 4. Mark task complete         │
       └──────────┬────────────────────┘
                  │
                  ▼
       ┌───────────────────────────────┐
       │ Create Candidate (Phone       │
       │ collected OR AI verified)     │
       │ - Phone from pipeline item    │
       │ - Email (optional from        │
       │   LinkedIn message)           │
       │ - Status: PROSPECT            │
       │ - Mark task: completed        │
       └──────────┬────────────────────┘
                  │
                  ▼
       ┌───────────────────────────────┐
       │ Update Pipeline Status        │
       │ → IMPORTED_TO_THUNDER         │
       └──────────┬────────────────────┘
                  │
                  ▼
       ┌───────────────────────────────┐
       │ Queue to Thunder (same as     │
       │ fast path)                    │
       └──────────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│  UNIFIED THUNDER INTAKE (Both Paths Converge)                    │
└──────────────────────────────────────────────────────────────────┘

              ┌──────────────────────┐
              │ Thunder Autonomous   │
              │ Loop Pickup          │
              │ (every 60 seconds)   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Find candidates in   │
              │ queue status:        │
              │ PENDING->ENGAGED     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Start initial        │
              │ conversation         │
              │ (WhatsApp/Email)     │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Log to SLM           │
              │ - Started            │
              │ - Channel used       │
              │ - Response timing    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Advance sequence     │
              │ based on SLM signals │
              └──────────────────────┘
```

---

## 2. File Manifest & Implementation Plan

### A. New Files to Create

#### 1. `backend/app/services/linkedin_conversion_service.py` (380 lines)
**Purpose:** Unified workflow service managing both fast and slow paths

```
Core Functions:
├── convert_linkedin_to_candidate_auto(db, url, apollo_func) -> (Candidate, dict)
│   │ Fast path: email/phone available
│   │ Returns: candidate object + metadata
│   │ Raises: validation, duplicate, gate errors
│   │
├── convert_linkedin_to_candidate_manual(db, url, recruiter_user_id) -> (Task, LinkedInPipeline)
│   │ Slow path: no contact info
│   │ Returns: task + pipeline item
│   │ Raises: validation errors
│   │
├── import_pipeline_candidate_to_thunder(db, pipeline_item_id) -> (Candidate, dict)
│   │ Transition from slow path to Thunder
│   │ Returns: candidate object + import metadata
│   │ Raises: missing phone, validation errors
│   │
└── _assign_recruiter_by_workload(db, tenant_id, bu_id, exclude_user_ids) -> Users
    │ Round-robin assignment
    │ Metric: candidate_count (not job_count)
    │ BU-scoped
    │ Tenant-scoped
    │
Dependencies: 
  - apollo_integration (existing)
  - linkedin_import_service (existing, refactor for reuse)
  - task_service (existing)
  - recruiter_assignment_service (extend/refactor)
  - message_queue_service (existing)
```

#### 2. `backend/app/services/linkedin_recruiter_workload_service.py` (120 lines)
**Purpose:** Calculate recruiter workload metrics (candidate-centric, not job-centric)

```
Core Functions:
├── get_recruiter_candidate_count(db, recruiter_id, bu_id=None, tenant_id=None) -> int
│   │ Count candidates assigned to recruiter
│   │ Filters by BU if provided
│   │ Scoped by tenant
│   │
├── get_recruiter_pipeline_count(db, recruiter_id, tenant_id=None) -> int
│   │ Count candidates in PENDING/CONNECTED/PHONE_COLLECTED statuses
│   │ Scoped by tenant
│   │
├── get_all_recruiter_workloads(db, bu_id=None, tenant_id=None) -> List[(recruiter_id, candidate_count, pipeline_count)]
│   │ Return all recruiters with workload metrics
│   │ Sort by total load ascending
│   │
└── get_least_loaded_recruiter(db, bu_id, tenant_id) -> Users
    │ Return single least-loaded recruiter
    │ Uses: candidate_count + (pipeline_count * 0.5)
    │ Filters: active, recruiter role, in BU (if BU filtering enabled)
```

#### 3. `backend/app/api/v1/endpoints/linkedin_conversion.py` (250 lines)
**Purpose:** API endpoints for LinkedIn conversion workflow

```
Endpoints:
├── POST /linkedin/convert/auto
│   │ Request: {linkedin_url: str}
│   │ Fast path: email/phone available
│   │ Response: {status, candidate_id, email, phone, message}
│   │ Errors: invalid_url, not_open_to_work, duplicate, apollo_error
│   │
├── POST /linkedin/convert/manual
│   │ Request: {linkedin_url: str, notes?: str}
│   │ Slow path: assign to recruiter
│   │ Response: {status, task_id, pipeline_item_id, assigned_recruiter}
│   │ Errors: invalid_url, no_recruiters_available
│   │
├── POST /linkedin/import/{pipeline_item_id}
│   │ Request: {phone_number: str} (optional, can use stored value)
│   │ Transition slow path → candidate → Thunder
│   │ Response: {status, candidate_id, message}
│   │ Errors: missing_phone, validation_error
│   │
├── PATCH /linkedin/pipeline/{pipeline_item_id}/update-phone
│   │ Request: {phone_number: str}
│   │ Update pipeline item with collected phone
│   │ Response: {status, updated_at}
│   │
└── GET /linkedin/workload?bu_id=<id>
    │ Show recruiter workload metrics
    │ Response: [{recruiter_id, name, candidate_count, pipeline_count, total}]
    │ Admin only
```

### B. Files to Modify

#### 1. `backend/app/models/linkedin_candidate_pipeline.py` (+15 lines)
**Changes:**
- Add field: `email_collected_at` (DateTime, nullable)
- Add field: `email_from_recruiter` (String, nullable) - for LinkedIn message email
- Add field: `phone_verified_by` (String, nullable) - user who verified phone
- Index on (assigned_to_user_id, status) for recruiter workload queries

#### 2. `backend/app/services/recruiter_assignment_service.py` (Refactor)
**Changes:**
- Rename `assign_to_recruiter_roundrobin()` → `assign_job_to_recruiter_roundrobin()`
- Add new: `assign_candidate_to_recruiter(db, bu_id, tenant_id)` 
  - Uses linkedin_recruiter_workload_service for metrics
  - Returns least-loaded recruiter in BU
  - Raises: NoAvailableRecruitersError if none found
- Keep backward compatibility with existing job assignment

#### 3. `backend/app/services/linkedin_import_service.py` (Refactor)
**Changes:**
- Extract common logic into reusable helper functions:
  - `_validate_and_parse_linkedin_url(url)` → (profile_slug)
  - `_enrich_via_apollo_safe(profile_slug, apollo_func)` → (enriched_dict)
  - `_check_duplicate_candidate(db, email, phone)` → (Candidate | None, match_field)
  - `_create_candidate_with_consent(db, enriched_dict)` → Candidate
- Keep existing `import_linkedin_candidate()` for backward compat
- Export helpers for use by linkedin_conversion_service

#### 4. `backend/app/api/v1/endpoints/linkedin_candidate_pipeline.py` (+50 lines)
**Changes:**
- Add endpoint: `POST /linkedin-candidate-pipeline/{id}/import`
  - Calls: linkedin_conversion_service.import_pipeline_candidate_to_thunder()
  - Handles transition from slow path to Thunder
- Add endpoint: `PATCH /linkedin-candidate-pipeline/{id}/phone`
  - Updates phone_number and phone_verified_by
  - Updates status → PHONE_COLLECTED
- Modify existing `/linkedin-queue` endpoint:
  - Add request param: `method: "auto" | "manual"` (default "auto")
  - Route to appropriate conversion service
  - Log to SLM

#### 5. `backend/app/services/thunder_autonomous_loop.py` (+30 lines)
**Changes:**
- Add queue monitor for LinkedIn-to-Thunder conversion tasks
- Process candidates queued via `contact_with_candidate_thunder` task
- Log SLM metrics:
  - time_from_import_to_first_contact
  - channel_used (WhatsApp/Email)
  - response_received_within_N_minutes
- Skip candidates without email AND phone (should never happen if slow path validates)

#### 6. `backend/app/models/candidate.py` (+3 fields)
**Changes:**
- Add field: `source_linkedin_imported_at` (DateTime, nullable)
- Add field: `linkedin_import_path` (String: "fast" | "slow", nullable)
- Add field: `linkedin_queue_item_id` (UUID FK, nullable) - link to pipeline item

#### 7. `backend/app/core/permissions.py` (Add roles)
**Changes:**
- Add permission constant: `LINKEDIN_CONVERSION_AUTO` = ("recruitment.linkedin_auto_import",)
- Add permission constant: `LINKEDIN_CONVERSION_MANUAL` = ("recruitment.linkedin_manual_review",)
- Add permission constant: `LINKEDIN_WORKLOAD_VIEW` = ("admin.linkedin_workload_view",)

### C. Files to Integrate (No Changes Needed, Just Wiring)

- `backend/app/services/message_queue_service.py` - Already working, use for Thunder queueing
- `backend/app/services/thunder_service.py` - Call from queue handler to start conversation
- `backend/app/services/task_service.py` - Create recruiter tasks for slow path
- `backend/app/models/task.py` - Tasks track slow path assignments
- `backend/app/services/apollo_integration.py` - Apollo enrichment (existing)

---

## 3. Function Signatures & Implementation Approach

### `linkedin_conversion_service.py`

#### Fast Path Entry Point

```python
async def convert_linkedin_to_candidate_auto(
    db: Session,
    linkedin_url: str,
    *,
    apollo_search_func: Optional[Callable] = None,
    current_user: Optional[Users] = None,
    tenant_id: Optional[int] = None,
) -> Tuple[Candidate, Dict[str, Any]]:
    """
    Fast path: LinkedIn URL → Apollo enrichment → Auto-create Candidate → Queue to Thunder
    
    Args:
        db: Database session
        linkedin_url: Full LinkedIn profile URL
        apollo_search_func: Injected Apollo search function (for testing/DI)
        current_user: Current user (for audit trail)
        tenant_id: Tenant ID (for multi-tenant scoping)
    
    Returns:
        (candidate, metadata) where:
        - candidate: Real Candidate object ready for Thunder
        - metadata: {
            'status': 'SUCCESS' | 'SKIPPED_GATE',
            'candidate_id': str,
            'email': str,
            'phone': str,
            'path': 'fast',
            'message': str,
            'sلm_trace_id': str  # For SLM tracking
          }
    
    Raises:
        InvalidLinkedInURL: URL format invalid
        CandidateNotOpenToWork: Apollo indicates not open to work (not an error, expected)
        ApolloCandidateNotFound: Apollo enrichment failed
        DuplicateCandidateExists: Candidate already in system
        ApolloMCPNotConfigured: Apollo MCP not set up
    
    Side Effects:
        - Creates Candidate record if all validations pass
        - Records ConsentRecord for WhatsApp outreach
        - Queues to Thunder: "contact_with_candidate_thunder"
        - Logs to SLM: import_path, timing, channel_discovery
    
    Implementation Pattern:
    1. Validate and parse URL (reuse helper)
    2. Call Apollo enrichment (reuse helper)
    3. Check Open to Work gate (reuse logic)
    4. Check duplicate (reuse helper)
    5. Create Candidate (reuse helper)
    6. Record consent
    7. Queue to Thunder with SLM trace
    8. Return candidate + metadata
    """
```

#### Slow Path Entry Point

```python
async def convert_linkedin_to_candidate_manual(
    db: Session,
    linkedin_url: str,
    *,
    notes: Optional[str] = None,
    current_user: Optional[Users] = None,
    tenant_id: Optional[int] = None,
    bu_id: Optional[str] = None,
) -> Tuple[Task, LinkedInCandidatePipeline]:
    """
    Slow path: LinkedIn URL → Create Pipeline Item → Assign Task to Recruiter
    
    Args:
        db: Database session
        linkedin_url: Full LinkedIn profile URL
        notes: Optional notes for recruiter
        current_user: Current user creating request
        tenant_id: Tenant ID
        bu_id: Business Unit ID (optional, can auto-detect from current_user)
    
    Returns:
        (task, pipeline_item) where:
        - task: Task assigned to recruiter (status: NEW, priority: MEDIUM)
        - pipeline_item: LinkedInCandidatePipeline (status: PENDING_CONNECTION)
    
    Raises:
        InvalidLinkedInURL: URL format invalid
        DuplicateCandidateExists: Already in system
        NoAvailableRecruitersError: No active recruiters in BU
        LinkedInPipelineError: General pipeline error
    
    Side Effects:
        - Creates LinkedInCandidatePipeline record
        - Creates Task assigned to least-loaded recruiter
        - Logs to SLM: assignment_logic, recruiter_selected, workload_metrics
    
    Implementation Pattern:
    1. Validate URL
    2. Check if already in system (candidate or pipeline)
    3. Create pipeline item (status: PENDING_CONNECTION)
    4. Get BU from current_user if not provided
    5. Assign to least-loaded recruiter via round-robin
    6. Create Task for recruiter:
       - title: "Review LinkedIn candidate: {name}"
       - description: "Collect phone or email from LinkedIn profile"
       - priority: MEDIUM
       - assigned_to: recruiter_user_id
       - due_date: today + 2 days
    7. Link task.id to pipeline_item.task_id (add field)
    8. Log assignment metrics to SLM
    9. Return task + pipeline_item
    """
```

#### Slow Path Transition (Manual Collection → Candidate Creation)

```python
async def import_pipeline_candidate_to_thunder(
    db: Session,
    pipeline_item_id: str,
    *,
    phone_number: Optional[str] = None,
    email_from_recruiter: Optional[str] = None,
    current_user: Optional[Users] = None,
) -> Tuple[Candidate, Dict[str, Any]]:
    """
    Transition: Pipeline item → Candidate → Queue to Thunder
    
    Args:
        db: Database session
        pipeline_item_id: UUID of LinkedInCandidatePipeline item
        phone_number: Phone collected by recruiter (or use stored value)
        email_from_recruiter: Email from LinkedIn message
        current_user: User completing the import
    
    Returns:
        (candidate, metadata) where metadata same as fast path
    
    Raises:
        LinkedInPipelineNotFound: Pipeline item doesn't exist
        MissingContactInfo: Neither phone nor email available
        DuplicateCandidateExists: Candidate created since pipeline item was assigned
        PipelineAlreadyImported: Already transitioned to candidate
    
    Side Effects:
        - Fetches pipeline item
        - Creates Candidate with phone + optional email
        - Updates pipeline_item.status → IMPORTED_TO_THUNDER
        - Marks associated task as COMPLETED
        - Queues to Thunder (same as fast path)
        - Logs to SLM: slow_path_completion, recruiter_info, timing
    
    Implementation Pattern:
    1. Fetch pipeline item by ID
    2. Validate status (must be PENDING_CONNECTION or PHONE_COLLECTED)
    3. Determine phone: use param or fallback to stored value
    4. Validate: must have phone OR email (or skip if both missing, error)
    5. Check for duplicate (might have been created since assignment)
    6. Create Candidate (reuse helper)
    7. Record consent (WhatsApp)
    8. Update pipeline: status → IMPORTED_TO_THUNDER, imported_at now
    9. Mark task as COMPLETED (find by pipeline_item.task_id)
    10. Queue to Thunder (same as fast path)
    11. Return candidate + metadata
    """
```

#### Recruiter Workload Round-Robin

```python
def _assign_recruiter_by_workload(
    db: Session,
    tenant_id: int,
    bu_id: str,
    exclude_user_ids: Optional[List[str]] = None,
) -> Users:
    """
    Select least-loaded recruiter for BU using round-robin by candidate count.
    
    Args:
        db: Database session
        tenant_id: Tenant ID (for multi-tenant scoping)
        bu_id: Business Unit ID (for BU-scoped assignment)
        exclude_user_ids: List of user IDs to skip (e.g., inactive recruiters)
    
    Returns:
        Users object of selected recruiter
    
    Raises:
        NoAvailableRecruitersError: No active recruiters found in BU
    
    Metrics Used:
        - candidate_count: Number of candidates assigned to recruiter
        - pipeline_count: Number of pipeline items in PENDING/CONNECTED/PHONE_COLLECTED
        - total_load: candidate_count + (pipeline_count * 0.5)
        
    Logic:
        1. Get all recruiters in BU with roles: Recruiter, HR Manager
        2. Filter: active only, not in exclude_user_ids
        3. Get workload metrics for each recruiter
        4. Select recruiter with minimum total_load
        5. Break ties: prefer recruiter with earlier last_assignment_date
        6. Return selected recruiter
    
    Implementation:
        - Use linkedin_recruiter_workload_service.get_all_recruiter_workloads()
        - Apply BU filter (bu_id)
        - Apply tenant filter (tenant_id)
        - Sort by total_load ascending
        - Return first (least loaded)
    """
```

### `linkedin_recruiter_workload_service.py`

```python
def get_recruiter_candidate_count(
    db: Session,
    recruiter_id: str,
    bu_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> int:
    """
    Count candidates assigned to recruiter.
    
    Query: 
        SELECT COUNT(*) FROM candidates 
        WHERE assigned_recruiter_id = recruiter_id
        AND (bu_id = bu_id if provided)
        AND (tenant_id = tenant_id if provided)
        AND candidateStatus IN ('PROSPECT', 'QUALIFIED', 'SCREENING', 'INTERVIEW')
    """

def get_recruiter_pipeline_count(
    db: Session,
    recruiter_id: str,
    tenant_id: Optional[int] = None,
) -> int:
    """
    Count pipeline items in manual review assigned to recruiter.
    
    Query:
        SELECT COUNT(*) FROM linkedin_candidate_pipeline
        WHERE assigned_to_user_id = recruiter_id
        AND status IN ('PENDING_CONNECTION', 'CONNECTED', 'PHONE_COLLECTED')
        AND (tenant_id = tenant_id if provided)
    """

def get_least_loaded_recruiter(
    db: Session,
    bu_id: str,
    tenant_id: int,
) -> Users:
    """
    Return single recruiter with minimum workload in BU.
    Metric: candidate_count + (pipeline_count * 0.5)
    """
```

---

## 4. Integration Points

### Queue Integration

**Task Name:** `contact_with_candidate_thunder`  
**Queue Type:** THUNDER_QUEUE  
**Payload:**
```python
{
    'candidate_id': str,  # UUID of Candidate
    'source': 'linkedin_fast' | 'linkedin_slow',
    'import_path': 'fast' | 'slow',
    'sัm_trace_id': str,  # For end-to-end tracing
    'created_at': timestamp,
    'email': str,  # Discovered or collected email
    'phone': str,  # Discovered or collected phone
}
```

**Handler:** Thunder autonomous loop picks up this queue task and:
1. Fetches Candidate by ID
2. Creates initial CandidateConversation
3. Starts outreach via WhatsApp (phone) or Email
4. Records SLM metrics:
   - `linkedin_import_to_first_contact_seconds`
   - `outreach_channel_used`
   - `response_received_within_minutes`

### SLM Integration (Must-Have)

Every LinkedIn conversion operation logs to SLM service:

**Fast Path Logging:**
```
linkedin_fast_path_started: {
    candidate_id, 
    email_available, 
    phone_available,
    apollo_enrichment_time_ms
}
linkedin_fast_path_completed: {
    candidate_id,
    status (success|gate_rejected|duplicate|error),
    reason,
    queued_to_thunder_at
}
```

**Slow Path Logging:**
```
linkedin_slow_path_assigned: {
    pipeline_item_id,
    recruiter_id,
    recruiter_workload_count,
    bu_id
}
linkedin_slow_path_import: {
    pipeline_item_id,
    candidate_id,
    time_in_pipeline_hours,
    phone_source (recruiter|email_message)
}
```

**Recruiter Workload Logging:**
```
recruiter_assignment_metrics: {
    recruiter_id,
    candidate_count,
    pipeline_count,
    total_load,
    bu_id,
    timestamp
}
```

### Task System Integration

**Task Creation (Slow Path):**
```python
task = task_service.create_task(
    db,
    title=f"Review LinkedIn candidate: {linkedin_profile_slug}",
    description=f"Collect phone or email from: {linkedin_url}\nNotes: {notes}",
    priority="MEDIUM",
    assigned_to_user_id=recruiter_id,
    created_by_user_id=current_user_id,
    due_date=datetime.utcnow() + timedelta(days=2),
    task_type="GENERAL",
    department_id=recruiter_dept_id,  # Recruitment department
    visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT",
)
# Store task.id in pipeline_item for later reference
```

**Task Completion (Slow Path → Candidate):**
```python
# When recruiter imports pipeline item to candidate:
task_service.update_task_status(db, task.id, "COMPLETED")
```

### Thunder Autonomous Loop Integration

**Monitor for LinkedIn-to-Thunder Conversions:**
```python
# In thunder_autonomous_loop.py:

# Get candidates queued via LinkedIn conversion
linkedin_queue_messages = db.query(ChannelQueueItem).filter(
    ChannelQueueItem.type == "contact_with_candidate_thunder",
    ChannelQueueItem.status == "PENDING"
).limit(10).all()

for msg in linkedin_queue_messages:
    candidate_id = msg.payload['candidate_id']
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    
    if not candidate:
        msg.status = "FAILED"
        continue
    
    # Start conversation (WhatsApp if phone, Email if only email)
    preferred_channel = "whatsapp" if candidate.candidateMobileNumber else "email"
    
    # Log SLM metrics
    sلm_log({
        'event': 'linkedin_first_contact_initiated',
        'candidate_id': candidate_id,
        'channel': preferred_channel,
        'import_path': msg.payload['import_path'],
        'time_from_import_seconds': (now - msg.created_at).total_seconds()
    })
    
    # Create conversation
    conversation = start_outreach_sequence(db, candidate)
    msg.status = "COMPLETED"
```

---

## 5. Error Handling & Failure Scenarios

### Retryable Errors

| Error | Scenario | Retry Strategy | Max Retries |
|-------|----------|-----------------|-------------|
| Apollo MCP timeout | Network issue | Exponential backoff | 3 |
| Duplicate key violation | Race condition (two imports same URL) | Fetch existing + return it | N/A |
| Recruiter unavailable | All recruiters at capacity | Wait 60s, retry | 5 |
| Queue write failure | Database transient error | Retry with new transaction | 3 |

### Non-Retryable Errors

| Error | Scenario | Handling |
|-------|----------|----------|
| Invalid LinkedIn URL | User input bad | Return 400, user fixes input |
| Candidate not open to work | Apollo indicates low intent | Return 403, skip (expected) |
| Apollo MCP not configured | Missing OAuth setup | Return 500, escalate to admin |
| Missing phone (slow path) | Recruiter forgot to collect | Return 400, ask recruiter to collect |

### Cascade Failures to Prevent

**Scenario 1:** All recruiters in BU are at capacity  
**Risk:** Candidates assigned then abandoned  
**Mitigation:**
- Check available recruiters BEFORE creating pipeline item
- If none available, reject slow path request (400)
- Return: "No recruiters available, try auto-import or wait 24h"

**Scenario 2:** Task assignment succeeds but candidate creation fails  
**Risk:** Recruiter has task but candidate created elsewhere  
**Mitigation:**
- Import pipeline item: check if candidate already exists
- If yes, skip creation, link pipeline to existing candidate
- Mark task as COMPLETED (no duplication)

**Scenario 3:** Duplicate candidates race condition  
**Risk:** Two imports of same LinkedIn URL create two candidates  
**Mitigation:**
- Use unique constraint on (linkedin_url)
- On violation, fetch existing + return it
- Atomic operation: check duplicate → create in single transaction

---

## 6. Testing Strategy

### Unit Tests (Test Helpers First)

**File:** `backend/tests/test_linkedin_conversion_service.py`

```python
# Test 1: Fast Path - Email & Phone Available
test_fast_path_with_email_and_phone():
    # Setup: Apollo mock returns email + phone + open_to_work=true
    # Action: Call convert_linkedin_to_candidate_auto()
    # Assert:
    #   - Candidate created
    #   - Email & phone stored
    #   - Queued to Thunder
    #   - SLM logged with "fast" path

# Test 2: Fast Path - Duplicate Detection
test_fast_path_duplicate_email():
    # Setup: Candidate with email already exists
    # Action: Call convert_linkedin_to_candidate_auto() with same email
    # Assert:
    #   - DuplicateCandidateExists raised
    #   - Returns existing candidate ID

# Test 3: Fast Path - Gate Rejection (Not Open to Work)
test_fast_path_gate_rejected_not_open_to_work():
    # Setup: Apollo returns open_to_work=false
    # Action: Call convert_linkedin_to_candidate_auto()
    # Assert:
    #   - CandidateNotOpenToWork raised
    #   - Candidate NOT created
    #   - No queue entry

# Test 4: Slow Path - Assign to Least-Loaded Recruiter
test_slow_path_round_robin_assignment():
    # Setup: 3 recruiters with loads [5, 3, 7]
    # Action: Call convert_linkedin_to_candidate_manual()
    # Assert:
    #   - Assigned to recruiter_2 (load=3)
    #   - Task created with title containing profile slug
    #   - Pipeline item created
    #   - SLM logged assignment metrics

# Test 5: Slow Path Transition - Import to Candidate
test_slow_path_import_pipeline_to_candidate():
    # Setup: Pipeline item in PENDING_CONNECTION, phone number from recruiter
    # Action: Call import_pipeline_candidate_to_thunder()
    # Assert:
    #   - Candidate created with phone from pipeline
    #   - Pipeline status → IMPORTED_TO_THUNDER
    #   - Task marked COMPLETED
    #   - Queued to Thunder
    #   - SLM logged completion

# Test 6: Recruiter Workload Calculation
test_recruiter_workload_includes_candidates_and_pipeline():
    # Setup: Recruiter_A has [5 candidates, 2 pipeline items]
    # Action: Call get_all_recruiter_workloads()
    # Assert:
    #   - Recruiter_A.total_load = 5 + (2 * 0.5) = 6
    #   - Pipeline items weighted at 50% to avoid over-loading

# Test 7: API Fast Path Endpoint
test_post_linkedin_convert_auto_success():
    # Setup: Valid LinkedIn URL, Apollo mock ready
    # Action: POST /linkedin/convert/auto {linkedin_url: "..."}
    # Assert:
    #   - Status 200
    #   - Response has candidate_id, email, phone
    #   - SLM trace_id included for correlation

# Test 8: API Slow Path Endpoint
test_post_linkedin_convert_manual_success():
    # Setup: Valid LinkedIn URL, recruiters available
    # Action: POST /linkedin/convert/manual {linkedin_url: "..."}
    # Assert:
    #   - Status 200
    #   - Response has task_id, pipeline_item_id, recruiter name
    #   - Task created and assigned

# Test 9: API Import Endpoint
test_post_linkedin_import_pipeline_item():
    # Setup: Pipeline item in PENDING, phone provided
    # Action: PATCH /linkedin/pipeline/{id}/import {phone: "..."}
    # Assert:
    #   - Status 200
    #   - Candidate created
    #   - Pipeline status updated
    #   - Response has candidate_id

# Test 10: Race Condition - Duplicate During Slow Path
test_slow_path_duplicate_during_assignment():
    # Setup: Pipeline item created, then candidate created from another source with same email
    # Action: Call import_pipeline_candidate_to_thunder()
    # Assert:
    #   - Detects duplicate
    #   - Links pipeline to existing candidate
    #   - Still marks task COMPLETED
    #   - No double-queue to Thunder
```

### Integration Tests (End-to-End)

**File:** `backend/tests/test_linkedin_conversion_end_to_end.py`

```python
# Test 1: Fast Path End-to-End (URL → Candidate → Thunder Queue)
test_e2e_fast_path():
    # Create candidate via fast path
    # Assert in database
    # Assert in Thunder queue
    # Assert SLM logged
    # Assert can be picked up by Thunder autonomous loop

# Test 2: Slow Path End-to-End (URL → Task → Import → Thunder Queue)
test_e2e_slow_path():
    # Create pipeline item
    # Verify task assigned to recruiter
    # Update pipeline with phone
    # Import to candidate
    # Assert candidate in database
    # Assert in Thunder queue

# Test 3: Recruiter Workload Over Time
test_e2e_recruiter_workload_accumulation():
    # Assign 5 candidates to recruiter_A via slow path
    # Assign 3 candidates to recruiter_B via slow path
    # Next assignment should go to recruiter_B (less loaded)
    # Verify round-robin logic works over multiple assignments
```

### Manual Testing Scenarios

**Scenario 1: Fast Path with Apollo Mock**
```
1. POST /linkedin/convert/auto
2. Payload: {linkedin_url: "https://linkedin.com/in/prabhu-..."}
3. Apollo returns: {email: "prabhu@...", phone: "+1-..."}
4. Expected: Candidate created, queued to Thunder
5. Verify: Candidate visible in database, Thunder can pick it up
```

**Scenario 2: Slow Path with Recruiter Assignment**
```
1. POST /linkedin/convert/manual
2. Payload: {linkedin_url: "..."}
3. Expected: Task created, assigned to recruiter
4. Login as recruiter, see task in dashboard
5. PATCH /linkedin/pipeline/{id}/phone {phone: "+1-..."}
6. POST /linkedin/import/{id}
7. Verify: Candidate created, in Thunder queue
```

**Scenario 3: Recruiter Workload Metrics**
```
1. GET /linkedin/workload?bu_id=...
2. Expected: JSON array showing each recruiter's load
3. Create 10 slow path assignments
4. Verify: Assignments distributed round-robin
5. Verify: Workload metrics update in real-time
```

---

## 7. Implementation Priority & Phasing

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create linkedin_conversion_service.py (fast path only)
- [ ] Create linkedin_recruiter_workload_service.py
- [ ] Update linkedin_import_service.py (refactor for reuse)
- [ ] Create API endpoint: POST /linkedin/convert/auto
- [ ] Write unit tests for fast path
- [ ] Integrate with Thunder queue
- [ ] Status: Fast path working end-to-end

### Phase 2: Manual Collection Path (Week 2)
- [ ] Add fields to LinkedInCandidatePipeline model
- [ ] Create slow path service: convert_linkedin_to_candidate_manual()
- [ ] Create recruiter assignment logic in linkedin_conversion_service
- [ ] Create API endpoints:
  - POST /linkedin/convert/manual
  - PATCH /linkedin/pipeline/{id}/phone
  - POST /linkedin/pipeline/{id}/import
- [ ] Create task assignment
- [ ] Write unit tests for slow path
- [ ] Status: Both paths working, manual collection tested

### Phase 3: Recruiter Dashboard & Monitoring (Week 3)
- [ ] Create API endpoint: GET /linkedin/workload
- [ ] Add SLM logging throughout
- [ ] Create recruiter dashboard UI (show assigned tasks, workload)
- [ ] Add monitoring/alerting for assignment failures
- [ ] Performance optimization (index on BU, status)
- [ ] Status: Full visibility into recruiter assignments and workload

### Phase 4: Thunder Integration & Testing (Week 4)
- [ ] Integrate with Thunder autonomous loop
- [ ] Log SLM metrics (import-to-contact timing)
- [ ] End-to-end testing (both paths → Thunder)
- [ ] Production readiness checklist
- [ ] Status: Production-ready, both paths working

---

## 8. Risk Assessment & Mitigation

### Risk 1: Recruiter Assignment Imbalance
**Scenario:** All candidates assigned to one recruiter while others idle  
**Root Cause:** Workload metrics not recalculated in real-time  
**Probability:** Medium  
**Impact:** High (bottleneck in slow path)  
**Mitigation:**
- Recalculate workload before EVERY assignment (not cached)
- Monitor workload metrics via SLM
- Alert if any recruiter > 2x average load
- Manual rebalance option in admin UI

### Risk 2: Apollo MCP Failures
**Scenario:** Apollo MCP down or quota exceeded → all fast path imports fail  
**Root Cause:** External dependency, no fallback  
**Probability:** Low  
**Impact:** Medium (can switch to slow path)  
**Mitigation:**
- Graceful degradation: if Apollo fails, offer slow path option
- Clear error message: "Apollo is temporarily unavailable, use manual collection"
- Retry with exponential backoff
- Monitor Apollo response times via SLM

### Risk 3: Duplicate Candidate Race Condition
**Scenario:** Two users import same LinkedIn URL simultaneously  
**Root Cause:** Check-then-insert window  
**Probability:** Low  
**Impact:** High (data duplication)  
**Mitigation:**
- Unique constraint on (linkedin_url) at database level
- On constraint violation, fetch existing and return it
- Wrap in transaction: check + insert atomic
- Unit test explicitly for race condition

### Risk 4: Missing Phone Number in Slow Path
**Scenario:** Recruiter never collects phone → cannot import to Thunder  
**Root Cause:** Task completed but phone not collected  
**Probability:** Medium  
**Impact:** Medium (candidate stuck in pipeline)  
**Mitigation:**
- Validation in import endpoint: require phone OR email
- If missing, return 400 with clear message
- Task SLA: auto-escalate if not completed in 3 days
- Admin report: show overdue pipeline items

### Risk 5: Cascade Failure - All Recruiters at Capacity
**Scenario:** No recruiters available for assignment → slow path request rejected  
**Root Cause:** Business growth outpacing recruiter hiring  
**Probability:** Low-Medium  
**Impact:** High (candidates rejected)  
**Mitigation:**
- Check recruiter availability BEFORE creating pipeline item
- Return clear error: "No recruiters available, try auto-import"
- Admin alert: notify when capacity < 20%
- Load-balancing: distribute across BUs if needed

### Risk 6: SLM Logging Cascades
**Scenario:** SLM logging fails → blocks candidate import  
**Root Cause:** SLM service down, tight coupling  
**Probability:** Low  
**Impact:** Critical (feature completely broken)  
**Mitigation:**
- SLM logging is async, non-blocking
- Failures logged but don't block import
- Retry SLM logging asynchronously
- Circuit breaker: if SLM fails > 5 times, log warning and continue

---

## 9. Answering Key Architectural Questions

### Q1: Where is task system?
**A:** `backend/app/models/task.py` and `backend/app/services/task_service.py`
- Task model: org-wide task ID (autoincrement), assigned_to_user_id, status, priority
- Service: create_task(), update_task_status(), get_task_by_id()
- Used for: recruiter assignments in slow path

### Q2: Where do we persist email/phone from Apollo enrichment?
**A:** Two locations:
1. **Direct to Candidate** (fast path): email/phone stored in Candidate.candidateEmail, Candidate.candidateMobileNumber
2. **To Pipeline Item** (slow path): phone_number stored in LinkedInCandidatePipeline.phone_number
3. **From LinkedIn Message** (slow path): email_from_recruiter stored in LinkedInCandidatePipeline.email_from_recruiter

### Q3: How do we trigger Thunder autonomous conversion?
**A:** Queue message with task_name="contact_with_candidate_thunder"
- Queue type: THUNDER_QUEUE
- Payload: {candidate_id, source, import_path, sلm_trace_id}
- Thunder autonomous loop monitors this queue
- Creates initial conversation for candidate

### Q4: What workload metrics matter for round-robin?
**A:** Candidate-centric, not job-centric:
- **Primary:** candidate_count (active candidates assigned)
- **Secondary:** pipeline_count (LinkedIn pipeline items)
- **Weighted:** total_load = candidate_count + (pipeline_count * 0.5)
- **Why 0.5 weight:** Pipeline items require LESS effort than candidates

### Q5: Can we safely assign candidates without role checks?
**A:** YES, with caveats:
- Assign only to users with Recruiter or HR Manager role
- Filter by active users
- Respect BU scoping (assign within BU only)
- Require LINKEDIN_CONVERSION_MANUAL permission on endpoint
- Admin override available if needed

### Q6: What happens if no recruiters available in BU?
**A:** Fail fast:
- Check recruiter availability BEFORE creating pipeline item
- Return 400 with message: "No recruiters available"
- Options: auto-import, wait, escalate to BU manager
- SLM alert: capacity below threshold

### Q7: Are tasks the pipeline tracking mechanism?
**A:** NO - two separate mechanisms:
- **Tasks:** Assigned to recruiter, tracks status (NEW → IN_PROGRESS → COMPLETED)
- **Pipeline:** Tracks phone collection status (PENDING_CONNECTION → CONNECTED → PHONE_COLLECTED → IMPORTED_TO_THUNDER)
- **Link:** Task.id stored in LinkedInCandidatePipeline.task_id for reference
- **Lifecycle:** When pipeline → candidate, task marked COMPLETED

---

## 10. Configuration & Deployment Checklist

### Backend Configuration (environment variables)

```
LINKEDIN_CONVERSION_ENABLED=true
LINKEDIN_AUTO_IMPORT_ENABLED=true
LINKEDIN_MANUAL_IMPORT_ENABLED=true
LINKEDIN_RECRUIT ER_ASSIGNMENT_STRATEGY=round_robin_by_candidate_count
LINKEDIN_RECRUITER_ASSIGNMENT_WEIGHT_PIPELINE=0.5
LINKEDIN_MAX_MANUAL_PIPELINE_PER_RECRUITER=20
LINKEDIN_PHONE_REQUIRED_FOR_IMPORT=false  # Allow email-only
LINKEDIN_AUTO_IMPORT_OPEN_TO_WORK_GATE=true
```

### Database Migrations

```sql
-- Add fields to linkedin_candidate_pipeline
ALTER TABLE linkedin_candidate_pipeline ADD COLUMN email_collected_at TIMESTAMP NULL;
ALTER TABLE linkedin_candidate_pipeline ADD COLUMN email_from_recruiter VARCHAR(255) NULL;
ALTER TABLE linkedin_candidate_pipeline ADD COLUMN phone_verified_by VARCHAR(255) NULL;
ALTER TABLE linkedin_candidate_pipeline ADD COLUMN task_id INTEGER NULL REFERENCES tasks(id);

-- Index for recruiter workload queries
CREATE INDEX idx_linkedin_pipeline_recruiter_status 
  ON linkedin_candidate_pipeline(assigned_to_user_id, status);

-- Add fields to candidate model
ALTER TABLE candidates ADD COLUMN linkedin_import_path VARCHAR(10) NULL;
ALTER TABLE candidates ADD COLUMN source_linkedin_imported_at TIMESTAMP NULL;
ALTER TABLE candidates ADD COLUMN linkedin_queue_item_id UUID NULL;
```

### Monitoring & Alerts

**SLM Metrics to Track:**
- linkedin_fast_path_success_rate (target: > 95%)
- linkedin_slow_path_time_to_import (target: < 24 hours)
- recruiter_assignment_imbalance (alert if > 2x standard deviation)
- linkedin_import_to_first_contact_seconds (target: < 3600)

**Critical Alerts:**
- Apollo MCP failures (fast path blocked)
- No recruiters available (slow path blocked)
- Task assignment failures
- Queue write failures

---

## Conclusion

This architecture provides:
1. **Two execution paths** for different contact info scenarios
2. **Auto-assignment logic** with real-time workload balancing
3. **Clear data flow** from LinkedIn → Candidate → Thunder
4. **Complete error handling** for edge cases
5. **SLM integration** for observability
6. **Backward compatibility** with existing systems
7. **Production readiness** with testing strategy

Implementation follows standard patterns already in the codebase (task creation, queue messaging, role-based auth) and extends them for LinkedIn-specific requirements.

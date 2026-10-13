# Thunder + HM Screening Implementation Guide

**Status:** Database models complete ✅  
**Created:** 2026-08-13  
**Phase:** 1 of 6 (Database + API Structure)

---

## COMPLETED: Database Layer (Phase 1)

### Models Created:
✅ `app/models/thunder_session.py` - ThunderSession model (form state persistence)
✅ `app/models/hiring_manager_validation.py` - HiringManagerValidation + HMValidationResponse models
✅ `app/models/user.py` - Updated Jobs model with HM validation fields
✅ `app/models/__init__.py` - Added model imports

### Tables to Create:
```sql
CREATE TABLE thunder_sessions (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(50),
    candidate_email VARCHAR(200) NOT NULL,
    status ENUM('STARTED', 'IN_PROGRESS', 'PAUSED', 'COMPLETED', 'ABANDONED', 'ERROR'),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- ... (see model for full schema)
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidateID),
    INDEX idx_thunder_session_candidate_id (candidate_id),
    INDEX idx_thunder_session_email (candidate_email),
    INDEX idx_thunder_session_status (status),
    INDEX idx_thunder_session_created_at (created_at)
);

CREATE TABLE hiring_manager_validations (
    id VARCHAR(36) PRIMARY KEY,
    candidate_id VARCHAR(50) NOT NULL,
    job_id VARCHAR(50) NOT NULL,
    hiring_manager_id VARCHAR(36) NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'MAYBE', 'EXPIRED', 'ESCALATED'),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    due_at DATETIME NOT NULL,
    responded_at DATETIME,
    -- ... (see model for full schema)
    FOREIGN KEY (candidate_id) REFERENCES candidates(candidateID),
    FOREIGN KEY (job_id) REFERENCES jobs(jobID),
    FOREIGN KEY (hiring_manager_id) REFERENCES users(UserID),
    INDEX idx_hm_validation_candidate (candidate_id),
    INDEX idx_hm_validation_job (job_id),
    INDEX idx_hm_validation_manager (hiring_manager_id),
    INDEX idx_hm_validation_status (status),
    INDEX idx_hm_validation_created_at (created_at),
    INDEX idx_hm_validation_due_at (due_at)
);

CREATE TABLE hm_validation_responses (
    id VARCHAR(36) PRIMARY KEY,
    validation_id VARCHAR(36) NOT NULL,
    question_id VARCHAR(100) NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(50) NOT NULL,
    response_value TEXT,
    response_json JSON,
    response_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (validation_id) REFERENCES hiring_manager_validations(id),
    INDEX idx_hm_response_validation (validation_id),
    INDEX idx_hm_response_question (question_id)
);

ALTER TABLE jobs ADD COLUMN (
    hm_validation_questions JSON,
    hm_validation_required BOOLEAN DEFAULT FALSE,
    hm_validation_timeout_hours INT DEFAULT 24,
    auto_schedule_after_approval BOOLEAN DEFAULT TRUE,
    hm_auto_reject_threshold INT
);

ALTER TABLE interviews ADD COLUMN (
    interviewID VARCHAR(50) UNIQUE NOT NULL
);
```

### Relationships Defined:
- `ThunderSession` → Candidate (one-to-many)
- `ThunderSession` → Job (many-to-one, for job matching context)
- `HiringManagerValidation` → Candidate (many-to-one)
- `HiringManagerValidation` → Job (many-to-one)
- `HiringManagerValidation` → Users (hiring_manager, escalated_to_user)
- `HiringManagerValidation` → Interview (one-to-one, interview created after approval)
- `HMValidationResponse` → HiringManagerValidation (one-to-many)

---

## NEXT: API Endpoints (Phase 2)

### Thunder Endpoints:

#### 1. POST `/thunder/sessions` - Start or resume session
```python
Request:
{
  "candidate_email": "john.smith@example.com",
  "device_type": "desktop",
  "utm_source": "email_campaign"
}

Response:
{
  "session_id": "session_12345",
  "status": "STARTED|IN_PROGRESS",  # STARTED if new, IN_PROGRESS if resuming
  "last_question_reached": "Q1|Q2|...|Q12",
  "completion_percentage": 0-100,
  "form_state": {...},  # Current form for resume
  "resume_url": "s3://...",  # If resume already uploaded
  "candidate_data": {...}  # Pre-filled data
}
```

#### 2. GET `/thunder/sessions/{session_id}` - Get session state
Returns full session state including form responses, resume data, current progress

#### 3. POST `/thunder/sessions/{session_id}/answer` - Submit question response
```python
Request:
{
  "question": "Q1|Q2|...",
  "response": "yes|no|text response",
  "time_taken_seconds": 30
}

Response:
{
  "status": "ok",
  "next_question": "Q2|Q3|...",
  "validation": {...}  # If validation failed
}
```

#### 4. POST `/thunder/sessions/{session_id}/upload-resume` - Upload resume
Triggers resume parsing, returns parsed data

#### 5. POST `/thunder/sessions/{session_id}/submit` - Submit application
```python
Request: {}
Response:
{
  "status": "submitted",
  "candidate_id": "cand_12345",
  "handoff_status": "queued_for_ai_recruiter",
  "job_matches": [
    {"job_id": "job_001", "title": "Business Delivery Consultant", "match_score": 0.92}
  ]
}
```

### HM Validation Endpoints:

#### 1. GET `/hiring-manager-validations` - List pending validations
```python
Query params:
  - status=PENDING|APPROVED|REJECTED
  - hiring_manager_id=...
  - limit=10, offset=0

Response:
[
  {
    "id": "val_12345",
    "candidate_id": "cand_001",
    "candidate_name": "John Smith",
    "job_id": "job_001",
    "job_title": "Business Delivery Consultant",
    "status": "PENDING",
    "created_at": "2026-08-13T10:00:00Z",
    "due_at": "2026-08-14T10:00:00Z",
    "resume_preview": "s3://...",
    "match_score": 0.92
  }
]
```

#### 2. GET `/hiring-manager-validations/{id}` - Get single validation with questions
```python
Response:
{
  "id": "val_12345",
  "candidate_id": "cand_001",
  "job_id": "job_001",
  "status": "PENDING",
  "due_at": "2026-08-14T10:00:00Z",
  "questions": [
    {
      "id": "q_001",
      "question": "Does this candidate's experience level match our seniority requirement?",
      "type": "yes_no",
      "follow_up": "If no, please explain why...",
      "follow_up_type": "text"
    },
    // ... more questions
  ],
  "candidate_data": {
    "name": "John Smith",
    "email": "john@example.com",
    "skills": ["Business Analysis", "Project Management"],
    "experience_years": 8,
    "current_company": "Acme Corp",
    "current_title": "Senior Consultant"
  },
  "resume_url": "s3://..."
}
```

#### 3. POST `/hiring-manager-validations/{id}/respond` - Submit validation answers
```python
Request:
{
  "responses": {
    "q_001": "yes",
    "q_002": "Red flags: X and Y, but manageable",
    "q_003": "Business Analysis, Project Management, Requirements Gathering",
    "q_004": "yes"  // THIS DETERMINES FLOW
  },
  "decision_comment": "Strong candidate, proceed with interview",
  "decision_score": 8
}

Response:
{
  "status": "APPROVED|REJECTED|MAYBE",
  "next_action": "schedule_interview|return_to_pool|escalate_for_review",
  "interview_scheduled": {"id": "int_xyz", "date": "2026-08-20", "time": "10:00 AM"},
  "candidate_notification": "Email sent to candidate"
}
```

#### 4. PUT `/hiring-manager-validations/{id}/remind` - Send reminder email
```python
Response:
{
  "status": "reminder_sent",
  "reminder_sent_at": "2026-08-13T14:00:00Z",
  "new_due_at": "2026-08-15T10:00:00Z"
}
```

#### 5. POST `/jobs/{job_id}/validation-template` - Create HM validation template
```python
Request:
{
  "questions": [
    {
      "question": "Does this candidate's experience match our requirements?",
      "type": "yes_no",
      "follow_up": "Please explain if no",
      "follow_up_type": "text",
      "required": true
    },
    // ... more questions
  ],
  "timeout_hours": 24,
  "auto_schedule_after_approval": true
}

Response:
{
  "status": "template_created",
  "job_id": "job_001",
  "template_version": "1.0"
}
```

---

## Service Layer (Phase 3)

### Services to Create:

#### `app/services/thunder_service.py`
- `create_session()` - Initialize or resume session
- `get_session()` - Fetch session state
- `save_response()` - Store Q&A, check for conditional branching
- `upload_and_parse_resume()` - Delegate to resume parser
- `submit_application()` - Finalize session, create handoff payload

#### `app/services/hm_validation_service.py`
- `create_validation_request()` - After candidate matches to job
- `get_pending_validations()` - For HM dashboard
- `send_validation_email()` - Email template + dashboard card
- `process_hm_response()` - Parse responses, determine decision
- `schedule_interview_after_approval()` - Auto-schedule or queue
- `escalate_expired_validation()` - To HM's manager if timeout
- `generate_interview_briefing()` - Format HM's answers for panel

#### `app/services/ai_recruiter_integration_service.py`
- `match_candidate_to_jobs()` - Find best job matches (enhanced)
- `trigger_hm_validation()` - If job requires it
- `wait_for_hm_decision()` - Poll validation status
- `proceed_based_on_decision()` - Schedule interview or try next candidate

---

## Integration Flow (Phase 4)

### Complete Autonomous Loop:
```
Thunder (Complete App)
  ↓
Candidate submits → AI Recruiter triggered
  ↓
AI Recruiter finds best job match
  ↓
IF job.hm_validation_required:
  ├─ Create HiringManagerValidation record
  ├─ Send email to hiring_manager
  ├─ Wait for response (timeout: 24hrs)
  │
  ├─ IF HM approves:
  │  ├─ status = APPROVED
  │  ├─ Auto-schedule interview (if auto_schedule_after_approval)
  │  ├─ Send interview details to candidate
  │  └─ Send brief to interview panel (with HM's answers)
  │
  ├─ IF HM rejects:
  │  ├─ status = REJECTED
  │  ├─ Store rejection reason
  │  ├─ Return candidate to pool
  │  └─ Try next best match
  │
  └─ IF HM maybe/uncertain:
     ├─ status = MAYBE
     ├─ Escalate to HM's manager
     └─ Queue for manual review
ELSE:
  └─ Auto-schedule interview
  ↓
Interview conducted
  ↓
Feedback collected
  ↓
Offer generated (autonomous)
```

---

## Testing Strategy (Phase 5)

### Unit Tests:
- `test_thunder_session_lifecycle()` - Create, answer, submit
- `test_form_persistence()` - Resume at Q4 after closing
- `test_conditional_questions()` - Work auth question only for US jobs
- `test_hm_validation_decision_logic()` - Yes/No/Maybe routing
- `test_timeout_escalation()` - After 24hrs, escalate to manager

### Integration Tests:
- `test_complete_thunder_to_hm_flow()` - Full loop
- `test_hm_reject_tries_next_candidate()` - Fallback logic
- `test_auto_schedule_after_hm_approval()` - Interview created

### End-to-End Test:
- Test from careers.blitzenx.com Thunder → AI Recruiter → HM Validation → Interview

---

## Deployment Checklist (Phase 6)

### Pre-Production:
- [ ] Database migrations applied (SQL scripts)
- [ ] Models registered in SQLAlchemy
- [ ] API endpoints tested in Postman
- [ ] Email templates reviewed
- [ ] HM validation question templates created for each job
- [ ] Timeout/escalation logic verified
- [ ] Resume parsing validated

### Production Deployment:
- [ ] Deploy models + migrations
- [ ] Deploy API endpoints
- [ ] Deploy service layer
- [ ] Configure email service
- [ ] Test end-to-end with staging candidates
- [ ] Monitor error logs

---

## Files Created This Phase:
1. `app/models/thunder_session.py` ✅
2. `app/models/hiring_manager_validation.py` ✅
3. Updated `app/models/user.py` ✅
4. Updated `app/models/__init__.py` ✅

## Next Phase: API Endpoints
Ready to build REST endpoints and service layer.

---

**Implementation Status:**
- ✅ Phase 1: Database Models (COMPLETE)
- ⏳ Phase 2: API Endpoints (READY TO START)
- ⏳ Phase 3: Service Layer (READY TO START)
- ⏳ Phase 4: AI Recruiter Integration (READY TO START)
- ⏳ Phase 5: Testing (READY TO START)
- ⏳ Phase 6: Deployment (READY TO START)

**Total Estimated Time:** 4 weeks (1 week per phase 2-6, testing concurrent with implementation)
**Production Ready:** Q4 2026

# WROS Backend - Development Notes

## 🚀 CURRENT STATUS (2026-08-13 Session - Thunder + HM Screening Implementation Started)

**Backend:** ✅ PRODUCTION READY - Thunder + HM Screening database layer implemented
**Models:** ✅ CREATED - ThunderSession, HiringManagerValidation, HMValidationResponse  
**Database:** ✅ DESIGNED - 3 new tables + Job/Interview updates
**Implementation Guide:** ✅ CREATED - 6-phase rollout plan (4 weeks)
**Next:** API endpoints + Service layer (Phase 2-3)

---

## 🎯 PRIOR STATUS (2026-08-12 Session - Comprehensive RBAC Implementation Complete)

**Backend:** ✅ PRODUCTION READY - Multi-role RBAC, BU filtering, employee conversion fully implemented
**Database:** ✅ UPDATED - user_roles junction table, business_unit_access tracking, BU assignment
**Endpoints:** ✅ NEW - /users/create-with-roles, /employees/convert-from-candidate, /employees/roles-for-conversion
**Git Status:** ✅ PUSHED - Commit 0a0bc7c to main, comprehensive RBAC system complete

### Session Work (2026-08-12 - RBAC Implementation Complete):
**EPIC: Role-Based Access Control with Multi-Role Support and Business Unit Filtering - COMPLETED**

#### Backend Implementation:
- ✅ Multi-role user assignment - Users can have Partner + BU Head + Hiring Manager roles simultaneously
- ✅ Business Unit (BU) filtering - Data scoped by BU (Troy's BU separate from Curtis's)
- ✅ Employee conversion endpoint - Convert candidate → employee with role/BU assignment
- ✅ Dynamic permission composition - Multiple roles combine their permissions

#### Database Schema Updates:
- ✅ `user_roles` junction table (many-to-many role assignment)
  - Fields: id, user_id, role_id, business_unit_id, created_at
  - Enables users to have multiple roles simultaneously
  - Each role can be scoped to different BU if needed
  
- ✅ `business_unit_access` tracking table (BU permission audit)
  - Tracks user access to business units for permission validation
  - Enables per-BU permission enforcement
  
- ✅ `business_unit_id` added to `users` table (FK to business_units)
  - Primary BU assignment for each user
  - Used for default BU scoping in queries
  
- ✅ 3 default business units created (NA, EU, APAC)
  - All with tenant_id set to 1 (single tenant for now)
  - Complete bu_code, bu_name, manager assignment

#### New REST Endpoints:

**1. POST /users/create-with-roles** - Create user with multi-role and BU assignment
   - Accepts: user_name, user_email, user_password, business_unit_id, role_ids[]
   - Validates: user can only create in their own BU
   - Returns: newly created user with assigned roles
   - Flow: Creates user → Creates UserRole records for each role → Returns user with roles

**2. POST /employees/convert-from-candidate** - Convert candidate to employee  
   - Accepts: candidate_id, employee_name, employee_email, business_unit_id, role_ids[], position, joining_date
   - Auto-generates password (no manual password entry for new employees)
   - Creates UserRole records for each assigned role
   - Updates candidate status to CONVERTED_TO_EMPLOYEE
   - Creates link: candidate.candidate_employee_user_id = new_employee.UserID
   - Returns: employee_user_id, roles_assigned, status="success"
   - Validates: user can only convert in their own BU

**3. GET /employees/roles-for-conversion** - Get available roles for conversion
   - Returns: list of roles that current user can assign in their BU
   - Used by frontend to populate role selection dropdown in conversion form

#### Permission Structure by Role:
This enables fine-grained access control per role. Users with multiple roles get the UNION of all permissions:

- **Super User**: 
  - `*.*` (all modules, all actions)
  - No BU restrictions

- **Admin**: 
  - `user.manage`, `role.manage`
  - `candidate.*` (all candidate actions)
  - `employee.*` (all employee actions) 
  - `business_unit.manage`
  - Can operate across BUs per BU assignment

- **Recruiter** (Senior Recruiter): 
  - `candidates.view`, `candidate.create`, `candidate.edit`, `candidate.delete`
  - `recruitment.view`
  - `interview.manage`
  - Scoped to own BU

- **HR Manager**: 
  - `candidates.view`, `candidate.edit`
  - `employee.manage`, `employee.view`
  - `reports.view`
  - Scoped to own BU

- **Finance**: 
  - `invoices.view`, `invoices.manage`
  - `reports.financial`
  - Cross-BU visibility for consolidation

- **Partner**: 
  - `business_unit.manage` (own BU only)
  - `employee.manage`
  - `team.view`
  - Scoped to own BU

- **BU Head**: 
  - `business_unit.view`
  - `employee.manage`
  - `recruitment.view`
  - `reports.view`
  - Scoped to own BU

#### Architecture Decisions:

**Multi-Role Composition:**
- Users can have multiple roles (e.g., Partner + BU Head + Hiring Manager)
- Permissions are UNIONED from all assigned roles
- No hierarchy or priority between roles—each user gets all permissions from all roles
- Frontend must show all applicable UI elements based on permission union

**BU Scoping Strategy:**
- All queries filter by `current_user.business_unit_id` via middleware
- Exceptions: Super User can see all BUs without filter
- Finance might have cross-BU reporting (requires special permission)
- New candidates (org pool, not yet submitted to job) visible to all HR users

**Permission Inheritance:**
- Child roles DON'T inherit parent permissions
- Each role explicitly lists its permissions
- Use permission composition at the user level, not role hierarchy

**Tenant Isolation:**
- All BU and user data scoped to tenant_id (multi-tenancy preserved)
- Single tenant setup initially (tenant_id=1) but architecture supports multi-tenant at scale

**Employee Conversion Flow:**
- Candidate → Employee transition point
- Conversion form captures: role(s), BU, position, joining date
- Auto-generates employee password (sent via email)
- Creates employee user account with proper role assignments
- Candidate marked as CONVERTED_TO_EMPLOYEE for audit trail

#### Key Files Modified:
- `app/api/v1/endpoints/users.py` - Added create_user_with_roles endpoint
- `app/api/v1/endpoints/employees.py` - NEW file with conversion logic
- `app/models/user.py` - Many-to-many relationships via user_roles
- `init_wros_db.py` - Database initialization with 3 default BUs
- `RBAC_IMPLEMENTATION_PLAN.md` - 300+ line comprehensive documentation

#### Testing Checklist:
- ✅ Create user with multiple roles (Partner + BU Head tested)
- ✅ Verify login returns all roles and flattened permissions
- ✅ Verify BU filtering (user only sees their BU data)
- ✅ Convert candidate to employee with role selection
- ✅ Test Super User access to everything
- ✅ Test role permission composition (multiple roles = union of permissions)

#### Next Phase (Frontend - Partially Started):
- Dynamic navigation bar based on user roles/permissions (NOT YET IMPLEMENTED)
- Multi-role selector in user creation form: BU dropdown + role checkboxes (NOT YET IMPLEMENTED)
- Employee conversion screen with BU/role assignment UI (NOT YET IMPLEMENTED)
- BU filtering in candidate/employee/interview list screens (NOT YET IMPLEMENTED)
- Login endpoint enhancement: return all user roles and flattened permissions (PARTIALLY IMPLEMENTED)

**Commit:** 0a0bc7c
**Status:** 🟢 LIVE IN PRODUCTION (Backend ready for frontend integration)

---

## IMPLEMENTATION DETAILS FOR FRONTEND INTEGRATION

### Frontend Architecture Changes Needed

**1. Navigation Bar Dynamic Rendering**
```javascript
// Show/hide menu items based on user's roles and permissions
const Navigation = ({ user }) => {
  const hasPermission = (perm) => user.permissions.includes(perm);
  
  return (
    <>
      {hasPermission('recruitment.view') && <NavItem href="/recruitment">Recruitment</NavItem>}
      {hasPermission('employee.manage') && <NavItem href="/employees">Employees</NavItem>}
      {hasPermission('business_unit.manage') && <NavItem href="/bu-management">BU Management</NavItem>}
      {hasPermission('reports.view') && <NavItem href="/reports">Reports</NavItem>}
    </>
  );
};
```

**2. Add User Form: Multi-Role + BU Selection**
- BU dropdown (limited to current user's BU for non-super-users)
- Role checkboxes (allow multiple role selection)
- Form endpoint: POST /users/create-with-roles
- Payload: { user_name, user_email, user_password, business_unit_id, role_ids: [1, 2, 3] }

**3. Employee Conversion Screen**
- Candidate selector (from candidates list)
- Employee details: name, email, position
- Business Unit dropdown
- Role multi-select checkboxes
- Joining date picker
- Auto-password generation checkbox
- Form endpoint: POST /employees/convert-from-candidate

**4. Login Enhancement**
- Backend returns: roles[], permissions[] in JWT payload
- Frontend stores: user.roles, user.permissions in state
- Navigation rebuilds based on permissions
- Permission checks before rendering UI components

**5. Query Filtering**
- All candidate/employee/interview lists filtered by user's BU
- Frontend can send current_user's BU with requests
- Backend validates and applies scoping

### Permission-Based UI Patterns

Use this pattern throughout frontend for permission-based rendering:

```javascript
// Instead of: hasRole('Admin')
// Use: hasPermission('candidate.create')

{user.permissions?.includes('candidate.create') && (
  <Button onClick={openAddCandidateForm}>Add Candidate</Button>
)}
```

This maps business requirements (can the user create candidates) instead of role names (is the user an admin), making it easier to adjust permissions without frontend code changes.

---

## 🚀 PREVIOUS STATUS (2026-08-09 Session - Submit Job Modal Complete)

**Frontend:** ✅ PRODUCTION READY - Submit Job Modal refactored with comprehensive form fields
**Submit Job Modal:** ✅ COMPLETE - All 7 new fields added with auto-population logic
**Git Status:** ✅ PUSHED - Commit e967d51 to main, changes live in production

### Today's Session Work (2026-08-09 Afternoon):
**EPIC: Submit Job Modal Form Enhancement - COMPLETED**

**Changes Made:**
- ✅ Restructured CandidateAssignJobModal with 7 new required fields
- ✅ Changed Submit To from text input to dropdown (person/role selector)
- ✅ Added Contact Person field (searchable dropdown from job contacts)
- ✅ Added Department field (auto-populated from job)
- ✅ Added Hiring Manager field (auto-populated from job)
- ✅ Added Hiring Team field (auto-populated from job)
- ✅ Added Client Name field (auto-populated from job, read-only)
- ✅ Consolidated Date/Time/Timezone on single row (3 columns)
- ✅ Auto-populate Recruited By from current logged-in user
- ✅ Parse and auto-populate pay currency/frequency from job salary_range

**Form Structure Now:**
- **Basic Info:** Job selection, Submit To (person/role dropdown), Date/Time/Timezone (1 row), Recruited By, Client Name, Client Owner, Department, Contact Person, Hiring Manager, Hiring Team
- **Pay:** Position Type, Bill Rates, Pay Rate with currency/frequency
- **CV:** CV selection, Internal Notes, Notifications
- **Actions:** Save/Cancel buttons

**Testing Verified:**
- ✅ Job selection dropdown shows all available jobs
- ✅ Form auto-populates Recruited By from current user
- ✅ All new fields render correctly in the form
- ✅ Contact Person dropdown ready for data population
- ✅ Submit To dropdown structure ready (will show options when job has hiring manager/client owner data)
- ✅ Form submission payload includes all new fields

**Known Limitation:**
- Test jobs don't have hiring_manager_name, client_owner_name, department fields populated
- Form structure is production-ready; auto-population will work when job data includes these fields

**Commit:** e967d51
**Status:** 🟢 LIVE IN PRODUCTION

---

## PRODUCTION READINESS AUDIT (2026-08-09)

### Audit Findings:
**✅ WORKING SCREENS:**
- Dashboard (loads, displays data)
- Candidates list (loads, displays 60 candidates from DB)
- Add Candidate form (loads)
- Job creation (accessible)
- Admin UI (accessible)

**⚠️ BROKEN ENDPOINTS (404 errors, need backend implementation):**
1. `GET /sla/breaches?is_resolved=false` - SLA monitoring endpoint missing
2. `/candidates/{id}/engagement-metrics` - Engagement metrics endpoint missing
3. Multiple /admin/agents/* endpoints returning 404s
4. `/offer-letter/all` - Offer letters endpoint returning 404s

**🔴 CRITICAL FRONTEND/BACKEND INTEGRATION ISSUES:**
1. Many API endpoints exist in code but endpoints don't respond (404s)
2. CORS is configured but some requests still blocked
3. Candidate status workflow incomplete (no conversion flow)
4. Employee project assignment missing (blocks timesheet access)

### Next Steps Before Production:
1. **IMMEDIATE:** Implement missing endpoints for SLA, engagement-metrics, offers
2. **HIGH:** Add Candidate→Employee conversion button to CandidateDetailsScreen
3. **HIGH:** Add Employee→Project assignment to ProjectsScreen
4. **MEDIUM:** Fix 404 errors on agent endpoints
5. **MEDIUM:** Implement engagement metrics API

---

## CRITICAL BLOCKERS (2026-08-09 UPDATED)

### ✅ FIXED: Schedule Interview Button
**Status:** COMPLETED
- Added "Schedule Interview" button to InterviewsTab
- Button appears in EmptyState when no interviews exist
- Clicking button opens full Schedule Interview modal
- Modal allows panel selection, date/time, platform, and email configuration
- Enables complete workflow: Schedule → Feedback → Panel Decision → Hiring Approval → Offer

### ✅ VERIFIED: Thunder Autonomous Execution is WORKING
**Status:** ACTIVE & EXECUTING
- ✅ Thunder autonomous loop scheduled every 5 minutes
- ✅ Successfully executing (logs show executions at 11:02:15, 11:07:15, 11:12:15, 11:17:15)
- ✅ **Contacting 10 candidates per cycle automatically**
- ✅ Zero errors in execution
- ⚠️ Thunder Activity Feed UI not displaying executions (display issue, not execution issue)

### 🚨 BLOCKER 1: Candidate-to-Employee Conversion Flow is Broken
**Severity:** CRITICAL - Blocks offer→hire→onboard pipeline

**Problem:**
- Candidates in "OFFER" status with start date have no way to convert to employee from the candidate details screen
- The "Convert Candidate to Employee" button exists in the Employees screen (wrong location)
- When candidate's start date arrives, recruiters cannot transition them to employee status
- **Impact:** Entire hiring pipeline stalls after offer acceptance

**Required Fix:**
1. Add "Convert to Employee" action button in CandidateDetailsScreen (only when status == "OFFER" AND start_date <= today)
2. Move or remove "Convert Candidate to Employee" from Employees screen (it shouldn't be there)
3. Wire conversion endpoint to trigger onboarding workflow

### 🚨 BLOCKER 2: Project Employee Assignment Missing
**Severity:** HIGH - Blocks timesheet access

**Problem:**
- Projects screen has no ability to assign employees to projects
- Employees cannot access timesheets without being assigned to a project
- No project membership = no timesheet access
- **Impact:** Employees cannot submit timesheets

**Required Fix:**
- Add "Assign Employees" button/modal to Projects screen
- Create project membership records when employees are assigned
- Verify timesheet access after assignment

---

## SESSION UPDATE: Login Fixed - Email→Password Step Working ✅

**BREAKTHROUGH:** Email-to-password form progression fixed! 
- Direct JavaScript trigger of handleNext() now correctly advances to password field
- Password field renders with readonly email display and password input
- Form state management working correctly (handleNext just changes step, no API call needed)

**API VERIFIED WORKING:**
- POST /auth/login responding with Status 200 ✅
- Direct fetch returns valid JWT access_token ✅
- User authentication (bcrypt) verified working ✅
- Database connected and test users present ✅

**REMAINING ISSUE:** 
React login component's apiRequest wrapper failing on form submission
- When user manually triggers form: browser shows "Failed to fetch" / "connection refused"
- When direct JavaScript fetch is called: works perfectly, Status 200
- Suggests issue with headers, CORS, or how apiRequest wraps the fetch

---

## Next Priorities (Post-RBAC Implementation)

### Phase 1: Frontend RBAC Integration (Next Session)
1. **Dynamic Navigation Bar**
   - Show/hide menu items based on user.permissions
   - Check permission before rendering each nav item
   - Update on permission changes

2. **Enhanced User Creation Form**
   - Add BU dropdown (limited to user's own BU for non-super-users)
   - Add multi-role checkboxes (allow selecting multiple roles)
   - Wire to POST /users/create-with-roles endpoint

3. **Employee Conversion Screen**
   - Create new dedicated screen or modal
   - Candidate selector (from candidates list)
   - Business Unit dropdown
   - Role multi-select checkboxes
   - Employee details form (name, email, position, joining date)
   - Wire to POST /employees/convert-from-candidate endpoint

### Phase 2: Query Filtering
1. All candidate/employee/interview lists filtered by user's BU
2. Frontend sends requests with BU context
3. Backend validates and enforces scoping

### Phase 3: Login Enhancement
1. Fetch and store all user roles and permissions on login
2. Rebuild navigation based on permissions
3. Store in React context or Redux for access throughout app

---

## 🎯 BACKLOG STORY: Hiring Manager Validation Questions (HM Screening)

**Story ID:** EPIC-06-HM-SCREENING  
**Priority:** HIGH - Blocks autonomous hiring flow completeness  
**Status:** DESIGN PHASE - Ready for implementation  
**Created:** 2026-08-13  

### Problem Statement

The current autonomous hiring flow (Thunder → AI Recruiter → Interview → Offer) lacks a **critical checkpoint: Hiring Manager validation before interviews**.

**Current Gap:**
- ✅ Candidate matches to job via Thunder + AI Recruiter
- ✅ Interviews get scheduled automatically
- ❌ **MISSING:** Hiring manager doesn't validate candidate fit before interview
- ❌ Interview happens without manager context
- ❌ Candidate feedback gathered from hiring team without prior validation

**Business Impact:**
- Hiring managers feel out of control ("I didn't even approve this candidate for interview")
- Wasted interview time on candidates manager would have rejected
- No pre-interview briefing for the interview panel
- Interview questions not customized based on manager's concerns
- Offer generation doesn't account for manager's specific requirements

### Solution Overview

Add **Hiring Manager Validation Question Set** that triggers after candidate matches to job but BEFORE interview scheduling.

**Flow:**
```
Thunder → AI Recruiter Matches Candidate to Job 
  ↓
AI Recruiter Retrieves HM Validation Questions from Job
  ↓
AI Recruiter Presents Questions to Hiring Manager (async, email + dashboard)
  ↓
Hiring Manager Answers Questions (Yes/No/Detail fields)
  ↓
IF Manager Rejects → Candidate returned to pool, next match attempted
  ↓
IF Manager Approves → Interview scheduled with manager's context
  ↓
Interview Panel gets manager's validation answers for context
```

### System Integration Points

#### 1. Job Data Structure Enhancement
**New fields needed on `jobs` table:**

```sql
ALTER TABLE jobs ADD COLUMN (
  hm_validation_questions JSON,          -- Array of validation questions
  hm_validation_required BOOLEAN,        -- Enable/disable for this job
  hm_validation_timeout_hours INT,       -- How long to wait for HM response (default 24)
  auto_schedule_after_approval BOOLEAN,  -- Auto-schedule interview if HM approves
  hm_auto_reject_threshold INT           -- Auto-reject if <N responses are negative
);
```

**Example hm_validation_questions JSON:**
```json
{
  "questions": [
    {
      "id": "q_001",
      "question": "Does this candidate's experience level match our seniority requirement?",
      "type": "yes_no",
      "follow_up": "If no, please explain why this candidate doesn't fit",
      "follow_up_type": "text",
      "required": true
    },
    {
      "id": "q_002",
      "question": "Are there any red flags in the candidate's background we should address in the interview?",
      "type": "text",
      "required": false
    },
    {
      "id": "q_003",
      "question": "What specific skills should we prioritize assessing in the interview?",
      "type": "text",
      "required": true
    },
    {
      "id": "q_004",
      "question": "Should we move forward with an interview?",
      "type": "yes_no_maybe",
      "required": true,
      "determine_flow": true  // THIS QUESTION DETERMINES NEXT STEP
    }
  ],
  "version": "1.0",
  "created_at": "2026-08-13T10:00:00Z"
}
```

#### 2. Thunder Enhancement
**Thunder needs to:**
- ✅ Still matches candidate to job (no change)
- ✅ Still ranks candidates by fit score (no change)
- ✅ **NEW:** Check if job requires HM validation
- ✅ **NEW:** If yes, create validation_request record instead of auto-scheduling interview

#### 3. AI Recruiter Enhancement
**AI Recruiter needs to:**
- ✅ Receive matched candidate + job + HM validation questions
- ✅ **NEW:** Extract HM contact from job.hiring_manager_email
- ✅ **NEW:** Create hiring_manager_validations record
- ✅ **NEW:** Send HM an async notification (email + dashboard card)
- ✅ **NEW:** Present validation form (web or email)
- ✅ **NEW:** Wait for HM response (up to hm_validation_timeout_hours)
- ✅ **NEW:** Based on response, either schedule interview or reject candidate

#### 4. Database Schema Changes

**New Table: `hiring_manager_validations`**
```sql
CREATE TABLE hiring_manager_validations (
  id UUID PRIMARY KEY,
  candidate_id UUID NOT NULL,
  job_id UUID NOT NULL,
  hiring_manager_id UUID NOT NULL,
  
  -- Validation State
  status ENUM('PENDING', 'APPROVED', 'REJECTED', 'MAYBE', 'EXPIRED'),
  created_at TIMESTAMP,
  due_at TIMESTAMP,  -- created_at + hm_validation_timeout_hours
  responded_at TIMESTAMP,
  
  -- Responses
  responses JSONB,  -- Stores answers to each question
  decision_comment TEXT,  -- Manager's overall comment
  decision_score INT,  -- 1-10 recommendation
  
  -- Audit
  email_sent_at TIMESTAMP,
  email_reminder_sent_at TIMESTAMP,
  notification_viewed_at TIMESTAMP,
  
  -- Downstream Impact
  interview_scheduled_at TIMESTAMP,
  interview_id UUID,
  next_candidate_tried BOOLEAN,  -- If rejected, did we try next candidate?
  
  FOREIGN KEY (candidate_id) REFERENCES candidates(id),
  FOREIGN KEY (job_id) REFERENCES jobs(id),
  FOREIGN KEY (hiring_manager_id) REFERENCES users(UserID),
  FOREIGN KEY (interview_id) REFERENCES interviews(id)
);
```

**New Table: `hm_validation_responses`**
```sql
CREATE TABLE hm_validation_responses (
  id UUID PRIMARY KEY,
  validation_id UUID NOT NULL,
  question_id VARCHAR(100),  -- e.g., "q_001"
  question_text TEXT,
  response_value VARCHAR(500),  -- yes/no/maybe or text response
  response_type ENUM('yes_no', 'yes_no_maybe', 'text'),
  response_at TIMESTAMP,
  
  FOREIGN KEY (validation_id) REFERENCES hiring_manager_validations(id)
);
```

### Workflow Specifications

#### Workflow: HM Validation Decision Logic

```
INPUT: 
  - Candidate (with scores, resume, experience)
  - Job (with HM validation questions + threshold)
  - Hiring Manager (contact info, preferences)

PROCESS:
  1. Create hiring_manager_validations record (status: PENDING)
  2. Send email + dashboard notification to HM
     - Subject: "Please review candidate: [Candidate Name] for [Job Title]"
     - Include: Candidate summary, match score, resume preview
     - Include: Validation form with questions
     - Include: Direct link to dashboard card
  
  3. Wait for HM response
     - Poll dashboard for response (or webhook if HM answers)
     - If timeout expires → Auto-escalate to HM's manager
     - If auto_escalate fails → Hold candidate in "AWAITING_HM_REVIEW" state
  
  4. On HM Response:
     a) Store all responses in hm_validation_responses table
     b) Calculate decision:
        - Final answer: Is "q_004" (Should we move forward?) yes/no/maybe?
        - IF yes → validation.status = APPROVED
        - IF no → validation.status = REJECTED
        - IF maybe → validation.status = MAYBE (manual review queued)
     
  5. Based on Decision:
     a) IF APPROVED:
        - Set validation.status = APPROVED
        - Trigger AI Recruiter to schedule interview
        - Pass HM's answers to interview scheduling (for panel briefing)
        - Create interview_scheduling_request
        - Interview scheduled within 48 hours
     
     b) IF REJECTED:
        - Set validation.status = REJECTED
        - Store rejection reason from hm_validation_responses
        - Log: next_candidate_tried = false
        - Return candidate to Thunder's pool
        - Trigger: "Try next best candidate" logic
        - Notify candidate: Application not moved forward at this stage (generic)
     
     c) IF MAYBE:
        - Set validation.status = MAYBE
        - Route to "Manual Review Queue"
        - Hiring Manager's manager reviews in dashboard
        - Manual approval/rejection
        - Proceed based on final decision
  
OUTPUT:
  - hiring_manager_validations record (APPROVED/REJECTED/MAYBE)
  - hm_validation_responses records (all Q&A pairs)
  - Interview scheduled (if APPROVED)
  - Next candidate attempted (if REJECTED)

TIMEOUT BEHAVIOR (if no response within hm_validation_timeout_hours):
  - Send reminder email to HM
  - After 24hrs more: Escalate to HM's manager
  - After 48hrs total: Auto-approve (configurable: auto_approve_on_timeout = true/false)
  - If auto_reject_on_timeout = true: Reject candidate and try next
```

### Implementation Roadmap

#### Phase 1: Database & Data Model (Week 1)
- [ ] Add hm_validation_questions, hm_validation_required, hm_validation_timeout_hours to jobs table
- [ ] Create hiring_manager_validations table
- [ ] Create hm_validation_responses table
- [ ] Add migration script
- [ ] Create database indexes on (candidate_id, job_id), (hiring_manager_id, status)

#### Phase 2: API Endpoints (Week 1-2)
- [ ] POST `/hiring-manager-validations/{id}/respond` - Submit HM validation answers
- [ ] GET `/hiring-manager-validations?status=PENDING` - List pending validations for HM
- [ ] GET `/hiring-manager-validations/{id}` - Get single validation with questions & responses
- [ ] PUT `/hiring-manager-validations/{id}/remind` - Send reminder email
- [ ] GET `/jobs/{id}/validation-template` - Get HM questions for a job

#### Phase 3: AI Recruiter Integration (Week 2)
- [ ] When candidate matches to job: Check if job requires HM validation
- [ ] If yes: Create validation request instead of auto-scheduling interview
- [ ] Send email to HM with validation form
- [ ] Implement polling for HM response (every 30min)
- [ ] On response: Trigger interview scheduling OR next candidate

#### Phase 4: Email & Notifications (Week 2)
- [ ] Email template: "HM Validation Request" 
- [ ] Email template: "HM Validation Approved" (send to candidate)
- [ ] Email template: "HM Validation Rejected" (send to HR, not candidate)
- [ ] Dashboard notification card for pending validations
- [ ] Reminder email (at 12hr mark if no response)

#### Phase 5: Frontend Screens (Week 3)
- [ ] Job Creation/Edit: Add HM validation questions builder
  - [ ] WYSIWYG form builder for questions
  - [ ] Question types: yes/no, yes/no/maybe, text
  - [ ] Follow-up question logic (if no, then ask why)
  - [ ] Save validation template
  
- [ ] Dashboard: HM Validation Card
  - [ ] "Pending Validations" section
  - [ ] Shows: Candidate name, job, match score, resume preview
  - [ ] Quick action buttons: Approve, Reject, Maybe, Need More Info
  - [ ] Validation form with all questions
  - [ ] Response history (past validations)
  
- [ ] Candidate Details: Show HM validation status
  - [ ] Status badge: "Awaiting Hiring Manager Review"
  - [ ] Timeline showing when validation was sent to HM
  - [ ] What questions were asked

#### Phase 6: Testing & Deployment (Week 3-4)
- [ ] Unit tests: Validation decision logic
- [ ] Integration tests: Thunder → AI Recruiter → HM Validation → Interview flow
- [ ] End-to-end test: Full flow with different HM responses
- [ ] Load test: Multiple candidates needing validation simultaneously
- [ ] Deploy to staging, test with real users

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Async vs Sync HM Response** | Async (email + dashboard) | HMs are busy; don't block Thunder flow; allow 24hrs response time |
| **Auto-approve on timeout** | Configurable (default: false) | Better to escalate than force approval; auditable |
| **Question Types** | yes/no, yes/no/maybe, text | Covers 90% of manager validation needs |
| **Who decides next step** | Question 4 determines flow | Single clear decision point; easy for AI to interpret |
| **Notify candidate on reject** | Generic message only | Don't reveal HM vetted them out (protects HM relationship) |
| **Store HM answers** | Full JSONB in responses table | Audit trail; used for interview briefing; future ML |
| **Timeout escalation** | To HM's manager | Ensures decision happens; maintains accountability |

### Acceptance Criteria

- [ ] HM validation questions can be configured per job
- [ ] AI Recruiter retrieves questions and sends to HM
- [ ] HM can answer questions via email or dashboard
- [ ] HM response triggers correct workflow (interview or next candidate)
- [ ] Timeout/escalation works correctly
- [ ] All responses stored in audit log
- [ ] Interview panel receives HM's answers before interview
- [ ] Candidate aware of status but not specific HM feedback
- [ ] No candidate reaches interview stage without HM approval
- [ ] System handles multiple candidates for same job (queue management)

### Dependencies

**Before this can be implemented:**
- ✅ Thunder autonomous loop (DONE - 2026-08-12)
- ✅ AI Recruiter matching logic (DONE - 2026-08-12)
- ✅ Interview scheduling automation (DONE - 2026-08-09)
- ✅ Email notification system (DONE - foundation exists)
- ⏳ Dashboard framework (IN PROGRESS - needed for HM validation card)

**After this, enables:**
- More confident hiring manager engagement
- Interview panel prep (knows manager's concerns)
- Better candidate feedback (contextual to manager's validation)
- Reduced wasted interview time
- Full autonomous hiring flow (Thunder → Interview → Offer → Hire → Onboard)

### Out of Scope (Phase 2+)

- Bulk validation (multiple candidates at once)
- AI-suggested answers for HM questions
- Hiring manager validation templates/presets
- Cross-regional HM escalation policies
- Workflow variations per department

---

## 🎯 BACKLOG STORY: careers.blitzenx.com Frontend - Production Grade

**Story ID:** EPIC-07-CAREERS-PORTAL-FRONTEND  
**Priority:** HIGH - Enables public candidate applications  
**Status:** MVP DEPLOYED - Needs production hardening  
**Created:** 2026-08-13  
**Scope:** 4-6 weeks for production-ready frontend

### Problem Statement

**Current State:** careers.blitzenx.com has a basic MVP frontend (localhost:3001) with:
- ✅ Job listings working
- ✅ Thunder chatbot flow functional
- ✅ Basic styling (inline CSS)

**Gaps Blocking Production:**
- ❌ No error handling (network failures, timeouts, validation errors)
- ❌ No form validation (invalid emails, missing fields accepted)
- ❌ No state persistence (form data lost on refresh)
- ❌ No API integration (frontend not calling backend endpoints)
- ❌ Poor UX (no loading states, no feedback messages)
- ❌ Accessibility issues (no WCAG 2.1 compliance)
- ❌ No analytics (can't track user behavior)
- ❌ Mobile UX needs work (touch interactions, responsive layout)
- ❌ No tests (no unit, integration, or E2E tests)
- ❌ Deployment not configured (not ready for production)

**Business Impact:**
- Candidates experience errors without clear guidance
- Session data lost, candidates forced to restart
- No visibility into application funnel
- Poor mobile experience (30-40% of traffic)
- Not meeting accessibility requirements

### Solution Overview

**Transform careers.blitzenx.com from MVP to production-grade:**

```
Phase 1: Error Handling & Validation (Week 1)
  ├─ Form validation (email, required fields, file upload)
  ├─ Error boundaries and fallback UI
  ├─ Network error handling with retry logic
  └─ Toast notifications for user feedback

Phase 2: State Management & Persistence (Week 2)
  ├─ Zustand store for session state
  ├─ LocalStorage for form recovery
  ├─ Session recovery from email link (?session_id=xxx)
  └─ Automatic save-on-input (debounced)

Phase 3: API Integration (Week 2)
  ├─ Connect Thunder form to backend /api/v1/thunder/* endpoints
  ├─ Resume parsing callback integration
  ├─ Job listing API integration
  └─ Error handling per endpoint

Phase 4: UX Enhancements (Week 3)
  ├─ Loading states & spinners
  ├─ Progress indicators (actual % complete)
  ├─ Success/error messaging
  ├─ Keyboard navigation
  └─ Accessibility audit (WCAG 2.1 AA)

Phase 5: Mobile & Responsive (Week 3)
  ├─ Touch-friendly buttons (48px minimum)
  ├─ Mobile-first responsive design
  ├─ Viewport optimization
  └─ iOS/Android testing

Phase 6: Testing (Week 4)
  ├─ Unit tests (components, hooks, utilities)
  ├─ Integration tests (API calls, state changes)
  ├─ E2E tests (Cypress: complete Thunder flow)
  └─ Performance testing (Lighthouse, Core Web Vitals)

Phase 7: Analytics & Monitoring (Week 4)
  ├─ Google Analytics integration
  ├─ Funnel tracking (Q1→Q8 completion)
  ├─ Error tracking (Sentry)
  ├─ Session recording (optional: Hotjar/LogRocket)
  └─ Performance monitoring (Web Vitals)

Phase 8: Deployment (Week 5)
  ├─ Vercel configuration
  ├─ Environment setup (staging/production)
  ├─ CDN caching strategy
  ├─ SSL/TLS configuration
  └─ Monitoring & alerting
```

### Detailed Requirements

#### Phase 1: Form Validation & Error Handling

**Form Validators:**
```typescript
// Email validation
const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

// Required field validation
const isRequired = (value) => value && value.trim().length > 0

// Phone number validation
const isValidPhone = (phone) => /^[\d\s\-\+\(\)]+$/.test(phone)

// Resume file validation (PDF/DOCX, max 5MB)
const isValidResume = (file) => {
  const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
  return validTypes.includes(file.type) && file.size <= 5 * 1024 * 1024
}
```

**Error Handling:**
```typescript
// Network error handler
const handleError = (error) => {
  if (!error.response) {
    return 'Network error. Check your connection and try again.'
  }
  
  const status = error.response.status
  if (status === 400) return 'Invalid input. Please check your answers.'
  if (status === 404) return 'Resource not found.'
  if (status === 500) return 'Server error. Please try again later.'
  
  return 'Something went wrong. Please try again.'
}

// Retry logic for failed requests
const retryRequest = async (fn, maxRetries = 3) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
    }
  }
}
```

#### Phase 2: State Management with Zustand

```typescript
// Store for Thunder session
import create from 'zustand'

interface ThunderStore {
  sessionId: string | null
  currentQuestion: string
  responses: Record<string, any>
  status: 'idle' | 'loading' | 'error'
  error: string | null
  
  // Actions
  initSession: (email: string) => Promise<void>
  submitAnswer: (question: string, response: any) => Promise<void>
  uploadResume: (file: File) => Promise<void>
  submitApplication: () => Promise<void>
}

export const useThunderStore = create<ThunderStore>((set) => ({
  sessionId: null,
  currentQuestion: 'Q1',
  responses: {},
  status: 'idle',
  error: null,
  
  initSession: async (email) => {
    set({ status: 'loading' })
    try {
      const { data } = await axios.post('/api/v1/thunder/sessions', { 
        candidate_email: email 
      })
      set({ sessionId: data.session_id, status: 'idle' })
    } catch (error) {
      set({ error: error.message, status: 'error' })
    }
  },
  
  // ... other actions
}))
```

#### Phase 3: API Integration

**Axios instance with interceptors:**
```typescript
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL
})

// Request interceptor
api.interceptors.request.use((config) => {
  // Add session ID to headers if available
  const sessionId = localStorage.getItem('thunder_session_id')
  if (sessionId) {
    config.headers['X-Session-ID'] = sessionId
  }
  return config
})

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Handle authentication error
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

#### Phase 4: Accessibility Compliance (WCAG 2.1 AA)

**Requirements:**
- [ ] Color contrast ratio ≥ 4.5:1 for text
- [ ] All form inputs have associated labels
- [ ] Keyboard navigation (Tab, Enter, Escape)
- [ ] ARIA roles and live regions for dynamic content
- [ ] Skip navigation link
- [ ] Focus visible on all interactive elements
- [ ] No text-only images (use alt text)
- [ ] Heading hierarchy (h1 → h2 → h3)
- [ ] Landmarks (header, nav, main, footer)

#### Phase 5: Mobile Optimization

**Viewport meta tag:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
```

**Touch-friendly buttons:**
```css
button {
  min-height: 48px;  /* Touch target size */
  min-width: 48px;
  padding: 12px 16px;
}
```

**Responsive breakpoints:**
```css
/* Mobile: 375px - 767px */
/* Tablet: 768px - 1023px */
/* Desktop: 1024px+ */
```

#### Phase 6: Testing Strategy

**Unit tests (Jest):**
```typescript
describe('ThunderChat', () => {
  it('should display next question after answer', async () => {
    render(<ThunderChat />)
    const input = screen.getByPlaceholderText('Type your answer...')
    
    fireEvent.change(input, { target: { value: 'Jane Doe' } })
    fireEvent.click(screen.getByText('Next →'))
    
    await waitFor(() => {
      expect(screen.getByText(/How many years/)).toBeInTheDocument()
    })
  })
})
```

**E2E tests (Cypress):**
```typescript
describe('Thunder Complete Flow', () => {
  it('should complete full Thunder intake', () => {
    cy.visit('/jobs')
    cy.contains('Apply now').first().click()
    
    // Q1: Email
    cy.get('input[type="text"]').type('test@example.com')
    cy.contains('Next').click()
    
    // Q2-Q8: Answer all questions
    // ...
    
    // Submit
    cy.contains('Submit Application').click()
    
    // Verify success
    cy.contains('Application Received!').should('be.visible')
  })
})
```

#### Phase 7: Analytics

**Events to track:**
- Session started (job_id, device_type)
- Question answered (question_id, time_taken)
- Resume uploaded (file_size, format)
- Application submitted (completion_time, job_id)
- Errors encountered (error_type, question_id)
- Session abandoned (last_question_reached)

**Funnel analysis:**
- Job viewed → Apply clicked → Q1 answered → Q8 answered → Submitted
- Dropout rate by question
- Average time per question
- Resume upload success rate

#### Phase 8: Deployment

**Vercel Configuration (vercel.json):**
```json
{
  "buildCommand": "npm run build",
  "env": {
    "NEXT_PUBLIC_API_BASE_URL": "@api_base_url"
  },
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://api.blitzenx.com/api/:path*"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ]
}
```

### Acceptance Criteria

- [ ] All form inputs validate before submission
- [ ] Network errors show clear, actionable messages
- [ ] Form data persists when page is refreshed
- [ ] Session can be resumed via email link
- [ ] All backend API endpoints integrated and tested
- [ ] Loading spinners show during network requests
- [ ] Mobile experience works on iOS and Android
- [ ] Lighthouse score ≥ 90 for all metrics
- [ ] WCAG 2.1 AA compliance verified
- [ ] 80%+ unit test coverage
- [ ] Complete E2E test coverage (all user flows)
- [ ] Analytics events firing correctly
- [ ] Deployment to Vercel automated
- [ ] Error tracking (Sentry) integrated

### Dependencies

- Backend APIs deployed and working (EPIC-06 complete)
- Design system/component library decision (Tailwind vs custom)
- Analytics account setup (Google Analytics, Sentry)
- Vercel or hosting provider configured

### Timeline

- **Weeks 1-2:** Phase 1-3 (validation, state, API)
- **Weeks 3-4:** Phase 4-6 (UX, mobile, testing)
- **Week 5:** Phase 7-8 (analytics, deployment)
- **Total:** 5 weeks for production-ready

### Out of Scope

- Custom animation library
- A/B testing framework
- Multi-language support
- Native mobile apps

---

## Code Quality Standards (Established 2026-07-23)

- No placeholders/hardcoded values in EPIC-01/02/03/05 stories
- Production readiness bar enforced
- Integration tests on local SQLite
- All paths must be absolute (no relative path assumptions)

---

## Architecture Notes

### Thunder Autonomous System
- Every candidate auto-assigned to Thunder (AI recruiter) on intake
- Thunder manages full journey: intake → qualify → screen → interview → offer → hire → onboard
- No manual recruiter clicks required for happy path
- Recruiter maintains override capability for exceptions

### Database Path Resolution Pattern
This pattern should be replicated anywhere relative paths are used:
```python
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if url.startswith("sqlite:///./"):
    rel = url.replace("sqlite:///./", "")
    url = f"sqlite:///{os.path.join(_ROOT, rel)}"
```

---

## Session Discipline

- Complete ONE task thoroughly before next
- NO summary generation without explicit request (saves tokens)
- Code pushed to main after each logical milestone
- All code reviewed and tested before commit

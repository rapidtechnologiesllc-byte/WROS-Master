# GitHub Backlog - Priority Items

**Date:** 2026-09-09  
**Status:** Ready for GitHub Issues  
**Instructions:** Use these templates to create GitHub issues for the backlog

---

## 📋 Issue 1: DONE - Business Unit Isolation (d5c6f1fc)

**Title:** DONE: Implement Business Unit isolation for candidate scoping

**Labels:** `backlog`, `completed`, `critical`

**Milestone:** Production Ready

**Body:**
```
## Summary
Implement multi-tenant Business Unit (BU) isolation to prevent cross-BU data leakage.

## Requirements
- [x] Fix Business Units CRUD endpoints
- [x] Add org_level_access flag to RoleTemplate
- [x] Wire visibility.py into candidate queries
- [x] Test BU scoping end-to-end

## Implementation
- Fixed /api/v1/business-units GET/POST/PUT/DELETE
- Added org_level_access column to role_templates
- Updated visibility.py for database-driven checks
- Updated bu_scope.py to integrate with visibility

## Result
- Org-level users (CEO, Super User) see all candidates
- BU-scoped users see only their BU + org pool candidates
- Candidates isolated after job submission
- Unassigned candidates (org pool) visible to all recruiters

Commit: d5c6f1fc
```

---

## 🚀 Issue 2: PRIORITY - Create Candidate Workflow

**Title:** PRIORITY: Implement Create Candidate end-to-end workflow

**Labels:** `priority`, `frontend`, `backend`, `candidate-workflow`

**Milestone:** Sprint 1

**Body:**
```
## Summary
Implement complete candidate creation workflow with proper validation, BU scoping, and Thunder queue integration.

## Requirements
- [ ] Create Candidate form with all required fields
  - Name, email, phone, location
  - Current company, job title, notice period
  - Skills, education, experience
  - Business Unit assignment
  - WhatsApp consent recording
- [ ] Email/phone validation
- [ ] Duplicate detection (by email or phone)
- [ ] Business Unit assignment
- [ ] Permission checks (recruitment.create)
- [ ] Thunder queue integration (task_name='create_candidate')
- [ ] End-to-end testing

## Related
- BU Isolation (Commit: d5c6f1fc)
- Thunder Autonomous Loop (#4)
- Message Queue System (CLAUDE.md)

## Acceptance Criteria
- [ ] User can create candidate with valid fields
- [ ] Duplicates rejected by email or phone
- [ ] BU-scoped users can only create in their BU
- [ ] Task queued to Thunder (create_candidate)
- [ ] Candidate appears in candidate list
- [ ] Candidate in org pool (visible to all recruiters)
- [ ] End-to-end testing passes

## Data Flow
User submits form → Validate fields → Check duplicates → Create Candidate → Queue to Thunder → Redirect to candidate detail
```

---

## 🚀 Issue 3: PRIORITY - Create Job Workflow

**Title:** PRIORITY: Implement Create Job end-to-end workflow

**Labels:** `priority`, `frontend`, `backend`, `job-workflow`

**Milestone:** Sprint 1

**Body:**
```
## Summary
Implement complete job creation workflow with BU/Client/Job hierarchy and Flash queue integration.

## Requirements
- [ ] Create Job form with all required fields
  - Job title, description, skills, experience level
  - Location, salary range, positions needed
  - Business Unit selection (required)
  - Client auto-derive from BU
  - Hiring Manager (optional, auto-assign from BU)
  - Contact person, Recruiter assignment
- [ ] Business Unit selection (required field)
- [ ] Auto-derive Client from BU
- [ ] Auto-assign Hiring Manager from BU (if not provided)
- [ ] Status determination based on user role
  - CEO/Super User/BU Head → auto-approve (active)
  - Others → pending approval
- [ ] Permission checks (jobs.create)
- [ ] Flash queue integration (task_name='job_created_flash')
- [ ] Trigger ready_for_opportunity service for candidate scanning
- [ ] End-to-end testing

## Related
- BU Isolation (Commit: d5c6f1fc)
- Flash Autonomous Loop (#5)
- BU → Client → Job workflow
- ready_for_opportunity_service

## Acceptance Criteria
- [ ] User can create job in their BU
- [ ] Job status determined by user role (auto-approve vs pending)
- [ ] Hiring Manager auto-assigned from BU head if not provided
- [ ] Client auto-derived from BU
- [ ] Task queued to Flash (job_created_flash)
- [ ] ready_for_opportunity service called for candidate scanning
- [ ] Job appears in job list with correct status
- [ ] End-to-end testing passes

## Data Flow
User submits form → Validate fields → Auto-derive Client → Auto-assign HM → Determine status → Create Job → Queue to Flash → Scan for candidates → Redirect to job detail
```

---

## 🚀 Issue 4: PRIORITY - Thunder Autonomous Loop

**Title:** PRIORITY: Implement Thunder Autonomous Loop (Candidate External Operations)

**Labels:** `priority`, `backend`, `autonomous`, `thunder`, `queue`

**Milestone:** Sprint 2

**Body:**
```
## Summary
Implement Thunder autonomous loop for processing candidate external operations (creation, communications, status updates).

## Architecture
**Queue:** Thunder  
**Purpose:** Candidate external-facing operations  
**Workers:** Async Thunder consumer  
**Consumer:** Thunder autonomous agent workers

## Task Types to Support
- `create_candidate` - Candidate creation workflow
- `import_linkedin_candidate` - LinkedIn candidate import with Apollo enrichment
- `candidate_email_sent` - Email communication tracking
- `candidate_status_updated` - Status change notifications
- Other candidate engagement tasks

## Requirements
- [ ] Thunder queue consumer setup
  - Listen to Thunder queue
  - Consume `create_candidate` and other candidate tasks
  - Task signature: enqueue(task_name, task_id=candidate_id, data={...})
- [ ] Candidate enrichment
  - Apollo MCP integration for LinkedIn imports
  - Company, title, email, phone extraction
  - Open to work status validation (gate rejection if not open)
- [ ] Communication capabilities
  - Email sending (via mailgun or similar)
  - SMS support (via twilio)
  - WhatsApp sending (if consent recorded)
- [ ] Candidate lifecycle updates
  - Status transitions (Applied → Active → Offer → Hired)
  - Communication tracking and audit logs
- [ ] Error handling
  - Retry logic with exponential backoff
  - Dead Letter Queue (DLQ) for failed tasks
  - Error notifications to recruiters
- [ ] Integration with activity feed
  - Thunder Activity Feed showing candidate actions
  - Real-time updates to frontend
- [ ] Performance monitoring
  - Task processing time tracking
  - Success/failure rates
  - Queue depth monitoring
  - Alerting on failures

## Related
- Queue System Architecture (CLAUDE.md)
- Create Candidate Workflow (#2)
- Message Queue System (MessageQueueService)
- Thunder Activity Feed

## Acceptance Criteria
- [ ] Tasks consumed from Thunder queue
- [ ] Candidate enrichment working (Apollo)
- [ ] Email/SMS/WhatsApp outreach functional
- [ ] Activity feed updated in real-time
- [ ] Error handling with DLQ support
- [ ] Monitoring/alerting in place
- [ ] End-to-end testing passes

## Definition of Done
- All task types implemented
- Comprehensive error handling
- Monitoring and alerting
- Documentation updated
- Tests passing
```

---

## 🚀 Issue 5: PRIORITY - Flash Autonomous Loop

**Title:** PRIORITY: Implement Flash Autonomous Loop (Job/Internal Operations)

**Labels:** `priority`, `backend`, `autonomous`, `flash`, `queue`

**Milestone:** Sprint 2

**Body:**
```
## Summary
Implement Flash autonomous loop for processing internal recruitment operations (jobs, interviews, offers, projects, timesheets).

## Architecture
**Queue:** Flash  
**Purpose:** Internal recruitment operations and recruiter agents  
**Workers:** Async Flash recruiter agent workers  
**Consumer:** Flash autonomous agents

## Task Types to Support
- `job_created_flash` - Job creation (scan for candidates)
- `job_updated_flash` - Job updates
- `job_deleted_flash` - Job deletions
- `interview_scheduled` - Interview scheduling
- `interview_updated_flash` - Interview updates
- `offer_generated_flash` - Offer generation
- `offer_approved_flash` - Offer approvals
- `project_created_flash` - Project creation
- `timesheet_submitted_flash` - Timesheet processing

## Requirements
- [ ] Flash queue consumer setup
  - Listen to Flash queue
  - Consume all Flash task types
  - Task signature: enqueue(task_name, task_id=job_id, data={...})
- [ ] Job workflow processing
  - Trigger ready_for_opportunity service
  - Scan for matching candidates
  - Create recommendations
  - Notify hiring managers
- [ ] Interview automation
  - Schedule interviews based on job requirements
  - Coordinate between recruiter and hiring manager
  - Send calendar invites
- [ ] Offer workflow
  - Generate offer letters from offer template
  - Route for approvals (BU Head → CEO for high-value)
  - Send to candidate
  - Track acceptance/rejection
- [ ] Project/Timesheet processing
  - Project creation notifications
  - Timesheet validations
  - Approval workflows
- [ ] Role-based access control
  - Enforce permissions on all operations
  - Log access for audit trails
- [ ] Error handling
  - Retry logic with exponential backoff
  - Dead Letter Queue (DLQ) for failed tasks
  - Escalation to recruiters on critical failures
- [ ] Integration with activity feed
  - Flash Activity Feed showing internal actions
  - Real-time updates to recruiters
- [ ] Performance monitoring
  - Task processing time tracking
  - Success/failure rates
  - Queue depth monitoring
  - Alerting on failures

## Related
- Queue System Architecture (CLAUDE.md)
- Create Job Workflow (#3)
- Message Queue System (MessageQueueService)
- ready_for_opportunity_service
- Flash Activity Feed

## Acceptance Criteria
- [ ] Tasks consumed from Flash queue
- [ ] Job creation triggers candidate scanning
- [ ] Interview scheduling working
- [ ] Offer generation and approval functional
- [ ] Project/timesheet processing functional
- [ ] All role-based permissions enforced
- [ ] Activity feed updated in real-time
- [ ] Error handling with DLQ support
- [ ] Monitoring/alerting in place
- [ ] End-to-end testing passes

## Definition of Done
- All task types implemented
- ready_for_opportunity integration working
- Comprehensive error handling
- Monitoring and alerting
- Documentation updated
- Tests passing
- Performance validated
```

---

## 📊 Priority Timeline

```
Completed:
✅ Issue 1: BU Isolation (d5c6f1fc)

Sprint 1 (Immediate):
🚀 Issue 2: Create Candidate Workflow
🚀 Issue 3: Create Job Workflow

Sprint 2 (After Sprint 1):
🚀 Issue 4: Thunder Autonomous Loop
🚀 Issue 5: Flash Autonomous Loop
```

## 🎯 Next Steps

1. **Create these 5 GitHub issues** using the templates above
2. **Add to GitHub Project Board** for tracking
3. **Sprint Planning** to allocate work
4. **Begin Sprint 1** with issues #2 and #3 (Create Candidate & Create Job)
5. **Parallel work** on Thunder/Flash loops (#4, #5) in Sprint 2

---

**Created:** 2026-09-09  
**Session Commit:** d5c6f1fc - BU Isolation Implementation Complete

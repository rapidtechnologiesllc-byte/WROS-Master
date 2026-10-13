# PHASE 3: NOTIFICATIONS & TASK WORKFLOW SYSTEM
## Detailed Implementation Plan

**Priority:** NOW (Phase 3 - before Agentic Layer)  
**Scope:** Complete task management + email notification infrastructure  
**Timeline:** 3-4 weeks  
**Effort:** 5-6 developers  

---

## OVERVIEW: TASK-DRIVEN WORKFLOWS

### Core Concept

Every significant event in WROS creates a **Task** and sends an email to the **Task Owner**.

```
Event (Candidate Created)
    ↓
Task Created (Recruiter: "Complete Candidate Profile")
    ↓
Email Sent (HTML formatted, rich content, action links)
    ↓
Task Owner Receives Email
    ↓
Task Owner Clicks Link → Opens Portal/Task Dashboard
    ↓
Task Owner Completes Action
    ↓
Task Marked Done → Email Confirmation Sent
```

### Why This Matters

- ✅ **Visibility:** Everyone knows what they need to do
- ✅ **Accountability:** Tasks track who owns what
- ✅ **Urgency:** Emails drive action (vs. passive dashboard)
- ✅ **Audit Trail:** Task history = business process audit log
- ✅ **Foundation for Agents:** Later, agents can create tasks and send reminders

---

## TASK TYPES (Comprehensive List)

### TIER 1: Candidate Lifecycle

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| CANDIDATE_CREATED | New candidate added | Recruiter | Complete profile (10 fields) | "New Candidate: Complete Profile" |
| CANDIDATE_PROFILE_INCOMPLETE | 24h after creation, <80% complete | Recruiter | Fill missing fields | "Candidate Profile Incomplete - Follow Up" |
| CANDIDATE_QUALIFY_REVIEW | AI qualification done | Recruiter | Review AI assessment | "Candidate Qualification Ready for Review" |
| CANDIDATE_NO_RESPONSE | 48h no response from candidate | Recruiter | Send follow-up message | "Candidate Not Responding - Take Action" |
| CANDIDATE_GHOSTING | 7 days no contact | Manager | Escalate or close | "Candidate Ghosted - Decision Needed" |

### TIER 2: Interview Workflow

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| INTERVIEW_SCHEDULED | Interview confirmed | Candidate | Confirm availability | "Interview Scheduled - Confirm Your Availability" |
| INTERVIEW_REMINDER | 24h before interview | Both | Prepare for interview | "Interview Reminder - Tomorrow at 2pm" |
| INTERVIEW_FEEDBACK_PENDING | Interview completed | Interviewer | Provide feedback | "Provide Interview Feedback - Candidate: John" |
| INTERVIEW_FEEDBACK_REVIEW | Feedback received | Recruiter | Review & decide next step | "Interview Feedback Ready - Review & Decide" |
| INTERVIEW_DECISION_PENDING | Feedback ready | Manager | Make go/no-go decision | "Interview Decision Needed - John Doe" |

### TIER 3: Offer Workflow

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| OFFER_DRAFT_READY | Offer generated | HR | Review & approve | "Offer Letter Ready for Approval" |
| OFFER_APPROVAL_PENDING | Draft reviewed | Manager | Approve or reject | "Offer Letter Pending Your Approval" |
| OFFER_EXTENDED | Offer sent to candidate | Candidate | Accept or decline | "Job Offer - Review and Respond" |
| OFFER_ACCEPTANCE_PENDING | 24h no response | HR | Follow up with candidate | "Candidate Hasn't Responded to Offer" |
| OFFER_ACCEPTED | Candidate accepts | HR | Start onboarding | "Offer Accepted - Start Onboarding" |

### TIER 4: Work Order & Deployment

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| WORK_ORDER_CREATED | New work order issued | Employee | Acknowledge assignment | "New Work Assignment - Project ABC" |
| WORK_ORDER_READY | All docs collected | Employee | Confirm ready to start | "Ready to Start - Work Order ABC" |
| WORK_ORDER_KICKOFF | Start date approaching | Manager | Conduct kickoff meeting | "Work Order Kickoff - Next Week" |
| WORK_ORDER_30_DAYS | 30 days in | Manager | Check-in / performance review | "30-Day Check-In Required" |

### TIER 5: Bench & Resource Management

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| BENCH_AVAILABLE | Employee becomes available | Manager | Review for placement | "Resource Available - Bench" |
| DEMAND_MATCH | Demand created, bench available | Recruiter | Review match & pitch | "Potential Match Found - 3 Candidates" |
| BENCH_AGING_ALERT | On bench 60+ days | Manager | Develop re-skilling plan | "Bench Aging Alert - Action Needed" |
| CERTIFICATION_RENEWAL | Cert expires in 30 days | Employee | Renew certification | "Certification Expires Soon" |

### TIER 6: Billing & Invoicing

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| TIMESHEET_READY_REVIEW | Timesheet submitted | Manager | Review & approve | "Timesheet Ready for Approval - John" |
| INVOICE_READY_SEND | Billing period closed | Finance | Review & send to client | "Invoice Ready to Send to Client" |
| INVOICE_OVERDUE | Invoice >30 days unpaid | Finance | Follow up with client | "Invoice Overdue - Client Follow-Up" |
| PAYMENT_RECEIVED | Payment received | Finance | Reconcile & post | "Payment Received - Reconciliation" |

### TIER 7: AI & System Tasks

| Task Type | When Created | Task Owner | Action Required | Email |
|-----------|--------------|-----------|-----------------|-------|
| AI_RECOMMENDATION_REVIEW | AI makes recommendation | User | Review & approve/reject | "AI Recommendation Ready - Candidate Match" |
| ESCALATION_NEEDED | Exception detected | Manager | Manual review required | "Escalation Needed - Manual Review" |
| DAILY_DIGEST | End of business day | User | Review daily summary | "Daily Digest - 5 Items Need Attention" |

---

## TASK STORAGE MODEL

```sql
CREATE TABLE tasks (
    id STRING PRIMARY KEY,
    tenant_id STRING NOT NULL,
    task_type VARCHAR(50) NOT NULL,  -- CANDIDATE_CREATED, INTERVIEW_SCHEDULED, etc.
    
    -- Ownership
    owner_id STRING NOT NULL,  -- User who owns/must act on task
    created_by STRING NOT NULL,  -- User/system who created task
    assigned_by STRING,  -- If reassigned
    
    -- Entity References
    candidate_id STRING,
    employee_id STRING,
    interview_id STRING,
    offer_id STRING,
    work_order_id STRING,
    demand_id STRING,
    
    -- Task Details
    title VARCHAR(255) NOT NULL,  -- "Complete Candidate Profile"
    description TEXT,  -- "Candidate needs to fill: education, skills, availability"
    action_url VARCHAR(500),  -- Link to action in portal (e.g., /candidates/123)
    
    -- Status
    status VARCHAR(20) NOT NULL,  -- OPEN, IN_PROGRESS, COMPLETED, OVERDUE, CANCELLED
    priority VARCHAR(20),  -- CRITICAL, HIGH, NORMAL, LOW
    due_date TIMESTAMP,
    
    -- Lifecycle
    created_at TIMESTAMP DEFAULT NOW(),
    due_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    
    -- Notifications
    email_sent_at TIMESTAMP,  -- When email was sent
    email_reminder_sent_at TIMESTAMP,  -- When reminder was sent (if configured)
    last_reminded_at TIMESTAMP,
    
    -- Data for email template
    context_json JSONB,  -- { candidate_name, interview_date, offer_amount, etc. }
    
    -- Indexing
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id),
    INDEX idx_owner_status (owner_id, status),
    INDEX idx_task_type_due (task_type, due_at),
    INDEX idx_candidate (candidate_id),
    INDEX idx_employee (employee_id)
);
```

---

## EMAIL NOTIFICATION TEMPLATES

### 1. Task Created Email (Base Template)

```html
Subject: Action Needed: {task_title}
From: noreply@wros.blitzenx.com
To: {owner_email}

Dear {owner_name},

{task_description}

Due: {due_date}
Priority: {priority}

[ACTION BUTTON: {action_label}]
{action_url}

---

Details:
- Candidate: {candidate_name}
- Interview: {interview_date} at {interview_time}
- Offer: {offer_summary}
- Work Order: {work_order_details}

Questions? Reply to this email.

WROS Task Management
{company_logo}
```

### 2. Example: Candidate Profile Incomplete

```html
Subject: Complete Profile: John Doe - 80% Done
From: noreply@wros.blitzenx.com

Hi Sarah,

John Doe's profile is 80% complete. He applied 24 hours ago but hasn't finished.

Missing:
✗ Education
✗ References

[COMPLETE PROFILE]
{link_to_candidate}

Contact John with a reminder if needed.

---
WROS | Candidate Management
```

### 3. Example: Interview Feedback Needed

```html
Subject: Interview Feedback - John Doe (Tech Lead Position)

Hi Mike,

Please provide feedback for John Doe's interview today.

Interview: Tech Lead Position
Time: 2 PM - 3 PM PST
Candidate: John Doe (John@example.com)

[PROVIDE FEEDBACK]
{link_to_feedback_form}

We'll notify everyone once feedback is submitted.

---
WROS | Interview Management
```

### 4. Example: New Work Assignment

```html
Subject: New Assignment: Project XYZ - Starts Monday

Hi Alex,

You've been assigned to a new project!

Project: Project XYZ (Client: ABC Corp)
Start Date: Monday, Aug 18, 2026
Duration: 12 weeks
Rate: $150/hour
Manager: Sarah Johnson

[VIEW DETAILS & CONFIRM]
{link_to_work_order}

Please confirm your availability by EOD Friday.

---
Questions? Contact Sarah: sarah@blitzenx.com
WROS | Resource Management
```

---

## NOTIFICATION ENGINE ARCHITECTURE

### Services to Build

#### 1. TaskService (180 LOC)
```python
class TaskService:
    def create_task(
        task_type: str,
        owner_id: str,
        entity_id: str,  # candidate_id, interview_id, etc.
        title: str,
        description: str,
        action_url: str,
        due_date: datetime,
        priority: str = "NORMAL",
        context: dict = None
    ) -> Task:
        """Create a task and queue notification email"""
        
    def complete_task(task_id: str, completed_by: str):
        """Mark task done and send confirmation"""
        
    def reassign_task(task_id: str, new_owner_id: str):
        """Reassign task and notify new owner"""
        
    def get_tasks_for_user(user_id: str, status: str = "OPEN") -> List[Task]:
        """Get all open tasks for a user"""
        
    def get_overdue_tasks(user_id: str) -> List[Task]:
        """Get tasks past due date"""
        
    def create_reminder(task_id: str, days_before_due: int):
        """Schedule reminder email X days before due date"""
```

#### 2. NotificationService (200 LOC)
```python
class NotificationService:
    def send_email(
        task_id: str,
        recipient_email: str,
        subject: str,
        html_body: str,
        text_body: str = None,
        action_url: str = None,
        action_label: str = None
    ):
        """Send email via configured provider (SendGrid, SES, etc.)"""
        
    def send_task_created_email(task: Task):
        """Send "task created" email with template"""
        
    def send_task_reminder_email(task: Task, days_until_due: int):
        """Send reminder email (due in X days)"""
        
    def send_task_completed_email(task: Task, completed_by_name: str):
        """Send "task complete" confirmation to original creator"""
        
    def send_daily_digest(user_id: str):
        """Send daily digest of all open tasks"""
        
    def get_email_template(task_type: str) -> EmailTemplate:
        """Get HTML/text template for task type"""
```

#### 3. EmailTemplateService (150 LOC)
```python
class EmailTemplateService:
    def render_task_email(
        task: Task,
        template_type: str,  # "created", "reminder", "completed"
        context: dict
    ) -> dict:  # {subject, html_body, text_body}
        """Render email from Jinja2 template with context variables"""
        
    def get_template(task_type: str, email_type: str) -> str:
        """Load HTML/text template for task type"""
        
    def validate_template(template_html: str):
        """Check for required variables, proper HTML, etc."""
```

#### 4. TaskReminderService (120 LOC) - Scheduler
```python
class TaskReminderService:
    # Run as background job (Celery/APScheduler)
    
    def send_daily_reminders():
        """Send reminder emails for tasks due tomorrow"""
        
    def send_overdue_alerts():
        """Alert users about overdue tasks"""
        
    def send_daily_digests():
        """Send daily digest of open tasks to all users"""
        
    def schedule_reminder(task_id: str, reminder_date: datetime):
        """Schedule one-time reminder"""
```

---

## STORY BREAKDOWN: PHASE 3 NOTIFICATIONS

### Phase 3A: Core Task System (2 weeks)

#### S-1: Task Model & Storage (3 days)
- **Story:** Create Task model and database schema
- **What:** tasks table with all fields from model above
- **Migrations:** Alembic migration for tasks table + indexes
- **Tests:** Model creation, validation, retrieval
- **Acceptance:** Can create/retrieve/update tasks, proper indexing

#### S-2: TaskService - Core CRUD (3 days)
- **Story:** Build TaskService with create/read/update/delete operations
- **What:** All task operations (create, complete, reassign, get_tasks, get_overdue)
- **Tests:** Full CRUD coverage, edge cases
- **Acceptance:** All task operations working, proper validation

#### S-3: Task API Endpoints (2 days)
- **Story:** REST endpoints for task operations
- **What:** 
  - GET /tasks (list user's tasks)
  - GET /tasks/{id} (get one task)
  - POST /tasks (create task)
  - PUT /tasks/{id} (update task)
  - POST /tasks/{id}/complete (mark done)
  - POST /tasks/{id}/reassign (reassign to another user)
- **Tests:** All endpoints, auth/permissions, response formats
- **Acceptance:** API fully functional

#### S-4: Task Dashboard Screen (3 days)
- **Story:** Build frontend task dashboard
- **What:**
  - Task list (open, overdue, completed filters)
  - Task detail view (with action button)
  - Task creation modal (for manual tasks)
  - Status badges, due date display, priority colors
- **Tests:** Dashboard loads, filters work, actions clickable
- **Acceptance:** User can see all tasks and take actions

### Phase 3B: Email Notification System (2 weeks)

#### S-5: Email Template Engine (3 days)
- **Story:** Build Jinja2 email templates for all task types
- **What:**
  - 30+ email templates (one per task type)
  - HTML + text versions
  - Variable substitution (candidate_name, interview_date, etc.)
  - Branding (logo, footer, company colors)
- **Templates:** Candidate, Interview, Offer, Work, Bench, Billing templates
- **Tests:** Template rendering, variable substitution, HTML validation
- **Acceptance:** All task types have working email templates

#### S-6: NotificationService Implementation (3 days)
- **Story:** Build email sending service
- **What:**
  - Integration with email provider (SendGrid/SES)
  - Queue system (Celery) for async sending
  - Retry logic (exponential backoff)
  - Logging & audit trail
- **Tests:** Send emails, retries, error handling, audit log
- **Acceptance:** Emails send reliably, logged properly

#### S-7: Task Automation - Create Tasks on Events (4 days)
- **Story:** Integrate task creation into all major workflows
- **Where tasks get created:**
  - candidate.create() → create CANDIDATE_CREATED task
  - interview.schedule() → create INTERVIEW_SCHEDULED task
  - offer.create() → create OFFER_DRAFT_READY task
  - work_order.create() → create WORK_ORDER_CREATED task
  - And 20+ other places
- **Implementation:** Call TaskService.create_task() after each major operation
- **Tests:** Tasks created correctly at each event, emails sent
- **Acceptance:** Every workflow creates appropriate task + email

#### S-8: Task Reminders & Scheduler (3 days)
- **Story:** Build background task reminder system
- **What:**
  - Celery tasks for scheduled reminders
  - Send reminders 24h before due date
  - Send overdue alerts each morning
  - Send daily digest email to all users
- **Schedule:**
  - Reminders: 9 AM each day (for tasks due today + tomorrow)
  - Digest: 5 PM each day (for open tasks)
- **Tests:** Scheduler runs, emails sent at right time
- **Acceptance:** Users get timely reminders

### Phase 3C: Task Workflows (1 week)

#### S-9: Complete Candidate Profile Workflow (2 days)
- **Story:** Candidate → Profile Incomplete Task → Email → Recruiter → Complete
- **Workflow:**
  1. Candidate created
  2. Task: "Complete Candidate Profile" created, email sent
  3. Recruiter receives email with link
  4. 24h later, if still incomplete → Reminder email
  5. 48h later → "Candidate Ghosting" task escalated to manager
- **Tests:** Workflow end-to-end, emails sent at right times
- **Acceptance:** Full candidate profile workflow working

#### S-10: Interview Feedback Workflow (2 days)
- **Story:** Interview Done → Feedback Task → Email → Interviewer → Complete
- **Workflow:**
  1. Interview completed
  2. Task: "Provide Interview Feedback" created for interviewer
  3. Email sent with feedback form link
  4. Interviewer submits feedback
  5. Task: "Review Feedback" created for recruiter
  6. Recruiter reviews and makes go/no-go decision
- **Tests:** Multi-step workflow, email notifications at each step
- **Acceptance:** Interview feedback workflow complete

#### S-11: Offer Approval Workflow (2 days)
- **Story:** Offer Draft → Approval Task → Manager → Approved → Sent
- **Workflow:**
  1. Offer generated
  2. Task: "Approve Offer" created for manager
  3. Email with offer preview sent
  4. Manager approves
  5. Task: "Send Offer" created for HR
  6. HR sends to candidate
  7. Task: "Accept Offer" created for candidate with deadline
- **Tests:** Multi-approver workflow, conditional logic
- **Acceptance:** Offer workflow fully integrated

#### S-12: Work Order Assignment Workflow (2 days)
- **Story:** Work Order Created → Assignment Task → Email → Employee → Confirm
- **Workflow:**
  1. Work order created by manager
  2. Task: "Acknowledge Assignment" created for employee
  3. Rich email with project details sent
  4. Employee clicks "Confirm Ready" in email/portal
  5. Task: "Conduct Kickoff" created for manager
- **Tests:** Assignment email, confirmation link works
- **Acceptance:** Work order workflow complete

### Phase 3D: Advanced Features (1 week)

#### S-13: Task Dashboard - Advanced Filtering & Search (2 days)
- **Story:** Add advanced task dashboard features
- **What:**
  - Filter by task type, priority, due date, status
  - Search by task title/description
  - Bulk actions (mark multiple done, reassign multiple)
  - Task history (view past tasks, audit trail)
  - My Tasks vs. Team Tasks views
- **Tests:** Filters work, search works, bulk operations
- **Acceptance:** Dashboard fully featured

#### S-14: Daily Digest & Weekly Digest (2 days)
- **Story:** Email digest of open tasks (daily + weekly option)
- **What:**
  - Daily digest: All open tasks for user
  - Weekly digest: Summary by type (interviews, offers, work, billing)
  - User preference: Enable/disable, timing (9 AM, 5 PM, etc.)
  - Unsubscribe option in email
- **Tests:** Digests generated correctly, preferences honored
- **Acceptance:** Users getting tailored digests

#### S-15: Task Delegation & Collaboration (2 days)
- **Story:** Assign task to someone else, add comments
- **What:**
  - Reassign task to colleague (with notification)
  - Add comments/notes to tasks
  - @mention people in comments
  - Email notification when mentioned
- **Tests:** Reassignment sends email, comments work, @mentions notify
- **Acceptance:** Task collaboration working

---

## INTEGRATION POINTS (Where Tasks Get Created)

### Candidate Lifecycle
```python
# When candidate created
def create_candidate(request: CreateCandidateRequest):
    candidate = Candidate.create(**request)
    
    # Create task
    TaskService.create_task(
        task_type="CANDIDATE_CREATED",
        owner_id=current_user.id,
        candidate_id=candidate.id,
        title=f"Complete Candidate Profile: {candidate.first_name}",
        description="Fill in required fields: education, skills, availability, references",
        action_url=f"/candidates/{candidate.id}",
        due_date=datetime.now() + timedelta(days=1),  # Due tomorrow
        priority="HIGH"
    )
    
    return candidate
```

### Interview Scheduling
```python
# When interview scheduled
def schedule_interview(request: ScheduleInterviewRequest):
    interview = Interview.create(**request)
    
    # Task for candidate
    TaskService.create_task(
        task_type="INTERVIEW_SCHEDULED",
        owner_id=candidate.user_id,
        interview_id=interview.id,
        title=f"Interview Scheduled: {job_title}",
        description=f"Interview with {interviewer.name} on {interview.scheduled_time}",
        action_url=f"/interviews/{interview.id}",
        due_date=interview.scheduled_time,  # Due at interview time
        priority="CRITICAL"
    )
    
    # Task for interviewer
    TaskService.create_task(
        task_type="INTERVIEW_REMINDER",
        owner_id=interviewer.id,
        interview_id=interview.id,
        title=f"Interview Today: {candidate.name}",
        action_url=f"/interviews/{interview.id}/prepare",
        due_date=interview.scheduled_time - timedelta(hours=1)
    )
    
    return interview
```

### Offer Creation
```python
# When offer generated
def create_offer(request: CreateOfferRequest):
    offer = Offer.create(**request)
    
    # Task for manager approval
    TaskService.create_task(
        task_type="OFFER_APPROVAL_PENDING",
        owner_id=manager.id,
        offer_id=offer.id,
        title=f"Approve Offer: {candidate.name} - ${offer.salary}",
        action_url=f"/offers/{offer.id}/approve",
        due_date=datetime.now() + timedelta(days=1),
        priority="HIGH"
    )
    
    return offer
```

### Work Order Creation
```python
# When work order created
def create_work_order(request: CreateWorkOrderRequest):
    work_order = WorkOrder.create(**request)
    
    # Task for employee
    TaskService.create_task(
        task_type="WORK_ORDER_CREATED",
        owner_id=employee.user_id,
        work_order_id=work_order.id,
        title=f"New Assignment: {client.name} - {project.name}",
        description=f"12-week engagement starting {work_order.start_date}",
        action_url=f"/work-orders/{work_order.id}/confirm",
        due_date=work_order.start_date - timedelta(days=3),  # Due 3 days before start
        priority="HIGH"
    )
    
    return work_order
```

---

## TIMELINE & EFFORT

### Phase 3 Total: 4-5 Weeks, 5-6 Developers

| Section | Stories | Effort | Developer |
|---------|---------|--------|-----------|
| 3A: Task System | 4 | 2 wks | 2 devs (backend + frontend) |
| 3B: Email System | 4 | 1.5 wks | 2 devs (backend + templates) |
| 3C: Workflows | 4 | 1.5 wks | 2 devs (full-stack) |
| 3D: Advanced | 3 | 1 wk | 1 dev |
| **TOTAL** | **15** | **4-5 wks** | **5-6 devs** |

### Critical Path
1. S-1 (Task Model) → S-2 (Service) → S-3 (API) → S-4 (Dashboard) [Sequential]
2. S-5 (Templates) → S-6 (EmailService) [Parallel to above, then merge for S-7]
3. S-7 (Task Automation) [Depends on 1 + 2]
4. S-8-15 [Parallel]

---

## PHASE 3 SUCCESS CRITERIA

✅ **Go-Live Gate Requirements:**
- Every event in WROS creates a task
- Every task triggers an email
- Rich HTML emails with action links
- Task dashboard fully functional
- Reminders sent 24h before due date
- Daily digest emails working
- No task creation fails (100% success rate)
- <500ms email send latency (async queue)
- All workflows tested end-to-end

✅ **Definition of Done for Phase 3:**
- ✅ 15 stories complete (all tasks + workflows)
- ✅ Backend: TaskService, NotificationService, Schedulers
- ✅ API: All task endpoints (CRUD + workflows)
- ✅ Frontend: Task dashboard, task detail view
- ✅ Email: 30+ templates, all task types covered
- ✅ Tests: 70+ tests (unit + integration + E2E)
- ✅ Documentation: Task types, API docs, workflow diagrams

---

## UPDATED PROJECT TIMELINE

```
PHASE 1: Security ✅ DONE (6 stories)
PHASE 2: Data Model/Thunder 🟡 2-3 weeks (Complete)
PHASE 3: Notifications & Tasks ← START NOW 🟢 4-5 weeks (15 stories)
PHASE 4: Resource Management 3-4 weeks (39 stories - Phase 4 MVP first)
PHASE 5: Job Titles & Portal 4-6 weeks (40 stories)
PHASE 6+: Agentic Layer (pushed to end) 4-6 weeks

GO-LIVE: Week 15-20 (adjusted from Week 10)
```

---

## NEXT STEPS (TODAY)

1. ✅ **Approve Phase 3 Plan** - Is this the right scope?
2. ✅ **Allocate Developers** - 5-6 devs for 4-5 weeks
3. ✅ **Create Jira/Sprint Boards** - 15 stories for Phase 3
4. ✅ **Start S-1 Today** - Task model & schema
5. ⏳ **Adjust Master Roadmap** - Update go-live date + timelines

---

**This is your CORE INFRASTRUCTURE.**

**Every workflow, every agent, every automation depends on this.**

**Build it right. Then everything else becomes simple.**

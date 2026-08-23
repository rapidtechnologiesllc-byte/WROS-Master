# Decisions LOCKED + Implementation Specifications

**Date:** 2026-08-09  
**Status:** All 8 decisions confirmed - Ready for frontend development  
**Timeline:** 5-6 weeks to production  
**Budget:** $250K-300K approved

---

## DECISIONS CONFIRMED ✅

### Decision 1: Email Strategy - HYBRID ✅
```
Rule 1: URGENT Role (High Priority + Early Start Date)
├─ Timing: Immediate email sent to all employees
├─ Trigger: Job marked as "URGENT" in create job form
├─ Content: Job details + $1,000-$2,000 bonus (typically)
└─ CTA: "Refer someone TODAY for this urgent role!"

Rule 2: STANDARD Role (Medium/Low Priority + Later Start)
├─ Timing: Included in daily digest (9 AM every business day)
├─ Trigger: Jobs marked as "STANDARD" or "LOW" priority
├─ Content: Summarized in daily email with 3-5 other jobs
└─ Bonus: $500-$750 (typically)

Rule 3: ESCALATING EMAIL (Urgent Role + No Onboarding)
├─ Trigger: Job start date approaching + no candidate in onboarding
├─ Timing: Daily reminder email to team (mornings)
├─ Duration: Last 7 days before start date
├─ Content: "URGENT: [Job Title] starts in [X days] - We need a referral!"
├─ Escalation: Day 7, Day 5, Day 3, Day 1 (increasing emphasis)
└─ Target: Hiring team + department team members
```

**Implementation:**
- Job Creator sees: Priority dropdown (Urgent/Standard/Low)
- Email Service: Checks priorities nightly
- Escalation Engine: Monitors start dates, sends escalating emails
- Tracking: Logs which employees clicked, opened, applied

---

### Decision 2: Email Frequency - FIXED POLICY ✅
```
NO job creator choice - Automatic based on priority:

09:00 AM Daily:
├─ Standard/Low priority jobs summary (5-10 jobs)
├─ Sent to: All active employees
├─ Template: "This week's referral opportunities"
└─ Opt-out: Employee email preferences screen

IMMEDIATE (within 1 minute of creation):
├─ Urgent priority jobs (1 per email)
├─ Sent to: All active employees + hiring team
├─ Template: "URGENT OPPORTUNITY - Referral Bonus $[Amount]"
└─ No opt-out: Can unsubscribe from "Urgent" only

ESCALATING (7-1 days before start):
├─ Daily reminders if no candidate in onboarding
├─ Sent to: Hiring team + department head
├─ Template: "CRITICAL: [Role] needs a referral (starts in [X] days)"
└─ Escalation: Increases frequency as date approaches
```

**Configuration:**
```python
EMAIL_POLICY = {
    "URGENT": {
        "trigger": "immediate",
        "recipients": "all_employees",
        "bonus_range": "$1,000-$2,000"
    },
    "STANDARD": {
        "trigger": "daily_digest_9am",
        "recipients": "all_employees",
        "bonus_range": "$500-$750"
    },
    "LOW": {
        "trigger": "daily_digest_9am",
        "recipients": "interested_employees",  # Opt-in based on job type
        "bonus_range": "$250-$500"
    }
}

ESCALATION_POLICY = {
    "enabled": True,
    "trigger_days_before_start": 7,
    "recipients": "hiring_team",  # Plus department head
    "frequency": "daily",
    "escalation": ["Day 7", "Day 5", "Day 3", "Day 1"]  # Increasing emphasis
}
```

---

### Decision 3: Duplicate Handling - AUTO-LINK ✅
```
When employee refers candidate that already exists:

Step 1: Detection
├─ System matches by: Email (exact) OR Name (95%+ similarity)
├─ If found: "This candidate is already in our system!"
└─ Action: Show candidate's history

Step 2: Previous History Display
├─ Show: Previous applications (job, date, status, reason)
├─ Show: Feedback from previous interviews
├─ Show: Skills assessment if done
└─ AI Recommendation: "Good fit for this role?" (confidence %)

Step 3: Candidate Ownership Assignment (CRITICAL)
├─ Current Ownership: Previous recruiter (no bonus on rehire)
└─ NEW Ownership: THIS REFERRAL (employee gets bonus if hired!)
│
├─ Database: CandidateOwnership
│  ├─ Old: recruiter_id = "recruiter_123"
│  ├─ New: referral_id = "ref_456"  # Links to THIS referral
│  ├─ Change: referral_employee_id = "emp_789"  # Employee earning bonus
│  └─ Note: "Candidate re-referred by emp_789 on 2026-08-09"

Step 4: Bonus Eligibility Rule
├─ If candidate hired from THIS referral:
│  ├─ Ownership = THIS referral
│  ├─ Bonus = Paid to THIS referring employee
│  └─ No bonus to original recruiter/sourcers
│
└─ If candidate hired from DIFFERENT referral first:
   ├─ Ownership = Other referral
   ├─ Bonus = Paid to OTHER referring employee
   └─ THIS referral = 0 bonus (but documented)

Step 5: Employee Communication
├─ Title: "Duplicate Candidate - You Still Get the Bonus!"
├─ Message:
│  ├─ "Jane Smith was in our system from 2026-05-15"
│  ├─ "She was rejected for Guidewire Dev role (skill gap)"
│  ├─ "But she's PERFECT for Solutions Architect role!"
│  ├─ "If hired, YOU get the $750 bonus"
│  ├─ "No penalty, we encourage reconsidering candidates"
│  └─ "Previous feedback: [snippet from interview]"
└─ Tone: Positive, encouraging re-submissions
```

**Database Changes Required:**
```python
# UPDATE: CandidateOwnership model
class CandidateOwnership(Base):
    # Existing
    candidate_id = Column(String, ForeignKey("candidate.id"))
    recruiter_id = Column(String, nullable=True)  # Original recruiter
    
    # NEW: Support multiple ownership types
    ownership_type = Column(String)  # "RECRUITER", "REFERRAL", "INTERNAL_SOURCE"
    
    # NEW: Link to referral if applicable
    referral_id = Column(String, ForeignKey("employee_referral.referral_id"), nullable=True)
    
    # NEW: Track why ownership changed
    previous_owner_id = Column(String, nullable=True)
    ownership_changed_date = Column(DateTime, nullable=True)
    ownership_change_reason = Column(String)  # "DUPLICATE_REFERRAL", "ESCALATION", etc.
    
    # NEW: Note field for documentation
    notes = Column(Text)  # "Candidate re-referred by emp_789, was rejected as Guidewire Dev"

# Link: EmployeeReferral should track if it's a re-referral
class EmployeeReferral(Base):
    # Existing fields...
    
    # NEW: Track if this is a duplicate
    is_duplicate_referral = Column(Boolean, default=False)
    previous_application_id = Column(String, nullable=True)  # Link to original application
    previous_rejection_reason = Column(String, nullable=True)
    
    # Track ownership
    bonus_eligible = Column(Boolean, default=True)  # Will they get bonus if hired?
    bonus_eligible_reason = Column(String)  # "First referral", "Previous hire via other referral", etc.
```

---

### Decision 4: External Referrals - FORM ONLY ✅
```
MVP: Simple form, no personalized links yet

Form: "Refer a Candidate"
├─ Job: [Dropdown - Select job to refer for]
├─ Candidate Name: [Text input]
├─ Candidate Email: [Text input]
├─ Candidate Phone: [Phone input]
├─ How you know them: [Text - optional]
├─ Why recommend them: [Textarea - optional]
├─ Resume upload: [File upload - optional]
├─ LinkedIn: [URL - optional]
└─ Submit button

Source Tracking:
├─ Source: EMPLOYEE_REFERRAL (always - whether from email link or form)
├─ Referral Method: FORM / EMAIL_LINK / DIRECT  (tracks how they referred)
├─ External: True/False (is candidate external or internal employee?)
└─ Campaign: [Optional - which job posting they referred for]

No Personalized Links (MVP):
├─ Links deferred to Phase 2
├─ Reason: Simpler MVP, faster to market
├─ Timeline: Add in week 7-8 after MVP launch
└─ Savings: 1 week development time
```

**Feature Scope:**
- ✅ Refer candidate via form
- ✅ Track external vs internal referrals
- ✅ Pre-fill job from email link (if clicked)
- ❌ Personalized sharing links (Phase 2)
- ❌ Link analytics dashboard (Phase 2)

---

### Decision 5: Dashboard Priority - EMPLOYEE FIRST ✅
```
Build Order:

WEEK 1-2: EMPLOYEE PORTAL (CRITICAL)
├─ Referral center portal
├─ Submit referral form
├─ My referrals tracking screen
├─ Bonus tracker screen
└─ All employees can refer and track

WEEK 2-3: EMAIL + NOTIFICATIONS
├─ Email notifications (immediate/digest/escalating)
├─ In-app notification center
├─ Status update emails
└─ Employees stay engaged

WEEK 3-4: DUPLICATE HANDLING
├─ Duplicate detection
├─ Previous application history UI
├─ AI recommendation scoring
├─ Candidate ownership assignment
└─ Critical for data integrity

WEEK 4-5: FINANCE WORKFLOW
├─ Pending bonuses queue
├─ Approval workflow (Finance + HR + Batch)
├─ Payment processing UI
├─ CSV export for payroll
└─ Critical for compliance/payments

WEEK 5-6: POLISH + ROLE DASHBOARDS
├─ CEO/Executive dashboard
├─ BU Head dashboard
├─ HR Manager dashboard
├─ Bug fixes, edge cases
└─ Ready for production
```

---

### Decision 6: Payroll Integration - CSV EXPORT + DASHBOARD ✅
```
Method: CSV Export (not API)

Finance Workflow:

Step 1: REVIEW PENDING BONUSES
└─ GET /referrals/dashboard/referrals (Finance role)
   ├─ Shows: 5 pending bonuses, $4,500 total
   ├─ Displays: Employee, candidate, amount, hire date
   └─ Actions: Approve, Reject, Hold, Batch actions

Step 2: APPROVE BONUSES
├─ Finance reviews each bonus for validation
├─ Checks: Valid employee, candidate hired, amount correct
├─ Actions: Approve (default), Reject, Hold for review
└─ Batch: "Approve all pending bonuses"

Step 3: EXPORT TO CSV
├─ Button: "Export for Payroll"
└─ CSV Format:
   ├─ Column 1: Employee ID (or Employee Email)
   ├─ Column 2: Bonus Amount (in dollars, e.g., 750.00)
   ├─ Column 3: Payment Method (PAYROLL / ACH / CHECK)
   ├─ Column 4: Bonus ID (for audit trail)
   ├─ Column 5: Candidate Name (reference)
   ├─ Column 6: Hire Date (reference)
   └─ Row 1: Headers
      Row 2-N: [Employee] [Amount] [Method] [BonusID] [Candidate] [HireDate]

Step 4: IMPORT TO PAYROLL
├─ Finance manually imports CSV to payroll system (ADP, Gusto, etc.)
├─ Payroll adds bonuses to next applicable paycheck
└─ Timing: Same day or next day

Step 5: MARK AS PAID
├─ Finance marks bonus as paid in system
├─ Records: Payment date, payment method, exported date
├─ Updates: EmployeeReferral.bonus_paid = True
└─ Notifies: Employee "Bonus paid on [date] via [method]"

Step 6: DASHBOARD VIEW (Audit Trail)
├─ Finance can see: All bonuses (pending + paid + rejected)
├─ Filter by: Date range, payment status, employee, job
├─ Export: Historical CSV for reconciliation
├─ Reports: Monthly bonus spend, year-to-date totals
└─ Compliance: Full audit trail (who approved, when, payment date)
```

**CSV Export Example:**
```
Employee ID,Bonus Amount,Payment Method,Bonus ID,Candidate Name,Hire Date
emp_123,750.00,PAYROLL,bon_001,Jane Smith,2026-08-09
emp_456,500.00,ACH,bon_002,Mike Johnson,2026-08-08
emp_789,1500.00,PAYROLL,bon_003,Sarah Williams,2026-08-07
```

---

### Decision 7: Bonus Approval - FINANCE + HR + WEEKLY BATCH ✅
```
Three-Part Approval Process:

PART 1: FINANCE REVIEW
├─ Checks: Amount correct, duplicate bonuses?
├─ Verifies: Candidate actually hired
├─ Approval: "Amount looks good"
└─ Status: APPROVED_BY_FINANCE

PART 2: HR VERIFICATION (Optional but Recommended)
├─ Checks: Candidate confirmed onboarded
├─ Verifies: No payroll issues (suspension, termination, etc.)
├─ Approval: "Employee eligible for payout"
└─ Status: APPROVED_BY_HR

PART 3: WEEKLY BATCH PROCESSING
├─ Schedule: Every Friday at 2 PM
├─ Process: Review all APPROVED_BY_FINANCE bonuses
├─ Filter: Only those approved by HR (if HR check done)
├─ Action: Export CSV to payroll
├─ Sync: Mark as EXPORTED, ready for payroll
└─ Notification: Finance → Payroll team "Bonuses ready for next paycheck"

Workflow Visual:

Referral HIRED
    ↓
ReferralBonus CREATED (status: PENDING)
    ↓
Finance Dashboard: Shows in pending queue
    ↓
Finance Reviews: "Amount $750, Jane Smith hired on 2026-08-09"
    ↓
Finance Approves → Status: APPROVED_BY_FINANCE
    ↓
HR Verifies: "Employee in system, onboarded successfully"
    ↓
HR Approves → Status: APPROVED_BY_HR
    ↓
EVERY FRIDAY 2 PM:
Batch Job runs:
├─ Selects all APPROVED_BY_HR bonuses
├─ Exports to CSV
├─ Updates status: EXPORTED_TO_PAYROLL
└─ Sends email: Finance → Payroll "5 bonuses ($4,500) ready for 2026-08-22 paycheck"
    ↓
Payroll Team: Imports CSV
    ↓
Bonus appears in employee paycheck (next cycle)
    ↓
Employee Notified: "Your $750 referral bonus was paid!"
    ↓
Finance marks: PAID (records payment date, method)
```

**Approval Rules:**
```python
APPROVAL_WORKFLOW = {
    "PART_1_FINANCE": {
        "checks": ["amount_correct", "no_duplicate", "candidate_hired"],
        "status": "APPROVED_BY_FINANCE",
        "timeout": "7_days",  # If not approved in 7 days, escalate to CFO
    },
    "PART_2_HR": {
        "checks": ["employee_still_eligible", "no_payroll_issues"],
        "status": "APPROVED_BY_HR",
        "timeout": "3_days",  # Must approve within 3 days
        "optional": False,  # Can skip if no HR check configured
    },
    "PART_3_BATCH": {
        "schedule": "Friday 2 PM",
        "process": "Export all APPROVED_BY_HR to CSV",
        "status": "EXPORTED_TO_PAYROLL",
        "email": "To payroll team with count and total amount"
    }
}

ESCALATION = {
    "Finance timeout (7 days)": "Notify CFO, follow up with Finance",
    "HR timeout (3 days)": "Notify Finance, HR head",
    "Rejected bonus": "Notify referring employee (optional feedback)",
}
```

---

### Decision 8: Budget & Timeline - APPROVED ✅
```
CONFIRMED:
├─ Budget: $250K-300K approved
├─ Timeline: 5-6 weeks to production
├─ Team: 2-3 frontend engineers + 1 QA
├─ Go-Live: Early October 2026
└─ Status: READY TO START

TEAM ASSIGNMENT:
├─ Lead Frontend Engineer: Employee Portal + Referral UI
├─ Frontend Engineer 2: Email/Notifications + Duplicate handling UI
├─ QA Engineer: End-to-end testing, edge cases
└─ Backend Support: As needed for API additions (duplicate logic, escalation emails)

BUDGET BREAKDOWN (Estimated):
├─ Frontend (2.5 engineers × 6 weeks × $150/hr × 40 hrs/week): $180,000
├─ QA (1 engineer × 6 weeks × $100/hr × 40 hrs/week): $24,000
├─ Tools/Cloud/Testing: $15,000
├─ Contingency (10%): $20,000
└─ Total: ~$239,000 (within budget)

TIMELINE CONFIRMATION:
├─ Week 1-2: Employee Portal
├─ Week 2-3: Email + Notifications
├─ Week 3-4: Duplicate Handling
├─ Week 4-5: Finance Workflow
├─ Week 5-6: Role Dashboards + Polish
└─ Week 6: Production Launch
```

---

## DATABASE SCHEMA ADDITIONS NEEDED

### 1. Job Priority and Escalation
```python
# ADD to Job model
class Job(Base):
    # Existing fields...
    
    # NEW: Priority for email strategy
    referral_priority = Column(String, default="STANDARD")  # URGENT, STANDARD, LOW
    
    # NEW: Escalation tracking
    last_escalation_email_sent = Column(DateTime, nullable=True)
    escalation_email_count = Column(Integer, default=0)
    onboarding_candidate_id = Column(String, nullable=True)  # Track if candidate in onboarding
```

### 2. Candidate Duplicate Detection
```python
# EXISTING: Update Candidate model
class Candidate(Base):
    # Existing fields...
    
    # NEW: Track if duplicate
    is_duplicate_of = Column(String, ForeignKey("candidate.id"), nullable=True)  # Link to original
    duplicate_notes = Column(Text, nullable=True)
    merged_at = Column(DateTime, nullable=True)
```

### 3. Candidate Ownership (Already exists, but add fields)
```python
# EXISTING: Update CandidateOwnership model
class CandidateOwnership(Base):
    # Existing fields...
    
    # NEW: Support referral ownership
    ownership_type = Column(String)  # "RECRUITER", "REFERRAL"
    referral_id = Column(String, ForeignKey("employee_referral.referral_id"), nullable=True)
    ownership_change_reason = Column(String)
    previous_owner_id = Column(String, nullable=True)
    notes = Column(Text)
```

### 4. Email Tracking
```python
# NEW: Track email sends
class EmailLog(Base):
    email_log_id = Column(String, primary_key=True)
    email_type = Column(String)  # IMMEDIATE, DAILY_DIGEST, ESCALATION
    job_id = Column(String, ForeignKey("job.id"))
    recipient_employee_id = Column(String, ForeignKey("employee.id"))
    sent_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    click_type = Column(String)  # REFER_LINK, DETAILS, APPLY
    candidate_id = Column(String, nullable=True)  # If they referred
```

### 5. Escalation Log
```python
# NEW: Track escalation emails sent
class EscalationLog(Base):
    escalation_id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("job.id"))
    days_before_start = Column(Integer)  # 7, 5, 3, 1
    recipient_ids = Column(JSON)  # ["hiring_team", "dept_head"]
    sent_at = Column(DateTime, default=datetime.utcnow)
    email_subject = Column(String)
    email_body = Column(Text)
    response = Column(String, nullable=True)  # Did anyone refer?
```

---

## IMPLEMENTATION SPECIFICATIONS

### Phase 1: Employee Portal (Weeks 1-2)

**Screens to Build:**
1. Referral Center Home
   - Browse open roles with referral enabled
   - Filter by bonus, department, start date
   - Quick view of "My referrals count" and "Bonuses earned"

2. Submit Referral Form
   - Pre-fill from email link (job_id, pre-fill bonus)
   - Manual selection of job
   - Fields: Candidate name, email, phone, resume, LinkedIn, why recommend
   - Validation: Required fields, email format, resume upload

3. My Referrals Dashboard
   - Summary: Total, Active, Hired, Bonuses Earned
   - Status filter: All, Pending, Screening, Interviewed, Offered, Hired
   - Referral list: Candidate, Job, Bonus, Status, Timeline, Days in Stage
   - Actions: View details, See feedback, View timeline

4. Referral Details Screen
   - Candidate info: Name, email, phone, resume link
   - Referral info: Job, date referred, bonus amount
   - Full timeline: Referred → Screening → Interview → Offer → Hired
   - Bonus status: Pending, Approved, Paid (with payment date/method)
   - Actions: Share (email), View candidate profile, Celebrate/Certificate

5. Bonus Tracker
   - Summary: Total Earned, Paid, Pending, Potential
   - Table: Date, Candidate, Job, Amount, Status, Method, Payment Date
   - Payment history: Download statement, Tax summary
   - Filters: Date range, payment status

**API Endpoints to Create:**
- GET /portal/referral-center (list jobs with referral enabled)
- POST /portal/refer-candidate (submit referral)
- GET /portal/my-referrals (list employee's referrals)
- GET /portal/referral/{id} (detail view)
- GET /portal/my-bonuses (bonus tracker)

---

### Phase 2: Email + Notifications (Weeks 2-3)

**Email Types:**
1. IMMEDIATE: Urgent job opportunity
2. DAILY_DIGEST: 9 AM summary of standard/low jobs
3. ESCALATION: Daily reminder if no onboarding (7/5/3/1 days before start)
4. STATUS_UPDATE: Screening started, interviewed, offered, hired
5. BONUS_ALERT: Bonus approved, payment pending, bonus paid

**Email Templates:**
- Urgent opportunity (1 job, 1,000-2,000 word bonus)
- Daily digest (3-5 jobs summary)
- Escalation (increasingly urgent tone)
- Status updates (candidate progress)
- Bonus notifications (payment timeline)

**In-App Notifications:**
- Same 5 types as emails
- Notification center screen
- Preference screen (opt-in/out per type)
- Read/unread tracking

**Background Jobs:**
- Daily digest job (9 AM every business day)
- Escalation job (check job start dates, send escalating emails)
- Status update job (when referral status changes)
- Bonus notification job (when bonus approved/paid)

---

### Phase 3: Duplicate Handling (Weeks 3-4)

**Duplicate Detection Service:**
- Match by: Email (exact) + Name (95%+ similarity)
- Return: Candidate record + previous applications + feedback

**Previous Application History Display:**
- List: All previous applications (job, date, status, reason)
- Feedback: Interview notes, skills assessment, rejection reason
- AI recommendation: "Good fit for this role?" with confidence score

**Candidate Ownership Assignment:**
- Update CandidateOwnership: ownership_type = "REFERRAL"
- Link: referral_id = this referral
- Employee: bonus_eligible = True
- Note: "Candidate re-referred by emp_789 on 2026-08-09"

**Employee Communication:**
- Show: "This candidate exists in system"
- Show: Previous application history
- Show: Why they were rejected before
- Show: Why this role is better fit
- Message: "You still get bonus if hired!"

---

### Phase 4: Finance Workflow (Weeks 4-5)

**Finance Dashboard:**
1. Pending Bonuses Queue
   - Shows: All pending bonuses
   - Filters: Date, employee, job, status
   - Actions: Approve, Reject, Hold, Batch approve

2. Approval Workflow
   - Finance approval (7 day timeout)
   - HR verification (3 day timeout)
   - Status tracking: Pending → Approved → Exported → Paid

3. Export to Payroll
   - Button: "Export for Payroll" (generates CSV)
   - CSV format: Employee ID, Amount, Method, Bonus ID, Candidate, Date
   - Download: CSV file
   - Manual upload: Finance uploads to payroll system

4. Payment History
   - Table: All bonuses (pending + paid + rejected)
   - Columns: Date, Employee, Candidate, Amount, Status, Payment Date, Method
   - Filters: Status, date range, employee
   - Export: CSV for reconciliation

5. Reports & Compliance
   - Monthly bonus spend
   - Year-to-date totals
   - Top referrers (by bonus paid)
   - Audit trail (approvals, exports, payments)
   - Tax summary (1099 tracking for freelancers)

**API Endpoints:**
- GET /finance/pending-bonuses
- POST /finance/approve-bonus/{bonus_id}
- POST /finance/batch-approve-bonuses
- GET /finance/export-payroll (generates CSV)
- GET /finance/payment-history
- GET /finance/reports/monthly-spend

---

### Phase 5: Role Dashboards (Weeks 5-6)

**CEO/Executive Dashboard:**
- Total referrals, hired, conversion rate
- Bonuses paid, program ROI
- Trends: Month-over-month growth
- Comparison: Referral vs external recruiting cost

**BU Head Dashboard:**
- Referrals in their BU
- Top referrers (with names and amounts)
- Conversion metrics
- Pending bonuses in their BU

**HR Manager Dashboard:**
- Candidate pipeline by status
- Referral quality metrics
- Follow-up actions needed
- Top referrers to celebrate

---

## GO-LIVE READINESS CHECKLIST

**Week 6 (Before Launch):**
- [ ] All UI screens built and tested
- [ ] Email system working (immediate, digest, escalation)
- [ ] Duplicate detection working
- [ ] Finance approval workflow tested
- [ ] CSV export format correct
- [ ] Role-based access verified
- [ ] Mobile responsive design
- [ ] Security audit passed
- [ ] Load testing (1000+ concurrent users)
- [ ] Employee training videos created
- [ ] Finance team trained on approval workflow
- [ ] Payroll team trained on CSV import

**Launch Day:**
- [ ] Database backup taken
- [ ] Email service activated
- [ ] Escalation jobs scheduled
- [ ] Daily digest jobs scheduled
- [ ] Employee communication sent
- [ ] Finance team standing by
- [ ] Support team trained and available

---

## SUCCESS METRICS (Post-Launch)

**Week 1-2 (Pilot):**
- [ ] 10 employees testing system
- [ ] 5+ referrals submitted
- [ ] 0 critical bugs
- [ ] Employee satisfaction > 7/10

**Month 1 (General Availability):**
- [ ] 50+ referrals submitted
- [ ] 20% of employees using system
- [ ] 5+ bonuses approved and paid
- [ ] 0 failed CSV exports
- [ ] Finance workflow smooth

**Month 3 (Established):**
- [ ] 200+ total referrals
- [ ] 30-40% of hires from referrals
- [ ] Cost per hire: $375 (vs $850 external)
- [ ] Employee NPS: 8/10
- [ ] Program ROI: 2-3x

---

## NEXT IMMEDIATE STEPS

### THIS WEEK:
1. ✅ Lock in all decisions (COMPLETE)
2. Create detailed UI mockups for Employee Portal
3. Assign 2-3 frontend engineers
4. Setup development environment
5. Create feature specifications for Week 1

### NEXT WEEK (Week 1):
1. Frontend team starts Employee Portal build
2. Backend adds duplicate detection logic
3. Backend adds escalation email scheduling
4. QA creates test cases

---

**Status:** READY FOR DEVELOPMENT 🚀

All decisions locked. Specifications documented. Budget approved. Timeline confirmed.

Frontend build can start immediately.


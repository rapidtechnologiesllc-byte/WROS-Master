# Referral System: UX Gaps, Stakeholder Mapping & Complete Feature Requirements

**Date:** 2026-08-09  
**Status:** Design Doc - Identifies gaps in current implementation  
**Priority:** CRITICAL - Must be addressed before production

---

## ISSUE 1: Where Does Employee Access Referral Feature?

### Current State (INCOMPLETE)
- ✅ API endpoints exist
- ✅ Database models created
- ❌ **NO UI/Portal entry point for employees**
- ❌ **NO way for employee to discover referral opportunities**
- ❌ **NO referral dashboard visible in employee portal**

### Required UX Entry Points

#### 1. **Dashboard Referral Widget** (Employee sees on login)
```
Home Dashboard → "New Referral Opportunities" Card
├─ Card shows: "3 open roles - earn referral bonuses"
├─ Button: "View Open Roles" 
├─ Shows quick stats:
│  ├─ Jobs with referral program enabled (3)
│  ├─ Available referral bonuses ($500-$1,500)
│  └─ Your pending referrals (2 in progress, 1 hired + $500 earned)
└─ Button: "Submit New Referral"
```

#### 2. **Referral Center Portal** (New screen)
```
Main Navigation → "Refer & Earn" Section
├─ All Open Roles (with referral enabled)
│  ├─ Job title, description, bonus amount, deadline
│  ├─ Button: "Refer Someone for This Role"
│  └─ Your referrals for this job (if any)
├─ Your Referrals (tracking view)
│  ├─ Status: PENDING, SCREENING, INTERVIEWED, OFFERED, HIRED
│  ├─ Candidate name, job applied for
│  ├─ Timeline: days in current stage
│  └─ Bonus status: Pending, Approved, Paid
└─ My Earnings
   ├─ Total referrals: 10
   ├─ Hired: 2
   ├─ Earned: $1,500
   ├─ Pending: $500 (approved, paying next cycle)
   └─ History: All past referrals with dates/amounts
```

#### 3. **Job Details Page** (Existing screen, enhanced)
```
Job Details → "Refer Someone" Card (below job description)
├─ Visible only if referrals enabled for this job
├─ Shows: "Earn $750 if they're hired!"
├─ Button: "Submit Referral"
├─ Shows referral program details
└─ Link: "Why refer? How bonuses work?"
```

#### 4. **Email Link Entry Point** (From referral email)
```
Email: "Referral Opportunity: Senior Guidewire Developer"
├─ Link: https://blitzenx.com/referral/add-candidate?job_id=job_001&ref_emp=emp_123
└─ Redirects to "Refer Candidate" form pre-filled:
   ├─ Job: Senior Guidewire Developer
   ├─ Bonus: $750
   ├─ Source: EMPLOYEE_REFERRAL
   ├─ Your name: Pre-filled (emp_123)
   └─ Fields for candidate details
```

### Missing Database/API
- [ ] EmployeeReferralSettings.referral_link_clicked tracking
- [ ] Dashboard preference (show referral widget?)
- [ ] Referral UI permissions by role

---

## ISSUE 2: Where Employee Tracks Status & Payment

### Current State (INCOMPLETE)
- ✅ API endpoint exists: `GET /referrals/dashboard/referrals`
- ❌ **NO UI screen to view dashboard**
- ❌ **NO referral status tracking UI**
- ❌ **NO payment timeline visibility**
- ❌ **NO notifications for status changes**

### Required UI Screens

#### Screen 1: "My Referrals" (Main tracking view)
```
My Referrals Dashboard
├─ Summary Cards
│  ├─ Total Referrals: 10
│  ├─ Currently Active: 3
│  ├─ Hired: 2
│  └─ Bonuses Earned: $1,500
│
├─ Status Filter
│  ├─ All (10)
│  ├─ Pending (2) - "Need to screen"
│  ├─ Screening (1) - "In progress"
│  ├─ Interview (0)
│  ├─ Offered (0)
│  └─ Hired (2) - "Bonuses earned!"
│
└─ Referral List (Timeline View)
   ├─ Candidate: John Doe
   │  ├─ Job: Senior Guidewire Dev
   │  ├─ Status: SCREENING (In Progress, 5 days)
   │  │  └─ Timeline: Referred (Day 1) → Screening (Day 5-10) → Interview → Offer → Hired
   │  ├─ Bonus: $750 (Not yet earned - awaiting hire)
   │  └─ Last Update: 2 days ago
   │
   ├─ Candidate: Jane Smith
   │  ├─ Job: Salesforce Admin
   │  ├─ Status: HIRED (Bonus Earned!)
   │  ├─ Bonus: $500 (PAID - via PAYROLL)
   │  │  └─ "Bonus paid on 2026-08-15"
   │  └─ Time from Referral to Hire: 28 days
   │
   └─ Candidate: Mike Johnson
      ├─ Job: Solution Architect
      ├─ Status: REJECTED
      └─ Bonus: $0 (Not qualified)
```

#### Screen 2: "Referral Details" (Per-candidate view)
```
Referral Details → Jane Smith
├─ Basic Info
│  ├─ Candidate: Jane Smith (jane.smith@external.com)
│  ├─ Job: Salesforce Admin
│  ├─ Referred: 2026-07-15
│  ├─ Status: HIRED (2026-08-09)
│  └─ Days to Hire: 28 days
│
├─ Status Timeline (Vertical)
│  ├─ ✓ REFERRED (Jul 15) - You referred Jane
│  ├─ ✓ SCREENING (Jul 16-19) - HR reviewed resume
│  ├─ ✓ INTERVIEW SCHEDULED (Jul 20) - Interview set for Jul 22
│  ├─ ✓ INTERVIEWED (Jul 22) - Interview completed, positive feedback
│  ├─ ✓ OFFERED (Jul 28) - Offer extended, bonus approval queued
│  └─ ✓ HIRED (Aug 09) - Onboarded, bonus sent to payroll
│
├─ Bonus Tracking
│  ├─ Bonus Amount: $500.00
│  ├─ Status: PAID
│  ├─ Payment Method: PAYROLL (direct deposit)
│  ├─ Payment Date: 2026-08-15
│  └─ Payment Details
│     ├─ Bonus ID: bon_001
│     ├─ Invoice: INV-2026-00456
│     └─ Finance Note: "Processed with payroll cycle"
│
└─ Actions
   ├─ Share Referral (refer friend network)
   ├─ Download Certificate (proof of referral)
   └─ Leave Feedback (about referral program)
```

#### Screen 3: "Bonus Tracking & Payment Timeline"
```
My Referral Bonuses
├─ Summary
│  ├─ Total Earned: $1,500
│  ├─ Paid This Year: $1,500
│  ├─ Pending Approval: $500 (awaiting hire)
│  └─ Potential (Current Active): $750
│
├─ Payment History (Table)
│  ├─ Date | Candidate | Job | Amount | Status | Payment Method
│  ├─ 2026-08-15 | Jane Smith | Salesforce Admin | $500 | PAID | PAYROLL
│  ├─ 2026-07-30 | Mike Chen | Guidewire Dev | $750 | PAID | PAYROLL
│  ├─ [Pending] | John Doe | Solution Arch | $750 | PENDING | AWAITING HIRE
│  └─ [Pending] | Sarah Wilson | Support Eng | $500 | AWAITING APPROVAL | AWAITING HIRE
│
└─ Tax & Finance
   ├─ Bonuses are subject to income tax
   ├─ Form 1099 (if freelancer)
   └─ Download Year-to-Date Statement
```

#### Notifications (In-App + Email)
```
Notification Types:

1. REFERRAL_SUBMITTED (Immediate)
   "Your referral of John Doe for Senior Guidewire Dev has been submitted.
    If hired, you'll earn $750!"

2. SCREENING_STARTED (Day 2)
   "Your referral John Doe entered screening phase.
    HR is reviewing their qualifications."

3. INTERVIEW_SCHEDULED (Day 5)
   "Great news! John Doe has an interview scheduled for Jul 22.
    Status: Interview Scheduled"

4. INTERVIEW_COMPLETED (Day 8)
   "Interview complete! Waiting for next decision..."

5. OFFER_EXTENDED (Day 15)
   "Offer extended to John Doe! One step closer to your $750 bonus."

6. CANDIDATE_HIRED (Day 20)
   "🎉 Congratulations! John Doe is hired!
    Your $750 referral bonus has been approved."

7. BONUS_APPROVED (Day 21)
   "Your $750 bonus has been approved and will be paid via PAYROLL.
    Expected: Next paycheck (Aug 15)"

8. BONUS_PAID (Day 27)
   "✓ Your $750 referral bonus has been paid!
    Check your paycheck or bank account. Thank you!"
```

### Missing from Current Implementation
- [ ] Employee referral dashboard UI screen
- [ ] Referral detail/timeline view
- [ ] Bonus tracking UI
- [ ] In-app notification system
- [ ] Email notification templates
- [ ] Payment timeline forecasting

---

## ISSUE 3: Email Strategy - Individual vs Daily Digest

### Current State
❌ **NOT DECIDED** - Will emails be sent per-job or consolidated?

### Option A: Individual Email Per Job (RECOMMENDED)
**Timing:** Immediately when job created + referral enabled

**Pros:**
- ✅ Fresh information, timely
- ✅ Employee sees opportunity immediately
- ✅ Higher engagement for urgent roles
- ✅ Can include job-specific details

**Cons:**
- ❌ Email overload if many jobs created daily
- ❌ Multiple similar emails if multiple jobs posted same day

**Email Template:**
```
From: referrals@blitzenx.com
Subject: New Referral Opportunity - Senior Guidewire Developer ($750 bonus!)

Hi John,

We're hiring for a Senior Guidewire Developer position!

[JOB DESCRIPTION]

Know someone perfect? Refer them and earn $750 when they're hired!

Referral Link: https://blitzenx.com/referral/add-candidate?job_id=job_001&ref_emp=emp_123
Learn About Our Referral Program: https://blitzenx.com/referral-program

Questions? Email referrals@blitzenx.com

Thanks for being a brand ambassador!
- The BlitzenX Team
```

### Option B: Daily Consolidated Digest (ALTERNATIVE)
**Timing:** 9 AM every business day

**Pros:**
- ✅ Fewer emails (1 per day max)
- ✅ Employee can see all opportunities at once
- ✅ Reduces email fatigue
- ✅ Better for comparison shopping

**Cons:**
- ❌ Delayed - employee sees job opportunity late
- ❌ Lower engagement for urgent roles
- ❌ May miss emails in crowded inbox

**Email Template:**
```
From: referrals@blitzenx.com
Subject: New Referral Opportunities This Week - Earn $2,750 in Bonuses!

Hi John,

3 new roles this week with referral bonuses:

1. Senior Guidewire Developer
   Location: Remote | Bonus: $750
   [Brief Description]
   Refer: https://blitzenx.com/referral/add-candidate?job_id=job_001

2. Salesforce Admin
   Location: Chicago | Bonus: $500
   [Brief Description]
   Refer: https://blitzenx.com/referral/add-candidate?job_id=job_002

3. Solutions Architect
   Location: New York | Bonus: $1,500
   [Brief Description]
   Refer: https://blitzenx.com/referral/add-candidate?job_id=job_003

View All Referral Opportunities: https://blitzenx.com/referral-center
My Referrals & Earnings: https://blitzenx.com/referral/my-referrals

---

This Week's Top Referrer: Alice Johnson (5 referrals, 1 hired - $750 earned!)
```

### RECOMMENDATION: **Option A (Individual) + Option B (Weekly Digest)**

**Hybrid Approach:**
```
Timeline:
├─ Immediate: Individual email for new job (if urgent or high-value role)
├─ Daily 9am: Summary of all jobs with referral enabled
├─ Weekly: Digest email with top referrers (gamification/recognition)
└─ Monthly: Referral program statistics + top earners
```

**Configuration:**
- Job creator selects: "Send immediate email" (urgent) or "Include in daily digest" (standard)
- Employee preference: Opt-in to "Daily Digest" email vs "Individual Emails"

### Missing Implementation
- [ ] Email frequency configuration
- [ ] Email template system
- [ ] Scheduled daily/weekly digest job
- [ ] Employee email preference settings
- [ ] Unsubscribe/preference management

---

## ISSUE 4: Complete Stakeholder Mapping

### 1. **EMPLOYEE (Internal) - What They Need**

**Primary Goal:** Earn referral bonuses easily + see progress

**Entry Points:**
- Dashboard widget: "New referral opportunities"
- Referral center portal: Browse jobs, submit referrals
- Email: Individual job notifications or daily digest
- Mobile app: Quick referral submission
- Slack bot: "/refer" command for quick submission

**Screens Needed:**
1. Referral center (discover opportunities)
2. Submit referral form (pre-filled from email link)
3. My referrals dashboard (status tracking)
4. Bonus tracker (earnings & payment timeline)
5. Referral settings (email preferences)

**Data They See:**
```json
{
  "view": "EMPLOYEE_DASHBOARD",
  "total_referrals": 3,
  "hired_referrals": 1,
  "bonus_potential": 500.00,
  "bonuses_earned": 500.00,
  "bonuses_pending": 0.00,
  "active_referrals": [
    {
      "candidate": "John Doe",
      "job": "Senior Guidewire Dev",
      "status": "SCREENING",
      "days_in_stage": 5,
      "bonus_amount": 750.00,
      "referral_date": "2026-08-01"
    }
  ]
}
```

**Notifications They Receive:**
- Status updates (screening → interview → offer → hired)
- Bonus approved notification
- Bonus payment notification
- Recognition (top referrer badge, milestone achievements)

**External Referral Need:**
- Refer friends who aren't employees yet
- Track referrals of candidates from outside network
- Earn bonus even if candidate is external

---

### 2. **EXTERNAL CANDIDATE - What They Experience**

**Primary Goal:** Easy application process, no friction

**Journey:**
```
Employee's Friend → Email with Referral Link
                  → Clicks: "Apply for this role"
                  → Candidate Form (Pre-filled)
                     ├─ Job: "Senior Guidewire Developer"
                     ├─ Source: "Employee Referral"
                     ├─ Referring Employee: "John Doe"
                     └─ Fields: Name, Email, Phone, Resume, LinkedIn
                  → Application Received
                     └─ "John referred you, thanks for applying!"
                  → Screening, Interview, Offer, Hire
```

**Data They See:**
```json
{
  "application_status": "SCREENING",
  "referred_by": "John Doe (Senior Developer at BlitzenX)",
  "job": "Senior Guidewire Developer",
  "timeline": {
    "applied": "2026-08-01",
    "screening_started": "2026-08-02",
    "interview_scheduled": "2026-08-10",
    "expected_decision": "2026-08-15"
  }
}
```

**No Direct Benefit:** External candidate doesn't earn referral bonus, but gets priority treatment in recruiting process.

---

### 3. **HIRING MANAGER - What They Need**

**Primary Goal:** Identify referred candidates, fast-track hiring

**Entry Points:**
- Candidate details screen: Badge showing "Referred by John Doe (Employee)"
- Jobs portal: "Referrals for this role" card showing incoming referrals
- Dashboard: "Referrals in hiring pipeline" widget

**Screens Needed:**
1. Candidates for my job (filtered)
2. Referral badge on candidate profile
3. Referral source tracking
4. Time-to-hire comparison (referred vs non-referred)

**Actions:**
- Priority screening for referred candidates (AI Thunder handles automatically)
- Mark candidate as hired (triggers referral bonus)
- Feedback: Why candidate wasn't hired (to improve referrer quality)

**Data They See:**
```json
{
  "job": "Senior Guidewire Developer",
  "candidates": [
    {
      "name": "John Doe",
      "referred_by": "Alice Johnson",
      "source": "EMPLOYEE_REFERRAL",
      "status": "INTERVIEW_SCHEDULED",
      "referral_bonus": 750.00,
      "hired": false
    }
  ],
  "referral_stats": {
    "total_referrals": 8,
    "referral_to_hire_rate": 12.5,
    "avg_time_to_hire_referred": 28,
    "avg_time_to_hire_non_referred": 35
  }
}
```

---

### 4. **BUSINESS UNIT HEAD / PARTNER - What They Need**

**Primary Goal:** Monitor team referral activity + bonus liabilities

**Entry Points:**
- BU Dashboard: Referral performance overview
- Team analytics: Who's referring, who's earning

**Screens Needed:**
1. BU referral dashboard (team metrics)
2. Top referrers in their BU (leaderboard)
3. Pending bonuses in their BU
4. Team engagement tracking

**Data They See:**
```json
{
  "view": "BU_DASHBOARD",
  "business_unit": "Guidewire",
  "total_referrals": 45,
  "hired_referrals": 4,
  "conversion_rate": 8.9,
  "bonuses_owed": 2000.00,
  "top_referrers": [
    {
      "name": "Alice Johnson",
      "referrals_count": 5,
      "hired": 1,
      "bonuses_earned": 750.00
    }
  ]
}
```

**Actions:**
- View pending bonuses in their BU
- Approve large bonuses (if configured)
- Celebrate top referrers

---

### 5. **CFO / FINANCE TEAM - What They Need**

**Primary Goal:** Track bonus liabilities, process payments, reconcile with payroll

**Entry Points:**
- Finance dashboard: Pending bonuses queue
- Reports: Monthly referral bonus spend

**Screens Needed:**
1. Pending bonuses queue (for payment approval)
2. Bonus payment processing workflow
3. Payment history (audit trail)
4. Finance reports (budget tracking)

**Data They See:**
```json
{
  "view": "FINANCE_DASHBOARD",
  "total_bonuses": 25,
  "pending_payment": 5,
  "pending_amount": 4500.00,
  "already_paid": 20,
  "paid_amount": 15000.00,
  "pending_bonuses": [
    {
      "bonus_id": "bon_001",
      "employee": "John Doe",
      "bonus_amount": 750.00,
      "candidate": "Jane Smith",
      "job": "Salesforce Admin",
      "hire_date": "2026-08-09",
      "payment_status": "PENDING",
      "actions": ["Approve", "Reject", "Hold for Review"]
    }
  ],
  "payment_methods": {
    "PAYROLL": 20,
    "ACH": 5,
    "CHECK": 0
  }
}
```

**Actions:**
- Review and approve bonus payment
- Select payment method (PAYROLL, ACH, CHECK)
- Mark as paid (syncs with payroll)
- Generate tax forms (1099 if freelancer)
- Download reconciliation report

---

### 6. **RECRUITER - What They Need**

**Primary Goal:** Encourage referrals, identify high-quality sources, manage follow-up

**Entry Points:**
- Recruitment dashboard: Referral stats by job
- Candidate screen: Referral badge + referrer info

**Screens Needed:**
1. Referral performance by job
2. Referrer quality metrics (conversion rate)
3. Follow-up list (candidates from referrals needing attention)

**Data They See:**
```json
{
  "job": "Senior Guidewire Developer",
  "referral_stats": {
    "total_referrals": 8,
    "in_screening": 2,
    "interviewed": 1,
    "offered": 0,
    "hired": 0,
    "referral_quality": 25.0  // % who pass initial screen
  },
  "top_referrer_for_this_job": {
    "name": "Alice Johnson",
    "referrals": 3,
    "quality": 66.7  // % of their referrals who pass
  }
}
```

**Actions:**
- Thank referrers for quality referrals
- Follow up on pending referrals
- Track referral source quality

---

### 7. **CEO / EXECUTIVE - What They Need**

**Primary Goal:** Referral program ROI, org-wide metrics, strategic insights

**Entry Points:**
- Executive dashboard: Referral KPIs
- Monthly reports: Program effectiveness

**Screens Needed:**
1. Referral program dashboard (org-wide)
2. ROI metrics (bonuses paid vs hires gained)
3. Year-over-year trends

**Data They See:**
```json
{
  "view": "CEO_DASHBOARD",
  "total_referrals": 150,
  "total_hired": 12,
  "conversion_rate": 8.0,
  "total_bonuses_owed": 9000.00,
  "bonuses_paid": 4500.00,
  "program_roi": {
    "total_bonuses_paid": 4500.00,
    "total_hires_from_referrals": 12,
    "cost_per_hire_referred": 375.00,
    "cost_per_hire_other_sources": 850.00,  // Industry avg
    "savings": 5700.00  // 12 * (850-375)
  },
  "engagement": {
    "total_employees": 350,
    "employees_who_referred": 45,  // 12.9% participation
    "top_referrer": "Alice Johnson",
    "top_referrer_earnings": 2250.00
  }
}
```

---

## ISSUE 5: External Referral Mechanism

### Current State (MISSING)
❌ **System assumes employee referrals only**
❌ **No mechanism for external referrals**
❌ **Employee can't refer friend outside company with incentive**

### Required Implementation

#### Use Case: "I Know a Guidewire Dev Looking for a Change"
```
John (Guidewire BA) knows Mike (Guidewire Dev at competitor)
├─ Mike is friend, not BlitzenX employee
├─ John wants to refer Mike AND EARN BONUS
├─ But Mike is external candidate
└─ System should support this!
```

### Solution: External Referral + Referral Link

#### External Referral Flow
```
1. EMPLOYEE SHARES LINK
   John goes to: https://blitzenx.com/referral/share
   ├─ Selects job: "Senior Guidewire Developer"
   ├─ Gets personalized link: https://blitzenx.com/referral/r/emp_123_job_001_abc123
   └─ Shares with Mike via:
      ├─ Email: "Hey Mike, I found a great role for you..."
      ├─ LinkedIn: Message link to friend
      ├─ WhatsApp: Direct message
      └─ Slack: Share in channel

2. EXTERNAL CANDIDATE CLICKS LINK
   Mike clicks: https://blitzenx.com/referral/r/emp_123_job_001_abc123
   ├─ Sees: "John Doe referred you for this role"
   ├─ Application form appears with:
   │  ├─ Job: "Senior Guidewire Developer"
   │  ├─ Referred by: "John Doe"
   │  ├─ Referral bonus (if hired): $750 for John
   │  └─ Fields: Name, Email, Phone, Resume
   ├─ Submits application
   └─ System creates:
      ├─ Candidate record (if not exists)
      ├─ EmployeeReferral record
      ├─ Source: EMPLOYEE_REFERRAL_EXTERNAL
      └─ Referring employee: John

3. PROCESSING SAME AS REGULAR REFERRAL
   ├─ Thunder screens
   ├─ Interview scheduled
   ├─ Offer sent
   ├─ Hired!
   └─ John's $750 bonus created + paid

4. TRACKING
   ├─ John sees in dashboard:
   │  ├─ "Mike Jones - Referred (External) - HIRED - $750 Earned"
   │  └─ Bonus paid with next paycheck
   └─ Finance sees:
      ├─ Referral source: EMPLOYEE_REFERRAL_EXTERNAL
      └─ Candidate type: EXTERNAL
```

### Database Schema Extension Needed
```python
# Current
class EmployeeReferral(Base):
    referral_id = Column(String)
    referring_employee_id = Column(String)  # Internal employee only
    
# Extended
class EmployeeReferral(Base):
    referral_id = Column(String)
    referring_employee_id = Column(String)  # Internal employee who referred
    referral_source = Column(String)  # DIRECT, EMAIL, LINK_SHARE, SOCIAL
    is_external_referral = Column(Boolean)  # True if candidate external
    referral_link_id = Column(String)  # Track which link was used
    external_share_method = Column(String)  # EMAIL, LINKEDIN, WHATSAPP, SLACK, etc.
```

### Referral Link Tracking
```python
class ReferralLink(Base):
    link_id = Column(String)
    job_id = Column(String)
    referring_employee_id = Column(String)
    personal_url = Column(String)  # https://blitzenx.com/referral/r/emp_123_job_001_abc123
    
    # Tracking
    created_at = Column(DateTime)
    clicks_count = Column(Integer)  # How many times clicked
    referrals_from_link = Column(Integer)  # How many applied via this link
    last_clicked = Column(DateTime)
    
    # Analytics
    share_method = Column(String)  # EMAIL, LINKEDIN, WHATSAPP, etc.
    device_info = Column(String)  # Mobile, Desktop, etc.
```

### Analytics for Employee
```
Referral Sharing Dashboard

My Personal Referral Links:
├─ Senior Guidewire Developer (Bonus: $750)
│  ├─ Link: https://blitzenx.com/referral/r/emp_123_job_001_abc123
│  ├─ Clicks: 5
│  ├─ Applications: 2
│  ├─ Hired: 0
│  ├─ Share Methods:
│  │  ├─ Email: 3 clicks
│  │  └─ LinkedIn: 2 clicks
│  └─ Button: "Copy Link", "Share", "Copy Email Template"
│
└─ Solutions Architect (Bonus: $1,500)
   ├─ Link: https://blitzenx.com/referral/r/emp_123_job_002_def456
   ├─ Clicks: 8
   ├─ Applications: 1
   ├─ Hired: 1 ✓
   ├─ Earnings: $1,500 (Pending)
   └─ [Share Again Button]

My Referral Network:
├─ Total people reached: 13
├─ Total applications: 3
├─ Conversion: 23%
└─ Top Shared Role: Senior Guidewire Dev (5 shares)
```

### Missing Implementation
- [ ] ReferralLink model
- [ ] Link generation service
- [ ] Link tracking/analytics
- [ ] Share dialog UI (copy link, email template, social share)
- [ ] External candidate tracking
- [ ] Duplicate candidate detection (see Issue 6)

---

## ISSUE 6: Duplicate Candidate Handling

### The Problem
```
Scenario: Candidate already in system
├─ John Smith applied 3 months ago via LinkedIn
├─ John applied and was rejected (not qualified)
├─ Today: Alice (employee) refers John for different role
├─ Question: Does John get counted as duplicate?
│  ├─ If YES → Alice doesn't get bonus (DEMOTIVATING!)
│  ├─ If NO → Same candidate in system twice (DATA PROBLEM!)
│  └─ How does system know John is "already here"?
└─ AI System Question: Why did Thunder miss him before?
```

### Current State (BROKEN)
❌ **No duplicate detection**
❌ **No previous application history visible**
❌ **AI can't learn why candidate was rejected before**
❌ **Employee loses bonus if candidate is resubmitted**
❌ **Candidate confusion (why different recruiter?)

### Required Implementation

#### Step 1: Duplicate Detection
```python
class CandidateDuplicateDetection:
    
    def find_duplicate(candidate_email, candidate_name):
        """Find if candidate already in system"""
        candidates = db.query(Candidate).filter(
            (Candidate.email == candidate_email) OR
            (similarity(Candidate.name, candidate_name) > 0.85)
        ).all()
        
        return candidates  # May find 0, 1, or multiple matches
    
    def merge_candidate_records(old_id, new_referral_id):
        """Merge if same candidate, track referral source"""
        old_candidate = db.get(Candidate, old_id)
        new_referral = db.get(EmployeeReferral, new_referral_id)
        
        # Link new referral to existing candidate
        new_referral.referred_candidate_id = old_id
        
        # Track: This candidate has multiple referral sources
        old_candidate.referral_sources.append({
            "referred_by": new_referral.referring_employee_id,
            "referred_on": new_referral.created_at,
            "bonus_eligible": True  # Employee still earns if hired!
        })
```

#### Step 2: Previous Application History
```
Candidate Detail Screen (for Recruiter/Thunder AI)

Candidate: John Smith
├─ Current Application (NEW)
│  ├─ Referred by: Alice Johnson
│  ├─ Job: Solutions Architect
│  ├─ Date: 2026-08-09
│  └─ Status: NEW - Same candidate has previous history!
│
├─ PREVIOUS HISTORY (System Alert)
│  ├─ Application 1: 2026-05-15
│  │  ├─ Job: Senior Guidewire Developer
│  │  ├─ Status: REJECTED
│  │  ├─ Rejection Reason: "Skills gap in specific Guidewire module"
│  │  └─ Feedback: "Good communication, needs Guidewire depth"
│  │
│  └─ Application 2: 2026-06-20
│     ├─ Job: Guidewire Admin
│     ├─ Status: REJECTED
│     ├─ Rejection Reason: "Not enough admin experience"
│     └─ Feedback: "Has developer skills, needs admin experience"
│
└─ RECOMMENDATION
   ├─ Alert: "This candidate has been rejected before"
   ├─ Reason Summary: "Skills gap in Guidewire modules, admin experience"
   ├─ Current Role Fit: Solutions Architect
   │  └─ This role DOES NOT require deep Guidewire - GOOD FIT!
   └─ AI Recommendation: "Worth reconsidering - different role type"
```

#### Step 3: AI System Learning (Why Thunder Missed It)

```python
class CandidateRejectionAnalysis:
    
    def analyze_previous_rejection(candidate_id, old_job_id, new_job_id):
        """
        Understand why candidate was rejected before
        and whether they're now suitable for new role
        """
        old_job = db.get(Job, old_job_id)
        new_job = db.get(Job, new_job_id)
        old_rejection = db.query(CandidateRejection).filter(
            (CandidateRejection.candidate_id == candidate_id) &
            (CandidateRejection.job_id == old_job_id)
        ).first()
        
        # Analyze skill gap
        gaps = {
            "Guidewire": {
                "old_job_requirement": "Expert",
                "old_job_actual": "Intermediate",
                "new_job_requirement": "Not required",  # Solutions Architect
                "verdict": "RESOLVED - New role doesn't need this skill"
            }
        }
        
        return {
            "resubmission_viable": True,
            "skill_gaps_resolved": True,
            "recommendation": "RECONSI DERS - Different role type, good fit",
            "confidence": 0.92
        }
    
    def ai_learning_loop():
        """
        Learn from previous rejections
        If candidate succeeds in new role, analyze what changed
        """
        if candidate.status == "HIRED":
            # Retrospective analysis
            previous_rejection = candidate.previous_rejections[0]
            
            log_to_ai_system({
                "type": "REJECTION_RECOVERY",
                "candidate": candidate.name,
                "originally_rejected_for": previous_rejection.job_title,
                "reason_failed": previous_rejection.reason,
                "now_hired_for": candidate.current_job_title,
                "success": True,
                "learning": "Candidate was overqualified for Guidewire Dev role, "
                           "better fit in higher-level Solutions Architect role"
            })
            
            # Improve future screening based on this learning
```

#### Step 4: Employee Still Gets Bonus!
```python
class ReferralBonusEligibility:
    
    def is_bonus_eligible(referral_id):
        """
        Determine if employee earns bonus
        Even if candidate resubmitted, employee gets credit
        """
        referral = db.get(EmployeeReferral, referral_id)
        candidate = db.get(Candidate, referral.referred_candidate_id)
        
        # Rule: Employee gets bonus if:
        # 1. They referred candidate (documented in EmployeeReferral)
        # 2. Candidate is hired from THIS referral
        # 3. Candidate wasn't already hired from another referral
        
        if candidate.status == "HIRED":
            # Check if already hired from another referral
            other_referrals = db.query(EmployeeReferral).filter(
                (EmployeeReferral.referred_candidate_id == candidate.id) &
                (EmployeeReferral.referral_id != referral_id) &
                (EmployeeReferral.referral_status == "HIRED")
            ).all()
            
            if not other_referrals:
                # This is the first/only successful referral
                return {
                    "eligible": True,
                    "amount": referral.referral_bonus_amount,
                    "reason": "Employee referred candidate who was hired"
                }
            else:
                # Candidate already hired via another referral
                return {
                    "eligible": False,
                    "amount": 0,
                    "reason": "Candidate already hired via different referral",
                    "original_referrer": other_referrals[0].referring_employee_id
                }
        
        return {"eligible": False, "amount": 0, "reason": "Candidate not hired"}
```

#### Step 5: Transparent Communication to Employee
```
Referral Status: DUPLICATE DETECTED

Alice, you referred John Smith for Solutions Architect.
John was in our system from a previous application!

GOOD NEWS:
✓ You still earn the referral bonus if hired
✓ John is a better fit for this role
✓ No penalty for duplicate - we encourage referring previously rejected candidates!

JOHN'S HISTORY:
├─ Applied: May 15, 2026 (Guidewire Dev) → Rejected (skill gap)
├─ Applied: Jun 20, 2026 (Guidewire Admin) → Rejected (need admin exp)
└─ Now: Solutions Architect (BETTER FIT!) → In Progress

WHY RECONSIDER?
This Solutions Architect role doesn't need deep Guidewire skills.
John's feedback was: "Good communication, good foundation"
This role is a much better match!

YOUR ACTION:
No action needed. We've linked your referral to John's existing profile.
If hired, you'll earn your $750 bonus!
```

### Missing Implementation
- [ ] Duplicate detection logic
- [ ] Merge candidate records
- [ ] Track multiple referral sources
- [ ] Previous application history display
- [ ] AI rejection analysis system
- [ ] Candidate suitability scoring for new roles
- [ ] Employee notification (duplicate detected, still get bonus)
- [ ] Bonus eligibility logic (handles duplicates)

---

## SUMMARY: What's Missing (Priority Order)

### CRITICAL (Must have before production)
1. ❌ **Employee Dashboard UI** - Where employees see referrals + status + earnings
2. ❌ **Referral Form UI** - Where employees submit candidates
3. ❌ **Referral Center Portal** - Browse open roles, submit referrals
4. ❌ **Email Notification System** - Individual or daily digest emails
5. ❌ **Duplicate Detection** - Handle candidates already in system
6. ❌ **Candidate History UI** - Show previous applications to recruiters

### HIGH (Should have for MVP)
7. ❌ **Role-Based Dashboards UI** - CEO, BU Head, HR, Finance screens
8. ❌ **In-App Notifications** - Status updates, bonus payment alerts
9. ❌ **Bonus Tracker UI** - Payment timeline, earnings history
10. ❌ **External Referral Links** - Share personalized referral URLs
11. ❌ **Referral Link Analytics** - Track shares, clicks, conversions

### MEDIUM (Nice to have MVP+)
12. ❌ **Gamification** - Badges, leaderboards, recognition
13. ❌ **AI Learning Loop** - Improve candidate matching over time
14. ❌ **Tax Forms** - 1099 generation for freelancers
15. ❌ **Mobile App** - Refer on the go
16. ❌ **Slack Integration** - "/refer" command

---

## RECOMMENDED NEXT STEPS

**Phase 1: Employee UX (Week 1-2)**
1. Build employee referral dashboard
2. Build referral submission form
3. Build referral status tracking screen
4. Build bonus tracker UI

**Phase 2: Email & Notifications (Week 2-3)**
1. Implement email notification system
2. Design email templates (individual vs digest)
3. Setup scheduled email jobs
4. Build notification preferences screen

**Phase 3: Duplicate Handling (Week 3-4)**
1. Implement duplicate detection
2. Build candidate history display
3. Add AI rejection analysis
4. Update bonus eligibility logic

**Phase 4: Role-Based Dashboards (Week 4-5)**
1. CEO/Exec dashboard UI
2. BU Head/Recruiter dashboards
3. Finance payment workflow UI
4. Reports & analytics

**Phase 5: External Referrals (Week 5-6)**
1. Referral link generation
2. Link sharing UI
3. External candidate tracking
4. Analytics for referral links

---

**Status:** Design Doc Complete - Ready for development planning


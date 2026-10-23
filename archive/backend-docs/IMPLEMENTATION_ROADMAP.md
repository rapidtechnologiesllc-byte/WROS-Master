# Referral System: Implementation Roadmap

**Current Status:** API Backend ✅ | Frontend UI ❌  
**Production Readiness:** 40% (Backend) + 0% (Frontend) = 40% Overall

---

## What's DONE (Backend)

```
✅ DATABASE MODELS
├─ EmployeeReferral (tracks individual referrals)
├─ JobReferralSettings (job-level configuration)
└─ ReferralBonus (finance tracking)

✅ SERVICE LAYER (14 methods)
├─ Core: create_job_referral_settings()
├─ Core: send_referral_emails_for_job()
├─ Core: record_referral()
├─ Core: update_referral_status()
├─ Core: mark_bonus_paid()
├─ Core: notify_finance_about_bonus()
├─ Core: notify_employee_about_bonus()
├─ Core: get_pending_bonuses()
├─ Core: get_referral_stats_for_job()
├─ Access: can_view_referral()
├─ Access: get_referrals_for_user()
├─ Access: get_bonuses_for_user()
├─ Access: get_dashboard_view_for_role()
└─ Access: get_job_referral_stats_for_user()

✅ API ENDPOINTS (9 total)
├─ POST /referrals/setup-job-referrals
├─ POST /referrals/record-referral
├─ PUT /referrals/update-referral-status/{id}
├─ GET /referrals/pending-bonuses
├─ POST /referrals/mark-bonus-paid/{id}
├─ GET /referrals/job-referral-stats/{id}
├─ GET /referrals/dashboard/referrals (ROLE-BASED)
├─ GET /referrals/referrals/all (ROLE-BASED)
└─ GET /referrals/bonuses/all (ROLE-BASED)

✅ ROLE-BASED ACCESS (5 levels)
├─ CEO: Org-wide access
├─ Workforce Manager: All bonuses
├─ BU Head/Partner: Their BU only
├─ HR Manager: Their BU (HR view)
├─ Finance: All bonuses for payment
└─ Employee: Own referrals only

✅ TEST SUITE
├─ 14 test classes
├─ 25+ test cases
└─ All scenarios covered
```

---

## What's MISSING (Frontend & UX)

```
❌ TIER 1: CRITICAL - Employee Portal Access

Employee Landing/Dashboard
├─ Referral opportunities widget
├─ New opportunities card (3 open roles, earn bonuses)
├─ Current referral status (2 pending, 1 hired)
└─ Quick action: "Submit Referral" button

Referral Center Portal
├─ Browse all open roles with referral enabled
├─ Each role card shows:
│  ├─ Job title, bonus amount, deadline
│  ├─ Button: "Refer Someone"
│  └─ Your referrals for this job (if any)
└─ Tabs:
   ├─ Open Roles (browse opportunities)
   ├─ My Referrals (status tracking)
   └─ My Earnings (bonus tracker)

Submit Referral Form
├─ Pre-filled from email link (if clicked)
├─ Job: [Auto-filled]
├─ Source: [Auto-filled as EMPLOYEE_REFERRAL]
├─ Your name: [Auto-filled from login]
├─ Candidate Details:
│  ├─ Name (required)
│  ├─ Email (required)
│  ├─ Phone (required)
│  ├─ Resume/LinkedIn (required)
│  └─ Why you recommend them (optional)
├─ Bonus amount displayed (read-only)
└─ Submit button


❌ TIER 2: HIGH - Referral Tracking

My Referrals Dashboard
├─ Summary Cards:
│  ├─ Total Referrals: 10
│  ├─ Active: 3
│  ├─ Hired: 2
│  └─ Earned: $1,500
├─ Status Filter (All, Pending, Screening, Interview, Offered, Hired)
└─ Referral List (Timeline view):
   ├─ Candidate name, job, bonus
   ├─ Current status + days in stage
   ├─ Timeline: Referred → Screening → Interview → Offer → Hired
   └─ Actions: View details, cancel, share

Referral Details Screen
├─ Candidate info (name, email, job)
├─ Full timeline (vertical):
   ├─ ✓ Referred (date)
   ├─ ✓ Screening (date range)
   ├─ ✓ Interview Scheduled (date)
   ├─ ✓ Interviewed (feedback snippet)
   ├─ ✓ Offered (offer details)
   └─ ✓ Hired (onboarded date)
├─ Bonus tracking:
   ├─ Amount: $750
   ├─ Status: PAID / PENDING / APPROVED
   ├─ Payment method: PAYROLL / ACH / CHECK
   ├─ Payment date: 2026-08-15
   └─ Invoice link (for finance)
└─ Actions: Share, Celebrate, Download certificate

Bonus Tracker Screen
├─ Summary:
│  ├─ Total Earned: $1,500
│  ├─ Paid: $1,500
│  └─ Pending: $500
├─ Payment History Table:
│  ├─ Date | Candidate | Job | Amount | Status | Method
│  ├─ 2026-08-15 | Jane Smith | Salesforce | $500 | PAID | PAYROLL
│  ├─ 2026-07-30 | Mike Chen | Guidewire | $750 | PAID | PAYROLL
│  └─ [Pending] | John Doe | Solutions | $750 | PENDING | AWAITING HIRE
└─ Finance:
   ├─ Tax implications
   └─ Download statement


❌ TIER 3: MEDIUM - Email & Notifications

Email System
├─ Trigger: Job created + referral enabled
├─ Recipients: All active employees
├─ Email type: Individual (urgent) or Daily Digest (standard)
├─ Template design:
│  ├─ Subject: "Referral Opportunity - [Job Title] ($[Bonus] bonus!)"
│  ├─ Content:
│  │  ├─ Job description
│  │  ├─ Referral bonus amount
│  │  ├─ Referral link (personalized)
│  │  └─ Referral program details
│  └─ CTA button: "Refer Someone"

In-App Notifications
├─ Notification types:
│  ├─ REFERRAL_SUBMITTED
│  ├─ SCREENING_STARTED
│  ├─ INTERVIEW_SCHEDULED
│  ├─ INTERVIEWED
│  ├─ OFFER_EXTENDED
│  ├─ CANDIDATE_HIRED
│  ├─ BONUS_APPROVED
│  └─ BONUS_PAID
├─ Delivery: In-app + Email + (SMS if preferred)
└─ History: Notification center screen

Email Preferences Screen
├─ Frequency: Individual / Daily Digest / Weekly
├─ Opt-out: Disable email notifications
├─ Job types: Which roles interest you?
└─ Payment notifications: How to notify about bonuses?


❌ TIER 4: HIGH - Role-Based Dashboards

CEO/Executive Dashboard
├─ Org-wide metrics:
│  ├─ Total referrals: 150
│  ├─ Hired: 12
│  ├─ Conversion: 8%
│  ├─ Total bonuses: $9,000
│  └─ Program ROI: $5,700 savings
├─ Charts:
│  ├─ Referrals by status (funnel)
│  ├─ Bonuses by month (spend trend)
│  └─ Conversion rate vs other sources
└─ Actions: Approve major policy changes

BU Head/Partner Dashboard
├─ BU-specific metrics:
│  ├─ Total referrals: 45
│  ├─ Hired: 4
│  ├─ Conversion: 8.9%
│  └─ Bonuses owed: $2,000
├─ Top referrers list:
│  ├─ Alice Johnson: 5 referrals, 1 hired, $750 earned
│  ├─ Bob Smith: 4 referrals, 1 hired, $500 earned
│  └─ Recognition badge: "Top Referrer this month"
└─ Pending bonuses in their BU

HR Manager Dashboard
├─ Pipeline view by status:
│  ├─ Pending: 12 referrals (need screening)
│  ├─ Screening: 8 referrals
│  ├─ Interviewed: 6 referrals
│  ├─ Offered: 3 referrals
│  └─ Hired: 4 referrals
├─ Referral quality metrics:
│  ├─ Total by employee (who's referring?)
│  └─ Conversion by referrer (quality)
└─ Actions: Follow up on pending, thank top referrers

Finance Payment Workflow
├─ Pending bonuses queue:
│  ├─ Card for each pending bonus:
│  │  ├─ Employee name, amount, candidate
│  │  ├─ Hire date, approval status
│  │  └─ Buttons: Approve, Reject, Hold
│  └─ Batch actions: Approve all, Process
├─ Payment processing:
│  ├─ Select payment method (PAYROLL/ACH/CHECK)
│  ├─ Confirm amounts and recipients
│  └─ Generate payment file for payroll
├─ Payment history:
│  ├─ All paid bonuses with dates
│  ├─ Search by employee, date, amount
│  └─ Export CSV for reconciliation
└─ Reports:
   ├─ Monthly referral bonus spend
   ├─ Tax summary (1099 if needed)
   └─ Approval audit trail


❌ TIER 5: MEDIUM - External Referrals & Duplicate Handling

Referral Link Sharing
├─ Personal referral link generator:
│  ├─ For each open job: Generate unique link
│  ├─ Link format: https://blitzenx.com/referral/r/emp_123_job_001_abc123
│  ├─ Tracking: Clicks, applications, hires
│  └─ Analytics: Who you referred, results
├─ Sharing UI:
│  ├─ Button: "Copy Link"
│  ├─ Button: "Email to Friend" (pre-filled template)
│  ├─ Button: "Share on LinkedIn"
│  └─ Button: "Share on WhatsApp/Slack"
└─ Share confirmation:
   ├─ "Link copied to clipboard"
   ├─ Email sent: "Check your email"
   └─ Tracking: "Your friend can apply via this link"

Referral Link Analytics
├─ Dashboard: "Links I've Shared"
├─ For each link:
│  ├─ Clicks: 5
│  ├─ Applications: 2
│  ├─ Hired: 0
│  ├─ Share methods: Email (3), LinkedIn (2)
│  └─ Last clicked: 2 days ago
└─ Actions: Re-share, Copy link, View analytics

Duplicate Candidate Detection
├─ When employee submits referral:
│  ├─ System checks: "We found John Smith in our system!"
│  ├─ Shows previous application history:
│  │  ├─ Applied May 15 (Guidewire Dev) → Rejected
│  │  ├─ Applied Jun 20 (Guidewire Admin) → Rejected
│  │  └─ Reason: Skill gaps in modules, needs admin experience
│  ├─ New role match analysis:
│  │  ├─ Current role: Solutions Architect
│  │  ├─ Why good fit: Doesn't need deep Guidewire
│  │  └─ AI recommendation: "Worth reconsidering"
│  └─ Employee notification:
│     ├─ "You still get the bonus if hired!"
│     ├─ "John's a better fit for this role"
│     └─ "No penalty for resubmitting"
└─ Continue with normal referral flow

Candidate History (Recruiter View)
├─ When recruiter opens candidate:
│  ├─ Alert: "This candidate has previous applications!"
│  ├─ Previous applications:
│  │  ├─ Date, job, status, reason
│  │  ├─ Feedback: "Good communication, skill gap"
│  │  └─ UI: Easy to see why they weren't hired before
│  ├─ Current role fit analysis:
│  │  ├─ Skills gaps resolved? (Yes/No)
│  │  ├─ Recommendation: RECONSIDER (High confidence)
│  │  └─ Why: "Different role type, better match"
│  └─ Actions:
│     ├─ Fast-track to interview (given context)
│     └─ Link to previous feedback
```

---

## Implementation Timeline

### Week 1-2: Employee Portal (CRITICAL)
```
Days 1-3:
- Build referral center portal UI
- Job listing with filters
- My referrals tracking screen
- Bonus tracker screen

Days 4-7:
- Build referral submission form
- Pre-fill from email link
- Validation and error handling
- Testing

Days 8-10:
- Integrate with backend APIs
- Connect to database
- Test end-to-end workflows
- Responsive design (mobile)

Deliverable: Employee can discover jobs, submit referrals, track status
```

### Week 2-3: Email & Notifications (HIGH)
```
Days 11-14:
- Email template design (individual vs digest)
- Email service integration (SendGrid/SES)
- Scheduled email job setup
- Email preference screen

Days 15-17:
- In-app notification system
- Notification center screen
- Notification templates
- Delivery: In-app + Email + SMS (optional)

Days 18-21:
- Testing email sending
- Notification delivery verification
- Preference management testing

Deliverable: Employees receive timely notifications about referral progress
```

### Week 3-4: Duplicate Handling (CRITICAL)
```
Days 22-24:
- Implement duplicate detection
- Candidate merge logic
- Previous application history storage

Days 25-28:
- Build candidate history UI (recruiter view)
- Duplicate detection UI (employee view)
- AI recommendation scoring

Days 29-31:
- Update bonus eligibility logic
- Handle duplicate scenarios
- Testing edge cases

Deliverable: System handles duplicate candidates, employee still gets bonus
```

### Week 4-5: Role-Based Dashboards (HIGH)
```
Days 32-35:
- CEO/Executive dashboard UI
- BU Head/Partner dashboard
- HR Manager dashboard

Days 36-40:
- Finance payment workflow UI
- Pending bonuses queue
- Payment processing screen
- Reports & exports

Days 41-43:
- Integration with backend
- Testing all role views
- Permission verification

Deliverable: Each role sees appropriate dashboard with their data
```

### Week 5-6: External Referrals (MEDIUM)
```
Days 44-47:
- Referral link generation UI
- Link sharing buttons (copy, email, social)
- Link tracking/analytics

Days 48-51:
- Referral link analytics dashboard
- External candidate tracking
- External referral flow (same as internal)

Days 52-55:
- Testing external referral journey
- Analytics verification
- Mobile optimization

Deliverable: Employees can refer external friends with same benefits
```

---

## Dependency Map

```
Employee Portal (Weeks 1-2)
    ├─ Depends on: Backend APIs (✅ DONE)
    └─ Blocks: Everything else

Email System (Weeks 2-3)
    ├─ Depends on: Employee Portal + Backend
    └─ Blocks: Duplicate Handling notifications

Duplicate Handling (Weeks 3-4)
    ├─ Depends on: Employee Portal + Email System
    ├─ Blocks: Role-Based Dashboards (for data clarity)
    └─ Required for: Production readiness

Role-Based Dashboards (Weeks 4-5)
    ├─ Depends on: All previous + RBAC backend (✅ DONE)
    └─ Enables: Management oversight

External Referrals (Weeks 5-6)
    ├─ Depends on: Employee Portal + Duplicate Handling
    └─ Optional but valuable feature
```

---

## Completion Checklist

### Employee Portal (Week 1-2)
- [ ] Referral center portal built and live
- [ ] Job listing with bonus amounts visible
- [ ] Submit referral form working
- [ ] My referrals tracking screen
- [ ] Bonus tracker visible
- [ ] Email link pre-fill working
- [ ] Mobile responsive
- [ ] Accessibility (WCAG AA)
- [ ] End-to-end testing passed

### Email & Notifications (Week 2-3)
- [ ] Email sending working
- [ ] Individual or digest templates
- [ ] Email preferences screen
- [ ] In-app notifications
- [ ] Notification center
- [ ] SMS notifications (optional)
- [ ] Email unsubscribe link
- [ ] Notification testing completed

### Duplicate Handling (Week 3-4)
- [ ] Duplicate detection working
- [ ] Candidate merge logic tested
- [ ] Previous application history visible
- [ ] Employee still earns bonus on duplicate
- [ ] AI recommendation scoring
- [ ] Recruiter sees previous feedback
- [ ] Employee sees "duplicate detected" message
- [ ] Bonus eligibility correctly calculated

### Role-Based Dashboards (Week 4-5)
- [ ] CEO dashboard showing org metrics
- [ ] BU Head sees only their BU
- [ ] HR sees candidate pipeline
- [ ] Finance sees pending bonuses
- [ ] Employee sees personal dashboard
- [ ] All dashboards integrated with backend
- [ ] Role permissions verified
- [ ] Charts and analytics working

### External Referrals (Week 5-6)
- [ ] Referral link generation
- [ ] Link sharing UI (copy, email, social)
- [ ] Link analytics dashboard
- [ ] External candidate tracking
- [ ] External referral flow working
- [ ] Bonuses paid for external referrals
- [ ] Analytics verified

---

## Success Metrics

After full implementation, measure:

### Engagement
- % of employees using referral system (Target: 20%+)
- Avg referrals per referring employee (Target: 2-3)
- Referral submissions per month (Target: 50+)

### Quality
- Referral to interview rate (Target: 40%+)
- Referral to hire rate (Target: 15%+)
- Time to hire for referred candidates (Target: 30 days)

### Finance
- Cost per hire (referred vs other) (Target: Referred 40% cheaper)
- Total bonus spend (Target: $5K-10K/month)
- Program ROI (Target: 2-3x return)

### Satisfaction
- Employee satisfaction with program (Target: 8/10+)
- Hiring manager satisfaction (Target: 8/10+)
- Candidate feedback (Target: 85%+ positive)

---

## Notes

- **Backend is complete** - All APIs ready, role-based access working
- **Frontend is missing** - Zero UI implemented, major effort required
- **Duplicate handling is critical** - Without it, employees lose bonuses
- **Email system is essential** - Without notifications, engagement dies
- **Total effort: 5-6 weeks** for MVP-complete system
- **Team size: 2-3 frontend engineers + 1 QA** recommended

---

**Next Step:** Approve this roadmap and begin Week 1 (Employee Portal)


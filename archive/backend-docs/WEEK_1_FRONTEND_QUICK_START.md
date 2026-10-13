# Week 1: Employee Portal Quick Start Guide

**Timeline:** Monday - Friday (Week 1)  
**Target:** Functional employee referral portal (MVP)  
**Go-Live:** By end of Week 6

---

## YOUR MISSION THIS WEEK

Build screens where employees can:
1. ✅ Discover open jobs with referral bonuses
2. ✅ Submit a referral for a candidate
3. ✅ See how many referrals they've made

**Success Criteria:**
- Employee can click "Refer Someone" button
- Form accepts candidate info (name, email, phone)
- Referral appears in "My Referrals" list
- No errors in console
- Mobile responsive (tablet/mobile)

---

## WEEK 1 DELIVERABLES

### Screen 1: Referral Center Home (Days 1-2)
```
URL: /referral-center

Layout:
├─ Header: "Refer & Earn - Your Gateway to Referral Bonuses"
│
├─ Hero Section
│  ├─ Headline: "Know someone looking for a new opportunity?"
│  ├─ Subheadline: "Earn $500-$2,000 per successful referral"
│  └─ CTA: "View Open Roles"
│
├─ Quick Stats Bar
│  ├─ Total Referrals: [X]
│  ├─ Bonuses Earned: $[X]
│  ├─ Referrals in Progress: [X]
│  └─ This Month's Earnings: $[X]
│
├─ Open Roles Section
│  ├─ Filter Bar:
│  │  ├─ Search: [Text box] "Search jobs..."
│  │  ├─ Priority: [All] [Urgent] [Standard] [Low]
│  │  ├─ Bonus Range: [All] [$250-500] [$500-1000] [$1000+]
│  │  └─ Start Date: [All] [This Week] [This Month]
│  │
│  └─ Job Cards (Grid or List)
│     ├─ Card for each open role with referral enabled
│     ├─ Job Title: Senior Guidewire Developer
│     ├─ Department: [Dept]
│     ├─ Bonus: $750
│     ├─ Start Date: 2026-08-22
│     ├─ Priority Badge: [URGENT] if applicable
│     ├─ Your Referrals: [X] for this job
│     └─ Button: "Refer Someone for This Role"
│
└─ Footer: "Questions? Email referrals@blitzenx.com"

API Integration:
├─ GET /portal/referral-center
│  └─ Returns: List of jobs with referral enabled
│     ├─ job_id, title, department, bonus_amount, start_date, priority
│     └─ referral_count_for_employee (how many they already referred)
```

**Development Tasks:**
- [ ] Create React component: ReferralCenter.jsx
- [ ] Build job filter component
- [ ] Build job card component
- [ ] Integrate with API: GET /portal/referral-center
- [ ] Add loading states
- [ ] Add error handling
- [ ] Style responsive layout
- [ ] Test: Filter by priority, bonus, start date

**Mockup Colors:**
```
Primary: #0066CC (Blue)
Success: #28A745 (Green for "Urgent" badge)
Warning: #FFC107 (Yellow for bonuses)
Neutral: #6C757D (Gray)
```

---

### Screen 2: Submit Referral Form (Days 2-3)
```
URL: /referral-center/submit?job_id=[id]
OR: /referral-center/submit (manual job selection)

Form Layout:
├─ Header: "Refer a Candidate"
│  └─ Subheader: "Earn $750 when they're hired!"
│
├─ Job Selection Section (if not pre-filled)
│  ├─ Label: "Which job are you referring for?"
│  ├─ Dropdown: [Select a job...]
│  └─ Info: Shows job title, bonus, start date when selected
│
├─ Candidate Information Section
│  ├─ Name: [Text input] (required)
│  │  └─ Placeholder: "John Doe"
│  │
│  ├─ Email: [Email input] (required)
│  │  └─ Placeholder: "john.doe@external.com"
│  │  └─ Validation: Must be valid email, cannot be your email
│  │
│  ├─ Phone: [Phone input] (required)
│  │  └─ Placeholder: "(555) 123-4567"
│  │
│  ├─ How do you know them?: [Dropdown] (optional)
│  │  ├─ College friend
│  │  ├─ Previous coworker
│  │  ├─ Industry connection
│  │  ├─ Friend/Family
│  │  └─ Other
│  │
│  ├─ Why do you recommend them?: [Textarea] (optional)
│  │  └─ Placeholder: "Tell us why they'd be a great fit..."
│  │  └─ Max 500 characters
│  │
│  ├─ Resume: [File upload] (optional but recommended)
│  │  └─ Accept: .pdf, .doc, .docx
│  │  └─ Max size: 5 MB
│  │
│  └─ LinkedIn URL: [Text input] (optional)
│     └─ Placeholder: "https://linkedin.com/in/..."
│
├─ Summary Section (Read-only)
│  ├─ Job: [Selected job title]
│  ├─ Bonus: $[Amount]
│  └─ Message: "If [Candidate Name] is hired, you'll receive $[Amount]"
│
└─ Actions
   ├─ Submit Button: "Submit Referral" (blue, prominent)
   └─ Cancel Link: "Cancel"

Pre-fill Logic (if from email link):
├─ URL params: ?job_id=job_001&ref_emp=emp_123
├─ Pre-fill: Job selection (job_id)
├─ Pre-fill: Employee name (from login, not visible but used)
└─ Focus: Name field (ready to type)

Validation Rules:
├─ Name: Required, 2-50 characters
├─ Email: Required, valid format, not employee's email
├─ Phone: Required, valid phone format
├─ Job: Required, must have referral enabled
├─ Resume: Optional, but < 5 MB if provided
├─ LinkedIn: Optional, must be valid URL if provided

Error States:
├─ "Please enter a valid email address"
├─ "You can't refer yourself!"
├─ "Please select a job"
├─ "This candidate is already in our system!"
└─ "Resume file too large (max 5 MB)"

Success State:
├─ Message: "✓ Referral submitted successfully!"
├─ Content: "John Doe has been submitted for [Job]"
├─ Content: "Bonus potential: $750 if hired"
├─ Content: "You can track status in 'My Referrals'"
├─ Action: "View My Referrals" link
└─ Redirect: After 2 seconds to "My Referrals"

API Integration:
├─ POST /portal/refer-candidate
│  ├─ Request: job_id, candidate_name, candidate_email, candidate_phone,
│  │          how_you_know_them, why_recommend, resume_url, linkedin_url
│  └─ Response: referral_id, status, bonus_amount, message
│
└─ GET /portal/referral-center (for job list if not pre-filled)
```

**Development Tasks:**
- [ ] Create React component: SubmitReferralForm.jsx
- [ ] Build form with all fields
- [ ] Add form validation
- [ ] Handle resume upload
- [ ] Pre-fill from URL params (job_id, ref_emp)
- [ ] Integrate with API: POST /portal/refer-candidate
- [ ] Add success/error messages
- [ ] Loading state while submitting
- [ ] Mobile responsive
- [ ] Test: All validation rules

---

### Screen 3: My Referrals Dashboard (Days 3-4)
```
URL: /referral-center/my-referrals

Layout:
├─ Header: "My Referrals"
│  └─ Subheader: "Track your referrals and earnings"
│
├─ Summary Stats (4 cards)
│  ├─ Card 1: Total Referrals
│  │  ├─ Number: [X]
│  │  └─ Subtitle: "You've referred X candidates"
│  │
│  ├─ Card 2: Active Referrals
│  │  ├─ Number: [X]
│  │  └─ Subtitle: "In screening, interview, or offered"
│  │
│  ├─ Card 3: Hired
│  │  ├─ Number: [X]
│  │  └─ Subtitle: "Successful hires!"
│  │
│  └─ Card 4: Bonuses Earned
│     ├─ Amount: $[X]
│     └─ Subtitle: "Total bonuses earned"
│
├─ Filters & Search
│  ├─ Status Filter:
│  │  ├─ [All] [Pending] [Screening] [Interviewed] [Offered] [Hired]
│  │  └─ Shows count for each: [All (5)] [Pending (2)] [Screening (1)]...
│  │
│  └─ Search: [Text box] "Search by candidate name or job..."
│
├─ Referrals List/Table
│  ├─ Column 1: Candidate Name (sortable)
│  ├─ Column 2: Job Title (sortable)
│  ├─ Column 3: Status (badge with color) (filterable)
│  │  ├─ Badge Colors:
│  │  │  ├─ PENDING: Gray
│  │  │  ├─ SCREENING: Blue
│  │  │  ├─ INTERVIEWED: Purple
│  │  │  ├─ OFFERED: Green
│  │  │  └─ HIRED: Gold ⭐
│  │  │
│  │  └─ Days in Current Stage: (e.g., "5 days")
│  │
│  ├─ Column 4: Bonus Amount (sortable)
│  │  ├─ $[Amount] if not yet hired (pending)
│  │  └─ $[Amount] ✓ EARNED if hired
│  │
│  ├─ Column 5: Date Referred (sortable)
│  │  └─ "2 days ago" or date format
│  │
│  └─ Column 6: Actions
│     ├─ Link: "View Details"
│     ├─ Link: "View Timeline"
│     └─ Link: "Share" (email to friend - optional)
│
├─ Referral Row Example:
│  ├─ Jane Smith | Salesforce Admin | HIRED ⭐ (8 days) | $500 ✓ EARNED | 2026-08-01 | [View Details]
│  ├─ John Doe | Senior Dev | INTERVIEWED (5 days) | $750 | 2026-08-05 | [View Details]
│  └─ Mike Johnson | Support Eng | REJECTED (15 days) | $0 | 2026-07-20 | [View Details]
│
└─ Pagination (if > 10 referrals)
   ├─ Previous | 1 2 3 ... 5 | Next
   └─ Showing 1-10 of 23 referrals

Empty State (if no referrals):
├─ Icon: 📋
├─ Headline: "No referrals yet"
├─ Message: "Start referring candidates to earn bonuses!"
└─ Button: "Refer Someone"

API Integration:
├─ GET /portal/my-referrals
│  ├─ Params: status (optional), search (optional), page, limit
│  └─ Returns: List of referrals
│     ├─ referral_id, candidate_name, job_title, status, bonus_amount,
│     ├─ created_date, days_in_stage, bonus_earned_flag
│     └─ pagination info
```

**Development Tasks:**
- [ ] Create React component: MyReferralsDashboard.jsx
- [ ] Build summary stats cards
- [ ] Build filter/search bar
- [ ] Build referrals table/list
- [ ] Implement pagination
- [ ] Add status badges with colors
- [ ] Sort by column (name, job, date)
- [ ] Filter by status
- [ ] Search by candidate name
- [ ] Integrate with API: GET /portal/my-referrals
- [ ] Empty state handling
- [ ] Mobile responsive (table → cards on mobile)

---

### Screen 4: Referral Details (Days 4-5)
```
URL: /referral-center/referral/[referral_id]

Layout:
├─ Header: "Referral Details"
│  └─ Back link: "← Back to My Referrals"
│
├─ Candidate Info Card
│  ├─ Candidate Photo: [Profile pic or initials]
│  ├─ Name: Jane Smith
│  ├─ Email: jane.smith@external.com
│  ├─ Phone: (555) 123-4567
│  └─ Job: Salesforce Admin
│
├─ Status Timeline (Vertical)
│  ├─ ✓ REFERRED (Aug 01, 2026)
│  │  └─ "You referred Jane Smith"
│  │
│  ├─ ✓ SCREENING (Aug 02-05, 3 days)
│  │  └─ "HR reviewed resume"
│  │
│  ├─ ✓ INTERVIEW SCHEDULED (Aug 05)
│  │  └─ "Interview set for Aug 08"
│  │
│  ├─ ✓ INTERVIEWED (Aug 08)
│  │  └─ "Interview completed, good feedback"
│  │
│  ├─ ✓ OFFERED (Aug 09)
│  │  └─ "Offer extended, awaiting response"
│  │
│  ├─ ✓ HIRED (Aug 09)
│  │  └─ "Jane accepted and onboarded!"
│  │  └─ Status: "Onboarded successfully"
│  │
│  └─ Timeline Summary: "Total time: 9 days"
│
├─ Bonus Tracking Section
│  ├─ Bonus Amount: $500.00
│  ├─ Status: PAID ✓
│  ├─ Payment Method: PAYROLL
│  ├─ Payment Date: 2026-08-15
│  ├─ Message: "Your bonus of $500 was paid on 2026-08-15 via PAYROLL"
│  └─ Details:
│     ├─ Bonus ID: bon_001
│     ├─ Expected Paycheck: 2026-08-22
│     └─ Invoice: INV-2026-00456
│
└─ Actions
   ├─ Button: "View Candidate Profile" (if available)
   └─ Link: "Back to My Referrals"

Different Status States:

PENDING Status:
├─ Timeline: Only REFERRED shown
├─ Bonus: "$500 potential if hired"
├─ Message: "We're reviewing Jane's application. Check back soon!"

SCREENING Status:
├─ Timeline: REFERRED → SCREENING shown
├─ Bonus: "$500 potential if hired"
├─ Days in stage: "5 days in screening"
├─ Message: "HR is reviewing Jane's qualifications."

REJECTED Status:
├─ Timeline: All stages up to rejection shown
├─ Bonus: "$0 (Not qualified)"
├─ Message: "Thanks for the referral! Jane wasn't the right fit for this role."

HIRED Status:
├─ Timeline: All stages shown (complete journey)
├─ Bonus: "$500 EARNED ✓"
├─ Payment status: PENDING / APPROVED / PAID
├─ Message: "Congratulations! Jane has been hired and onboarded!"

API Integration:
├─ GET /portal/referral/[referral_id]
│  └─ Returns: Full referral details
│     ├─ candidate_name, email, phone, job_title
│     ├─ status, created_date, timeline (all stage dates)
│     ├─ bonus_amount, bonus_status, payment_date, payment_method
│     └─ feedback (if any)
```

**Development Tasks:**
- [ ] Create React component: ReferralDetails.jsx
- [ ] Build candidate info card
- [ ] Build timeline component (vertical)
- [ ] Build bonus tracker section
- [ ] Integrate with API: GET /portal/referral/[id]
- [ ] Handle all status states
- [ ] Show payment details if paid
- [ ] Mobile responsive
- [ ] Test: Click from list to details

---

### Screen 5: Bonus Tracker (Days 5)
```
URL: /referral-center/bonuses

Layout:
├─ Header: "My Referral Bonuses"
│  └─ Subheader: "Track your earnings"
│
├─ Summary Cards (3)
│  ├─ Total Earned: $[X]
│  ├─ Paid This Year: $[X]
│  └─ Pending/Potential: $[X]
│
├─ Bonus History Table
│  ├─ Column 1: Date Earned (sortable)
│  ├─ Column 2: Candidate (sortable)
│  ├─ Column 3: Job (sortable)
│  ├─ Column 4: Bonus Amount (sortable)
│  ├─ Column 5: Status (badge - PENDING/APPROVED/PAID)
│  ├─ Column 6: Payment Date
│  └─ Column 7: Payment Method (PAYROLL/ACH/CHECK)
│
├─ Bonus Row Example:
│  ├─ 2026-08-15 | Jane Smith | Salesforce | $500 | PAID | 2026-08-15 | PAYROLL
│  ├─ 2026-08-08 | Mike Chen | Guidewire | $750 | PAID | 2026-08-08 | PAYROLL
│  └─ [Pending] | John Doe | Solutions | $750 | PENDING | - | AWAITING
│
├─ Filters
│  ├─ Status: [All] [Pending] [Approved] [Paid]
│  ├─ Date Range: [All] [This Month] [Last 3 Months] [Last Year]
│  └─ Search: [By candidate name or job]
│
└─ Actions
   └─ Button: "Download Statement" (PDF or CSV)

Empty State:
├─ Message: "No bonuses yet"
└─ Hint: "Submit referrals to start earning!"

API Integration:
├─ GET /portal/my-bonuses
│  ├─ Params: status, date_range, search
│  └─ Returns: Bonus list with all details
│
└─ GET /portal/download-statement
   └─ Returns: PDF/CSV file
```

**Development Tasks:**
- [ ] Create React component: BonusTracker.jsx
- [ ] Build summary cards
- [ ] Build bonus history table
- [ ] Add filters and search
- [ ] Integrate with API: GET /portal/my-bonuses
- [ ] Download statement functionality
- [ ] Mobile responsive
- [ ] Sorting by columns

---

## DAILY STANDUP TEMPLATE

**Daily Progress Check:**
```
Day 1 (Monday):
├─ Morning: Setup React project, install dependencies
├─ Midday: Build ReferralCenter.jsx (home page)
├─ EOD: API integration for GET /portal/referral-center
└─ Done: Screen 1 complete

Day 2 (Tuesday):
├─ Morning: Build SubmitReferralForm.jsx
├─ Midday: Form validation, error handling
├─ EOD: API integration for POST /portal/refer-candidate
└─ Done: Screen 2 complete

Day 3 (Wednesday):
├─ Morning: Build MyReferralsTab.jsx
├─ Midday: Table, filters, pagination
├─ EOD: API integration for GET /portal/my-referrals
└─ Done: Screen 3 complete

Day 4 (Thursday):
├─ Morning: Build ReferralDetails.jsx
├─ Midday: Timeline component, status states
├─ EOD: API integration for GET /portal/referral/[id]
└─ Done: Screen 4 complete + Bonus Tracker started

Day 5 (Friday):
├─ Morning: Complete BonusTracker.jsx
├─ Midday: Polish all screens, mobile responsive
├─ EOD: Testing, bug fixes, code review
└─ Done: All 5 screens complete, ready for testing
```

---

## API ENDPOINTS NEEDED (Backend to provide)

**Already Built (use these):**
```
✅ POST /referrals/setup-job-referrals
✅ POST /referrals/record-referral
✅ PUT /referrals/update-referral-status/{id}
✅ GET /referrals/dashboard/referrals (role-based)
✅ GET /referrals/referrals/all (role-based)
```

**Need to Build (for Week 1 Frontend):**
```
🔴 GET /portal/referral-center (list jobs with referral enabled)
🔴 POST /portal/refer-candidate (submit referral)
🔴 GET /portal/my-referrals (employee's referrals with pagination)
🔴 GET /portal/referral/{referral_id} (detail view)
🔴 GET /portal/my-bonuses (bonus tracker)
```

**Backend Should Provide By Monday:**
- [ ] Documentation for all 5 endpoints
- [ ] Sample response JSON
- [ ] Authentication method
- [ ] Error codes and messages
- [ ] Rate limiting info

---

## TECH STACK

**Frontend:**
```
Framework: React 18+
State: Redux or Context API
UI Components: Material-UI or Tailwind
Forms: React Hook Form or Formik
HTTP: Axios or Fetch API
File Upload: React Dropzone
Routing: React Router v6+
```

**Browser Support:**
- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Mobile: iOS Safari, Chrome Android

---

## RESOURCES PROVIDED

**Documentation:**
- ✅ DECISIONS_LOCKED_IMPLEMENTATION_SPECS.md (comprehensive)
- ✅ REFERRAL_UX_GAPS_AND_STAKEHOLDER_MAPPING.md (stakeholder view)
- ✅ IMPLEMENTATION_ROADMAP.md (timeline)
- ✅ This file (Week 1 quick start)

**Backend:**
- ✅ Database models (Candidate, EmployeeReferral, ReferralBonus)
- ✅ Service layer (14 methods)
- ✅ Existing API endpoints (use these)
- ✅ Role-based access control (use for auth)

**Testing:**
- ✅ Test user credentials: Admin@blitzenx.com / Admin!123
- ✅ Dev server: http://localhost:8080
- ✅ API documentation: Swagger at /docs

---

## SUCCESS = Week 1 DONE

```
✅ Employee can see "Refer & Earn" section
✅ Employee can click "Refer Someone"
✅ Form accepts candidate details
✅ Referral appears in "My Referrals"
✅ Bonus amount displays
✅ No console errors
✅ Mobile responsive
✅ Code reviewed and ready for Week 2
```

---

## BLOCKERS TO ESCALATE

If you hit any of these, escalate immediately:
- Backend APIs not responding
- Authentication not working
- Database connection issues
- Unclear API response format
- Missing required endpoints

**Escalation Contact:** [Backend Lead]

---

**You've got this! 🚀 Build something awesome!**

Frontend team: You're 1/3 of the way to making this program real. Employees are waiting to earn referral bonuses. Let's ship Week 1 on Friday!


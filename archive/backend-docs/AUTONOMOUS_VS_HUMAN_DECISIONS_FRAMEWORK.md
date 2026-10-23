# AUTONOMOUS VS HUMAN DECISIONS FRAMEWORK
## What the System Auto-Does vs. What Needs Human Tasks

**Core Principle:** Only create tasks for decisions that REQUIRE human judgment. 
Automate everything else.

---

## EXAMPLE 1: CANDIDATE CREATED

### Event: New Candidate Added (Resume + Contact Info)

---

## SYSTEM DOES AUTOMATICALLY (NO TASK)

### 1. Parsing & Extraction (Autonomous)
```
✅ Parse resume PDF/file
✅ Extract: Name, email, phone, location, work history, education, skills
✅ Structure into candidate profile fields
✅ Identify Guidewire experience & years (match R-09: Core-Pull rule)
```

### 2. Validation (Autonomous)
```
✅ Validate email format
✅ Validate phone number
✅ Check for duplicates (same email, name) within tenant
✅ Verify contact info is reachable
✅ Flag suspicious patterns (incomplete profile, obviously fake)
```

### 3. Scoring (Autonomous)
```
✅ Calculate profile completeness % (education, skills, availability, references)
✅ Extract Guidewire experience years
✅ Categorize role (Developer, Architect, Business Analyst, etc.)
✅ Identify skills tags (Java, Cloud, etc.)
✅ Basic qualification score (meets minimum years? meets minimum skills?)
```

### 4. Automated Communications (Autonomous)
```
✅ Send auto-response email to candidate (thanks for applying)
✅ Send verification email (confirm email address)
✅ Send 1st qualification questions via WhatsApp/Email (system-driven)
```

### 5. Workflow Initiation (Autonomous)
```
✅ Create workspace (already done in HRMS-0401)
✅ Log audit trail entry
✅ Trigger background check (if applicable)
✅ Trigger visa sponsorship check (if applicable)
✅ Queue for initial AI qualification questions
```

### 6. Data Enhancement (Autonomous)
```
✅ Run LinkedIn scraper (if profile found) → get additional data
✅ Run skill validation tool → verify claimed skills
✅ Run market rate lookup → get typical compensation for role
✅ Create initial candidate score (1-10)
```

---

## HUMAN MUST DECIDE (CREATE TASK)

### TASK 1: "Initial Screening Review"
**When:** Immediately after candidate created + auto-scoring done  
**Owner:** Assigned Recruiter  
**What Recruiter Sees in Email:**
```
Subject: New Candidate Review - John Doe (Score: 7/10)

John Doe - Java Developer
Experience: 8 years (5+ Guidewire) ✅
Skills: Java, Spring Boot, AWS ✅
Location: Portland, OR
Rate Expectation: $150/hour

Quick Score:
✅ Meets experience minimum (5+ years Guidewire)
✅ Has required skills
❓ No AWS project details yet
❓ Availability unclear

[QUICK DECISION - 2 minutes]
┌─────────────────────────────────┐
│ ✓ Worth pursuing                │
│ ✗ Not a fit (explain)           │
│ ❓ Needs more info (ask what)   │
└─────────────────────────────────┘

[If Worth Pursuing]
Match to demand: [Dropdown list of open demands]
```

**Why Human Decision?**
- Market knowledge: "Is $150/hour realistic for this skill level?"
- Judgment call: "Does 5 years Guidewire count if it's all one job?"
- Demand knowledge: "Do we have ANY open role for this skill set?"
- Relationship: "Is this someone worth developing (even if not perfect fit)?"
- Context: "What's our current fill rate? Can we afford to pass on good candidates?"

**System Cannot Do This:**
- ❌ Decide if worth pursuing (business judgment)
- ❌ Choose which demand to match (market knowledge)
- ❌ Negotiate rate (relationship)
- ❌ Prioritize over other candidates (portfolio management)

---

### TASK 2: "Complete Candidate Profile" (Only if system got partial data)
**When:** IF resume parsing failed or candidate uploaded partial profile  
**Owner:** Candidate (or Recruiter if candidate unresponsive)  
**What Recruiter Sees in Email:**
```
Subject: Complete Profile - John Doe (Incomplete)

We need a bit more info from John to move forward.

Missing:
❌ Education details (diploma/certification)
❌ Professional references (2+ required)
❌ Current availability (start date)
❌ Visa sponsorship needed? (Yes/No)

[SEND TO CANDIDATE]
{link_to_portal_form}

Deadline: 24 hours (or candidate drops to inactive)
```

**Why Human Decision?** 
- Recruiter decides if worth the follow-up (vs. just closing)
- Recruiter knows which fields are critical (and can skip if rushing hire)
- Relationship: "Should we follow up? Do we have time?"

**System Cannot Do This:**
- ❌ Decide if candidate worth pursuing (already did in Task 1)
- ❌ Know which fields are CRITICAL vs. nice-to-have

---

### TASK 3: "Approve Qualification & Schedule Interview"
**When:** After candidate completes profile + AI qualification done  
**Owner:** Recruiter  
**What Recruiter Sees in Email:**
```
Subject: Interview Decision - John Doe (AI: Recommended / Not Recommended)

CANDIDATE PROFILE COMPLETE ✅
Profile Completeness: 95%

AI Qualification Assessment:
✅ Meets all hard requirements (8 years exp, Guidewire, Java, AWS)
✅ Technical score: 8/10
✓ Communication: Excellent
✓ Problem-solving: Good
⚠️ Cloud experience: Limited (but willing to learn)

AI Recommendation: INTERVIEW THIS CANDIDATE
Confidence: 85%

[RECRUITER DECISION - 5 minutes]
┌──────────────────────────────┐
│ ✓ Interview (Schedule when?) │
│ ✗ Reject with feedback       │
│ ❓ Request more info         │
│ 💬 Discuss with manager      │
└──────────────────────────────┘
```

**Why Human Decision?**
- Context: "Do we have time to interview RIGHT NOW or should we batch?"
- Pipeline: "Is this candidate better than others in queue?"
- Role fit: "Does AI assessment match the actual job we need filled?"
- Relationship: "Should recruiter personally call? Or auto-schedule?"
- Negotiation: "Can we negotiate this candidate's rate preference?"

**System Cannot Do This:**
- ❌ Decide GO/NO-GO (even with AI recommendation)
- ❌ Choose interview timing (business context)
- ❌ Prioritize among candidates (portfolio management)
- ❌ Know if role is still open (demand might have filled)

---

## EXAMPLE 2: INTERVIEW SCHEDULED

### Event: Interview Confirmed with Candidate

---

## SYSTEM DOES AUTOMATICALLY (NO TASK)

```
✅ Send calendar invite to both parties
✅ Add to calendar (iCal/Teams/Outlook)
✅ Set up video call link (Zoom/Teams)
✅ Send prep materials to interviewer
✅ Send interview details to candidate
✅ Set reminder for 24h before
✅ Log in calendar system
✅ Update candidate status → "INTERVIEW_SCHEDULED"
```

---

## HUMAN MUST DECIDE (CREATE TASKS)

### TASK 1: "Prepare for Interview" (Interviewer)
**Why Human?**
- Read candidate's resume (AI summary not enough)
- Prepare specific technical questions (role-specific)
- Review candidate's background (context)
- Decide interview format (technical deep-dive vs. culture fit vs. both)
- Arrange appropriate interview setting (quiet room?)

---

### TASK 2: "Confirm Interview Availability" (Candidate)
**Why Human?** 
- Candidate might have questions
- Candidate might realize they're not available
- Candidate might want to reschedule
- Candidate might want to ask about role

---

## EXAMPLE 3: OFFER GENERATED

### Event: Offer Letter Created (Auto-generated with candidate data)

---

## SYSTEM DOES AUTOMATICALLY (NO TASK)

```
✅ Generate offer letter (template + variables)
✅ Calculate compensation (base + bonus + benefits)
✅ Set start date (from conversation)
✅ Set offer expiration (14 days standard)
✅ Add all legal/compliance clauses
✅ Format as PDF
✅ Sign digitally (if policy allows)
```

---

## HUMAN MUST DECIDE (CREATE TASKS)

### TASK 1: "Approve Offer" (Manager)
**Why Human?**
- Approve compensation level (budget authority)
- Approve start date (team readiness)
- Approve any special conditions (visa sponsorship, remote work)
- Decide if offer is competitive (market knowledge)
- Check if budget still available (hiring freeze? Budget changed?)

**System Cannot:**
- ❌ Decide if offer is business-wise sound
- ❌ Commit organizational budget
- ❌ Negotiate with candidate

---

### TASK 2: "Respond to Offer" (Candidate)
**Why Human?**
- Candidate might negotiate
- Candidate might decline
- Candidate might ask questions
- Candidate might request changes (start date, remote work, etc.)

---

## EXAMPLE 4: WORK ORDER CREATED

### Event: Employee Assigned to Project (Work Order)

---

## SYSTEM DOES AUTOMATICALLY (NO TASK)

```
✅ Create work order record
✅ Set billing rate (from job rate card)
✅ Set pay rate (from employee contract)
✅ Calculate expected hours
✅ Add project details (client, location, start date)
✅ Set up invoicing schedule
✅ Send client notification (if automation enabled)
✅ Create timesheet template
```

---

## HUMAN MUST DECIDE (CREATE TASKS)

### TASK 1: "Confirm Assignment Acceptance" (Employee)
**Why Human?**
- Employee might have conflict (another project, vacation)
- Employee might have questions about role
- Employee might need clarifications (location, hours, etc.)
- Employee might need onboarding coordination

---

### TASK 2: "Prepare for Kickoff" (Manager)
**Why Human?**
- Arrange kickoff meeting with client
- Prepare SOW/expectations document
- Arrange equipment/access/credentials for employee
- Brief employee on client expectations
- Coordinate with project team

---

## EXAMPLE 5: DEMAND CREATED

### Event: New Demand/Job Requisition (Hiring Need)

---

## SYSTEM DOES AUTOMATICALLY (NO TASK)

```
✅ Create demand record
✅ Set required skills/experience from template
✅ Set budget rate from salary band
✅ Set timeline (hiring needed by X date)
✅ Calculate bench utilization (how many resources needed)
✅ Match against bench profiles (which available employees could fill?)
✅ Create job description (from template)
```

---

## HUMAN MUST DECIDE (CREATE TASK)

### TASK 1: "Approve Demand & Prioritize"
**Why Human?**
- Approve if hiring is still needed (circumstances might have changed)
- Approve rate/compensation level (budget)
- Approve timeline (urgent vs. backlog)
- Decide sourcing strategy (internal bench vs. external hiring)
- Approve job description (might need tweaks)

**System Cannot:**
- ❌ Know if business conditions changed
- ❌ Know current budget situation
- ❌ Know hiring priorities
- ❌ Make organizational decisions

---

## FRAMEWORK: AUTONOMOUS VS HUMAN

### Pattern 1: Data Collection → Auto
```
Resume uploaded
    ↓
System extracts data (autonomous)
    ↓
NO TASK - System handles this
```

### Pattern 2: Decision Required → Human Task
```
Data collected (complete)
    ↓
System provides context/recommendation
    ↓
TASK: "Human must decide"
```

### Pattern 3: Negotiation/Relationship → Human Task
```
System generates offer
    ↓
Candidate must accept/negotiate
    ↓
TASK: "Candidate decision needed"
```

### Pattern 4: Implementation After Decision → Auto
```
Decision made (approved offer)
    ↓
System executes (sends offer, creates work order, etc.)
    ↓
NO TASK - System handles this
```

---

## COMPLETE WORKFLOW: CANDIDATE TO HIRE

```
[AUTONOMOUS PHASE 1]
Candidate Applied
    ↓
Resume parsed automatically ✅
Skills extracted automatically ✅
Profile scored automatically ✅
Qualification questions sent automatically ✅
Background check triggered automatically ✅

[HUMAN PHASE 1]
TASK: "Initial Screening Review" → Recruiter
    Decision: Worth pursuing? If yes → match to demand
    
[AUTONOMOUS PHASE 2]
Candidate responds to questions ✅
AI qualification assessment run ✅
Interview prep materials generated ✅

[HUMAN PHASE 2]
TASK: "Approve Qualification & Schedule Interview" → Recruiter
    Decision: Interview now? When? In what format?

[AUTONOMOUS PHASE 3]
Calendar invites sent ✅
Interview reminder sent ✅
Interview room booked ✅

[HUMAN PHASE 3]
TASK: "Prepare for Interview" → Interviewer
    Action: Read resume, prepare questions, arrange setting

TASK: "Confirm Interview Availability" → Candidate
    Action: Confirm they're still available, ask questions

[INTERVIEW HAPPENS]
Human takes place

[AUTONOMOUS PHASE 4]
Interview feedback request sent ✅
Feedback form ready ✅

[HUMAN PHASE 4]
TASK: "Provide Interview Feedback" → Interviewer
    Decision: Go/No-Go? Why?

TASK: "Review Feedback & Decide Next Step" → Recruiter
    Decision: Hire? Reject? Ask for more info?

[AUTONOMOUS PHASE 5]
Offer generated ✅
Offer letter created ✅
Benefits summary created ✅

[HUMAN PHASE 5]
TASK: "Approve Offer" → Manager/HR
    Decision: Compensation OK? Start date OK? Budget OK?

TASK: "Respond to Offer" → Candidate
    Action: Accept/decline/negotiate

[AUTONOMOUS PHASE 6]
Offer sent ✅
Work order created ✅
Invoicing set up ✅
Timesheet template created ✅
Employee onboarding workflow triggered ✅

[HUMAN PHASE 6]
TASK: "Confirm Assignment" → Employee
    Action: Confirm availability and readiness

TASK: "Prepare for Kickoff" → Manager
    Action: Arrange meeting, prepare materials, brief team

[HIRE COMPLETE]
Employee starts work on project 🎉
```

---

## TASK TYPES: REVISED (Only Human Decisions)

| Event | AUTONOMOUS Actions | HUMAN TASK | Why Human? |
|-------|-------------------|-----------|-----------|
| Candidate Created | Parse resume, extract skills, score completeness, send auto-response | "Initial Screening" | Decide if worth pursuing |
| Candidate Responds | Validate responses, run AI qualification | "Review Qualification" | Decide go/no-go for interview |
| Interview Scheduled | Send invites, create video link, send reminders | "Prepare for Interview" | Read resume, prepare questions |
| Interview Done | Log feedback form ready | "Provide Feedback" | Judge candidate performance |
| Feedback Received | Compile feedback, create summary | "Review & Decide Next" | Hire or reject? Why? |
| Offer Approved | Generate letter, set expiration | "Approve Offer" | Budget OK? Compensation fair? |
| Offer Sent | Track acceptance, set reminders | "Respond to Offer" | Accept, decline, or negotiate |
| Offer Accepted | Create work order, set up invoicing, triggers onboarding | "Confirm Assignment" | Employee confirms readiness |
| Work Starts | Log time tracking, etc. | "Prepare Kickoff" | Manager arranges team meeting |

---

## KEY INSIGHT

### Tasks Should Represent DECISION POINTS, Not Workflows

**Wrong Task (Workflow, not decision):**
```
❌ "Complete Candidate Profile"
   (This is a workflow the system drives, not a human decision)

❌ "Parse Resume" 
   (System does this automatically)

❌ "Extract Skills"
   (System does this automatically)
```

**Right Tasks (Decision points):**
```
✅ "Initial Screening Review"
   (Recruiter decides: worth pursuing?)

✅ "Review Qualification & Decide Interview"
   (Recruiter decides: interview now or not?)

✅ "Approve Offer"
   (Manager decides: is compensation OK? Budget OK?)

✅ "Provide Interview Feedback"
   (Interviewer decides: hire or no-hire? Why?)

✅ "Review Feedback & Make Go/No-Go Decision"
   (Recruiter decides: hire or reject? Next steps?)
```

---

## GUIDELINE: When to Create a Task

**Create a task when:**
- ✅ Human judgment is required (decision, not just action)
- ✅ Multiple options exist and human must choose
- ✅ Business context matters (budget, timing, prioritization)
- ✅ Relationship/negotiation involved
- ✅ Approval/authorization needed
- ✅ Exception handling required

**DON'T create a task when:**
- ❌ System can do it fully automatically
- ❌ No decision needed (just workflow execution)
- ❌ No human judgment required
- ❌ Data collection/validation (system handles)
- ❌ Communication (system-driven, one-way)

---

## RESULT: Lean Task System

Instead of 50+ task types, you really need ~20 core decision tasks:

1. Initial Screening Review
2. Review Qualification & Decide Interview
3. Prepare for Interview
4. Provide Interview Feedback
5. Review Feedback & Decide Next Step
6. Approve Offer
7. Respond to Offer
8. Confirm Work Assignment
9. Prepare for Kickoff
10. Approve Demand
11. Match Candidate to Demand
12. Approve Timesheet
13. Approve Invoice
14. Review Escalation
15. Handle Exception
16. Manager Approval (generic)
17. HR Approval (generic)
18. Client Approval (if applicable)
19. Budget Approval
20. Performance Review

**~20 core tasks** that represent real human decisions.

All other actions → **Automated by system.**

---

## UPDATED EMAIL STRATEGY

### Instead of "Task Created → Email Sent"

### Now: "Decision Point Reached → Email Sent"

**Example Email:**
```
Subject: Action Needed: John Doe - Initial Screening

John Doe just applied. Quick review needed.

WHAT SYSTEM DID:
✅ Parsed resume
✅ Extracted 8 years Guidewire experience
✅ Identified Java, Spring Boot, AWS skills
✅ Calculated 85/100 compatibility score
✅ Ran background check (pending results)

WHAT RECRUITER MUST DECIDE:
Is this candidate worth pursuing?

[VIEW FULL PROFILE]
[✓ Worth pursuing → Match to demand]
[✗ Not a fit → Reject with feedback]
[❓ Need more info → Request from candidate]

This takes 2-3 minutes.
```

**Much better than:** "Complete candidate profile" (which system auto-collects)

---

## CONCLUSION

**Task = Decision Point Where Human Judgment is Required**

**Not Task = System Workflow Execution**

Most candidate lifecycle work is **autonomous.**

Only **decision points** become tasks.

This means:

- ✅ 50 autonomous actions per candidate
- ✅ 3-4 human decision tasks per candidate
- ✅ Recruiter focused on what matters (decisions)
- ✅ System handles the rest
- ✅ Much leaner, more efficient

This is the **right model**.

---

## REVISED PHASE 3 SCOPE

Not "all events create tasks."

**Rather: "All decision points create tasks."**

The system handles:
- Data collection ✅
- Validation ✅
- Scoring ✅
- Automated actions ✅
- Communications (one-way) ✅

Human handles:
- All decisions ✅
- All judgments ✅
- All approvals ✅
- All negotiations ✅
- Relationship/context ✅

**Phase 3 builds infrastructure for the decision points.**

**That's what matters.**

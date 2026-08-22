# Business Unit Implementation - Autonomous & Cascading Design (2026-08-12)

## Core Philosophy
**BU should be implicit, not explicit.** Users shouldn't have to choose BU - the system should know it.

---

## 🤖 AUTONOMY PRINCIPLES

### Rule 1: Auto-Derive, Don't Ask
**Instead of:**
```
User selects Job → selects Candidate → chooses BU
```

**Do:**
```
User selects Job → system auto-uses job's BU for candidate
```

**Implementation:**
- Candidate's BU auto-set from job when submitted ✅ DONE
- Employee's BU auto-set from candidate's BU when converted
- Timesheet's BU auto-set from employee's BU
- Invoice's BU auto-set from employee's BU
- Allocation's BU auto-set from employee's BU

### Rule 2: Smart Defaults, Not Required Fields
**Instead of:**
```
[Job Creation Modal]
Business Unit: [Dropdown - REQUIRED]
```

**Do:**
```
// If user has a BU, use it
// If user has multiple BUs, show recent/primary
// If system can infer BU from context, use it
[Job Creation Modal]
Business Unit: [Auto-populated from user's BU]
  [Allow override if needed]
```

### Rule 3: Invisible Scoping
**User should never see data outside their BU** unless they're Finance/Executive with explicit cross-BU role.

**Implementation:**
- Login → check user.business_unit_id
- All list screens → filter by that BU automatically
- User doesn't see "Business Unit" filter dropdown - just sees THEIR data
- Finance role → can toggle all BUs with a single switch

---

## 🔄 CASCADE PATTERNS

### Pattern 1: User Changes/Assignment
```
User created/updated with business_unit_id
  ↓
Profile shows their BU context
  ↓
All their screens auto-filter to that BU
  ↓
Their reports show only that BU's data
```

### Pattern 2: Candidate Journey
```
Job created with BU = "NA"
  ↓
Candidate submitted to Job
  ↓ AUTOMATIC
Candidate.business_unit_id = "NA" ✅ DONE
  ↓
HM reviews candidate - auto-filtered to NA
  ↓
Offer created - inherits candidate's BU
  ↓
Candidate converts to employee
  ↓ AUTOMATIC
Employee.bu_id = candidate's BU
  ↓
Employee's future timesheets → business_unit_id = employee.bu_id
  ↓
Invoices for employee → business_unit_id = employee.bu_id
  ↓
Performance events → business_unit_id = employee.bu_id
```

### Pattern 3: Employee Allocation
```
Employee allocated to Project
  ↓
Allocation.business_unit_id = employee.bu_id (automatic)
  ↓
All timesheets under that allocation → same BU
  ↓
Reports group by that BU
```

### Pattern 4: Manager Assignment
```
Hiring Manager assigned from BU = "EU"
  ↓
Can only see candidates in EU
  ↓
Can only assign jobs to EU candidates
  ↓
Cannot see NA candidates, jobs, or reports
  ↓ UNLESS
Manager given cross-BU role (Finance, Executive) → override kicks in
```

---

## 🔐 AUTOMATIC VALIDATION RULES

These prevent invalid cross-BU operations:

### Rule: No Cross-BU Assignment
```python
# When allocating employee to project:
if allocation.job.business_unit_id != employee.bu_id:
  raise ValidationError(
    f"Cannot allocate {employee.name} (BU: {employee.bu_id}) "
    f"to {job.title} (BU: {job.business_unit_id})"
  )
```

### Rule: BU Context Consistency
```python
# When creating offer:
offer.business_unit_id = candidate.business_unit_id  # auto-set
# Cannot be overridden by user
```

### Rule: Cross-BU Visibility
```python
# User querying data:
if user.has_role("FINANCE") or user.has_role("EXECUTIVE"):
  return all_data  # Cross-BU access
else:
  return data.filter(business_unit_id=user.business_unit_id)
```

---

## 📊 UPSTREAM IMPACTS (What affects BU Assignment)

### High Impact
| Event | Impact | Auto-Action | Manual Override? |
|-------|--------|-------------|------------------|
| Create Job with BU | Future candidates submitted to this job inherit BU | ✅ Auto-set BU | ❌ NO - fixed at job creation |
| Create User with BU | User can only manage that BU's data | ✅ Auto-filter all screens | ✅ YES - can reassign later |
| Create Candidate | BU set when submitted to job | ✅ Auto-set on submission | ✅ YES - can override if needed |
| Convert to Employee | Employee inherits candidate's BU | ✅ Auto-set | ❌ NO - fixed at conversion |

### Medium Impact
| Event | Impact | Auto-Action |
|-------|--------|-------------|
| Update Job BU | Existing submissions NOT affected (historical) | ✅ Future submissions use new BU |
| Update User BU | User can now see different BU data | ✅ Screens immediately filter to new BU |
| Allocate Employee | Allocation inherits employee's BU | ✅ Auto-set |

### Low Impact
| Event | Impact | Auto-Action |
|-------|--------|-------------|
| Create Timesheet | Auto-inherits employee's BU | ✅ Auto-set |
| Create Invoice | Auto-inherits employee's BU | ✅ Auto-set |
| Create Expense | Auto-inherits employee's BU | ✅ Auto-set |

---

## 📉 DOWNSTREAM IMPACTS (What BU Change Affects)

### Candidate BU Change
```
Candidate.business_unit_id changes
  ↓
All future submissions use new BU ✅
  ↓
Offers (if created after change) inherit new BU ✅
  ↓
Employee (if converted after change) inherits new BU ✅
  ↓
Historical data: unchanged (audit trail)
```

### Employee BU Transfer
```
Employee.bu_id changes (e.g., promoted to different BU)
  ↓
Current Allocation: needs validation - can't allocate outside new BU
  ↓
Future Timesheets: use new BU automatically
  ↓
Create Employment History Record: "BU change from EU to NA on 2026-08-12"
  ↓
Reports: now grouped under new BU going forward
  ↓
Access: user can now see NA data instead of EU
```

### Job BU Change
```
Job.business_unit_id changes
  ↓
Historical submissions: unchanged (keep their BU)
  ↓
Future submissions: use new BU automatically
  ↓
Employees already allocated: can stay if already in that BU, fail if not
```

---

## 🎨 UI/UX IMPLICATIONS

### Principle 1: Hide What's Determined
**Show only fields user can actually change:**

```
OLD (Asks for everything):
Business Unit: [Dropdown] ← User must choose
Department: [Dropdown] ← User must choose
Manager: [Dropdown] ← User must choose

NEW (Smart defaults):
Business Unit: NA [Cannot change - locked from job]
Department: Engineering [Auto-populated - can override if needed]
Manager: John Smith [Auto-populated from job - can change]
```

### Principle 2: Make Scoping Invisible
**User never sees a "BU Filter" because their view is already scoped:**

```
OLD (Visible filter):
┌─ Candidates ──────────────────┐
│ [All BUs ▼] [Status ▼]        │
│                                │
│ North America (5)              │
│  - John (NA)                   │
│  - Jane (NA)                   │
│ Europe (3)                     │
│  - Bob (EU)                    │
│  - Alice (EU)                  │
└────────────────────────────────┘

NEW (Invisible scoping - user is "NA Manager"):
┌─ Candidates ──────────────────┐
│ [Status ▼]                     │
│                                │
│ - John (NA)                    │
│ - Jane (NA)                    │
│ - Sarah (NA)                   │
└────────────────────────────────┘
// User can only see NA candidates
```

### Principle 3: One-Click Cross-BU Access (For Finance Only)
**Finance/Executive role gets ONE toggle:**

```
// Finance user sees:
[View All BUs ✓]  ← Toggle for cross-BU view

// When toggled ON:
┌─ All Companies ────────────────┐
│                                │
│ North America (5)              │
│  - John (NA)                   │
│  - Jane (NA)                   │
│ Europe (3)                     │
│  - Bob (EU)                    │
│  - Alice (EU)                  │
│ Asia-Pacific (2)               │
│  - Chen (APAC)                 │
│  - Raj (APAC)                  │
└────────────────────────────────┘
```

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 1: Finance (Auto-Scoping) - Week 1
- [ ] **Invoices Screen**
  - Auto-filter: `where business_unit_id = current_user.business_unit_id`
  - No dropdown shown to regular Finance users
  - Finance Director: toggle "View All BUs"
  - Group/sort: by BU automatically
  
- [ ] **Timesheets Screen**
  - Auto-filter: `where business_unit_id = current_user.business_unit_id`
  - Show column: `timesheet.employee.bu_name`
  - Approval workflow: only shows this user's BU
  
- [ ] **Revenue Screen**
  - Auto-group: by BU
  - Filter auto-applied: current user's BU
  - Finance Director: "View All BUs" toggle

- [ ] **Finance Operations**
  - All reconciliation data auto-filtered to user's BU
  - Cross-BU consolidated view (Finance role only)

- [ ] **Forecast + Forecast vs Actual**
  - Auto-grouped by BU
  - User sees only their BU forecast by default

### Phase 2: Recruitment (Smart Defaults) - Week 1-2
- [ ] **Candidates List**
  - Auto-filter: from user's BU
  - Show column: `business_unit_name`
  - Recruiters in NA: only see NA candidates
  - Global Recruiter: "View All BUs" toggle

- [ ] **Jobs List**
  - Auto-filter: jobs in user's BU
  - Create Job form: auto-fill BU from user
  - Can override in form if user has multi-BU role

- [ ] **Job Details**
  - Candidate list: auto-filtered to job's BU
  - Cannot assign candidate from different BU (validation)

- [ ] **Job Create**
  - BU field: pre-filled from user's BU
  - Read-only: cannot change (hard constraint)
  - Rationale: "All candidates submitted to this job will be in {user_bu}"

- [ ] **Submissions**
  - ✅ BACKEND DONE - just verify UI shows BU
  - Auto-assign on POST: candidate.business_unit_id = job.business_unit_id

- [ ] **Offer Letters**
  - Auto-set: offer.business_unit_id = candidate.business_unit_id
  - Display: show candidate's BU
  - No user choice

### Phase 3: Workforce (Inheritance) - Week 2
- [ ] **Employees List**
  - Auto-filter: to user's BU
  - Show column: `bu_name`
  - Cannot see employees from other BUs

- [ ] **Employee Conversion**
  - ✅ ALREADY DONE: BU selector in form
  - Pre-fill: candidate's BU
  - Validation: "This candidate is in {candidate_bu}. Confirm assignment to {selected_bu}?"

- [ ] **Allocations**
  - Auto-inherit: allocation.business_unit_id = employee.bu_id
  - Validation: cannot allocate outside employee's BU
  - Display: show employee's BU

- [ ] **Projects**
  - Associate with BU (if not already)
  - Auto-filter: user can only see projects in their BU
  - Prevent: cannot assign employee from different BU

- [ ] **Resource Management**
  - Auto-filter: user's BU pool only
  - Finance: cross-BU pool visibility
  - Show pool BU: highlight which employees belong to which BU

### Phase 4: Sales & Executive (Cross-BU Views) - Week 3
- [ ] **Client Management**
  - Show: client.business_unit_id
  - Auto-filter: user's BU clients
  - Cannot create/edit clients outside their BU

- [ ] **Opportunity Pipeline**
  - Auto-group: by BU columns on Kanban
  - Auto-filter: user's BU opportunities
  - Finance: "View All BUs"

- [ ] **Executive Revenue Dashboard**
  - Default: auto-filtered to user's BU
  - Toggle: "View All BUs" (Finance/Exec only)
  - Auto-group: all data by BU

- [ ] **Risk Dashboard**
  - Auto-filter: candidates in user's BU
  - Finance: cross-BU risk view

- [ ] **Thunder Analytics**
  - Auto-group: performance metrics by BU
  - User sees: only their BU agent performance

### Phase 5: Auto-Validation Rules - Week 4
- [ ] **Add Backend Validators**
  ```python
  # When assigning employee to job:
  validate_same_bu(employee.bu_id, job.business_unit_id)
  
  # When creating allocation:
  validate_same_bu(employee.bu_id, job.business_unit_id)
  
  # When converting candidate:
  candidate.business_unit_id must be set
  ```

- [ ] **Add Automatic Cascades**
  ```python
  # When employee created:
  employee.bu_id = candidate.business_unit_id
  
  # When timesheet created:
  timesheet.business_unit_id = employee.bu_id
  
  # When invoice created:
  invoice.business_unit_id = employee.bu_id
  ```

- [ ] **Add Employment History**
  ```python
  # When employee.bu_id changes:
  create_employment_history_record(
    employee_id=emp.id,
    change_type="BU",
    old_value=old_bu,
    new_value=new_bu,
    effective_date=today()
  )
  ```

---

## 🚨 FAILURE SCENARIOS & AUTOMATION RESPONSES

### Scenario 1: User tries to assign EU candidate to NA job
```
User Action: Drag candidate to job
System Check: candidate.business_unit_id (EU) != job.business_unit_id (NA)
Auto-Response: 
  ❌ Validation Error
  Message: "Cannot assign candidate from EU to NA job"
  Suggestion: "Resubmit candidate to EU job or reassign job to EU"
```

### Scenario 2: User from NA tries to access EU data
```
User Action: Navigate to /candidates
System Check: user.business_unit_id = NA
Auto-Response:
  ✅ Load candidates
  Filter: WHERE business_unit_id = 'NA'
  Display: Only NA candidates shown
  User never knows EU candidates exist (unless Finance role)
```

### Scenario 3: Finance Director needs all BU data
```
User Action: Navigate to /invoices
User Role: has "FINANCE" permission
System Check: has cross-BU permission
Auto-Response:
  ✅ Show toggle: "View All BUs"
  Default: All BUs loaded
  User can toggle per BU: "Show only NA" / "Show only EU" / "Show All"
```

### Scenario 4: Employee transfers from EU to NA
```
Event: Employee.bu_id changed from EU to NA
Auto-Actions:
  1. Create employment history record ✅
  2. Validate current allocations:
     - EU allocation: ❌ FAIL - cannot stay
     - Auto-notify: "Employee moved to NA, EU allocation must be updated"
  3. Future timesheets: ✅ Use NA automatically
  4. Future expenses: ✅ Use NA automatically
  5. Reports: ✅ Group under NA going forward
```

---

## 📈 REPORTING AUTOMATION

### Invoice Report
**Current (Manual):**
```
User goes to Finance Ops
Manually selects: BU = "NA", Date Range = "Aug 2026"
Sees: NA invoices for Aug

User must repeat for EU, APAC
```

**New (Automatic):**
```
Invoice Report
├─ North America
│  ├─ Total: $500k
│  ├─ Invoices: 45
│  └─ Approval Status: 40 approved, 5 pending
├─ Europe
│  ├─ Total: $300k
│  ├─ Invoices: 28
│  └─ Approval Status: 28 approved, 0 pending
└─ Asia-Pacific
   ├─ Total: $200k
   ├─ Invoices: 18
   └─ Approval Status: 15 approved, 3 pending
```

### Revenue Report
**Automatic:**
```
Revenue by Business Unit (Last Quarter)
├─ North America: $2.5M (trending +15%)
├─ Europe: $1.8M (trending -5%)
└─ Asia-Pacific: $900k (trending +20%)

Detailed Breakdown (click any BU):
├─ By Client
├─ By Employee
├─ By Project
└─ By Period
```

---

## ✅ SUCCESS METRICS

**Implementation is successful when:**

1. **Autonomy:** User never manually selects a BU filter (except Finance's "View All" toggle)
2. **Cascade:** Changing candidate's job auto-updates candidate's BU
3. **Validation:** System prevents cross-BU assignments
4. **Scoping:** Regular user can only see their BU data
5. **History:** All BU changes tracked in employment history
6. **Reports:** All reports automatically group by BU

---

## 🎯 KEY DIFFERENTIATOR

**Traditional BU Implementation:**
```
User: "Show me candidates"
System: "Which BU? (dropdown)"
User: *selects BU*
System: "Here are candidates"
```

**Our Implementation:**
```
User: "Show me candidates"
System: "Here are your (NA) candidates"
User: "Done"
```

**Finance User:**
```
User: "Show me all invoices"
System: "Here are all invoices (all BUs)"
User: "Group by BU"
System: (shows BU breakdown)
```

---

## 📋 IMPLEMENTATION PRIORITY

**Must Do (Changes cascading logic):**
1. Add automatic cascade validators
2. Add employment history tracking
3. Update error messages for validation

**Should Do (Improves UX):**
1. Hide BU filters from regular users (show only Finance toggle)
2. Pre-fill BU from context
3. Lock BU fields that shouldn't change

**Nice To Have:**
1. BU breakdown in reports
2. Visual highlighting of cross-BU issues
3. Audit log for BU changes

---

## 🔗 INTEGRATION POINTS

### With Thunder (AI Recruiter)
```
When Thunder submits candidate:
  candidate.business_unit_id = job.business_unit_id (AUTO)
  
Thunder can only see:
  Jobs in candidates' BU (auto-filtered)
  Candidates in their BU context
```

### With Timesheet System
```
When timesheet created:
  timesheet.business_unit_id = employee.bu_id (AUTO)
  
Timesheet approvers:
  Only see timesheets in their BU (auto-filtered)
```

### With Invoice System
```
When invoice generated:
  invoice.business_unit_id = employee.bu_id (AUTO)
  
Reports:
  Auto-grouped by BU
  Finance can toggle cross-BU view
```


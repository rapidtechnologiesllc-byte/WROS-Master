# Business Unit Implementation - 5-Phase Execution Roadmap (2026-08-12)

## Summary
**Timeline:** 2-3 weeks | **Screens:** 35 required + 13 optional | **Dev Pattern:** Copy-paste from templates

---

# 🔥 PHASE 1: FINANCE SYSTEMS (CEO/CFO Blockers) - Week 1

**Goal:** All financial data is BU-scoped. Finance can run reports by BU.

## Screens to Update (6)

### 1. Invoices Screen
**File:** `/screens/InvoicesScreen.jsx`
**Current:** List of all invoices
**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add Finance toggle: "View All BUs"
- [ ] Add column: `business_unit_name`
- [ ] Auto-group by BU in table
- [ ] Hide BU filter for non-Finance users

**Template to use:** Pattern 2 (Cross-BU Toggle)

**Backend ready:** ✅ YES (invoices table has business_unit_id)

---

### 2. Timesheets Screen
**File:** `/screens/TimesheetsScreen.jsx`
**Current:** Approve timesheets
**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `employee.business_unit_name`
- [ ] Auto-group by BU
- [ ] Finance toggle: "View All BUs"

**Template to use:** Pattern 2

**Backend ready:** ✅ YES (timesheets table has business_unit_id)

---

### 3. Revenue Screen
**File:** `/screens/RevenueScreen.jsx`
**Current:** Revenue metrics
**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Auto-group all data by BU
- [ ] Finance toggle: "View All BUs"
- [ ] Show BU breakdown table

**Template to use:** Pattern 10 (Reporting with Auto-Grouping)

**Backend ready:** ✅ YES (invoices grouped by employee.bu_id)

---

### 4. Finance Operations
**File:** `/screens/FinanceOperationsScreen.jsx`
**Current:** Reconciliation, AR, GL data
**Changes:**
- [ ] Auto-filter all data: `where business_unit_id = user.business_unit_id`
- [ ] Group reconciliation by BU
- [ ] Finance toggle: "View All BUs"
- [ ] Add BU column to all tables

**Template to use:** Pattern 2

**Backend ready:** ✅ YES (all finance tables have business_unit_id)

---

### 5. Forecast Screen
**File:** `/screens/ForecastScreen.jsx`
**Current:** Revenue forecast
**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Auto-group forecast by BU
- [ ] Finance toggle: "View All BUs"

**Template to use:** Pattern 10

**Backend ready:** ✅ YES

---

### 6. Forecast vs Actual Screen
**File:** `/screens/ForecastVsActualScreen.jsx`
**Current:** Compare forecast to actual
**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Group comparison by BU
- [ ] Finance toggle: "View All BUs"

**Template to use:** Pattern 10

**Backend ready:** ✅ YES

---

## Phase 1 Checklist
- [ ] All 6 screens filter by user's BU
- [ ] Finance users have "View All BUs" toggle
- [ ] BU column visible in all tables
- [ ] Reports auto-grouped by BU
- [ ] No BU dropdown visible to regular users
- [ ] Test: Regular Finance user sees only their BU
- [ ] Test: Finance Director sees all BUs when toggled
- [ ] Test: Finance can group/sort by BU

**Commit message:**
```
feat(finance): Implement automatic BU scoping for all financial screens

- Add BU filtering to Invoices, Timesheets, Revenue screens
- Add Finance "View All BUs" toggle
- Auto-group reports by Business Unit
- Hide BU filter for non-Finance users
```

---

# 🔴 PHASE 2: RECRUITMENT CORE (High Volume) - Week 1-2

**Goal:** All recruitment data scoped by BU. Hiring managers see only their BU's candidates/jobs.

## Screens to Update (14)

### 1-2. Candidates List + Search
**Files:** `/screens/CandidateSearch.jsx`, component references

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `business_unit_name`
- [ ] Hide BU dropdown (use Pattern 1)
- [ ] No "View All BUs" - recruiters never see other BUs

**Template:** Pattern 1 (Auto-Scoped List)

**Backend ready:** ✅ YES (candidate table has business_unit_id, auto-assigned on submission)

---

### 3. Jobs List
**File:** `/screens/ActiveJobs.jsx` (or consolidate into one Jobs screen)

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `business_unit_name`
- [ ] Hide BU dropdown

**Template:** Pattern 1

**Backend ready:** ✅ YES (jobs table has business_unit_id)

---

### 4. Job Create
**File:** `/screens/JobCreate.jsx`

**Changes:**
- [ ] Pre-fill: `business_unit_id = user.business_unit_id`
- [ ] Make BU read-only for single-BU users
- [ ] Add help text: "All candidates submitted to this job will be in {BU}"
- [ ] Filter departments by selected BU

**Template:** Pattern 3 (Auto-Populated BU Field)

**Backend ready:** ✅ YES

---

### 5. Job Details
**File:** `/screens/JobDetails.jsx`

**Changes:**
- [ ] Show BU banner: BUInfoBanner component
- [ ] Display: `job.business_unit_name`
- [ ] Candidate list: auto-filter to job's BU only
- [ ] Cannot assign candidate from different BU (validation)

**Template:** Pattern 4 + Pattern 5 (Validation)

**Backend ready:** ✅ YES

---

### 6. Candidate Details Screen
**File:** `/screens/CandidateDetailsScreen.jsx`

**Changes:**
- [ ] Show BU banner: BUInfoBanner component
- [ ] Display: `candidate.business_unit_name`
- [ ] Show how BU was assigned: "Auto-assigned from Job X"
- [ ] Add optional override (future phase)

**Template:** Pattern 4

**Backend ready:** ✅ YES

---

### 7. Offer Letters (View)
**File:** `/screens/OfferLettersScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `business_unit_name`
- [ ] Group by BU

**Template:** Pattern 1

**Backend ready:** ✅ YES (offers inherit candidate's BU)

---

### 8. Offer Screen (Create)
**File:** `/screens/OfferScreen.jsx`

**Changes:**
- [ ] Show BU banner: auto-inherited from candidate
- [ ] Make BU read-only
- [ ] Display: "Offer will be for {candidate.business_unit_name}"

**Template:** Pattern 4

**Backend ready:** ✅ YES

---

### 9. Submissions
**File:** `/screens/SubmissionsScreen.jsx`

**Changes:**
- [ ] ✅ BACKEND DONE (auto-assign on POST)
- [ ] Just verify: Show `business_unit_name` column
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`

**Template:** Pattern 1

**Backend ready:** ✅ YES - NO CHANGES NEEDED, JUST UI

---

### 10. Assignments (Manager Assignment)
**File:** `/screens/AssignmentsScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where candidate.business_unit_id = user.business_unit_id`
- [ ] Add column: `candidate.business_unit_name`
- [ ] Cannot assign candidate from different BU

**Template:** Pattern 1 + Pattern 5

**Backend ready:** ✅ YES

---

### 11. Pre-Onboarding
**File:** `/screens/PreOnboarding.jsx`

**Changes:**
- [ ] Auto-filter: `where candidate.business_unit_id = user.business_unit_id`
- [ ] Show BU banner

**Template:** Pattern 1 + Pattern 4

**Backend ready:** ✅ YES

---

### 12-14. Interview Screens (3 screens)
**Files:**
- `/screens/InterviewSchedule.jsx`
- `/screens/InterviewStatus.jsx`
- `/screens/InterviewAnalytics.jsx`

**Changes (all three):**
- [ ] Auto-filter: `where job.business_unit_id = user.business_unit_id` (show interviews for user's BU jobs)
- [ ] Add column: `business_unit_name`
- [ ] Group/sort by BU

**Template:** Pattern 1

**Backend ready:** ✅ YES (interviews linked to jobs which have business_unit_id)

---

## Phase 2 Checklist
- [ ] All 14 recruitment screens filter by user's BU
- [ ] BU column visible in all lists
- [ ] No recruiters can see other BUs (no cross-BU access)
- [ ] Create forms pre-fill BU
- [ ] Detail screens show BU banner
- [ ] Validation prevents cross-BU assignment
- [ ] Test: Recruiter A (NA) cannot see Recruiter B's (EU) candidates
- [ ] Test: Cannot assign NA candidate to EU job

**Commit message:**
```
feat(recruitment): Implement BU scoping for all recruitment screens

- Auto-filter candidates, jobs, offers by user's BU
- Add BU column to all recruitment lists
- Show BU banner on detail screens
- Prevent cross-BU job-candidate assignments
- Auto-assign candidate BU from job on submission (backend verified)
```

---

# 🟠 PHASE 3: WORKFORCE MANAGEMENT - Week 2

**Goal:** Employees and allocations scoped by BU. Prevent cross-BU assignments.

## Screens to Update (9)

### 1. Employees List
**File:** `/screens/EmployeesConsolidatedScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where bu_id = user.business_unit_id`
- [ ] Add column: Show `bu_name` (from employee.bu_id)
- [ ] Cannot see employees from other BUs

**Template:** Pattern 1

**Backend ready:** ✅ YES (employee table has bu_id)

---

### 2. Employee Conversion
**File:** `/screens/EmployeeConversionScreen.jsx`

**Changes:**
- [ ] ✅ ALREADY DONE (has BU selector)
- [ ] Verify: Pre-fill BU from candidate
- [ ] Verify: Show candidate's BU in banner

**Template:** Already implemented ✅

**Backend ready:** ✅ YES

---

### 3. Allocations
**File:** `/screens/AllocationsScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where employee.bu_id = user.business_unit_id`
- [ ] Add column: `employee.bu_name`
- [ ] Validation: Cannot allocate employee to job outside their BU (Pattern 5)
- [ ] Auto-set: `allocation.business_unit_id = employee.bu_id`

**Template:** Pattern 1 + Pattern 5 + Pattern 8

**Backend ready:** ✅ YES (allocation should have business_unit_id)

---

### 4. Projects
**File:** `/screens/ProjectsScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `business_unit_name`
- [ ] When allocating employee: validate same BU

**Template:** Pattern 1 + Pattern 5

**Backend ready:** ⚠️ VERIFY (may need business_unit_id added)

---

### 5. Resource Management
**File:** `/screens/ResourceManagementScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Show pool employees: only from user's BU
- [ ] Validate: cannot assign outside BU

**Template:** Pattern 1 + Pattern 5

**Backend ready:** ✅ YES (employees have bu_id)

---

### 6. Core-Pull & Pool Guard
**File:** `/screens/CorePullScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where employee.bu_id = user.business_unit_id`
- [ ] Show: which BU each employee belongs to

**Template:** Pattern 1

**Backend ready:** ✅ YES (employee has bu_id)

---

### 7. Buddy Program
**File:** `/screens/BuddyProgramListScreen.jsx`, `/screens/BuddyProgramScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where employee.bu_id = user.business_unit_id`
- [ ] Add column: `employee.bu_name`

**Template:** Pattern 1

**Backend ready:** ✅ YES

---

### 8. Utilization & Bench Cost
**File:** `/screens/UtilizationDashboardScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where employee.bu_id = user.business_unit_id`
- [ ] Auto-group: by BU
- [ ] Finance toggle: "View All BUs"

**Template:** Pattern 10

**Backend ready:** ✅ YES

---

### 9. Demand Confirmation
**File:** `/screens/DemandConfirmationScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where job.business_unit_id = user.business_unit_id`
- [ ] Show: job's BU

**Template:** Pattern 1

**Backend ready:** ✅ YES

---

## Phase 3 Checklist
- [ ] All 9 workforce screens filter by BU
- [ ] BU column visible in employee lists
- [ ] Cross-BU allocation validation works
- [ ] Employee conversion pre-fills BU
- [ ] Test: Manager A (NA) cannot allocate to Manager B's (EU) projects
- [ ] Test: Allocation auto-inherits employee's BU

**Commit message:**
```
feat(workforce): Implement BU scoping for employee management

- Auto-filter employees and allocations by user's BU
- Add BU validation to prevent cross-BU assignments
- Show employee BU in all lists and detail screens
- Auto-inherit BU in allocations from employee
```

---

# 🟡 PHASE 4: SALES & EXECUTIVE DASHBOARDS - Week 3

**Goal:** Sales can see their BU's pipeline. Executives have cross-BU view option.

## Screens to Update (8)

### 1. Client Management
**File:** `/screens/ClientManagementScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Add column: `business_unit_name`
- [ ] Pre-fill: BU in create form from user context
- [ ] Cannot create/edit clients outside their BU

**Template:** Pattern 1 + Pattern 3

**Backend ready:** ✅ YES (client has business_unit_id)

---

### 2. Opportunity Pipeline
**File:** `/screens/OpportunityPipelineScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where business_unit_id = user.business_unit_id`
- [ ] Auto-group: Kanban columns by BU
- [ ] Executive toggle: "View All BUs"
- [ ] Show: `business_unit_name` on cards

**Template:** Pattern 2 + Pattern 10

**Backend ready:** ✅ YES (opportunity has business_unit_id added)

---

### 3. Executive Revenue Dashboard
**File:** `/screens/ExecutiveRevenueDashboardScreen.jsx`

**Changes:**
- [ ] Default: show all BUs (cross-BU view)
- [ ] Auto-group: by BU
- [ ] Add toggle: "View Only My BU" if not global executive
- [ ] Show: detailed breakdown by BU

**Template:** Pattern 2 (inverted - show all by default)

**Backend ready:** ✅ YES

---

### 4. Risk Dashboard
**File:** `/screens/RiskDashboardScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where candidate.business_unit_id = user.business_unit_id`
- [ ] Finance/Executive toggle: "View All BUs"
- [ ] Show: at-risk candidates grouped by BU

**Template:** Pattern 2

**Backend ready:** ✅ YES

---

### 5-7. Agent Dashboards (3 screens)
**Files:**
- `/screens/PartnerROIAgentScreen.jsx`
- `/screens/CEOFYProgressScreen.jsx`
- `/screens/CFOAgentScreen.jsx`

**Changes (all three):**
- [ ] Auto-filter: to user's assigned BU(s)
- [ ] Add toggle: "View All BUs" (if permitted)
- [ ] Group data: by BU

**Template:** Pattern 2

**Backend ready:** ✅ YES

---

### 8. Thunder Analytics
**File:** `/screens/ThunderAnalyticsScreen.jsx`

**Changes:**
- [ ] Auto-filter: `where candidate.business_unit_id = user.business_unit_id`
- [ ] Auto-group: agent performance metrics by BU
- [ ] Show: which candidates' interactions contributing to metrics

**Template:** Pattern 1 + Pattern 10

**Backend ready:** ✅ YES

---

## Phase 4 Checklist
- [ ] Sales can only see their BU's clients/opportunities
- [ ] Executives have cross-BU view by default
- [ ] All dashboards auto-group by BU
- [ ] Test: Sales Manager A (NA) cannot see Manager B's (EU) opportunities
- [ ] Test: CFO can see all BUs, then filter to one

**Commit message:**
```
feat(sales & executive): Implement BU scoping for dashboards

- Auto-filter sales data by user's BU
- Add cross-BU view toggle for Finance/Executive roles
- Auto-group all dashboard metrics by BU
- Show business unit context in all cards/lists
```

---

# 🟢 PHASE 5: VALIDATION & AUTOMATION - Week 4

**Goal:** Automatic cascades work. Cross-BU operations impossible. Employment history tracked.

## Backend Validators to Add

### 1. Allocation Validation
**File:** `app/services/allocation_service.py`

**Add:**
```python
def validate_allocation_same_bu(employee_id: str, job_id: str, db: Session):
    """Prevent cross-BU allocation"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if employee.bu_id != job.business_unit_id:
        raise ValidationError(f"Cannot allocate to job in different BU")
```

- [ ] Add to allocation endpoint
- [ ] Test: Validate error when cross-BU

---

### 2. Employee BU Transfer Handler
**File:** `app/services/employee_service.py`

**Add:**
```python
def update_employee_bu(employee_id: str, new_bu_id: int, db: Session):
    """Update BU and create history"""
    employee = db.query(Employee).first()
    old_bu = employee.bu_id
    
    # Validate no active allocations in different BU
    allocations = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee_id,
        EmployeeAllocation.status == "active"
    ).all()
    
    for alloc in allocations:
        job = db.query(Jobs).filter(Jobs.jobID == alloc.job_id).first()
        if job.business_unit_id != new_bu_id:
            raise ValidationError("Cannot transfer while allocated to different BU")
    
    # Update
    employee.bu_id = new_bu_id
    
    # Create history
    history = EmployeeEmploymentHistory(
        employee_id=employee_id,
        change_type="BU",
        old_value=str(old_bu),
        new_value=str(new_bu_id),
        effective_date=date.today()
    )
    db.add(history)
    db.commit()
```

- [ ] Add to employee update endpoint
- [ ] Test: Transfer employee BU, verify history

---

### 3. Timesheet Auto-Set
**File:** `app/services/timesheet_service.py`

**Add:**
```python
def create_weekly_draft(employee_id: str, week_start: date, db: Session):
    """Auto-set BU from employee"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    timesheet = Timesheet(
        employee_id=employee_id,
        business_unit_id=employee.bu_id,  # AUTO
        week_starting_date=week_start
    )
    db.add(timesheet)
    db.commit()
```

- [ ] Verify: All timesheet creation flows set BU

---

### 4. Invoice Auto-Set
**File:** `app/services/invoice_service.py`

**Add:**
```python
def generate_invoice(timesheet_id: str, db: Session):
    """Auto-set BU from timesheet"""
    timesheet = db.query(Timesheet).first()
    invoice = Invoice(
        timesheet_id=timesheet_id,
        business_unit_id=timesheet.business_unit_id,  # AUTO
        total_usd_cents=calculate_total(timesheet)
    )
    db.add(invoice)
    db.commit()
```

- [ ] Verify: All invoice generation flows set BU

---

## Frontend Validation to Add

### 1. Allocation Form Validation
**File:** `components/AllocationForm.jsx`

**Add:**
```javascript
const result = validateAllocationSameBU(selectedEmployee, selectedJob);
if (result !== true) {
  showError(result.error);
  return; // Prevent submit
}
```

- [ ] Add to allocation creation
- [ ] Test: Show error for cross-BU

---

## Documentation to Update

### 1. API Documentation
**File:** `docs/WROS_API.md`

- [ ] Add BU parameter documentation
- [ ] Add BU validation rules
- [ ] Add BU cascade documentation

---

### 2. Frontend Patterns Guide
**File:** Already created: `BU_IMPLEMENTATION_PATTERNS.md`

- [ ] Share with frontend team
- [ ] Reference in code reviews

---

## Phase 5 Checklist
- [ ] All validators implemented and tested
- [ ] All cascades working (employee → timesheet → invoice)
- [ ] Employment history tracks BU changes
- [ ] Cross-BU operations impossible (validation blocks them)
- [ ] Test: Cannot allocate cross-BU
- [ ] Test: Timesheet auto-gets employee's BU
- [ ] Test: Invoice auto-gets timesheet's BU
- [ ] Test: Employee BU transfer creates history

**Commit message:**
```
feat(bu-validation): Add automatic validation and cascading

- Add allocation validation: prevent cross-BU assignment
- Auto-set BU cascade: timesheet → invoice → expense
- Track BU changes in employment history
- Add backend validators for all BU constraints
```

---

# 📊 SUMMARY

| Phase | Screens | Priority | Impact | Timeline |
|-------|---------|----------|--------|----------|
| **1: Finance** | 6 | 🔥 CRITICAL | CEO/CFO reports work | Week 1 |
| **2: Recruitment** | 14 | 🔴 HIGH | Core business process | Week 1-2 |
| **3: Workforce** | 9 | 🟠 HIGH | Employee management | Week 2 |
| **4: Executive** | 8 | 🟡 MEDIUM | Dashboard visibility | Week 3 |
| **5: Validation** | Backend | 🟢 ESSENTIAL | Data integrity | Week 4 |
| **TOTAL** | **35+** | - | Full BU system | **2-3 weeks** |

---

# ✅ Success Criteria

When all 5 phases are complete:

1. ✅ User logs in → sees only their BU data
2. ✅ Finance user toggles → sees all BUs
3. ✅ Recruiter submits candidate → BU auto-assigned from job
4. ✅ Employee allocated → BU validated same as job
5. ✅ Timesheet created → BU auto-set from employee
6. ✅ Invoice generated → BU auto-set from timesheet
7. ✅ Employee transfers → BU change tracked in history
8. ✅ Cross-BU operations → Blocked with helpful error
9. ✅ Reports → Auto-grouped by BU
10. ✅ Zero data leakage → User never sees other BU data

---

# 🚀 Next Steps

1. **Create util files** (Can do in parallel with Phase 1):
   - `/utils/userContext.js` - `getCurrentUserBU()` hook
   - `/utils/buValidation.js` - Validation functions
   - `/components/BUInfoBanner.jsx` - Reusable component

2. **Start Phase 1** - Pick one Finance screen, implement fully, copy pattern to others

3. **Quality gate:** Each phase requires:
   - All screens in phase updated
   - Frontend + backend validation working
   - One E2E test per screen
   - Code review

4. **Documentation:** Update API docs as you go

---

This roadmap is your detailed implementation guide. Use the patterns, follow the checklist, and scale systematically.


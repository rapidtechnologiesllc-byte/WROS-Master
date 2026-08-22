# PHASE 2 DEVELOPER GUIDE — Implementation Checklist

**Status:** Code pushed, documentation complete, ready for team execution  
**Timeline:** 2-3 weeks for full Phase 2 completion  
**Effort:** ~82 hours (backend ~19h, frontend ~48h, testing ~15h)  
**Definition of Done:** All 6 acceptance gates passed  

---

## BEFORE YOU START

### Prerequisites
- Backend: Python 3.11, SQLAlchemy, FastAPI, Alembic set up
- Frontend: Node.js, React, TypeScript
- Database: SQLite (dev), PostgreSQL (staging)
- Testing: pytest (backend), Jest/Cypress (frontend)

### Key Documents to Read
1. `PHASE_2_END_TO_END_COMPLETION_PLAN.md` — Detailed roadmap
2. `PHASE_2_FIX_IMPLEMENTATION_PLAN.md` — Code templates (copy-paste ready)
3. `PHASE_2_AUDIT_REPORT_FINAL.md` — Findings + hard rules status

### Git Status
```
Backend: Commit ba4c454 (R-01 enforcement + missing fields added)
Frontend: Clean, ready for work
Main Repo: Commit 2333b3d (Phase 2 documentation pushed)
```

---

## PHASE 2 ACCEPTANCE GATES (HARD STOPS)

Each gate MUST be 100% complete before proceeding. No partial credit.

### Gate 1: Data Model (36/42 → 42/42)

**Missing 6 Tables:**

#### 1. candidate_conversations
```python
# Location: app/models/candidate_conversations.py (NEW FILE)
# Status: Spec requires structured message history tracking

class CandidateConversation(Base):
    __tablename__ = "candidate_conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)  # WHATSAPP, EMAIL, SMS, PLATFORM
    message_history = Column(JSON, nullable=True)  # Array of {timestamp, sender, text, direction}
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Action:** Create model + migration + test

---

#### 2. specialty_certification_clocks
```python
# Location: app/models/specialty_certification_clock.py (NEW FILE)
# Status: Track 90-day HTD billable day progression (R-04 related)

class SpecialtyCertificationClock(Base):
    __tablename__ = "specialty_certification_clocks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    clock_type = Column(Enum("STANDARD_90", "HTD_365", name="clock_type"), nullable=False)
    status = Column(String(50), nullable=False, default="RUNNING")  # RUNNING, PAUSED, COMPLETED
    billable_days_elapsed = Column(Integer, nullable=False, default=0)
    paused = Column(Boolean, nullable=False, default=False)
    reset_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Action:** Create model + migration + service (increment billable days)

---

#### 3. erp_sync_log
```python
# Location: app/models/sync_log.py (NEW FILE)
# Status: Track invoice ERP synchronization

class ERPSyncLog(Base):
    __tablename__ = "erp_sync_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    invoice_id = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    sync_status = Column(Enum("PENDING", "IN_PROGRESS", "SUCCESS", "FAILED", "RETRYING"), nullable=False, default="PENDING")
    created_at = Column(DateTime, server_default=func.now())
    synced_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    erp_invoice_id = Column(String(100), nullable=True, unique=True)
```

**Action:** Create model + migration + service (track sync status)

---

#### 4. employee_payroll_sync_log
```python
# Location: app/models/sync_log.py (same file as ERP)
# Status: Track payroll synchronization

class PayrollSyncLog(Base):
    __tablename__ = "payroll_sync_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(50), ForeignKey("employees.id"), nullable=False, index=True)
    sync_status = Column(Enum("PENDING", "IN_PROGRESS", "SUCCESS", "FAILED", "RETRYING"), nullable=False, default="PENDING")
    created_at = Column(DateTime, server_default=func.now())
    synced_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)
    payroll_period_start = Column(DateTime, nullable=False)
    payroll_period_end = Column(DateTime, nullable=False)
    payroll_record_id = Column(String(100), nullable=True, unique=True)
```

**Action:** Create model + migration + service

---

**Subtotal: Gate 1 = 4 hours**

**Done when:** All 6 tables exist in database, can query via ORM, have proper indexes and FK constraints

---

### Gate 2: Hard Rules (R-01 to R-10)

**Current Status:** 5/10 enforced, 3 partial, 2 missing

#### Already Complete ✅
- ✅ **R-03:** W2/full-time only (Demand.employment_type = W2_FULLTIME)
- ✅ **R-04:** Bench-first before sourcing (demand_service gate)
- ✅ **R-05:** L1 before L2 (interview_sequencing_service)
- ✅ **R-09:** USD cents only (all *_usd_cents fields)

#### Partially Complete ⚠️ (Fix Needed)
- ⚠️ **R-01:** 5-year experience floor (app-level only, add DB CHECK constraint)
  - **Action:** CREATE MIGRATION to add CHECK constraint
  - **Alembic Note:** Migration chain has issues; may need to fix manually in db/env.py
  - **SQL:** `ALTER TABLE candidates ADD CONSTRAINT chk_experience_5yr CHECK (total_experience_months IS NULL OR total_experience_months >= 60);`

- ⚠️ **R-07:** Multi-field dedup (email only, add phone + LinkedIn)
  - **Action:** Implement app/services/dedup_service.py (template in FIX_IMPLEMENTATION_PLAN.md)
  - **Functions:** find_duplicate_by_phone(), find_duplicate_by_linkedin(), find_duplicate_candidate()
  - **Test:** Unit tests for each dedup method, fuzzy matching threshold

- ⚠️ **R-10:** Unapproved timesheet blocks invoice
  - **Action:** Add gate in invoice_service.create_invoice()
  - **Check:** Query timesheet table, verify all entries approved before allowing invoice
  - **SQL:** `SELECT * FROM timesheets WHERE approval_status != 'APPROVED' AND employee_id = ?`

#### Missing ❌ (Implement)
- ❌ **R-02:** No market profile without recruiter + CS sign-off
  - **Action:** Define "market profile" workflow, add approval gates
  - **Research:** Check Phase 2 spec + requirements for clarification
  - **Implement:** Service + API endpoint + frontend workflow

- ❌ **R-06:** Human dependency < 20% by Month 6
  - **Action:** Add tracking to employee allocation (compute human_dependency_pct)
  - **Calculation:** (human_support_hours / total_project_hours) * 100
  - **Report:** Add to admin dashboard

- ❌ **R-08:** Thunder locked when recruiter owns conversation
  - **Action:** Verify race-condition safety in thunder_service.send_message()
  - **Check:** Atomic lock on conversation ownership before sending
  - **Test:** Concurrent send attempts should fail gracefully

**Subtotal: Gate 2 = 2-3 days**

**Done when:** All 10 hard rules enforced + tested, no violations pass through

---

### Gate 3: API Endpoints (80% → 100%)

**Existing Endpoints:** Most exist, need verification + 20% new endpoints

**Must Implement:**

**Candidate Management:**
- [ ] POST /candidates — Create (uses create_candidate_safe with dedup)
- [ ] GET /candidates — List with filtering
- [ ] GET /candidates/{id} — Read
- [ ] PUT /candidates/{id} — Update
- [ ] POST /candidates/{id}/dedup-check — Check for duplicates

**Scoring & Auto-Assignment:**
- [ ] GET /candidates/{id}/scores — Get candidate scores
- [ ] POST /admin/auto-score-all — Trigger batch scoring
- [ ] GET /demands/{id}/top-candidates — Get auto-proposed matches

**Hard Rule Verification:**
- [ ] POST /admin/verify-hard-rules — Check all R-01 to R-10
- [ ] GET /admin/hard-rule-violations — Report violations

**Endpoints Validation:** All endpoints should:
- ✅ Have proper error handling (return user-friendly error messages)
- ✅ Validate input (return 400 Bad Request for invalid data)
- ✅ Enforce hard rules (return 403 Forbidden for rule violations)
- ✅ Include auth + tenant scoping
- ✅ Have OpenAPI/Swagger documentation

**Subtotal: Gate 3 = 2-3 days**

**Done when:** All endpoints exist, return correct status codes, pass integration tests

---

### Gate 4: Frontend Screens (40% → 100%)

**Screens to Build:**

**Recruiter Workflows:**
- [ ] Candidate List Screen (filter, search, bulk actions)
- [ ] Add Candidate Modal (form validation, dedup check)
- [ ] Candidate Details Screen (view/edit, show scores)
- [ ] Job Matching Screen (submit to demand, auto-scores)
- [ ] Interview Scheduling Screen (L1/L2 enforcement)
- [ ] Interview Feedback Form (rating, notes)

**HR/Manager Workflows:**
- [ ] Employee Conversion Modal (candidate → employee)
- [ ] Employee List Screen (filter by BU, engine, status)
- [ ] Project Allocation Screen (assign to project)

**Admin Workflows:**
- [ ] Admin Dashboard (metrics, scoring status, sync logs)
- [ ] Hard Rule Enforcement Dashboard (violations + actions)

**Each Screen Must Have:**
- ✅ Form validation (required fields, format checks, length limits)
- ✅ Error handling (show API errors to user)
- ✅ Loading states (spinners, disabled buttons)
- ✅ Success/error messages (toast notifications)
- ✅ Empty states (helpful message when no data)
- ✅ Responsiveness (mobile 375px, tablet 768px, desktop 1920px)
- ✅ Dark mode support
- ✅ Accessibility (labels, ARIA, keyboard nav)

**Subtotal: Gate 4 = 4-5 days**

**Done when:** All screens built, integrated with backend APIs, tested, responsive, accessible

---

### Gate 5: Integration Testing (30% → 100%)

**Test Scenarios (Happy Path):**
- [ ] Create candidate → Auto-scored → Auto-assigned to Thunder
- [ ] Submit candidate to demand → Schedule L1 interview
- [ ] L1 feedback → Schedule L2 interview → L2 feedback → Hire
- [ ] Convert to employee → Allocate to project → Track utilization

**Test Scenarios (Hard Rules):**
- [ ] R-01: Reject <60 months experience at submission
- [ ] R-05: Reject L2 before L1 pass
- [ ] R-04: Reject sourcing without bench-first check
- [ ] R-07: Reject all 3 dedup types (email, phone, LinkedIn)
- [ ] R-10: Reject invoice with unapproved timesheet

**Test Scenarios (Negative Cases):**
- [ ] Duplicate candidate (email) — Should show warning
- [ ] Invalid employment type — Should reject
- [ ] Concurrent operations — Should handle gracefully

**Testing Stack:**
- Backend: pytest (unit + integration)
- Frontend: Jest/React Testing Library (unit + integration)
- E2E: Cypress (full workflow testing)
- Coverage: Aim for >80% code coverage

**Subtotal: Gate 5 = 2 days**

**Done when:** All test scenarios passing, >80% code coverage, CI/CD green

---

### Gate 6: Database & Migrations (Partial → 100%)

**Migration Status:** Alembic chain has issues, need to fix

**Action Plan:**
1. [ ] Audit current migration state (find broken references)
2. [ ] Create clean migration from base (if needed)
3. [ ] Add migrations for 6 new tables
4. [ ] Add migration for R-01 CHECK constraint
5. [ ] Test migrations on clean SQLite
6. [ ] Test migrations on staging PostgreSQL
7. [ ] Verify all tables created correctly

**Migration Files to Create:**
- `add_candidate_conversations_table.py`
- `add_specialty_certification_clocks_table.py`
- `add_erp_and_payroll_sync_logs.py`
- `add_r01_experience_constraint.py`
- `add_missing_candidate_fields.py` (if needed for migration)

**Subtotal: Gate 6 = 1-2 days**

**Done when:** All migrations run cleanly, database schema matches spec

---

## IMPLEMENTATION ORDER (Priority)

### Week 1: Backend Critical Path (3 days)

**Day 1: Models + Migrations**
- [ ] Create 4 missing table models
- [ ] Create/fix Alembic migrations
- [ ] Test migrations on SQLite
- [ ] Add models to __init__.py

**Day 2: Hard Rules + Services**
- [ ] Implement R-02, R-06, R-08, R-10
- [ ] Implement dedup service (R-07)
- [ ] Implement auto-scoring daemon (needs timer/scheduler)
- [ ] Write unit tests

**Day 3: API + Integration**
- [ ] Add missing 20% of API endpoints
- [ ] Add error handling to all endpoints
- [ ] Write integration tests
- [ ] Verify all endpoints + hard rules

**Subtotal: 19 hours backend**

### Week 2: Frontend (4 days)

**Day 1-2: Core Screens**
- [ ] Build all recruiter screens (candidate, demand, interview)
- [ ] Build all HR screens (employee conversion, allocation)
- [ ] Connect to APIs
- [ ] Add form validation + error handling

**Day 3: Polish**
- [ ] Add loading states + toasts
- [ ] Add empty states + confirmations
- [ ] Fix responsive layout issues
- [ ] Test on mobile/tablet/desktop

**Day 4: Dark Mode + Testing**
- [ ] Implement dark mode theme toggle
- [ ] Write unit + integration tests
- [ ] Test E2E workflows with Cypress
- [ ] Verify accessibility

**Subtotal: 48 hours frontend**

### Week 3: Testing + Deployment (3 days)

**Day 1: Comprehensive Testing**
- [ ] Run full test suite (backend + frontend)
- [ ] Verify >80% code coverage
- [ ] Performance testing (page load, API response)
- [ ] Load testing (1000 candidate scoring)

**Day 2-3: Deploy + Verify**
- [ ] Deploy to staging
- [ ] Smoke test all workflows
- [ ] Verify hard rules in staging
- [ ] Production readiness check

**Subtotal: 15 hours testing + deployment**

---

## SUCCESS CRITERIA

### Code Quality
- [ ] No TypeScript/Python errors
- [ ] No console warnings/errors
- [ ] >80% test code coverage
- [ ] All pre-commit hooks passing
- [ ] No security vulnerabilities (npm audit, bandit)

### Functionality
- [ ] All 42 tables exist and queryable
- [ ] All hard rules R-01 to R-10 enforced + tested
- [ ] All API endpoints return correct status codes
- [ ] All frontend screens render without errors
- [ ] All workflows tested end-to-end

### Performance
- [ ] Page load < 2 seconds
- [ ] API response < 500ms
- [ ] Batch scoring 1000 candidates < 1 minute
- [ ] Database queries < 100ms (use indexes)

### User Experience
- [ ] All forms have validation + error messages
- [ ] All buttons have loading states
- [ ] All screens work on mobile/tablet/desktop
- [ ] All screens have dark mode support
- [ ] All screens accessible (WCAG 2.1 AA)

### Deployment
- [ ] Migrations run cleanly on staging
- [ ] CI/CD pipeline green
- [ ] No database errors
- [ ] Rollback plan documented

---

## COMMON GOTCHAS

**Database Migration Issues:**
- ❌ Don't ignore Alembic warnings about missing migrations
- ✅ Fix migration chain before creating new migrations
- ✅ Test all migrations on clean database first

**Hard Rule Enforcement:**
- ❌ Don't skip hard rule tests
- ✅ Test both happy path and violation cases
- ✅ Verify database-level + app-level enforcement

**Frontend Integration:**
- ❌ Don't assume API endpoints exist without testing
- ✅ Test each endpoint before building screens
- ✅ Handle all error codes (400, 403, 500, etc.)

**Performance:**
- ❌ Don't load all candidates without pagination
- ✅ Add indexes on FK + filter columns
- ✅ Use database queries (not N+1)

---

## RESOURCES

**Code Templates:** See `PHASE_2_FIX_IMPLEMENTATION_PLAN.md` for copy-paste ready code

**Findings:** See `PHASE_2_AUDIT_REPORT_FINAL.md` for detailed analysis per domain

**Roadmap:** See `PHASE_2_END_TO_END_COMPLETION_PLAN.md` for full timeline

---

## CHECKPOINT: When You're Done

All 6 gates passed? Then:
- ✅ Phase 2 is DONE
- ✅ Phase 3 can kickoff
- ✅ Go-live confidence is HIGH
- ✅ Technical debt is MINIMAL

---

**Next Step:** Assign tasks to team, establish daily standups, start Day 1 work.

**Timeline:** 2-3 weeks to completion.

**Go-Live:** On track for 4.5 months.

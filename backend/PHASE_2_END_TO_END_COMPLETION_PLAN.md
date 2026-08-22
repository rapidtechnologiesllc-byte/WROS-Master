# PHASE 2 END-TO-END COMPLETION PLAN

**Objective:** Complete Phase 2 FULLY (backend + frontend) before any Phase 3 work  
**Timeline:** 2-3 weeks of focused development  
**Commitment:** 100% completion, not partial, not "ready for Phase 3"  
**Definition of Done:** All acceptance gates passed, all tests passing, entire workflow tested end-to-end  

---

## PHASE 2 SCOPE (From 02-DATA-MODEL.md)

### What Phase 2 Must Deliver

1. **Complete Data Model** (36/42 models, need 6 more)
2. **All Hard Rules Enforced** (R-01 to R-10)
3. **Full API Layer** (endpoints for all major workflows)
4. **Frontend Screens** (for all Phase 2 workflows)
5. **Integration Testing** (workflows tested end-to-end)
6. **Database Migrations** (clean, tested, reversible)

### Current Status

**Backend:** 36/42 models (86%), 206 services, needs 6 critical fixes  
**Frontend:** Basic screens exist, needs full integration + workflows  
**Tests:** Partial coverage, needs comprehensive end-to-end tests  
**API:** Most endpoints exist, needs complete verification + integration  

---

## PHASE 2 ACCEPTANCE GATES

### 1. Data Model Completeness ✅/❌

**Requirement:** Every table in spec exists with tenant_id, proper indexing, foreign keys

**Status:**
- ✅ Domain 2 (Candidate): 13/16 models (81%)
- ✅ Domain 3 (Employee): 11/12 models (92%)  
- ✅ Domain 4 (Client/Revenue): 12/14 models (86%)
- **TOTAL: 36/42 (86%)**

**Missing 6 Models:**
- ❌ candidate_conversations (Schema mismatch - exists but wrong structure)
- ❌ specialty_certification_clocks (HTD 90-day tracking)
- ❌ erp_sync_log (Invoice ERP sync tracking)
- ❌ employee_payroll_sync_log (Payroll sync tracking)

**Timeline:** 4-6 hours to add all 6 tables + migrations

---

### 2. Hard Rules Enforcement ✅/❌

**Requirement:** All 10 hard rules (R-01 to R-10) enforced at code + database level

**Current Status:**

| Rule | Status | Evidence | Work Needed |
|------|--------|----------|------------|
| R-01 (5-year floor) | ⚠️ PARTIAL | App-level only, DB constraint added | Alembic migration |
| R-02 (Market profile approval) | ❌ UNKNOWN | Not found in codebase | Research + implement |
| R-03 (W2/full-time) | ✅ FULL | Enum + CHECK constraint | None |
| R-04 (Bench-first) | ✅ FULL | demand_service gate | None |
| R-05 (L1 before L2) | ✅ FULL | Dual enforcement | None |
| R-06 (Human dependency <20%) | ❌ UNKNOWN | Not tracked | Implement tracking |
| R-07 (Multi-field dedup) | ⚠️ PARTIAL | Email only | Implement phone + LinkedIn |
| R-08 (Thunder lock) | ❌ UNCLEAR | Race-condition safety unclear | Verify atomic behavior |
| R-09 (USD cents only) | ✅ FULL | All *_usd_cents BIGINT | None |
| R-10 (Timesheet blocks invoice) | ❌ PARTIAL | Unclear if implemented | Verify + implement |

**Timeline:** 2-3 days to complete all hard rules

---

### 3. API Layer Completeness ✅/❌

**Requirement:** REST endpoints for all major Phase 2 workflows

**Workflows to Verify/Build:**

**Candidate Lifecycle:**
- [ ] POST /candidates — Create candidate (create_candidate_safe)
- [ ] GET /candidates/{id} — Read candidate
- [ ] PUT /candidates/{id} — Update candidate
- [ ] GET /candidates — List candidates (with filtering, pagination)
- [ ] POST /candidates/{id}/dedup-check — Check for duplicates

**Demand Management:**
- [ ] POST /demands — Create demand
- [ ] GET /demands/{id} — Read demand
- [ ] PUT /demands/{id}/status — Update demand status
- [ ] GET /demands — List open demands
- [ ] POST /demands/{id}/bench-first-check — Verify bench-first gate

**Submissions & Interviews:**
- [ ] POST /submissions — Submit candidate to demand
- [ ] GET /submissions/{id} — Read submission
- [ ] POST /submissions/{id}/schedule-interview — Schedule interview
- [ ] POST /interviews/{id}/feedback — Record interview feedback
- [ ] GET /interviews — List interviews (with filter by level L1/L2)

**Employee Management:**
- [ ] POST /employees — Convert candidate to employee
- [ ] GET /employees/{id} — Read employee
- [ ] PUT /employees/{id}/allocate — Allocate to project
- [ ] GET /employees — List employees (with BU filtering)

**Scoring & Auto-Assignment:**
- [ ] GET /candidates/{id}/scores — Get candidate scores
- [ ] POST /admin/auto-score-all — Trigger batch scoring
- [ ] GET /demands/{id}/candidate-matches — Auto-proposed matches

**Status:** ~80% of endpoints exist, need integration verification + 20% new endpoints

**Timeline:** 3-4 days to complete all endpoints + integration tests

---

### 4. Frontend Screens ✅/❌

**Requirement:** UI screens for all Phase 2 user workflows

**Screens to Build/Verify:**

**Recruiter Workflows:**
- [ ] Candidate List Screen — Filter, search, sort, bulk actions
- [ ] Add Candidate Modal — Create candidate with validation
- [ ] Candidate Details Screen — View, edit, dedup check
- [ ] Job Matching Screen — Submit candidate to job with auto-scores
- [ ] Demand Dashboard — Open demands, gaps, bench-first status
- [ ] Interview Scheduling Screen — Schedule L1/L2 with panel selection
- [ ] Interview Feedback Form — Record interviewer feedback + recommendation

**HR/Manager Workflows:**
- [ ] Employee List Screen — View all employees, filter by BU/engine
- [ ] Employee Conversion Form — Convert candidate → employee with role assignment
- [ ] Employee Details Screen — View employee profile, allocations, HTD progress
- [ ] Project Allocation Screen — Assign employee to project

**Admin Workflows:**
- [ ] Admin Dashboard — System metrics, auto-scoring status, sync logs
- [ ] Hard Rule Enforcement Dashboard — Verify all rules enforced

**Status:** Basic screens exist, need full integration + error handling + dark mode + mobile

**Timeline:** 5-7 days to build complete, polished screens

---

### 5. Integration Testing ✅/❌

**Requirement:** End-to-end workflows tested (candidate creation → interview → hire)

**Test Scenarios to Cover:**

**Happy Path:**
- [ ] Create candidate → Parse resume → Auto-score → Auto-assign Thunder
- [ ] Submit candidate to demand → Schedule L1 interview
- [ ] L1 feedback → Schedule L2 interview → L2 feedback → Hire
- [ ] Convert to employee → Assign to project → Track allocation

**Negative Cases:**
- [ ] Duplicate candidate (email) — Should be rejected
- [ ] Duplicate candidate (phone) — Should be rejected
- [ ] Duplicate candidate (LinkedIn) — Should be rejected
- [ ] Candidate with <60 months experience — Should be gated at submission
- [ ] Schedule L2 without L1 pass — Should be rejected (R-05)
- [ ] Submit to demand without bench-first check — Should be gated (R-04)
- [ ] Unapproved timesheet → Create invoice — Should be blocked (R-10)

**Edge Cases:**
- [ ] Candidate with NULL experience — Should allow creation, gate at submission
- [ ] Employee allocation > 100% — Should warn or reject
- [ ] Demand demand with no employment_type — Should default to W2_FULLTIME
- [ ] Thunder disabled candidate — Should skip auto-engagement

**Status:** Partial unit tests exist, need full integration test suite

**Timeline:** 3-4 days to build comprehensive test suite

---

### 6. Database & Migrations ✅/❌

**Requirement:** All migrations run cleanly, reversible, schema matches spec

**Migrations Needed:**
- [ ] Add R-01 CHECK constraint to candidates
- [ ] Add missing 4 candidate fields (thunder_channel_user_id, overall_desire_score, consent_given, employment_type_confirmed)
- [ ] Add candidate_conversations table (per spec)
- [ ] Add specialty_certification_clocks table
- [ ] Add erp_sync_log table
- [ ] Add employee_payroll_sync_log table
- [ ] Update any existing models with missing indexes/constraints
- [ ] Add R-10 timesheet → invoice foreign key constraint (if missing)

**Timeline:** 1-2 days to create, test, verify all migrations

---

## BACKEND COMPLETION ROADMAP

### Week 1: Data Model + Hard Rules (3 days)

**Day 1: Complete Data Model**
- [ ] Create specialty_certification_clocks model + migration
- [ ] Create candidate_conversations model (standardize schema)
- [ ] Create erp_sync_log model
- [ ] Create employee_payroll_sync_log model
- [ ] Add R-01 migration (CHECK constraint)
- [ ] Add missing candidate fields migration
- **Effort:** 4 hours

**Day 2: Hard Rules Enforcement**
- [ ] Implement R-02 (Market profile approval workflow)
- [ ] Implement R-06 (Human dependency tracking)
- [ ] Implement R-08 (Thunder lock race-condition safety)
- [ ] Verify/implement R-10 (Timesheet blocks invoice)
- [ ] Implement R-07 dedup service (multi-field)
- [ ] Implement auto-scoring daemon
- **Effort:** 8 hours

**Day 3: Services + Migrations**
- [ ] Create all missing service classes
- [ ] Create sync services (ERP + Payroll)
- [ ] Test all migrations on SQLite
- [ ] Verify migrations run cleanly
- [ ] Commit all backend changes
- **Effort:** 6 hours

### Week 1.5: API Completeness (2 days)

**Day 4-5: API Endpoints + Integration**
- [ ] Verify all required endpoints exist
- [ ] Add missing 20% of endpoints (specialized workflows)
- [ ] Add API error handling (validation errors, business rule violations)
- [ ] Add comprehensive API documentation (OpenAPI/Swagger)
- [ ] Test all endpoints with Postman/curl
- [ ] Add integration tests for all workflows
- **Effort:** 8 hours

---

## FRONTEND COMPLETION ROADMAP

### Week 2: Core Screens (4 days)

**Day 1: Recruiter Workflows (Candidate & Demand)**
- [ ] Complete Candidate List Screen
  - [ ] Filter by source, employment type, experience level
  - [ ] Search by name/email/phone
  - [ ] Show candidate scores (desire, drop risk, etc.)
  - [ ] Bulk actions (convert to employee, add to demand, dedup)
  
- [ ] Complete Add Candidate Modal
  - [ ] Form validation (email, phone format)
  - [ ] Dedup check (show warning if duplicate found)
  - [ ] Employment type selection (W2_FULLTIME required, warn on other)
  - [ ] Resume upload + parsing trigger
  
- [ ] Complete Candidate Details Screen
  - [ ] Display all candidate fields
  - [ ] Show linked jobs/demands
  - [ ] Show interview history
  - [ ] Edit candidate fields (with validation)
  - [ ] Actions: Convert to employee, submit to demand, view dedup

**Effort:** 8 hours

**Day 2: Interview Management**
- [ ] Complete Interview Scheduling Screen
  - [ ] Select job/demand
  - [ ] Choose interview level (L1 or L2, enforce L1 first via API)
  - [ ] Select panel members
  - [ ] Pick date/time (with timezone support)
  - [ ] Add email configuration
  - [ ] Calendar integration (Google Calendar view)
  
- [ ] Complete Interview Feedback Form
  - [ ] Display candidate + interviewer info
  - [ ] Rating scales (recommendation: Hire/Hold/Reject)
  - [ ] Free-text feedback
  - [ ] Special notes/red flags
  - [ ] Submit button (sends API request)
  - [ ] Success message with next steps
  
- [ ] Complete Interview Dashboard
  - [ ] Scheduled interviews (upcoming)
  - [ ] Pending feedback (overdue)
  - [ ] Completed interviews (archive)
  - [ ] Filter by status/level/date

**Effort:** 10 hours

**Day 3: Employee Management**
- [ ] Complete Employee Conversion Modal
  - [ ] Candidate selector (with search)
  - [ ] Employee info form (name, email, position)
  - [ ] Business unit selector
  - [ ] Role multi-select (with permission check)
  - [ ] Joining date picker
  - [ ] Review + confirm button
  - [ ] Success message with new employee ID
  
- [ ] Complete Employee List Screen
  - [ ] Filter by BU, delivery engine (SPECIALITY/CORE), status
  - [ ] Search by name/email
  - [ ] Show allocation status (bench/allocated/non-billable)
  - [ ] Show HTD progress (phase gates)
  - [ ] Bulk actions (assign to project, update status)
  
- [ ] Complete Project Allocation Screen
  - [ ] Select employee (with search/filter)
  - [ ] Select project
  - [ ] Set utilization % and dates
  - [ ] Confirm + track via allocation records

**Effort:** 10 hours

**Day 4: Admin & Monitoring**
- [ ] Build Admin Dashboard
  - [ ] System metrics (candidates, demands, employees)
  - [ ] Auto-scoring status (last run, success rate)
  - [ ] Sync logs status (ERP, payroll)
  - [ ] Hard rule enforcement dashboard (verify R-01 to R-10)
  - [ ] Error monitoring
  
- [ ] Build Hard Rule Enforcement Dashboard
  - [ ] R-01 violations (candidates <60 months)
  - [ ] R-03 violations (non-W2 employment type)
  - [ ] R-05 violations (L2 scheduled before L1)
  - [ ] R-07 duplicates (email/phone/LinkedIn matches)
  - [ ] R-10 violations (unapproved timesheets blocking invoices)
  - [ ] Action buttons (auto-fix where possible)

**Effort:** 8 hours

### Week 3: Polish & Testing (2 days)

**Day 1: Error Handling + UX Polish**
- [ ] Add form validation errors (inline field errors)
- [ ] Add API error handling (show user-friendly messages)
- [ ] Add loading states (spinners, disabled buttons)
- [ ] Add success/error toast notifications
- [ ] Add confirmation dialogs for destructive actions
- [ ] Add empty states (helpful messages when no data)
- [ ] Add pagination (for large lists)
- [ ] Add sorting (by multiple columns)
- **Effort:** 6 hours

**Day 2: Responsiveness + Dark Mode**
- [ ] Test all screens on mobile (375px width)
- [ ] Test all screens on tablet (768px width)
- [ ] Test all screens on desktop (1920px width)
- [ ] Fix responsive layout issues
- [ ] Implement dark mode (system preference detection)
- [ ] Test all colors in dark mode
- [ ] Performance optimization (lazy load, code splitting)
- **Effort:** 6 hours

---

## INTEGRATION & TESTING (1 week)

### Testing Strategy

**Unit Tests (Backend)**
- Service layer tests (scoring, dedup, matching)
- Model tests (validation, constraints)
- Utility functions (normalization, matching algorithms)

**Integration Tests (Backend)**
- End-to-end workflows:
  1. Create candidate → Parse resume → Score → Match to jobs
  2. Submit candidate → Schedule L1 → Record feedback → Schedule L2 → Hire
  3. Convert to employee → Allocate to project → Track utilization
- Hard rule verification:
  - R-01: Reject <60 months
  - R-05: Reject L2 before L1 pass
  - R-04: Reject sourcing without bench-first check
  - R-07: Reject all 3 dedup types
  - R-10: Reject invoice with unapproved timesheet

**End-to-End Tests (Frontend + Backend)**
- Full recruiter workflow (candidate creation to hire)
- Full HR workflow (employee conversion and allocation)
- Full interview workflow (scheduling to feedback to hire)

**Performance Testing**
- Page load times (< 2 seconds target)
- API response times (< 500ms target)
- Batch scoring (1000 candidates < 1 minute)
- Database queries (all use indexes, <100ms queries)

**Timeline:** 5-7 days for comprehensive test suite

---

## DETAILED TASK BREAKDOWN

### Backend Tasks (Priority Order)

**CRITICAL PATH (Must do first):**
1. Add 6 missing data models + migrations (4 hours)
2. Implement R-07 dedup service (2 hours)
3. Implement auto-scoring daemon (3 hours)
4. Implement R-02, R-06, R-08, R-10 enforcement (4 hours)
5. Complete all API endpoints (4 hours)
6. Test all migrations + endpoints (2 hours)

**SUBTOTAL:** ~19 hours (2-3 days focused work)

### Frontend Tasks (Priority Order)

**CRITICAL PATH:**
1. Build Candidate List + Details screens (6 hours)
2. Build Add Candidate + Dedup screens (4 hours)
3. Build Interview Scheduling + Feedback screens (8 hours)
4. Build Employee Management screens (8 hours)
5. Build Admin Dashboard (4 hours)
6. Add error handling + validation (6 hours)
7. Add responsiveness + dark mode (6 hours)
8. Build integration + E2E tests (6 hours)

**SUBTOTAL:** ~48 hours (6-7 days focused work)

**TOTAL PHASE 2 COMPLETION:** ~67 hours (8-10 days at 8 hrs/day, or 2-3 weeks at part-time)

---

## SUCCESS CRITERIA

### Acceptance Gates

✅ **Data Model:** All 42 tables exist, tenant_id on all, proper indexing, FK constraints enforced  
✅ **Hard Rules:** R-01 to R-10 all enforced at code + database level, testable  
✅ **API:** All required endpoints exist, documented, tested, error handling complete  
✅ **Frontend:** All required screens built, polished, accessible, responsive  
✅ **Integration:** End-to-end workflows tested (create → hire → allocate)  
✅ **Migrations:** All run cleanly, reversible, tested on SQLite + staging  
✅ **Tests:** >80% code coverage, all hard rules have test cases  
✅ **Documentation:** API docs (OpenAPI), frontend component docs, runbooks  

### Definition of Done

A story is DONE when:
- Backend: Models + services + migrations + tests + API endpoints all working
- Frontend: Screens built, integrated with APIs, tested, responsive
- Integration: End-to-end workflow tested (happy path + negative cases)
- Deployment: Code committed, CI/CD passing, ready for staging

---

## RISK MITIGATION

| Risk | Impact | Mitigation |
|------|--------|----------|
| **Schema conflicts** | HIGH | Careful Alembic migration testing on clean DB |
| **R-07 dedup false positives** | HIGH | Threshold tunable, extensive unit tests |
| **Frontend integration delays** | HIGH | Parallel work (backend + frontend teams) |
| **API breaking changes** | MEDIUM | Versioning strategy (v1 stable) |
| **Performance degradation** | MEDIUM | Load testing, query optimization, indexing |
| **Test coverage gaps** | MEDIUM | Enforce >80% coverage before merge |

---

## DELIVERABLES AT END OF PHASE 2

1. ✅ Complete Phase 2 codebase (backend + frontend)
2. ✅ All 42 data models implemented
3. ✅ All hard rules (R-01 to R-10) enforced + tested
4. ✅ Complete REST API (OpenAPI docs)
5. ✅ Production-ready frontend (all screens, dark mode, responsive)
6. ✅ Comprehensive test suite (unit + integration + E2E)
7. ✅ Database migrations (clean, reversible, tested)
8. ✅ Deployment guide + runbooks
9. ✅ Phase 3 ready (Phase 2 is **actually complete**, not "ready")

---

## COMMITMENT

**This plan ensures Phase 2 is FINISHED — not "ready for Phase 3," not "mostly working," but ACTUALLY DONE.**

Every acceptance gate passed. Every hard rule enforced. Every workflow tested. Every screen built.

**Timeline:** 2-3 weeks of focused development  
**Effort:** ~67 hours backend + frontend  
**Confidence:** HIGH — Clear scope, documented requirements, testable criteria  
**Go-Live Impact:** Phase 2 completion is prerequisite for Phase 3 and all downstream phases  

---

**Status:** Ready to begin Phase 2 completion work  
**Next Step:** Assign tasks, establish daily standups, track progress against acceptance gates

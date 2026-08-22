# PHASE 2 AUDIT — REQUIREMENTS FOR EXPLORE AGENT

**Goal:** Conduct a systematic, comprehensive audit of Phase 2 implementation against 02-DATA-MODEL.md specification.

**Timeline:** Single session (audit + fixes + documentation before Phase 3 kickoff)

---

## CRITICAL VERIFICATION REQUIREMENTS

### 1. HARD RULES ENFORCEMENT (R-01 through R-10)

For each rule, audit must verify:
- [ ] **Where** is it enforced in code? (file:line)
- [ ] **When** is it enforced? (creation, submission, scheduling, etc.)
- [ ] **How** does it fail? (exception, HTTP status, database constraint)
- [ ] **Is it actually tested?** (grep for test cases)
- [ ] **What are the gaps?** (known edge cases not covered)

**CRITICAL RULES** (must be fully enforced before Phase 3):
- R-01: 5-year experience floor (currently: submission-time gate, needs verification)
- R-03: W2/full-time only (currently: enum defaults to UNKNOWN, needs server-side gate verification)
- R-04: Bench-first before external sourcing (currently: mentioned in demand_service, needs implementation verification)
- R-05: L1 before L2 interview (currently: dual enforcement verified ✅)
- R-07: createCandidateSafe() multi-field dedup (currently: implemented ✅)
- R-08: Thunder locked when recruiter owns (currently: race-condition safety unclear)
- R-09: USD cents only (currently: spot-checked, needs full scan)
- R-10: Unapproved timesheet blocks invoice (currently: unclear if implemented)

**UNCLEAR RULES** (audit needed):
- R-02: No market profile without recruiter + CS sign-off (unknown where/if implemented)
- R-06: Human dependency < 20% by Month 6 (unknown if tracked)

---

### 2. DOMAIN 2 — CANDIDATE & TALENT PIPELINE

**Verification Checklist:**

✅ Core Candidate Tables:
- [ ] `candidates` — exists with all required fields? (id, tenant_id, thunder_channel_user_id, source_channel, overall_desire_score, consent_given, employment_type_confirmed)
- [ ] `candidate_conversations` — exists? (message_history tracking)
- [ ] `candidate_desire_profiles` — exists? (AI scoring data)

✅ Demand & Submission:
- [ ] `job_requisitions` — exists? (track, role_title, required_skills, employment_type)
- [ ] `demands` — exists? (client_id, delivery_engine, demand_type, p1_emergency, source_type)
- [ ] `submissions` — exists? (demand_id, candidate_id, status, overall_score, client_approved)
- [ ] `interviews` — exists? (submission_id, level [L1/L2], outcome, panel_id)

✅ Sourcing & AI:
- [ ] `staged_candidates` — exists? (LinkedIn sourcing staging)
- [ ] `sourcing_alerts` — exists? (auto-generated hiring triggers)
- [ ] `sourcing_search_runs` — exists? (boolean search execution)
- [ ] `outreach_sequences` — exists? (candidate touch tracking)

**CRITICAL AUTOMATION GAPS TO IDENTIFY:**
- Is auto-candidate-scoring implemented? (drop risk, ghosting, joining likelihood, qualification)
- Is auto-dedup recommendation implemented? (beyond just "reject duplicate")
- Is LinkedIn enrichment implemented? (sourcing intelligence)
- Is sourcing alert generation automated? (when to trigger external search)
- Is boolean search intelligence implemented? (synonym-aware query generation)
- Is outreach sequence automation working? (when to message, what to say)

---

### 3. DOMAIN 3 — EMPLOYEE, HR & DELIVERY ENGINE

**Verification Checklist:**

✅ Employee Lifecycle:
- [ ] `employees` — exists with all fields? (candidate_id, delivery_engine [SPECIALITY/CORE], htd_track, core_certified, buddy_program_status, etc.)
- [ ] `employee_allocations` — exists? (project_id, client_id, utilization_pct)
- [ ] `employee_performance_events` — exists AND verified INSERT-ONLY?

✅ Delivery Engine Tracking:
- [ ] `specialty_certification_clocks` — exists? (billable_days_elapsed, paused, reset_count)
- [ ] `core_pull_events` — exists? (competing_demand_ids, resolution)
- [ ] `core_eligibility_reviews` — exists? (AI + RM + BU Head decisions)

✅ HTD & Quality:
- [ ] `htd_phase_gates` — exists? (INDUCTION → SHADOW → CONTROLLED_OWNERSHIP → CORE_REVIEW)
- [ ] `buddy_program_kpi_scores` — exists? (35 KPI tracking)
- [ ] `peer_trust_surveys` — exists? (week_number 6/12)
- [ ] `escalation_classifications` — exists? (RESOURCE_ERROR vs ENVIRONMENT)

**CRITICAL AUTOMATION GAPS TO IDENTIFY:**
- Is R-05 L1-before-L2 enforced in BOTH legacy and new interview systems?
- Is employee_performance_events truly append-only? (INSERT grants but no UPDATE/DELETE?)
- Is specialty_certification_clock auto-tracking billable days? (or manual?)
- Is core-pull conflict detection automated? (Core wins policy)
- Is HTD phase sequencing enforced? (can't skip phases?)
- Is auto-assignment to delivery engine implemented?

---

### 4. DOMAIN 4 — CLIENT, REVENUE & FINANCIAL

**Verification Checklist:**

✅ Client & Project:
- [ ] `clients` — exists? (industry, country, default_currency)
- [ ] `client_contacts` — exists? (name, email, role, is_primary)
- [ ] `projects` — exists? (opportunity_id, delivery_engine, si_partner, billing_type)

✅ Revenue & Invoicing:
- [ ] `invoices` — exists? (status [Draft/Approved/Sent/Paid], total_usd_cents, billing_period)
- [ ] `opportunities` — exists? (stage, revenue_value_usd_cents, probability_pct)

✅ Timesheet & Leakage:
- [ ] `timesheet_anomaly_flags` — exists? (anomaly_type)
- [ ] `timesheet_corrections` — exists? (resubmission_count, response_note)
- [ ] `revenue_leakage_time_layer` — exists? (unbilled_hours, partial_billing_reason)
- [ ] `leakage_events` — exists? (leakage_type, estimated_impact_usd_cents)

✅ Financial Integration:
- [ ] `erp_sync_log` — exists? (sync_status, synced_at)
- [ ] `employee_payroll_sync_log` — exists? (sync_status, synced_at)

**CRITICAL AUTOMATION GAPS TO IDENTIFY:**
- Is R-09 verified across ALL models? (ZERO floats, ALL *_usd_cents as BIGINT?)
- Is R-10 implemented? (Unapproved timesheet blocks invoice creation?)
- Is timesheet anomaly detection automated? (system finds issues or manual?)
- Is revenue leakage detection automated? (triggers alerts when hours unbilled?)
- Is ERP sync actually working? (or stubbed/mocked?)
- Is payroll sync working? (integration with payroll provider?)
- Is single-currency (USD) enforced? (no multi-currency fields?)

---

### 5. SERVICE LAYER QUALITY

**For each automation gap identified, audit must check:**

1. **Does a service class exist?**
   - File path (app/services/*.py)
   - What does it do?

2. **Is it used anywhere?**
   - Which API endpoints call it?
   - Which models/workflows depend on it?
   - Is it actually called or is it dead code?

3. **Is it tested?**
   - Are there unit tests? (tests/unit/*.py)
   - Are there integration tests?
   - What cases are covered?

4. **Does it have the automation logic?**
   - Is it a smart service (business logic) or just a CRUD wrapper?
   - Does it enforce rules or just store data?

5. **Is it wired to the workflow?**
   - Does it get called at the right time?
   - Does it get the right input?
   - Does it update the right state?

**Example Flow to Verify:**
```
Candidate Created
  → candidate_service.create_candidate_safe() called? ✅
  → R-07 dedup check executed? ✅
  → Consent record created? ✅
  → Thunder auto-assigned? (verify: thunder_assigned_at set?)
  → Scoring loop triggered? (candidate_ai_auto_assignment_service?)
  → First engagement message sent? (email_first_engagement_service?)
```

---

### 6. TESTING & VERIFICATION

**Audit must identify:**

- [ ] Which hard rules have test cases?
- [ ] Which automated workflows have integration tests?
- [ ] Which services have unit tests?
- [ ] What critical paths have NO tests?
- [ ] What gaps would a developer hit if building Phase 3?

---

### 7. DATABASE SCHEMA HEALTH

**Verify:**

- [ ] Every table has `tenant_id` (NOT NULL, indexed)?
- [ ] Every table has `id` (UUID or appropriate primary key)?
- [ ] Foreign key relationships enforced at DB level?
- [ ] Soft deletes used for business entities? (status/is_active, never hard DELETE)
- [ ] Append-only tables grants correct? (employee_performance_events, audit_log)
- [ ] Migration script exists and runs cleanly?
- [ ] Indexes on foreign keys and filtering columns?
- [ ] No naming conflicts or reserved words?

---

## AUDIT OUTPUT FORMAT

When complete, provide:

```markdown
## PHASE 2 AUDIT — FINDINGS REPORT

### Executive Summary
- Total models found: X / ~120 expected
- Hard rules fully enforced: Y / 10
- Critical gaps found: Z
- Estimated fix effort: N hours

### Domain-by-Domain Findings

#### Domain 2 — Candidate Pipeline
[Detailed findings, existing models, missing models, automation gaps]

#### Domain 3 — Employee/HR
[Detailed findings, existing models, missing models, automation gaps]

#### Domain 4 — Client/Revenue
[Detailed findings, existing models, missing models, automation gaps]

### Hard Rules Enforcement Status

| Rule | Status | Evidence | Gaps |
|------|--------|----------|------|

### Critical Automation Gaps (Prioritized by Blast Radius)

1. [Gap 1] — Impact: HIGH, Effort: MEDIUM, Files affected: [list]
2. [Gap 2] — Impact: HIGH, Effort: SMALL, Files affected: [list]
...

### Service Layer Assessment

**Total Services:** 206  
**Functional Services:** X  
**Partial Services:** Y  
**Stubbed/Missing:** Z  

### Next Steps for Phase 2 Completion

1. [Fix 1]: [description]
2. [Fix 2]: [description]
...

### Phase 3 Readiness Check

- [ ] All hard rules enforced
- [ ] Candidate automation working
- [ ] Interview sequencing working
- [ ] Employee lifecycle working
- [ ] Notification engine wired
- [ ] Task model ready
- [ ] All critical gaps fixed
```

---

## SUCCESS CRITERIA

Audit is complete when:

✅ Every model in 02-DATA-MODEL.md spec is checked (exists or missing documented)  
✅ Every hard rule (R-01 to R-10) enforcement status is verified  
✅ Every critical automation gap is identified with file:line evidence  
✅ Service layer coverage assessed per gap  
✅ Testing coverage identified per gap  
✅ Prioritized fix list provided (red/yellow/green)  
✅ Clear picture of Phase 3 foundation quality  

---

**Audit Status:** IN PROGRESS  
**Agent:** Explore (a7129dc52976c2ac7)  
**Expected Completion:** This session

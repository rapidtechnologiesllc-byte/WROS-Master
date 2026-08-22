# PHASE 2 AUDIT CHECKLIST — COMPREHENSIVE

**Owner:** Audit Agent (a7129dc52976c2ac7)  
**Status:** IN PROGRESS  
**Started:** 2026-08-14 14:30 UTC  
**Target Completion:** Same session before Phase 3 kickoff  

---

## DOMAIN 2 — CANDIDATE & TALENT PIPELINE

### Core Models
- [ ] `candidates` — Full field check + tenant_id + indexing
  - [ ] `id` (UUID primary key)
  - [ ] `tenant_id` (NOT NULL, indexed)
  - [ ] `thunder_channel_user_id` (auto-assigned)
  - [ ] `source_channel` (DIRECT/SUBVENDOR)
  - [ ] `overall_desire_score` (from AI scoring)
  - [ ] `consent_given` (WhatsApp/email)
  - [ ] `employment_type_confirmed` (W2_FULLTIME only, R-03)
  - [ ] `total_experience_months` (from resume parsing)
  - [ ] `linkedin_url` (for R-07 dedup)
  
- [ ] `candidate_conversations` — Message history tracking
  - [ ] `id`, `tenant_id`, `candidate_id`, `channel`, `message_history`
  
- [ ] `candidate_desire_profiles` — Motivation/fit scoring
  - [ ] `id`, `tenant_id`, `candidate_id`, `desire_score`, `motivation_gap_analysis`

### Sourcing & Pipeline
- [ ] `job_requisitions` — Standardized job definitions
  - [ ] Track (STANDARD/HTD), role_title, required_skills, employment_type
  
- [ ] `demands` — Client-specific hiring needs
  - [ ] `id`, `tenant_id`, `client_id`, `delivery_engine`, `demand_type`
  - [ ] `p1_emergency` (priority flag)
  - [ ] `source_type` (BENCH_FIRST, EXTERNAL, HYBRID)
  
- [ ] `submissions` — Candidate-to-demand mappings
  - [ ] `id`, `tenant_id`, `demand_id`, `candidate_id`, `status`, `overall_score`
  - [ ] `client_approved` (final gate)
  
- [ ] `interviews` — Interview events
  - [ ] `id`, `submission_id`, `level` (L1/L2)
  - [ ] `outcome`, `panel_id`
  - [ ] R-05 enforcement (L1 before L2)

### AI/Automation Tables
- [ ] `staged_candidates` — LinkedIn/sourcing staging
  - [ ] `id`, `search_run_id`, `linkedin_profile_url`, `dedup_status`
  
- [ ] `sourcing_alerts` — Auto-generated sourcing triggers
  - [ ] `id`, `demand_id`, `severity`, `rationale`, `status`
  
- [ ] `sourcing_search_runs` — Boolean search execution
  - [ ] `id`, `sourcing_alert_id`, `boolean_query`, `alt_queries`
  
- [ ] `outreach_sequences` — Candidate touch tracking
  - [ ] `id`, `candidate_id`, `message_text`, `primary_channel`, `sequence_status`

### AUDIT FINDINGS — Domain 2
```
TODO: Audit agent will populate:
- Which models actually exist vs. spec
- Which models are missing
- Auto-scoring: implemented? (drop risk, ghosting, joining likelihood, qualification)
- Auto-dedup recommendation: implemented?
- LinkedIn enrichment: implemented?
- Sourcing alert generation: implemented?
- Boolean search intelligence: implemented?
```

---

## DOMAIN 3 — EMPLOYEE, HR & DELIVERY ENGINE

### Core Models
- [ ] `employees` — Employee lifecycle
  - [ ] `id`, `tenant_id`, `candidate_id`, `wros_id`
  - [ ] `delivery_engine` (SPECIALITY/CORE)
  - [ ] `status`, `htd_track`, `core_certified`, `core_certified_date`
  - [ ] `engine_entry_date`, `core_eligible_from`
  - [ ] `buddy_program_status`, `reporting_manager_user_id`, `job_title`
  
- [ ] `employee_allocations` — Project assignments
  - [ ] `id`, `employee_id`, `project_id`, `client_id`, `delivery_engine`
  - [ ] `utilization_pct`, `start_date`, `end_date`
  
- [ ] `employee_performance_events` — Append-only audit trail
  - [ ] Verified INSERT-only (no UPDATE/DELETE)
  - [ ] `id`, `employee_id`, `event_type`, `event_data`, `occurred_at`

### Delivery Engine & Certifications
- [ ] `specialty_certification_clocks` — Billable day tracking
  - [ ] `id`, `employee_id`, `clock_type` (STANDARD_90/HTD_365)
  - [ ] `billable_days_elapsed`, `paused`, `reset_count`
  
- [ ] `core_pull_events` — Core vs Speciality conflict tracking
  - [ ] `id`, `employee_id`, `competing_demand_ids`, `resolution`
  - [ ] R-04 enforcement (bench-first before pull)
  
- [ ] `core_eligibility_reviews` — Core transition gates
  - [ ] `id`, `employee_id`, `ai_recommendation`, `rm_recommendation`, `bu_head_decision`
  
- [ ] `htd_phase_gates` — HTD progression tracking
  - [ ] `id`, `employee_id`, `phase` (INDUCTION/SHADOW/CONTROLLED_OWNERSHIP/CORE_REVIEW)
  - [ ] `decision`, `decided_by`, `decided_at`

### Buddy Program & Quality
- [ ] `buddy_program_kpi_scores` — 35 KPI tracking
  - [ ] `id`, `employee_id`, `kpi_number` (1-35), `scorer_role`, `score`, `week_number`
  
- [ ] `peer_trust_surveys` — Trust assessment
  - [ ] `id`, `employee_id`, `week_number` (6 or 12), `respondent_id`, `scores_json`
  
- [ ] `escalation_classifications` — Issue categorization
  - [ ] `id`, `employee_id`, `escalation_type` (RESOURCE_ERROR/ENVIRONMENT)
  - [ ] `classified_by`, `description`

### AUDIT FINDINGS — Domain 3
```
TODO: Audit agent will populate:
- Which models exist vs. spec
- R-05 enforcement verified (L1 before L2 interview)
- employee_performance_events: INSERT-only verified?
- specialty_certification_clocks: append logic verified?
- core_pull_events: R-04 bench-first gate enforced?
- HTD phase gates: sequencing enforced?
- Auto-assignment to delivery engine: implemented?
```

---

## DOMAIN 4 — CLIENT, REVENUE & FINANCIAL

### Client & Project
- [ ] `clients` — Client master data
  - [ ] `id`, `tenant_id`, `name`, `industry`, `country`, `default_currency`
  
- [ ] `client_contacts` — Contact records
  - [ ] `id`, `client_id`, `name`, `email`, `role`, `is_primary`
  
- [ ] `projects` — Engagement tracking
  - [ ] `id`, `tenant_id`, `client_id`, `opportunity_id`, `delivery_engine`
  - [ ] `si_partner`, `status`, `billing_type`

### Revenue & Invoicing
- [ ] `invoices` — Billing documents
  - [ ] `id`, `tenant_id`, `client_id`, `status` (Draft/Approved/Sent/Paid)
  - [ ] `total_usd_cents` (R-09: BIGINT, no floats)
  - [ ] `billing_period`, `unapproved_timesheet_blocks` (R-10)
  
- [ ] `opportunities` — Sales pipeline
  - [ ] `id`, `tenant_id`, `client_id`, `stage`
  - [ ] `revenue_value_usd_cents` (R-09)
  - [ ] `probability_pct`, `owner_id`

### Timesheet & Anomalies
- [ ] `timesheet_anomaly_flags` — Auto-detected issues
  - [ ] `id`, `timesheet_entry_id`, `anomaly_type`
  - [ ] Auto-detection implemented?
  
- [ ] `timesheet_corrections` — Resubmission tracking
  - [ ] `id`, `timesheet_id`, `resubmission_count`, `response_note`
  
- [ ] `timesheet` entries — Billable hours
  - [ ] Unapproved timesheet blocks invoice (R-10)?

### Revenue Leakage
- [ ] `revenue_leakage_time_layer` — Unbilled hour tracking
  - [ ] `id`, `project_id`, `unbilled_hours`, `partial_billing_reason`
  - [ ] Auto-detection implemented?
  
- [ ] `leakage_events` — Escalations
  - [ ] `id`, `tenant_id`, `leakage_type`, `source_entity_id`
  - [ ] `estimated_impact_usd_cents` (R-09)

### Financial Infrastructure
- [ ] `erp_sync_log` — Accounting system integration
  - [ ] `id`, `invoice_id`, `sync_status`, `synced_at`
  
- [ ] `employee_payroll_sync_log` — Payroll integration
  - [ ] `id`, `employee_id`, `sync_status`, `synced_at`

### AUDIT FINDINGS — Domain 4
```
TODO: Audit agent will populate:
- Which models exist vs. spec
- R-09 verification: ALL monetary fields BIGINT cents? (no floats anywhere)
- R-10 verification: Unapproved timesheet blocks invoice?
- Timesheet anomaly detection: automated or manual?
- Revenue leakage detection: automated or manual?
- ERP sync: implemented or stubbed?
- Currency support: single USD only?
```

---

## HARD RULES VERIFICATION MATRIX

| Rule | Spec | Implementation Status | Evidence/File | Gaps |
|------|------|----------------------|---|---|
| **R-01** | 5-year experience floor, no exceptions without BU Head override | Moved to submission-time (submission_service.check_experience_eligibility) | candidate_service.py:145+ | Create at any level, gate submission ✅ |
| **R-02** | No market profile without recruiter + CS sign-off | Both roles required independently | [NEEDS VERIFICATION] | [AUDIT NEEDED] |
| **R-03** | W2/full-time only | employment_type ENUM, server-side enforced | candidate.py:62-64 | Defaults to UNKNOWN (fail-closed) ✅ |
| **R-04** | Bench-first before external sourcing | Hard gate checked before sourcing | demand_service.py:20 | [AUDIT NEEDED: gate enforcement] |
| **R-05** | L1 must pass before L2 scheduled | Enforced at panel-creation time | interview_sequencing_service.py:76, interview_service.py:128 | Both systems gated ✅ |
| **R-06** | Human dependency < 20% by Month 6 | Platform-level tracking | [NEEDS VERIFICATION] | [AUDIT NEEDED] |
| **R-07** | createCandidateSafe() only path, multi-field dedup | Email + phone + LinkedIn dedup | candidate_service.py:47-72 | All call sites retrofitted ✅ |
| **R-08** | Thunder locked when recruiter owns | Race-condition safe | [NEEDS VERIFICATION] | [AUDIT NEEDED: atomic check] |
| **R-09** | USD cents only, no second-currency column | BIGINT *_usd_cents naming | candidate.py, invoice.py | [AUDIT NEEDED: full scan] |
| **R-10** | Unapproved timesheet blocks invoice | Server-side block | [NEEDS VERIFICATION] | [AUDIT NEEDED: implementation] |

---

## SERVICE LAYER QUALITY ASSESSMENT

**Total Services Found:** 206  
**Categories:**
- [ ] Candidate automation (scoring, dedup, matching)
- [ ] Interview automation (sequencing, scheduling, feedback)
- [ ] Employee lifecycle (conversion, allocation, tracking)
- [ ] Financial automation (timesheet, invoice, leakage)
- [ ] Thunder/AI autonomy (session, execution, state)
- [ ] Notification/Communication (email, task, alert)

**AUDIT FINDINGS:**
```
TODO: Audit agent will categorize by:
- Automation implemented (service exists + logic tested)
- Partial automation (service exists but gaps in logic)
- Stubbed/planned (service exists but not functional)
- Missing entirely (no service found)
```

---

## AUTOMATION GAPS PRIORITY MATRIX

| Gap | Impact | Effort | Dependency | Priority |
|-----|--------|--------|------------|----------|
| Auto-candidate-scoring (all metrics) | HIGH | MEDIUM | None | 🔴 **CRITICAL** |
| Auto-dedup recommendation (not just reject) | MEDIUM | SMALL | R-07 exists | 🟡 **HIGH** |
| R-03 server-side enforcement gate | HIGH | SMALL | Model exists | 🔴 **CRITICAL** |
| R-04 bench-first hard gate | HIGH | SMALL | Service exists | 🔴 **CRITICAL** |
| R-08 race-condition safety (Thunder lock) | HIGH | MEDIUM | Model exists | 🔴 **CRITICAL** |
| R-09 full currency scan (no floats anywhere) | HIGH | MEDIUM | Code review | 🔴 **CRITICAL** |
| R-10 timesheet → invoice block | HIGH | SMALL | Models exist | 🔴 **CRITICAL** |
| Auto-timesheet-anomaly detection | MEDIUM | MEDIUM | Model exists | 🟡 **HIGH** |
| Auto-demand-to-bench matching | MEDIUM | MEDIUM | Services exist | 🟡 **HIGH** |
| Auto-revenue-leakage detection | MEDIUM | MEDIUM | Model exists | 🟡 **HIGH** |
| Market profile approval workflow | MEDIUM | LARGE | Needs design | 🟡 **HIGH** |

---

## COMPLETION CRITERIA

### Before Phase 3 Kickoff, Phase 2 Must Have:

- [ ] All 10 hard rules (R-01 to R-10) fully enforced at code level
- [ ] All critical automation gaps fixed (red 🔴 items above)
- [ ] All Domain 2/3/4 models verified exist + indexed + tenant-scoped
- [ ] No monetary field exists outside `*_usd_cents` convention
- [ ] append-only verification for `employee_performance_events` and `audit_log`
- [ ] All foreign key relationships enforced at DB level
- [ ] Migration can run cleanly end-to-end, produces all Phase 2 tables
- [ ] Documentation: Phase 2 completion report signed off

### Phase 3 Can Assume:

✅ Candidate creation/dedup/scoring working automatically  
✅ Interview sequencing (R-05) enforced  
✅ Employee lifecycle (creation, allocation, tracking) automated  
✅ Notification engine (HRMS-0113) ready to wire  
✅ Task model ready for workflow integration  
✅ All hard rules enforced at code level  

---

**Status:** Will be updated as Explore agent audit completes.  
**Next:** Execute fixes for all identified gaps, then Phase 3 kickoff.

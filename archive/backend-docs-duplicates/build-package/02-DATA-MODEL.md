# Phase 2: Complete Data Model

**Build this second, after every Phase 1 acceptance gate passes. Every table below inherits Phase 1's guarantees automatically — `tenant_id` on every table, permission-gated access, audit logging on every mutation of a flagged entity, no exceptions.**

---

## How to use this document

This is the full-platform entity map, organized by domain. For any table that belongs to a story with a complete 12-section requirements doc, this document gives you the table's name, its core fields, and its relationships — the story doc itself is the authoritative source for validation rules, business rules tied to specific fields, and acceptance criteria. For the 94 stories without a full doc yet, this document gives you a minimum viable schema stub, marked `[GAP-SPEC]`, sufficient to unblock building — treat these as provisional, expect refinement once the full requirements doc exists.

**Universal rules for every table in this document, no exceptions:**
- `id` — UUID primary key, never an auto-increment integer (per R-09-adjacent platform convention)
- `tenant_id` — UUID, NOT NULL, indexed, on every table without exception (per Phase 1)
- Soft deletes only on business entities (candidates, employees, clients, demands, projects, submissions) — use `status`/`is_active`, never a hard DELETE
- All monetary fields — `BIGINT`, USD cents, named `*_usd_cents` — per R-09, no exceptions, no second-currency columns anywhere

---

## Domain 1 — Platform Foundation (built in Phase 1, referenced everywhere after)

```
tenants, users, business_units, bu_access, audit_log, error_log,
consent_records, system_config, notifications, activity_timeline, file_uploads
```
Full detail: see Phase 1 document and stories HRMS-0109, 0110, 0111, 0113, 0114, 0115, 0117, 0118, 0121.

---

## Domain 2 — Candidate & Talent Pipeline

```
candidates (id, tenant_id, thunder_channel_user_id, source_channel, overall_desire_score,
            consent_given, employment_type_confirmed)
candidate_conversations (id, candidate_id, channel, message_history)
candidate_desire_profiles (id, candidate_id, desire_score, motivation_gap_analysis, updated_at)
job_requisitions (id, tenant_id, track [STANDARD/HTD], role_title, required_skills, employment_type)
demands (id, tenant_id, client_id, delivery_engine, demand_type, p1_emergency, source_type, opportunity_id)
submissions (id, tenant_id, demand_id, candidate_id, status, overall_score, client_approved)
interviews (id, submission_id, level [L1/L2], outcome, panel_id, scheduled_via_graph_event_id)
job_specifications (id, demand_id, jd_text, required_certifications)
sourcing_alerts (id, demand_id, severity, rationale, status)          — HRMS-1102's output
sourcing_search_runs (id, sourcing_alert_id, boolean_query, alt_queries) — HRMS-1103's output
staged_candidates (id, search_run_id, linkedin_profile_url, dedup_status, promoted_to_candidate_id)
outreach_sequences (id, candidate_id, message_text, primary_channel, sequence_status, touch_count)  — HRMS-1104/S-319
```
Full detail on the agent-produced tables: EPIC-11 stories HRMS-1101 through 1110 (all fully specified).

**`[GAP-SPEC]` LinkedIn Autonomous Sourcing Pipeline (7 stories, no doc yet)** — minimum stub:
```
linkedin_search_sessions (id, tenant_id, query, rate_limit_window, session_status)
linkedin_profile_enrichment (id, staged_candidate_id, enriched_fields, confidence)
```
Build against HRMS-1103's already-complete LinkedIn Sourcing Agent Loop pattern — this gap cluster is almost certainly refining/extending that agent's capability, not a separate system. Do not build a second LinkedIn integration; extend the existing one.

**`[GAP-SPEC]` Boolean Search & AI Search Intelligence (11 stories, no doc yet)** — minimum stub:
```
boolean_search_templates (id, tenant_id, skill_category, query_template, synonym_library_ref)
search_execution_log (id, template_id, executed_query, result_count, executed_at)
```
Cross-check against HRMS-1103's existing Boolean query generation (max_tokens=800, synonym-aware) before building — likely overlapping scope, resolve before writing new code.

**`[GAP-SPEC]` Interview Decision Engine & Compliance Rules (10 stories, no doc yet)** — minimum stub:
```
interview_panels (id, tenant_id, candidate_id, level, panel_members, scheduled_at)
interview_scorecards (id, panel_id, scores_json, recommendation)
```
**This gap cluster is where R-05 (L1-before-L2) must be enforced** — do not build any part of this without the sequencing gate specified in the Development & Review Standard, Part 1. This is also where the existing Onboarding Module's interview-scheduling code lives and needs its R-05 gate retrofitted (see Phase 1's referenced onboarding gaps).

**`[GAP-SPEC]` Talent Engine ATS Layer (7 stories, no doc yet) & Proactive Nurture Engine (7 stories, no doc yet)** — these extend candidate pipeline stage tracking and nurture campaign scheduling respectively; build against the `candidates`/`submissions` tables above, do not create parallel candidate-state tables.

---

## Domain 3 — Employee, HR & Delivery Engine

```
employees (id, tenant_id, candidate_id, wros_id, delivery_engine [SPECIALITY/CORE], status,
           htd_track, core_certified, core_certified_date, engine_entry_date, core_eligible_from,
           buddy_program_status, reporting_manager_user_id, job_title)
employee_engine_history (id, employee_id, old_engine, new_engine, changed_at, approval_reference)
employee_allocations (id, employee_id, project_id, client_id, delivery_engine, utilization_pct,
                       start_date, end_date, client_reporting_manager_contact_id)
employee_performance_events (id, employee_id, event_type, event_data, occurred_at)  — append-only, INSERT only
specialty_certification_clocks (id, employee_id, clock_type [STANDARD_90/HTD_365], status,
                                 billable_days_elapsed, paused, reset_count)
core_pull_events (id, employee_id, competing_demand_ids, resolution, occurred_at)
core_eligibility_reviews (id, employee_id, ai_recommendation, rm_recommendation, bu_head_decision)
htd_phase_gates (id, employee_id, phase [INDUCTION/SHADOW/CONTROLLED_OWNERSHIP/CORE_REVIEW],
                 decision, decided_by, decided_at)
htd_candidate_scores (id, candidate_id, htd_readiness_score, sub_scores_json)  — S-258
htd_interviews (id, candidate_id, l1_outcome, l2_outcome, director_decision)   — S-261
buddy_program_kpi_scores (id, employee_id, kpi_number [1-35], scorer_role, score, week_number)
peer_trust_surveys (id, employee_id, week_number [6 or 12], respondent_id, scores_json)
escalation_classifications (id, employee_id, escalation_type [RESOURCE_ERROR/ENVIRONMENT],
                             classified_by, description)
specialty_pool_guard_log (id, tenant_id, current_count, move_blocked, replacement_plan)
```
Full detail: NEW-RM stories S-351 through S-378 (all fully specified — this is the richest-detailed domain in the whole backlog, use it directly).

**`[GAP-SPEC]` Resource & Bench Management (11 stories, no doc yet)** — minimum stub, **this is Phase 4's primary domain, detailed further in 04-RESOURCE-MANAGEMENT.md**:
```
bench_pool (id, employee_id, available_from, skill_tags, bench_duration_days)
bench_allocation_recommendations (id, employee_id, recommended_demand_id, confidence_pct, rm_decision)
allocation_conflict_log (id, employee_id, conflicting_allocations_json, resolution)
```

---

## Domain 4 — Client, Revenue & Financial

```
clients (id, tenant_id, name, industry, country, default_currency, account_manager_id)
client_contacts (id, client_id, name, email, role, is_primary)
opportunities (id, tenant_id, client_id, stage, revenue_value_usd_cents, probability_pct, owner_id)
projects (id, tenant_id, client_id, opportunity_id, delivery_engine, si_partner, status, billing_type)
project_milestones (id, project_id, due_date, completion_date, delay_days, owner_id)
invoices (id, tenant_id, client_id, status [Draft/Approved/Sent/Paid], total_usd_cents, billing_period)
timesheet_anomaly_flags (id, timesheet_entry_id, anomaly_type)
timesheet_corrections (id, timesheet_id, resubmission_count, response_note)
revenue_leakage_time_layer (id, project_id, unbilled_hours, partial_billing_reason)
leakage_events (id, tenant_id, leakage_type, source_entity_id, estimated_impact_usd_cents)
client_health_scores (id, client_id, health_score, sub_scores_json)  — internal only, never client-visible
ai_predictions (id, tenant_id, prediction_type, prediction_value, confidence_pct, rationale)
exchange_rate_snapshots (id, currency, rate, snapshot_date)
erp_sync_log (id, invoice_id, sync_status, synced_at)
employee_payroll_sync_log (id, employee_id, sync_status, synced_at)
```
Full detail: EPIC-02 Revenue Visibility stories (S-230, 236-244), EPIC-09 Time Tracking (S-225, 226, 228, 229), EPIC-08 Project & Delivery (S-299, 301-305), Integration Hub (S-338, 342-344).

**`[GAP-SPEC]` Analytics & Executive Dashboards (7 stories, no doc yet)** — build as read-only aggregation views over the tables above; per the Development & Review Standard's consolidation logic, this likely collapses into fewer dashboard components than 7, following the same CRUD-framework-reuse pattern applied elsewhere in this backlog.

---

## Domain 5 — Sub-Vendor Portal

```
sub_vendor_accounts (id, tenant_id, vendor_name, compliance_status [GOOD_STANDING/UNDER_REVIEW/SUSPENDED])
sub_vendor_requests (id, tenant_id, vendor_id, deadline, status)
sub_vendor_submissions (id, request_id, candidate_data_json, employment_type, review_decision, feedback_note)
sub_vendor_violations (id, vendor_id, violation_type, occurred_at)
sub_vendor_dedup_rejections (id, submission_id, matched_candidate_id)
clarification_qa (id, request_id, question, answer, asked_by, answered_by)
```
Full detail: EPIC-P8 stories S-142 through S-154 (all fully specified).

---

## Domain 6 — Internal Collaboration, Scheduling & Interview Integrity (Batch 7)

```
check_in_cadence_config (id, tenant_id, level_name, cadence_days)
employee_hierarchy_resolution (id, employee_id, hierarchy_depth, resolved_level, unmapped_title_flag)
check_in_history (id, manager_id, report_id, last_check_in_date, check_in_status)
interview_integrity_assessments (id, interview_id, integrity_concern_level, concern_categories_json,
                                  supporting_evidence_json, confidence_pct)
interview_clarification_log (id, interview_id, clarification_triggered, panel_response)
```
Full detail: EPIC-14 stories S-379 through S-384, EPIC-15 stories S-385 through S-386 (all fully specified).

---

## Cross-domain relationship notes worth knowing before you start writing queries

- `candidates.id` → `employees.candidate_id` — a candidate becomes an employee at hire, the row is never deleted and recreated, it's a lifecycle transition tracked via `employee_engine_history`.
- `demands.opportunity_id` → `opportunities.id` — nullable, since not every demand originates from a tracked sales opportunity (e.g., a direct client follow-on request).
- `employee_allocations` is the single join point between Domain 3 (employee) and Domain 4 (project/client) — every utilization, margin, and billing calculation ultimately traces through this table.
- `ai_predictions` is intentionally generic (one table, a `prediction_type` discriminator) per HRMS-1001/1004's unified-engine design — do not create a separate table per prediction type.

---

## Acceptance gate for this phase

- [ ] Every table listed above exists with `tenant_id` NOT NULL, indexed
- [ ] Every foreign key relationship listed above is enforced at the database level (real FK constraints, not just application-level convention)
- [ ] A migration can run cleanly end-to-end against an empty database and produce every table in this document
- [ ] No monetary column exists anywhere outside the `*_usd_cents` BIGINT convention
- [ ] `employee_performance_events` and `audit_log` are confirmed append-only at the grant level (inherited from Phase 1, re-verify here since this is where the largest number of write paths into them get built)

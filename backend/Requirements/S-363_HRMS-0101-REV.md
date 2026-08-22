# S-363 — HRMS-0101-REV: Employee Entity Model — Delivery Engine Fields (REVISED)

| Field | Value |
|---|---|
| Epic | PATCHES — Revised Existing Documents |
| Sprint / Week | Sprint 23 \| W8 |
| Priority | P0 — Critical |
| Owner / Assignee | Riya / Backend — DBA |
| Estimate | 2 days |
| Status | UPDATE — Revise Existing Doc |
| Depends On | HRMS-0101 original Employee Entity (S-199 in final backlog). HRMS-0512 Delivery Engine Assignment (S-351). |
| Blocks | HRMS-0351 to HRMS-0378 — all NEW-RM stories depend on these fields being on the employees table. |

## Why — Business Rationale

- The original employee entity (HRMS-0101) was built without delivery engine awareness because the two-engine architecture was defined later. All new Delivery Engine and Performance Intelligence stories (S-351 to S-378) require fields that do not yet exist on the employees table. This story is the database migration that adds those fields and the associated constraints, without disrupting any existing data.

## What — Scope

- AMEND HRMS-0101: Add all Delivery Engine and Performance Intelligence fields to employees table via migration. Backfill all existing employees to SPECIALITY. Add DB CHECK constraint preventing CORE without core_certified=TRUE. Add buddy program status fields. Add HTD track fields. Zero downtime migration.

## Before — Prerequisites

- HRMS-0101 employees table live in all environments. HRMS-0512 (S-351) Delivery Engine Assignment ready to use new fields.

## Implementation Steps

## Step 1: Write and test migration script

- Migration adds the following columns to employees table:

- delivery_engine ENUM('SPECIALITY','CORE') NOT NULL DEFAULT 'SPECIALITY'

- engine_entry_date DATE NOT NULL DEFAULT CURRENT_DATE

- core_eligible_from DATE nullable

- core_certified BOOLEAN NOT NULL DEFAULT FALSE

- core_certified_date DATE nullable

- buddy_program_status ENUM('NOT_STARTED','IN_PROGRESS','GRADUATED','EXTENDED','EXITED') NOT NULL DEFAULT 'NOT_STARTED'

- buddy_program_start_date DATE nullable

- buddy_program_graduation_date DATE nullable

- htd_track BOOLEAN NOT NULL DEFAULT FALSE

- htd_start_date DATE nullable

- htd_phase ENUM('INDUCTION','SHADOW_DELIVERY','CONTROLLED_OWNERSHIP','CORE_ELIGIBILITY_REVIEW','COMPLETED','EXITED') nullable

- reporting_manager_user_id UUID nullable FK→users.id

## Step 2: Add DB CHECK constraint

- ALTER TABLE employees ADD CONSTRAINT chk_core_requires_certified CHECK (delivery_engine != 'CORE' OR core_certified = TRUE).

- This is a database-level guard — independent of application code. If any code path tries to set delivery_engine=CORE without core_certified=TRUE: PostgreSQL rejects the write with constraint violation.

## Step 3: Backfill existing employees

- UPDATE employees SET delivery_engine='SPECIALITY', engine_entry_date=joining_date, buddy_program_status='GRADUATED' WHERE status NOT IN ('PRE_JOINING','EXITED').

- Rationale: existing employees have already completed onboarding — backfilling as GRADUATED is correct. Their delivery_engine starts as SPECIALITY pending any historical Core Certification review.

- Run in a transaction with rollback on any error. Test on staging with full production data volume before production run.

## Step 4: Create employee_engine_history table

- CREATE TABLE employee_engine_history: id UUID PK, tenant_id UUID, employee_id UUID FK, from_engine ENUM('SPECIALITY','CORE') nullable, to_engine ENUM('SPECIALITY','CORE'), changed_at TIMESTAMP, changed_by UUID, approval_reference VARCHAR(200) nullable, reason TEXT.

- Seed one history record per existing employee: from_engine=NULL, to_engine=SPECIALITY, changed_at=migration_run_date, changed_by=system, reason='Initial migration — all employees enter SPECIALITY'.

## UI Fields

| Field Name | Input Type | Required | Validation | Placeholder / Example | Notes |
|---|---|---|---|---|---|
| No new UI — database migration only | N/A | N/A | N/A | N/A | All new fields exposed via existing employee profile screens once HRMS-0512 UI is built. |

## Business Rules

## BR: Migration Must Run in Transaction — Rollback on Any Row Failure

- The backfill UPDATE must run inside a single database transaction. If any row update fails: the entire migration rolls back. Partial migrations create inconsistent data state that is worse than no migration. Test on staging first with production data copy.

- Field: Transactional migration — all or nothing

## BR: CHECK Constraint Is Independent of Application Layer

- The DB CHECK constraint (delivery_engine != CORE OR core_certified = TRUE) must be added to PostgreSQL, not just enforced in application code. This ensures no future code path — including direct DB access, scripts, or future migrations — can accidentally set an employee to CORE without certification.

- Field: DB-level constraint independent of application code

## Integrations

| System / API | Direction | Trigger | Payload | Auth | Notes |
|---|---|---|---|---|---|
| HRMS-0512 Engine Assignment (S-351) | Consumer | Uses new delivery_engine field | employees.delivery_engine | Internal |  |
| All NEW-RM stories S-352 to S-378 | Consumers | Use new fields | employees table | Internal |  |

## Data Mapping

| Source Field | Source Table | Target Field | Target Table | Notes |
|---|---|---|---|---|
| employees (existing) | employees | delivery_engine=SPECIALITY (backfill) | employees | All existing employees backfilled on migration |

## Acceptance Criteria

- AC-1: Migration adds all 12 new fields to employees table without downtime

- AC-2: All existing employees backfilled to SPECIALITY with buddy_program_status=GRADUATED

- AC-3: DB CHECK constraint prevents CORE without core_certified=TRUE

- AC-4: employee_engine_history seeded with one record per employee

- AC-5: Migration fully transactional — tested on staging before production

- AC-6: Rollback tested: if migration fails mid-run, zero rows committed

## Test Cases

| TC | AC Ref | Test Name | Steps | Expected Result | Notes |
|---|---|---|---|---|---|
| TC-001 | AC-3 | DB constraint | Direct SQL: UPDATE employees SET delivery_engine='CORE' WHERE core_certified=FALSE. | PostgreSQL CHECK constraint violation. Zero rows updated. |  |
| TC-002 | AC-4 | History seeded | After migration. Count employee_engine_history. | One row per employee. to_engine='SPECIALITY'. reason='Initial migration'. |  |

## Not In Scope

- Do NOT build a UI for this migration — DBA runs migration script

- Do NOT build automated migration scheduling — manual DBA execution with sign-off
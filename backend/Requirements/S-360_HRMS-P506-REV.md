# S-360 — HRMS-P506-REV: HTD Training Module Tracker — 4-Phase Gate Structure (REVISED)

| Field | Value |
|---|---|
| Epic | PATCHES — Revised Existing Documents |
| Sprint / Week | Sprint 23 \| W7 |
| Priority | P0 — Critical |
| Owner / Assignee | Riya / Backend |
| Estimate | 2 days |
| Status | UPDATE — Revise Existing Doc |
| Depends On | HRMS-P506 original. HRMS-0515 Performance Store. HRMS-0513 Core Eligibility Gate. |
| Blocks | HRMS-0359 HTD Intake Pause Engine depends on gate outcomes. |

## Why — Business Rationale

- The original HTD training tracker (HRMS-P506) treated training as a single continuous block with a pass/fail at the end. The BU Head architecture requires four explicit phases with a distinct gate at each transition. A candidate who fails the Phase 2 gate (Shadow Delivery — Technical Manager sign-off) must not quietly continue into Phase 3. Each gate must be logged, signed off by the right person, and visible in the performance intelligence store.

## What — Scope

- AMEND HRMS-P506: Add 4-phase gate structure. Induction (0-30d), Shadow Delivery (30-60d), Controlled Ownership (60-90d), Core Eligibility Review (90-120d). Each phase has a defined gate owner and sign-off requirement. Gate failure = documented exit or clock restart with BU Head decision. No quiet graduation.

## Before — Prerequisites

- HRMS-P506 original deployed. HRMS-0515 performance store live. HRMS-0513 Core Eligibility Gate built.

## Implementation Steps

## Step 1: Add htd_phase and phase gate tables

- ALTER TABLE employees ADD COLUMN htd_phase ENUM('INDUCTION','SHADOW_DELIVERY','CONTROLLED_OWNERSHIP','CORE_ELIGIBILITY_REVIEW','COMPLETED','EXITED') nullable.

- CREATE TABLE htd_phase_gates: id UUID PK, tenant_id UUID, employee_id UUID FK, phase ENUM (above), gate_owner_role ENUM('HR','TECHNICAL_MANAGER','PRACTICE_HEAD','HEMANT_BU_HEAD'), gate_owner_user_id UUID, gate_decision ENUM('PASS','FAIL','EXTEND'), gate_notes TEXT (min 50 chars), decided_at TIMESTAMP, created_at TIMESTAMP.

## Step 2: Build phase transition logic

- Phase gates: Induction→Shadow: training module completion % >= 80% in system + HR sign-off. Shadow→Controlled: Technical Manager logs PASS in htd_phase_gates. Controlled→Core Review: Practice Head logs PASS. Core Review→COMPLETED: Hemant + BU Head both log PASS.

- On FAIL at any gate: htd_phase stays at current phase. BU Head notified. Decision required: EXTEND (restart that phase, max 1 extension per phase) or EXIT (employee.status = PERFORMANCE_MANAGED).

- All gate decisions write to HRMS-0515 as CERTIFICATION_GATE events.

## Step 3: Build phase progress UI on HTD employee profile

- HTD Phase Timeline widget: 4 phases shown as progress steps. Current phase highlighted. Each completed phase shows gate owner, decision date, notes. Gate pending phases show who needs to act and SLA remaining (72h per gate).

## UI Fields

| Field Name | Input Type | Required | Validation | Placeholder / Example | Notes |
|---|---|---|---|---|---|
| HTD Phase Timeline | 4-step progress widget | N/A | N/A | [Induction ✓ Jan 1-30] → [Shadow Delivery ✓ TM: Feb 28] → [Controlled Ownership ⏳ Day 67] → [Core Review —] | Gate owner shown per step. |
| Gate Decision Form | Form per gate | Yes | Min 50 char notes | Phase: Shadow Delivery \| Gate Owner: Technical Manager \| Decision: [PASS] [FAIL] [EXTEND] \| Notes (min 50 chars): ___ | Each gate owner submits via portal. |

## Business Rules

## BR: No Quiet Graduation — Every Gate Must Be Explicitly Logged

- An HTD employee cannot advance to the next phase without an explicit htd_phase_gates PASS record from the correct gate owner. Time passing alone does not advance phases. If a gate owner does not act within 72 hours of phase end date: BU Head is alerted.

- Field: Explicit gate record required — no time-based auto-advance

## BR: Maximum One Extension Per Phase

- Each phase can be extended once if the gate owner logs EXTEND with justification. A second EXTEND attempt on the same phase is blocked — decision must be PASS or EXIT.

- Field: Max 1 extension per phase — second attempt forces PASS or EXIT

## Integrations

| System / API | Direction | Trigger | Payload | Auth | Notes |
|---|---|---|---|---|---|
| HRMS-0515 PerformanceStoreWriter | Write | On every gate decision | CERTIFICATION_GATE event | Internal |  |
| HRMS-0513 Core Eligibility Gate | Triggered by | COMPLETED status after all 4 gates | employee_id | Internal |  |

## Data Mapping

| Source Field | Source Table | Target Field | Target Table | Notes |
|---|---|---|---|---|
| htd_phase_gates.gate_decision=PASS (all 4 phases) | htd_phase_gates | employees.htd_phase=COMPLETED | employees | All 4 gates must PASS for COMPLETED |

## Acceptance Criteria

- AC-1: 4 phases with correct gate owners defined in system

- AC-2: No phase advance without explicit gate PASS logged

- AC-3: Gate failure triggers BU Head notification within 72h

- AC-4: Max 1 extension per phase enforced

- AC-5: All gate decisions written to HRMS-0515 performance store

- AC-6: COMPLETED status only set when all 4 gates passed

## Test Cases

| TC | AC Ref | Test Name | Steps | Expected Result | Notes |
|---|---|---|---|---|---|
| TC-001 | AC-2 | No auto-advance | Phase 1 end date passes without TM logging gate decision. | Employee stays in INDUCTION. BU Head alerted after 72h. |  |
| TC-002 | AC-4 | Extension limit | Phase 2 already extended once. Gate owner tries to log EXTEND again. | HTTP 400: Maximum one extension per phase reached. Decision must be PASS or EXIT. |  |

## Not In Scope

- Do NOT build automatic gate pass based on time elapsed

- Do NOT allow phase gates to be backdated
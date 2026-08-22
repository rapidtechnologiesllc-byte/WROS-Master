# S-361 — HRMS-P507-REV: HTD Training Failure Workflow — 50% Breach Trigger (REVISED)

| Field | Value |
|---|---|
| Epic | PATCHES — Revised Existing Documents |
| Sprint / Week | Sprint 23 \| W7 |
| Priority | P1 — High |
| Owner / Assignee | Riya / Backend |
| Estimate | 2 days |
| Status | UPDATE — Revise Existing Doc |
| Depends On | HRMS-P507 original. HRMS-0359 HTD Intake Pause Engine (HRMS-P511). |
| Blocks | Nothing — amendment to existing failure flow. |

## Why — Business Rationale

- The original failure workflow handled individual candidate failures. This amendment adds the systemic failure trigger: when conversion rate drops below 50% for two consecutive months, the failure workflow now calls HRMS-P511 (Intake Pause Engine) to auto-pause new intake. It also adds the quality decline signal from Specialty RM — if graduates from HTD are underperforming at Specialty clients, that signal must extend the validation phase rather than continuing to graduate substandard candidates.

## What — Scope

- AMEND HRMS-P507: Wire HRMS-P511 intake pause on conversion breach. Add quality decline signal from Specialty RM that triggers extended validation. Add Practice Head written justification requirement for any validation extension. Ensure no graduation to meet headcount targets.

## Before — Prerequisites

- HRMS-P507 original. HRMS-P511 (S-359) built and live.

## Implementation Steps

## Step 1: Wire P511 intake pause into failure workflow

- In HRMS-P507 monthly review job: after computing conversion_rate, call HRMS-P511.checkBreach(). If breach detected (2 consecutive months < 50%): P511 auto-pause fires. P507 generates audit report for BU Head with: cohort breakdown, phase-by-phase drop-off analysis, sourcing quality assessment.

## Step 2: Add quality decline signal from Specialty RM

- Weekly: RM can log quality_concern on any HTD graduate currently deployed in Specialty: POST /api/htd/quality-signal { employee_id, concern_description (min 100 chars), severity: WATCH|CONCERN|CRITICAL }.

- On CRITICAL signal: auto-extend current HTD cohort validation phase by 30 days. Notify Practice Head and Hemant. Do NOT graduate next cohort member until concern resolved.

- Pattern: 3+ WATCH signals on graduates from same intake cohort = systemic signal. Auto-flag cohort for Hemant review.

## Step 3: Enforce no-graduation-to-meet-headcount rule

- Add system check on Core Eligibility Review gate (Phase 4): if htd_monthly_metrics shows current month conversion_rate < 50%: require Hemant + Director dual sign-off for any PASS decision (instead of Hemant alone). This prevents pressure to graduate to hit numbers during a bad month.

## UI Fields

| Field Name | Input Type | Required | Validation | Placeholder / Example | Notes |
|---|---|---|---|---|---|
| Quality Decline Signal Form | RM form | Yes | Min 100 chars, severity required | Employee \| Concern (min 100 chars): ___ \| Severity: [WATCH] [CONCERN] [CRITICAL] \| [Log Signal] | Specialty RM logs when HTD graduate underperforms. |
| Cohort Quality Heatmap | Visual on HTD Dashboard | N/A | N/A | Jan Cohort: 3 graduates \| 2 green, 1 WATCH signal at PwC \| Feb Cohort: 2 graduates \| 1 CONCERN signal | Pattern detection across cohorts. |

## Business Rules

## BR: CRITICAL Quality Signal Extends Next Cohort Validation — Not Current Employee

- When a CRITICAL quality signal is logged on an HTD graduate, it does not change that employee's status (they are already deployed). It extends the validation phase for the next cohort member awaiting graduation, ensuring the programme quality gate is tightened before more graduates are released.

- Field: CRITICAL signal → extend next cohort validation phase 30 days

## BR: Below-50% Month Requires Dual Sign-Off for Any Phase 4 PASS

- During any month where conversion_rate < 50%: Phase 4 (Core Eligibility Review) gate requires both Hemant AND Director sign-off for a PASS decision. Single Hemant sign-off insufficient. This prevents graduation pressure overriding quality standards.

- Field: Dual sign-off required when conversion < 50%

## Integrations

| System / API | Direction | Trigger | Payload | Auth | Notes |
|---|---|---|---|---|---|
| HRMS-P511 Intake Pause Engine | Called by | Conversion breach detection | conversion_rate | Internal |  |
| HRMS-0515 PerformanceStoreWriter | Write | Quality signals | employee_id + CERTIFICATION_GATE event | Internal |  |

## Data Mapping

| Source Field | Source Table | Target Field | Target Table | Notes |
|---|---|---|---|---|
| quality_concern.severity=CRITICAL | quality_concerns | htd_phase_gates extension | Next cohort member | 30-day validation extension |

## Acceptance Criteria

- AC-1: P511 intake pause triggered when conversion < 50% for 2 months

- AC-2: Specialty RM quality signal form available for HTD graduates

- AC-3: CRITICAL signal extends next cohort validation 30 days

- AC-4: 3+ WATCH signals on same cohort = Hemant review flag

- AC-5: Below-50% month requires Hemant + Director dual Phase 4 sign-off

## Test Cases

| TC | AC Ref | Test Name | Steps | Expected Result | Notes |
|---|---|---|---|---|---|
| TC-001 | AC-1 | P511 wire | Month 1: 43%, Month 2: 38%. Check intake status. | HRMS-P511 auto-pause triggered. HTD intake blocked. |  |
| TC-002 | AC-4 | Dual sign-off | Conversion rate this month = 42%. Phase 4 gate attempt. | System requires both Hemant and Director sign-off. Single sign-off rejected. |  |

## Not In Scope

- Do NOT build automatic cohort graduation — always requires human gate sign-off

- Do NOT build quality signal visible to the employee being assessed
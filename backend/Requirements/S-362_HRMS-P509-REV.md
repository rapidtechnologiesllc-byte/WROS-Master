# S-362 — HRMS-P509-REV: HTD Pipeline Dashboard — Conversion Rate Metrics (REVISED)

| Field | Value |
|---|---|
| Epic | PATCHES — Revised Existing Documents |
| Sprint / Week | Sprint 23 \| W7 |
| Priority | P1 — High |
| Owner / Assignee | Riya / Backend + Frontend |
| Estimate | 2 days |
| Status | UPDATE — Revise Existing Doc |
| Depends On | HRMS-P509 original. HRMS-P511 (S-359). HRMS-1201 Analytics Warehouse. |
| Blocks | Nothing — amendment to existing dashboard. |

## Why — Business Rationale

- The original HTD Pipeline Dashboard showed who was in training and what phase they were at. This amendment adds the conversion rate intelligence: monthly conversion trend chart, the 50% vs 75% target line, Hemant's accountability visibility, intake pause status, per-cohort time-to-Core-ready, and an alert system that fires before a breach happens rather than after. The BU Head and Hemant must be able to see the trajectory getting worse before it hits the 50% floor.

## What — Scope

- AMEND HRMS-P509: Add monthly conversion rate trend chart (6 months trailing), 50% floor and 75% target reference lines, Hemant accountability indicator, HRMS-P511 intake pause status banner, per-cohort time-to-Core-ready breakdown, phase gate completion rates, and AMBER alert when conversion approaching 50% (60% threshold).

## Before — Prerequisites

- HRMS-P509 original. HRMS-P511 (S-359) live. HRMS-1201 analytics warehouse feeding htd_monthly_metrics.

## Implementation Steps

## Step 1: Add conversion rate trend chart

- New chart on HTD Dashboard: line chart of monthly conversion_rate for trailing 6 months. Reference lines: 50% (red floor — DO NOT BREACH) and 75% (green target). Data from htd_monthly_metrics.

- AMBER alert badge: when conversion_rate < 60% for current month (approaching floor). 'Conversion rate at 58% — approaching 50% minimum threshold. Review sourcing quality.'

## Step 2: Add Hemant accountability widget

- Dashboard header: 'HTD Pipeline — Accountability: Hemant [user name]'. Shows Hemant's last checkpoint sign-off date per active cohort. Overdue checkpoints highlighted: 'Checkpoint overdue: [employee] Day 90 — Hemant sign-off pending [N] days.'

## Step 3: Add intake pause status banner and per-cohort breakdown

- If htd_intake_paused=TRUE: full-width red banner at top of dashboard: 'HTD INTAKE PAUSED — Conversion rate below 50% for 2 consecutive months. [View Audit] [Re-enable — BU Head Only]'

- Per-cohort table: intake month, cohort size, phase breakdown (how many at each phase), graduates, conversion rate, avg days to Core-ready, quality signals count.

## UI Fields

| Field Name | Input Type | Required | Validation | Placeholder / Example | Notes |
|---|---|---|---|---|---|
| Conversion Rate Trend Chart | Line chart | N/A | N/A | 6-month line \| Aug:65% \| Sep:60% \| Oct:58%⚠ \| Nov:52%⚠ \| Dec:48%🔴 \| Jan:42%🔴 \| Floor: 50% \| Target: 75% | AMBER when < 60%. RED when < 50%. |
| Intake Pause Banner | Full-width red banner | N/A | N/A | 🔴 HTD INTAKE PAUSED — Conversion below 50% for 2 months (Dec:48%, Jan:42%). [View Audit Report] [Re-enable Intake — BU Head Only] | Always at top when paused. |
| Per-Cohort Table | Table | N/A | N/A | Jan 2025 \| 5 intake \| Induction:0, Shadow:1, Controlled:2, Review:1, Complete:1 \| Conversion:20% \| Avg 118d \| 1 quality signal | Drill-down per cohort. |

## Business Rules

## BR: AMBER Alert at 60% — One Month Before Hard Floor

- Dashboard fires AMBER alert when conversion_rate < 60% for the current month. This gives the BU Head and Hemant one month of warning before the 50% breach that triggers auto-pause. Proactive alert, not reactive.

- Field: AMBER at < 60% — one cycle warning before P511 fires

## BR: Intake Pause Banner Cannot Be Dismissed — Visible Until Re-Enabled

- When HRMS-P511 has set htd_intake_paused=TRUE: the red banner on this dashboard cannot be closed or minimised. It remains visible on every HTD Dashboard page load until BU Head explicitly re-enables intake via HRMS-P511 with documented audit.

- Field: Pause banner permanent until P511 re-enable — no dismiss button

## Integrations

| System / API | Direction | Trigger | Payload | Auth | Notes |
|---|---|---|---|---|---|
| HRMS-P511 Intake Pause Engine | Reader | Pause status for banner | htd_intake_paused flag | Internal |  |
| htd_monthly_metrics | Reader | Conversion rate trend data | bu_id + month range | Internal |  |
| HRMS-1201 Analytics Warehouse | Reader | Cohort analytics | htd cohort data | Internal |  |

## Data Mapping

| Source Field | Source Table | Target Field | Target Table | Notes |
|---|---|---|---|---|
| htd_monthly_metrics.conversion_rate by month | htd_monthly_metrics | Trend chart data points | Dashboard chart | 6-month trailing window |

## Acceptance Criteria

- AC-1: Conversion rate trend chart shows 6-month trailing data

- AC-2: 50% floor and 75% target reference lines shown

- AC-3: AMBER alert fires when rate < 60%

- AC-4: Intake pause banner shows when P511 paused — cannot be dismissed

- AC-5: Hemant checkpoint overdue indicator shown

- AC-6: Per-cohort breakdown shows phase distribution and quality signals

## Test Cases

| TC | AC Ref | Test Name | Steps | Expected Result | Notes |
|---|---|---|---|---|---|
| TC-001 | AC-3 | AMBER alert | Current month conversion = 57%. | AMBER alert badge shown: 'Approaching 50% minimum threshold.' |  |
| TC-002 | AC-4 | Pause banner permanent | htd_intake_paused=TRUE. User tries to close banner. | No dismiss/close option. Banner persists. |  |

## Not In Scope

- Do NOT build public HTD dashboard — internal BU Head and Hemant only

- Do NOT build conversion rate targets adjustable by recruiter — BU Head sets targets
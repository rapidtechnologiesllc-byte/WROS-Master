# Backlog Verification: Cluster 6 — EPIC-14 / EPIC-15 / EPIC-16 / DESIRE

Verified directly against code on 2026-08-06. Backend repo:
`OnboardingModule-Backend`. Frontend repo: `OnboardingModule-Frontend-main`.
Sheet "Status" column and prior summary claims were **not** trusted — every
row below was checked against real source files.

## Summary counts

- CONFIRMED-DONE: 5 (S-389, S-392, S-347, S-348, S-349)
- PARTIAL: 11 (S-379, S-387, S-388, S-390, S-391, S-393, S-397, S-398, S-399, S-346, S-350)
- NOT-DONE: 12 (S-380, S-381, S-382, S-383, S-384, S-385, S-386, S-394, S-395, S-396, S-400, S-401)
- CANT-DETERMINE: 0

Headline corrections vs the "EPIC-16 fully built" assumption: **S-394 (RM
Burden Allocation) and S-395 (Minimum Bill Rate) have zero implementation
anywhere in the codebase** — not partial, not stubbed, simply absent. **S-396
(BXIN/BXUS Separate P&L) is explicitly documented as NOT built** inside
`pnl_service.py`'s own docstring (a different-dimension BU P&L exists
instead). **S-400 (Executive Finance Dashboard)** — no 7-block CEO dashboard
exists at all, only a P&L-only org rollup. Of the 15 EPIC-16 stories, only
**S-391 (Bank Reconciliation) has zero frontend UI** — it is missing from
`FinanceOperationsScreen.js` entirely, unlike every other built EPIC-16
engine, which all get a panel there.

## EPIC-14 — Internal Collaboration Hub

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| S-379 | HRMS-1401 | M365 SSO & Embedded App Shell | Ready for Build | **PARTIAL** | `app/api/v1/endpoints/msgraph.py:64-120` (signin/link/link-status/unlink), `app/core/graph_auth.py`, frontend `src/pages/AuthPage.js`, `src/services/api/msgraph.js:1-45` | SSO/account-linking is real and wired end-to-end (this is the piece already confirmed built+pushed 2026-08-05 as "S-379 email linking"). But the story's actual ask — a generic "embedded tab/dock framework" shell that S-380/S-381 would render inside — does not exist. No `Launchpad` component, no tab-shell UI anywhere in the frontend (`grep -rli launchpad src` = 0 hits). |
| S-380 | HRMS-1402 | Embedded Outlook Mail & Calendar Tab | Ready for Build | **NOT-DONE** | `app/api/v1/endpoints/msgraph.py:338-460` (calendar schedule/list), `app/services/msgraph_mail_sync_service.py` | What exists is (a) calendar meeting scheduling reused for Interview Scheduling (pre-existing feature, not an embedded Outlook tab) and (b) one-way mail sync for candidate/employee linking (S-435). Neither is an embedded Mail/Calendar tab rendered inside WROS with deep-linking. No such screen/component found in frontend. |
| S-381 | HRMS-1403 | Teams Chat Dock & Notification Center | Ready for Build | **NOT-DONE** | n/a | No Teams chat dock, no unified notification center found in backend or frontend. Consistent with memory note that S-381 was explicitly deferred by Avinash. |
| S-382 | HRMS-1404 | Dynamic Reporting Hierarchy Engine | Ready for Build | **NOT-DONE** | `app/services/task_assignment_service.py:45-51`, `app/services/timesheet_nag_service.py:106-107` | `reporting_manager_user_id` is only ever read one hop up (direct manager lookup) in two unrelated services. No chain-walk, no configurable org-level list anywhere in the codebase. |
| S-383 | HRMS-1405 | Check-In Cadence Config by Org Level | Ready for Build | **NOT-DONE** | n/a | Zero hits for org_level/cadence/"BU Head quarterly"/"Principal Architect" anywhere in `app/`. |
| S-384 | HRMS-1406 | Auto-Scheduler & Booking Agent | Ready for Build | **NOT-DONE** | n/a | Zero hits for auto-scheduler/booking-agent/recurring-check-in logic. Depends on S-382/S-383/S-380, none of which exist. |

## EPIC-15 — Interview Integrity Layer

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S-385 | HRMS-1501 | Interview Integrity Analysis Engine | Ready for Build | **NOT-DONE** | n/a | Zero hits for rehearsed-answer/outside-assistance/identity-mismatch/interview_integrity anywhere in `app/`. No recording/transcript analysis service exists. |
| S-386 | HRMS-1502 | Panel Feedback Cross-Validation & Clarification Routing | Ready for Build | **NOT-DONE** | n/a | Depends on S-385, which doesn't exist. No cross-validation logic found. |

Both EPIC-15 stories are entirely unbuilt — sheet's "0/2" status is accurate here, unlike most of this cluster.

## EPIC-16 — Finance & Accounting Operations

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| S-387 | HRMS-1601 | Timesheet Submission Nag Agent | Ready for Build | **PARTIAL** | `app/services/timesheet_nag_service.py:42-118` (2-level cascade), scheduler registration `app/core/scheduler.py:798-816` | Real, tested, and scheduled (registered as part of the 2026-08-06 "built but never wired" fix, alongside S-390). But it's a 2-step cascade (employee → reporting manager only), not the story's 7-step RM → RM's-manager → BU-Head chain, and WhatsApp isn't provisioned (`notification_service.py:66` `_send_whatsapp_unconfigured` raises `ChannelNotConfigured`, silently swallowed) — Teams isn't a channel option either. No frontend UI needed (background job). |
| S-388 | HRMS-1602 | Monthly Invoice Generation Cycle (2nd-of-Month) | Ready for Build | **PARTIAL** | `app/services/invoice_service.py:46` `generate_invoice()`, frontend `src/screens/InvoicesScreen.js` | Invoice generation itself is real (pre-existing S-226 logic) and has a working manual-trigger UI. But there is no scheduled job anywhere in `app/core/scheduler.py` for a 2nd-of-month automatic cycle — `grep "generate_invoice"` in scheduler.py returns nothing. It's manual-only, not the "scheduled trigger" the story specifies. |
| S-389 | HRMS-1603 | Manual Invoice Mark-as-Paid | Ready for Build | **CONFIRMED-DONE** | `app/services/invoice_service.py:116-120` `mark_invoice_paid()`, frontend `src/screens/InvoicesScreen.js:137-138` "Mark Paid" button | Real Sent→Paid transition, captures `paid_at`. Frontend button wired and working. |
| S-390 | HRMS-1604 | Accounts Receivable Follow-Up Agent | Ready for Build | **PARTIAL** | `app/services/ar_followup_service.py:25-114`, scheduler registration `app/core/scheduler.py:827-845` | Real aging scan + idempotent Task-creation, registered in scheduler as of a 2026-08-06 fix (its own docstring at line 98 admits it was "fully tested but never actually registered" until now). But it's a single 30-day grace-period threshold, not the 15/30/45-day escalating tiers the story specifies, and messages are plain Task/notification text, not "LLM-drafted client messages queued for account-manager review" — no LLM drafting, no review queue UI found in frontend. |
| S-391 | HRMS-1605 | Bank Statement Reconciliation (Manual Upload) | Ready for Build | **PARTIAL — no frontend** | `app/services/bank_reconciliation_service.py:15-67`, endpoints in `app/api/v1/endpoints/cost_rate.py:189-232` | Real backend: manual transaction entry, exact-amount deterministic matching (`match_transaction_to_invoice` rejects non-exact amounts), unreconciled/unmatched-paid-invoice views. Two real gaps: (1) no PDF/Excel upload + LLM extraction — pure manual numeric entry only (the only "bank statement upload" endpoint found, `documents.py:206`, is an unrelated candidate-onboarding document upload, not Finance's reconciliation flow); (2) **`src/screens/FinanceOperationsScreen.js` has zero UI for this engine** — every other EPIC-16 engine (Cost/P&L, Reserve Fund, Hiring Affordability, Intercompany, Partner Incentives) gets a panel there; bank reconciliation does not. Confirmed via full read of that file. |
| S-392 | HRMS-1607(dup)/1606 | Intercompany Settlement Ledger (BXIN/BXUS) | Ready for Build | **CONFIRMED-DONE** | `app/services/intercompany_ledger_service.py:14-51`, frontend `src/screens/FinanceOperationsScreen.js:283-303` | Manual entry only, net-position reference calc, matches spec. Frontend panel present and wired ("Intercompany Settlement" section). |
| S-393 | HRMS-1608 | Fully Loaded Cost Calculation Engine | Ready for Build | **PARTIAL** | `app/services/cost_rate_service.py:61-72`, `app/models/cost_rate_config.py:1-16`, frontend `FinanceOperationsScreen.js:250-257` | Real, working, config-driven FLC calc (base salary + statutory% + overhead%) with a UI panel. But it deliberately does **not** implement the story's specific ask: "India and US locked formulas exactly, ESI cap logic, 4 placeholder constants visibly flagged." The model's own docstring (`cost_rate_config.py:12-15`) states percentages are "Avinash's to configure, never invented here" — a simpler, different design than the locked-formula spec. |
| S-394 | HRMS-1609 | RM Burden Allocation Engine | Ready for Build | **NOT-DONE** | n/a | `grep -rliE "burden" app/ --include=*.py` returns zero files. No RM overhead allocation logic exists anywhere. |
| S-395 | HRMS-1610 | Minimum Bill Rate Engine | Ready for Build | **NOT-DONE** | n/a | No `minimum_bill_rate`/`min_bill_rate` logic anywhere. The only "bill_rate" hits in the codebase (`demand.py`, `candidate_context_service.py`, `opportunity_service.py`) are unrelated recruiting bill-rate fields, not the (FLC + RM Burden) × multiplier formula the story specifies. |
| S-396 | HRMS-1607 | BXIN/BXUS Separate P&L Engine | Ready for Build | **NOT-DONE** | `app/services/pnl_service.py:1-11` (module docstring) | Explicitly self-documented as not built: *"Location P&L is NOT built: no field anywhere on Employee identifies which legal entity (India vs US) an employee sits in... Building Location P&L against either would be a guess dressed up as data."* What IS built (`get_bu_pnl`) is a **BU P&L** (Axion vs Prism), a different dimension entirely from the legal-entity split S-396 requires. |
| S-397 | HRMS-1612 | Reserve Fund Engine | Ready for Build | **PARTIAL** | `app/services/reserve_fund_service.py:22-87`, frontend panel `FinanceOperationsScreen.js:259-266` | Real ledger with a computed target (12x trailing-average monthly BU cost) and a UI panel. But the story's specific auto-calc — "25% of EBITDA if positive, drawdown if negative" — does not exist: `grep -rniE "EBITDA" app/` returns zero hits anywhere in the codebase. Contributions/withdrawals are pure manual entries, and no seeded provisional starting balances were found. |
| S-398 | HRMS-1613 | Hiring Affordability Gate Engine | Ready for Build | **PARTIAL** | `app/services/hiring_affordability_service.py:21,24-59` | Real single-gate margin check (projected gross margin must stay ≥ `MIN_ACCEPTABLE_MARGIN_PCT = 0.0`, line 21) with a working UI panel. But the story requires **two hard gates** (Reserve check + Run-rate check), both required. This function never calls `reserve_fund_service` — only one of the two specified gates exists. |
| S-399 | HRMS-1611 | Partner Incentive Calculator | Ready for Build | **PARTIAL** | `app/services/partner_incentive_service.py:54-119` (new-logo), `:140-206` (revenue share), frontend `FinanceOperationsScreen.js:305-326` | Real, idempotent, well-tested (race-condition-safe via unique constraint) new-logo bonus + revenue-share calculation with a working UI panel — the strongest EPIC-16 implementation. One real deviation: story specifies "Paid-invoices-only trigger"; `check_new_logo_incentive` (line 83) actually fires on invoice status in `(APPROVED, SENT, PAID)`, not strictly PAID — eligibility can trigger before the invoice is actually paid. |
| S-400 | HRMS-1614 | Executive Finance Dashboard | Ready for Build | **NOT-DONE** | `app/api/v1/endpoints/cost_rate.py:107` `org_pnl_summary` | Only a P&L-only org rollup exists (revenue/cost/margin summed across BUs). No 7-block dashboard combining all 5 engines (Cost/P&L, Reserve Fund, Hiring Affordability, Intercompany, Partner Incentive) with a "shared color-coding function" — no such endpoint or screen found (`grep -rliE "7.block|color.coding|cfo_dashboard"` = 0 hits). `FinanceOperationsScreen.js` is the closest analog but it's a BU-scoped input/operations tool, not an aggregated read-only exec view, and doesn't even surface Partner Incentives at the org level. |
| S-401 | HRMS-1615 | GST & Statutory Compliance | BLOCKED — Awaiting Finance/CA Review | **NOT-DONE** | n/a | Zero gst/statutory/compliance files anywhere. This is the one EPIC-16 row where sheet status and real status actually agree (correctly blocked/not built). |

## DESIRE — Desire Intelligence System

Per instructions, spent light effort here (S-347/348/349 were confirmed real
in a prior session pass); S-350 turned up a real, code-verified correction.

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S-346 | HRMS-P116 | Portal Real-Time Chat Widget | NEW — Ready for Build | **PARTIAL (confirmed, still holds)** | Backend: `app/services/portal_message_service.py:233` (long-polling fallback, added since the prior pass — docstring: *"S-346 Step 2 (long-polling fallback)"*). Frontend: `src/screens/CandidatePortalScreen.js` (single `getPortalMessages` call, `src/services/api/candidatePortal.js:41`, no `setInterval`/poll loop found) | Backend polling support now exists (an improvement since the last check), but the frontend chat widget still never calls it repeatedly — one fetch on load, no real-time updates. Gap confirmed to still exist, just narrower than before (backend side is now ready; only the frontend wiring is missing). |
| S-347 | HRMS-P117 | Candidate Desire Intelligence Engine | NEW — Ready for Build | **CONFIRMED-DONE** | `app/services/desire_signal_service.py` (248 lines) | Real signal-analysis logic, matches prior finding. |
| S-348 | HRMS-P118 | Desire Profile Builder | NEW — Ready for Build | **CONFIRMED-DONE** | `app/services/desire_profile_service.py` (353 lines) | Real persistent/versioned profile builder with LLM narrative summarization, matches prior finding. |
| S-349 | HRMS-P119 | Proactive Motivation Engine | NEW — Ready for Build | **CONFIRMED-DONE** | `app/services/motivation_engine_service.py:120` `detect_trigger()`, `:276` `run_motivation_job()` | Real threshold-based trigger detection + LLM-generated engagement message + scheduled job, matches prior finding. |
| S-350 | HRMS-P120 | HR Intelligence Briefing | NEW — Ready for Build | **PARTIAL (correction to prior "confirmed real" claim)** | `app/api/v1/endpoints/desire_intelligence.py:1-109` | What's actually built is a real **on-demand, per-candidate** desire-intelligence view (`GET /candidates/{id}/desire-intelligence` + refresh endpoint, gated behind `candidate.view`), visible on the candidate detail screen. The story's actual spec — a **daily 08:00 digest per recruiter** summarizing their whole assigned candidate list, delivered via portal notification + email, stored in an `hr_intelligence_briefings` table — is **not built**: that table doesn't exist anywhere (`grep -rli hr_intelligence_briefing app/` = 0 hits), and the codebase's one real 8am daily-digest job (`app/services/daily_digest_service.py`, S-065/HRMS-0465, a different pre-existing story) has zero desire/motivation-score integration (`grep desire_score/motivation_gap` in that file = 0 hits). A real, useful, adjacent feature was built instead of the literal spec. |

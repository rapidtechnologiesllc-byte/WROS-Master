# Cluster 3 Verification: EPIC-04-ONB — Onboarding Portal (onboarding.blitzenx.com)

**Verified:** 2026-08-06
**Repos checked:** OnboardingModule-Backend, OnboardingModule-Frontend-main
**Sheet claim:** 32 stories, 0% Done ("Planned")

## Headline finding

The sheet's 0% claim is **essentially correct**. There is no distinct Onboarding Portal —
no separate subdomain/app entry point, no post-offer step-by-step new-hire journey UI,
and no backend route namespace for it. `AppRoutes.jsx` has exactly two unauthenticated
entry points: `/careers-chat` (public Thunder chat for external job-seekers) and
`/candidate/:token` (the **Candidate Self-Service Web Portal**, S-017/HRMS-0417 — a
pre-hire recruiting-pipeline portal for messages/profile/interviews). Neither is the
new-hire pre-boarding journey this epic describes.

Two things this codebase DOES have, which are easy to mistake for this epic if skimmed
quickly, and which the task brief flagged as a risk:
1. **S-067 Onboarding Agent** (`onboarding_agent_service.py`, `preboarding_touchpoint.py`) —
   automated D-7/D-3/D-1/D+1 WhatsApp/Email messages. This is one-way outbound messaging,
   not an interactive portal the new hire logs into and steps through.
2. **Buddy Program** (`buddy_program.py`, `BuddyProgramScreen.js`) — a 30-day *post-join*
   KPI tracking system for already-converted employees. Real and built, but it is not a
   pre-boarding portal step.

Also relevant: `app/api/v1/endpoints/onboarding.py` is misleadingly named — despite the
`/onboarding` URL prefix, every route in it is HR-side **Candidate CRUD** (create/list/
update/delete candidate records). It has nothing to do with a new-hire-facing portal.

The one genuinely reusable, logged-in-candidate-facing screen is `CandidateSelfService.js`
(+ `candidate_status.py`/`checklists.py`/`documents.py`/`offer_letters.py` backends), used
by internal "CANDIDATE"-role accounts. It has real personal-info/PAN/Aadhar forms, document
upload (incl. bank statement, UAN/PF), offer-letter e-signature (`SignatureModal.js`), and
a generic HR-configurable todo/queue checklist engine. None of it is organized as the 32-step
sequential journey these stories specify, and it does not implement the story-specific fields/
flows (IFSC routing number, background-verification consent, policy scroll+acknowledge,
org chart, benefits enrollment, IT equipment request, etc.) — but it is the closest
adjacent, reusable infrastructure for a handful of steps, called out per-row below.

## Story-by-story

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| S-402 | HRMS-ONB-001 | Welcome Note (Step 1) | Planned | NOT-DONE | — | No welcome-screen component/route found anywhere in frontend. No portal to host it. |
| S-403 | HRMS-ONB-002 | Email Access Validation (Step 2) | Planned | NOT-DONE | — | No mailbox-validation flow found (msgraph.py / msgraph_mail_sync_service.py sync mail for EPIC-14 linking, not new-hire email verification). |
| S-404 | HRMS-ONB-003 | Induction / company overview (Step 3) | Planned | NOT-DONE | — | No induction video/deck content or screen found. |
| S-405 | HRMS-ONB-004 | Emergency Information (Step 4) | Planned | NOT-DONE | `app/models/employee.py:110-111` | `emergency_contact_name`/`emergency_contact_phone` columns exist on `Employee`, but no medical-info field and no onboarding-portal capture UI writes to them — they're plain HR-editable employee fields, not a new-hire self-serve step. |
| S-406 | HRMS-ONB-005 | Personal Interests (Step 5) | Planned | NOT-DONE | — | No hobbies/interests field anywhere in `Candidate`/`Employee` models or forms. |
| S-407 | HRMS-ONB-006 | Personal & Emergency Contact Details Form → Employee record (Step 6) | Planned | PARTIAL | `src/screens/CandidateSelfService.js:24-41`, `app/models/candidate.py` (CandidateInfoForm: current_address/permanent_address/marital_status/nationality) | Candidate-side self-service already captures overlapping fields (address, DOB, marital status) via `submitCandidateInfoForm`, but this is pre-hire candidate data, not a distinct onboarding-portal step that writes into the Employee record post-offer as the story specifies. |
| S-408 | HRMS-ONB-007 | Bank Account / Payroll Setup (IFSC, PAN) (Step 7) | Planned | PARTIAL | `src/screens/CandidateSelfService.js:52-55` (`uploadBankStatement`, `uploadUanPfDocument`), `app/models/candidate.py` (`CandidatePanForm`) | Document *upload* for bank statement/UAN-PF and a PAN form exist, but there is no structured bank-account-number/IFSC/routing-number field capture anywhere — only file uploads, not the payroll-setup data entry the story describes. |
| S-409 | HRMS-ONB-008 | Government ID & Tax Documents Upload (virus scan + SharePoint) (Step 8) | Planned | PARTIAL | `app/services/virus_scan_service.py`, `app/services/sharepoint_service.py`, `app/models/candidate.py` (CandidateAadharForm) | The reusable pipeline (virus scan + SharePoint storage) is real and already used for candidate documents, exactly as the story assumes — but it's used for the recruiting-pipeline candidate, not wired into any post-offer onboarding-portal step. |
| S-410 | HRMS-ONB-009 | Offer Letter Digital Acknowledgement (Step 9) | Planned | PARTIAL | `src/screens/CandidateSelfService.js:43-46` (`respondToOffer`, `signOfferLetter`), `app/api/v1/endpoints/offer_letters.py`, `app/models/offer_letter.py` | Real offer accept/sign flow exists in the recruiting-stage candidate self-service screen — closest real match of any story in this epic — but it's part of the offer-response step in the hiring pipeline, not a distinct "Onboarding Portal Step 9" re-confirmation screen. |
| S-411 | HRMS-ONB-010 | Employment Agreement E-Signature (reuses SignatureModal.js) (Step 10) | Planned | PARTIAL | `src/components/ui/SignatureModal.js` | The component is real and reusable exactly as the story assumes, but it is currently wired only to offer-letter signing, not to a full employment-contract flow. |
| S-412 | HRMS-ONB-011 | Company Policies Acknowledgement (Step 11) | Planned | NOT-DONE | — | No policy content, scroll-to-bottom gate, or per-policy timestamped acknowledgement found. The generic checklist engine (`checklists.py`) could theoretically hold a "todo" item titled after a policy, but no such template/content exists and it wouldn't implement scroll-gating or per-policy storage. |
| S-413 | HRMS-ONB-012 | NDA / Confidentiality E-Signature (Step 12) | Planned | NOT-DONE | `CHECKLIST_README.md:387` | "Sign NDA" appears only as a documentation *example* checklist-item title, not a real seeded template, content, or e-signature flow. |
| S-414 | HRMS-ONB-013 | Background Verification Consent (via ConsentRecord, subject_type='employee') (Step 13) | Planned | NOT-DONE | `app/models/consent.py`, `app/core/consent.py` | `ConsentRecord` model and `has_consent`/helper functions exist and are generic enough to support this, but grep across the whole backend shows **zero production callers** of `app.core.consent` — only `tests/test_consent.py` exercises it. No employee-facing consent capture exists at all. |
| S-415 | HRMS-ONB-014 | IT Equipment Request (Step 14) | Planned | NOT-DONE | `app/models/ticket.py` | Generic Help Desk/IT-HR ticketing exists with admin-configurable Category/Subcategory routing (built 2026-08-04 per prior session), which *could* be configured for equipment requests, but no "IT Equipment Request" record type, laptop/accessory preference capture, or onboarding-portal trigger exists today. |
| S-416 | HRMS-ONB-015 | SharePoint Access Walkthrough (Step 15) | Planned | NOT-DONE | `app/services/sharepoint_service.py` | SharePoint integration exists for document storage/retrieval, but there is no walkthrough/tutorial content or screen. |
| S-417 | HRMS-ONB-016 | Email & Calendar Setup Walkthrough (Step 16) | Planned | NOT-DONE | — | No Outlook/Teams orientation content found. |
| S-418 | HRMS-ONB-017 | Org Chart & Company Structure Overview (Step 17) | Planned | NOT-DONE | — | No org-chart visualization screen/component found anywhere in the frontend. |
| S-419 | HRMS-ONB-018 | Meet the Leadership (Step 18) | Planned | NOT-DONE | — | No leadership welcome video/message content or screen. |
| S-420 | HRMS-ONB-019 | Company Culture & Values (Step 19) | Planned | NOT-DONE | `app/services/culture_agent_service.py` | This service is the internal Executive Signal & Culture Agent (CEO-facing quarterly cycle / concern triage, built 2026-08-04) — an unrelated system, not a new-hire-facing culture deck/video. Flagging explicitly so it isn't mistaken for coverage of this story. |
| S-421 | HRMS-ONB-020 | Benefits Enrollment (Step 20) | Planned | NOT-DONE | — | No benefits/insurance/PF election model or screen found. |
| S-422 | HRMS-ONB-021 | Dress Code & Office Guidelines (Step 21) | Planned | NOT-DONE | — | No content found. |
| S-423 | HRMS-ONB-022 | First Week Schedule Preview (Step 22) | Planned | NOT-DONE | — | No Week-1 day-by-day preview screen. |
| S-424 | HRMS-ONB-023 | IT Security & Data Protection Training (Step 23) | Planned | NOT-DONE | — | No training-module content or acknowledgement flow. |
| S-425 | HRMS-ONB-024 | Workplace Conduct / POSH Training Acknowledgement (Step 24) | Planned | NOT-DONE | — | No content found. |
| S-426 | HRMS-ONB-025 | Tools & Software Access Setup checklist (Step 25) | Planned | NOT-DONE | `app/models/checklist.py`, `CHECKLIST_README.md` | The generic HR-configurable todo/queue checklist engine is real and could be pointed at this use case, but no seeded template/content for Slack/Teams/Jira access confirmation exists. |
| S-427 | HRMS-ONB-026 | Client Confidentiality Agreement (Step 26) | Planned | NOT-DONE | — | No per-assignment client-confidentiality content/e-sign flow distinct from the (also-missing) NDA step. |
| S-428 | HRMS-ONB-027 | Payroll & Timesheet System Walkthrough (Step 27) | Planned | PARTIAL | `app/models/timesheet.py`, `src/screens/MyTimesheetScreen.js` | The underlying Timesheets module the story explicitly says to reuse is real, built, and in production use (per prior session's employee self-service timesheet work) — but there is no guided "first submission" walkthrough/tutorial layer for a new hire. |
| S-429 | HRMS-ONB-028 | Photo & ID Badge Submission (Step 28) | Planned | NOT-DONE | — | No photo-upload-for-badge flow found (`document_service.py` has no photo/badge document type). |
| S-430 | HRMS-ONB-029 | Ask Thunder — Onboarding FAQ (Step 29) | Planned | NOT-DONE | `app/api/v1/endpoints/thunder.py`, `app/api/v1/endpoints/internal_ask_thunder.py`, `app/api/v1/endpoints/public_chat.py` | Thunder conversational infra (public candidate chat + internal Ask Thunder) is real and reusable exactly as the story assumes, but there is no third instance embedded for new hires, and no onboarding portal to embed it into. |
| S-431 | HRMS-ONB-030 | Day-1 Logistics Confirmation (Step 30) | Planned | PARTIAL | `app/models/preboarding_touchpoint.py` (D1 touchpoint), `app/services/onboarding_agent_service.py` | The one-time D-1 WhatsApp/Email message with this content is real (S-067). The story's own text acknowledges this — it asks for the *same* information made "persistently viewable" in a portal, which does not exist. |
| S-432 | HRMS-ONB-031 | Introduction to Reporting Manager (Step 31) | Planned | PARTIAL | `app/models/user.py` (`reporting_manager_id`/similar), `app/models/candidate.py` (`assignedReportManagerID`) | The data relationship (who is the reporting manager) is real and queryable, but no "introduce by name/photo/note" portal screen exists. |
| S-433 | HRMS-ONB-032 | Reporting Manager Introduces Buddy (Step 32) | Planned | PARTIAL | `app/models/buddy_program.py:25-42` (`BuddyProgramRecord.buddy_engineer_user_id`), `src/screens/BuddyProgramScreen.js` | Buddy assignment data and a real UI (BuddyProgramListScreen/BuddyProgramScreen) exist per S-364/S-365 (built 2026-08-04), so the dependency this story names is genuinely satisfied — but nothing surfaces that handoff inside a reporting-manager-introduction portal step, because no such portal exists. |

## Counts

- **CONFIRMED-DONE:** 0
- **PARTIAL:** 12 (S-407, S-408, S-409, S-410, S-411, S-428, S-431, S-432, S-433, plus S-409/S-410/S-411 reuse real e-sign/offer infra) — see table; all 12 are cases where a real, reusable *piece* of backend/frontend infrastructure exists (document upload, e-signature component, timesheet module, buddy program, offer acceptance) but the actual onboarding-portal *step* the story specifies is not built.
- **NOT-DONE:** 20
- **CANT-DETERMINE:** 0

## Bottom line

Unlike Finance & Accounting (falsely claimed 0/15, actually 15/15 built), this epic's 0%
claim holds up under inspection: **no distinct Onboarding Portal exists** — no subdomain,
no route namespace, no step-sequence UI, no new-hire login journey. What exists is a
constellation of *adjacent* infrastructure (candidate self-service forms, e-signature
component, document upload + virus scan + SharePoint pipeline, generic checklist engine,
Timesheets module, Buddy Program, Thunder chat, offer-letter acceptance) that a real build
of this epic would legitimately reuse — which is presumably why several of these stories'
own `DependsOn`/body text call those pieces out by name. But reusable adjacent infra is not
the same as the stories being built, and none of the 32 steps has a dedicated screen, form,
or API route today. If anything, this epic is genuinely 32 stories away from done, with a
non-trivial amount of the *dependency* work (not the portal work itself) already sitting in
the codebase.

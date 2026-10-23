# Open Requirements Backlog (S-001..S-401)

Generated 2026-10-13 from `docs/backlog-verification/*.md` (story-by-story code verification done 2026-08-22),
re-checked against current `main` by searching `backend/app` and `frontend/src` for each story ID / HRMS ID.

- **Status** = verified status on 2026-08-22 (NOT-DONE / PARTIAL).
- **Signal today** = whether code referencing the story changed after 2026-08-22. `re-verify` rows may now be done; everything else is still open as written.
- Source of truth for story text: `WROS_Canonical_Backlog_S001-401.xlsx`. Careers site stories are out of production scope (user decision 2026-10-07).

**Totals:** 166 NOT-DONE, 79 PARTIAL, 1 undetermined; 57 need re-verification.

## NEW-RM (9 stories) — sheet claims 6/9 Done

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-352 | HRMS-0513 | Core Eligibility Gate — Performance Gate Workflow | NOT-DONE | re-verify (code touched after 08-22) | No sequential two-step approval workflow exists. Its own dependencies (S-357 AI assessment, S-366 90-day cert clock) are also not built, so it structurally cannot exist yet. Sheet is accurate. |
| S-355 | HRMS-0516 | Reporting Manager Weekly Input Bot | NOT-DONE | re-verify (code touched after 08-22) | No WhatsApp-triggered weekly manager input flow exists. Sheet is accurate. |
| S-357 | HRMS-0518 | Core Eligibility AI Assessment — Agentic Bot | NOT-DONE | re-verify (code touched after 08-22) | No agentic weighted-scoring bot exists. Sheet is accurate. |

## NEW-RM-EXT (15 stories) — sheet claims 4/15 Done

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-366 | HRMS-0522 | Specialty Deployment 90-Day Certification Clock | NOT-DONE | no code references | No billable-days tracking / reset-pause clock exists. Sheet is accurate. |
| S-367 | HRMS-0523 | Escalation Classification Engine — Resource vs Environment | NOT-DONE | no code references | No such engine exists. Sheet is accurate. |
| S-368 | HRMS-0524 | Peer Trust Pulse Survey — Week 6 and Week 12 | NOT-DONE | no code references | Not built. Sheet is accurate. |
| S-369 | HRMS-0525 | Core Certification Scorecard — Full AI Assessment Output | NOT-DONE | no code references | Depends on S-357 (also not built) and S-352 (also not built) — structurally can't exist yet. Sheet is accurate. |
| S-370 | HRMS-0526 | HTD 365-Day Specialty Certification Track | NOT-DONE | no code references | Not built. Sheet is accurate. |
| S-371 | HRMS-0527 | Curtis Rule — Partner Intent ML Engine | PARTIAL | re-verify (code touched after 08-22) | `app/models/partner_intent.py:1-27` (`PartnerIntentProfile` model); `app/services/partner_intent_service.py:1-50` (`compute_partner_intent_profile()`) — both real and per the module's own docstring, tested / Genuinely re |
| S-374 | HRMS-0530 | BU Head ML Dashboard — Workforce Command Centre | NOT-DONE | no code references | Not built. Sheet is accurate. |
| S-375 | HRMS-0531 | Individual Employee Scorecard — 35 KPI Live View | NOT-DONE | no code references | Not built (distinct from the milestone/performance panel built for S-354/S-356, which is not a 5-tab scorecard). Sheet is accurate. |
| S-376 | HRMS-0532 | Predictive Demand ML Engine | NOT-DONE | no code references | Not built. Sheet is accurate. |
| S-377 | HRMS-0533 | Interviewer Quality Scoring — Client Pass Rate | NOT-DONE | no code references | Not built. Sheet is accurate. |
| S-378 | HRMS-0534 | Specialty Client Release Approval Workflow | NOT-DONE | re-verify (code touched after 08-22) | `app/services/demand_confirmation_service.py:143` references "HRMS-0534 Specialty Client Release" but only as the name for S-372's minimal notify-the-RM trigger. Requirements doc `Requirements/S-378_HRMS-0534.md` calls f |

## EPIC-01 (14 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-208 | HRMS-0110 | Audit Log Base System | PARTIAL | re-verify (code touched after 08-22) | `app/models/audit_log.py:38,43` (`before_update`/`before_delete` listeners — real, ORM-level append-only guard); `alembic/versions/a3b4c5d6e7f8_add_audit_log_table.py:50-65` (`DENY UPDATE, DELETE ON audit_log TO [onboard |
| S-209 | HRMS-0111 | Core Navigation & Search Shell | CANT-DETERMINE | re-verify (code touched after 08-22) | Avinash's 2026-08-04 explicit deferral stands; partial real shell exists per sheet's own note (search covers only candidates+jobs, not full spec). |

## EPIC-02 (10 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-242 | HRMS-0213 | Forecast vs Actual Comparison | PARTIAL | re-verify (code touched after 08-22) | `app/services/forecast_variance_service.py:1-14` (real logic pulling Invoice actuals + weighted forecast), `app/api/v1/endpoints/forecast_and_leakage.py:47-56` (`GET /forecast-vs-actual`, gated `revenue.view`, BU-scoped) |
| S-243 | HRMS-0214 | Revenue Leakage Detection | PARTIAL | re-verify (code touched after 08-22) | `app/services/pipeline_leakage_service.py` (159 lines, `scan_all_leakage`/`get_active_leakage_flags`/`resolve_leakage_flag`), `app/models/pipeline_leakage.py` (`PipelineLeakageFlag`), `app/api/v1/endpoints/forecast_and_l |

## EPIC-03 (14 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-268 | HRMS-0302 | Map Revenue to Role Demand | PARTIAL | no code references | `app/services/revenue_to_demand_service.py:61-104` `get_revenue_to_demand_projection()` (trailing revenue-per-head ratio × forward forecast → projected headcount need & gap), `app/api/v1/endpoints/revenue_to_demand.py`;  |
| S-269 | HRMS-0303 | Generate Demand Plan from Revenue Target | NOT-DONE | no code references | No code that auto-creates `Demand` rows with role mix/headcount/timing/continent sourcing plan from a BU target. `revenue_to_demand_service.py` (S-268) produces a projection number only, never writes a Demand row. |
| S-270 | HRMS-0304 | Forecast 30/60/90 Day Hiring Demand | NOT-DONE | no code references | This is a false-positive match: it's explicitly S-256/HRMS-0506 "Resource Demand Planning / Future Demand vs Bench Forecast" (a different, EPIC-05 story, bucketing *allocation expiry*, not hiring-demand forecast). No ded |
| S-271 | HRMS-0305 | Convert Opportunity Pipeline to Demand | NOT-DONE | no code references | Only a manual, single-opportunity, single-role creation path exists (`create_role_demand_from_opportunity` = S-239/HRMS-0210). No bulk/automatic conversion of the *entire open pipeline* weighted by close probability, and |
| S-272 | HRMS-0306 | Match Bench vs Demand — Gap Analysis | PARTIAL | no code references | `app/services/demand_gap_monitoring_service.py` (tagged `HRMS-1102`, not `HRMS-0306`), `app/models/sourcing.py` (`DemandGapScore`, `SourcingAlert`) / A real gap-severity/alerting agent exists but under a different (later |
| S-273 | HRMS-0307 | Trigger Sourcing Workflow on Demand Creation | NOT-DONE | re-verify (code touched after 08-22) | Explicit in-code confirmation of absence from an unrelated feature (S-359 HTD Intake Pause) that was going to depend on it. |
| S-275 | HRMS-0309 | Auto Create Job Requisitions from Demand | NOT-DONE | no code references | No code found (keyword + ID search both empty). |
| S-276 | HRMS-0310 | View Demand Forecast Dashboard | NOT-DONE | no code references | No dedicated demand-forecast dashboard endpoint or screen found. |
| S-277 | HRMS-0311 | AI Revenue to Workforce Conversion Model | NOT-DONE | no code references | The existing conversion logic is deterministic arithmetic (trailing revenue ÷ headcount), not an ML model, has no confidence scoring, and doesn't learn per-continent conversion rates as specified. Does not meet this stor |
| S-278 | HRMS-0312 | Workforce Scenario Planning | NOT-DONE | re-verify (code touched after 08-22) | `app/models/core_pull.py:7-9`, `app/services/core_pull_service.py:6-7`, `app/services/resource_management_agent_service.py:2-4` / All three files explicitly disclaim being HRMS-0312: they state the Core-Pull engine and R |
| S-279 | HRMS-0313 | Plan vs Execution Variance Tracking | NOT-DONE | re-verify (code touched after 08-22) | File explicitly states it "Does NOT depend on S-279/HRMS-0313 ... that story is unrelated hiring-headcount variance (planned heads vs actual hires), confirmed by reading it directly." No planned-vs-actual-hires tracking  |
| S-280 | HRMS-0314 | BU Planning Approval Workflow | NOT-DONE | re-verify (code touched after 08-22) | No code found; only unrelated approval workflows exist (buddy-program graduation gate). |

## backlog-verification\cluster2_recruiter_platform

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-005 | HRMS-0405 | Unified Conversation Timeline UI | PARTIAL | re-verify (code touched after 08-22) | Chronological timeline with timestamps and sender ("by AI"/"by recruiter") is real, but **no channel icon per message** — spec explicitly calls for "channel icon per message"; actual code has zero icon/emoji usage anywhe |
| S-033 | HRMS-0433 | Intent Detection Engine | PARTIAL | re-verify (code touched after 08-22) | app/services/detect_intent_service.py:2,74-93 / Code itself, in `INTENT_ROUTING` dict and module docstring, self-documents: "Not wired into any live inbound path (whatsapp_webhook_service, ai_conversation_service.process |
| S-035 | HRMS-0435 | Human Escalation Detection | PARTIAL | re-verify (code touched after 08-22) | app/services/conversation_state_service.py:207 (+ escalation_detection_service.py) / `check_escalation()` is called live from `portal_message_service.py:178` and `public_chat_service.py:279`, but NOT from the primary Wha |
| S-047 | HRMS-0447 | Interview Availability Collection | PARTIAL | re-verify (code touched after 08-22) | app/services/detect_intent_service.py:26,80 (+ interview_availability_service.py) / Backend logic real and tested (`send_availability_request`, `parse_availability_response`). Story's own note says "deliberately not wire |
| S-068 | HRMS-0468 | Voice Calling Agent Framework | NOT-DONE | no code references | none found / Zero hits for HRMS-0468 anywhere in backend or frontend. Keyword search for "voice", "transcription", "CallLog", "call_log", "phone_screen", "VoiceAgent" across `app/` and `src/` returns only false positives |
| S-079 | HRMS-0479 | Production Load Testing — AI Recruiter | NOT-DONE | no code references | Zero hits for HRMS-0479. Keyword search for "load_test", "locust" across app/tests/docs finds nothing except a build-package spec doc. No load-testing harness exists. Sheet is accurate here. |
| S-080 | HRMS-0480 | AI Recruiter Go-Live Checklist & Monitoring | NOT-DONE | no code references | Zero hits for HRMS-0480. No go-live checklist, monitoring dashboard, or deployment automation found. Sheet is accurate here. |

## Story-by-story

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-402 | HRMS-ONB-001 | Welcome Note (Step 1) | NOT-DONE | no code references | No welcome-screen component/route found anywhere in frontend. No portal to host it. |
| S-403 | HRMS-ONB-002 | Email Access Validation (Step 2) | NOT-DONE | no code references | No mailbox-validation flow found (msgraph.py / msgraph_mail_sync_service.py sync mail for EPIC-14 linking, not new-hire email verification). |
| S-404 | HRMS-ONB-003 | Induction / company overview (Step 3) | NOT-DONE | no code references | No induction video/deck content or screen found. |
| S-405 | HRMS-ONB-004 | Emergency Information (Step 4) | NOT-DONE | no code references | `emergency_contact_name`/`emergency_contact_phone` columns exist on `Employee`, but no medical-info field and no onboarding-portal capture UI writes to them — they're plain HR-editable employee fields, not a new-hire sel |
| S-406 | HRMS-ONB-005 | Personal Interests (Step 5) | NOT-DONE | no code references | No hobbies/interests field anywhere in `Candidate`/`Employee` models or forms. |
| S-407 | HRMS-ONB-006 | Personal & Emergency Contact Details Form → Employee record (Step 6) | PARTIAL | no code references | `src/screens/CandidateSelfService.js:24-41`, `app/models/candidate.py` (CandidateInfoForm: current_address/permanent_address/marital_status/nationality) / Candidate-side self-service already captures overlapping fields ( |
| S-408 | HRMS-ONB-007 | Bank Account / Payroll Setup (IFSC, PAN) (Step 7) | PARTIAL | no code references | Document *upload* for bank statement/UAN-PF and a PAN form exist, but there is no structured bank-account-number/IFSC/routing-number field capture anywhere — only file uploads, not the payroll-setup data entry the story  |
| S-409 | HRMS-ONB-008 | Government ID & Tax Documents Upload (virus scan + SharePoint) (Step 8) | PARTIAL | no code references | The reusable pipeline (virus scan + SharePoint storage) is real and already used for candidate documents, exactly as the story assumes — but it's used for the recruiting-pipeline candidate, not wired into any post-offer  |
| S-410 | HRMS-ONB-009 | Offer Letter Digital Acknowledgement (Step 9) | PARTIAL | no code references | `src/screens/CandidateSelfService.js:43-46` (`respondToOffer`, `signOfferLetter`), `app/api/v1/endpoints/offer_letters.py`, `app/models/offer_letter.py` / Real offer accept/sign flow exists in the recruiting-stage candid |
| S-411 | HRMS-ONB-010 | Employment Agreement E-Signature (reuses SignatureModal.js) (Step 10) | PARTIAL | no code references | The component is real and reusable exactly as the story assumes, but it is currently wired only to offer-letter signing, not to a full employment-contract flow. |
| S-412 | HRMS-ONB-011 | Company Policies Acknowledgement (Step 11) | NOT-DONE | no code references | No policy content, scroll-to-bottom gate, or per-policy timestamped acknowledgement found. The generic checklist engine (`checklists.py`) could theoretically hold a "todo" item titled after a policy, but no such template |
| S-413 | HRMS-ONB-012 | NDA / Confidentiality E-Signature (Step 12) | NOT-DONE | no code references | "Sign NDA" appears only as a documentation *example* checklist-item title, not a real seeded template, content, or e-signature flow. |
| S-414 | HRMS-ONB-013 | Background Verification Consent (via ConsentRecord, subject_type='employee') (Step 13) | NOT-DONE | no code references | `ConsentRecord` model and `has_consent`/helper functions exist and are generic enough to support this, but grep across the whole backend shows **zero production callers** of `app.core.consent` — only `tests/test_consent. |
| S-415 | HRMS-ONB-014 | IT Equipment Request (Step 14) | NOT-DONE | no code references | Generic Help Desk/IT-HR ticketing exists with admin-configurable Category/Subcategory routing (built 2026-08-04 per prior session), which *could* be configured for equipment requests, but no "IT Equipment Request" record |
| S-416 | HRMS-ONB-015 | SharePoint Access Walkthrough (Step 15) | NOT-DONE | no code references | SharePoint integration exists for document storage/retrieval, but there is no walkthrough/tutorial content or screen. |
| S-417 | HRMS-ONB-016 | Email & Calendar Setup Walkthrough (Step 16) | NOT-DONE | no code references | No Outlook/Teams orientation content found. |
| S-418 | HRMS-ONB-017 | Org Chart & Company Structure Overview (Step 17) | NOT-DONE | no code references | No org-chart visualization screen/component found anywhere in the frontend. |
| S-419 | HRMS-ONB-018 | Meet the Leadership (Step 18) | NOT-DONE | no code references | No leadership welcome video/message content or screen. |
| S-420 | HRMS-ONB-019 | Company Culture & Values (Step 19) | NOT-DONE | no code references | This service is the internal Executive Signal & Culture Agent (CEO-facing quarterly cycle / concern triage, built 2026-08-04) — an unrelated system, not a new-hire-facing culture deck/video. Flagging explicitly so it isn |
| S-421 | HRMS-ONB-020 | Benefits Enrollment (Step 20) | NOT-DONE | no code references | No benefits/insurance/PF election model or screen found. |
| S-422 | HRMS-ONB-021 | Dress Code & Office Guidelines (Step 21) | NOT-DONE | no code references | No content found. |
| S-423 | HRMS-ONB-022 | First Week Schedule Preview (Step 22) | NOT-DONE | no code references | No Week-1 day-by-day preview screen. |
| S-424 | HRMS-ONB-023 | IT Security & Data Protection Training (Step 23) | NOT-DONE | no code references | No training-module content or acknowledgement flow. |
| S-425 | HRMS-ONB-024 | Workplace Conduct / POSH Training Acknowledgement (Step 24) | NOT-DONE | no code references | No content found. |
| S-426 | HRMS-ONB-025 | Tools & Software Access Setup checklist (Step 25) | NOT-DONE | no code references | The generic HR-configurable todo/queue checklist engine is real and could be pointed at this use case, but no seeded template/content for Slack/Teams/Jira access confirmation exists. |
| S-427 | HRMS-ONB-026 | Client Confidentiality Agreement (Step 26) | NOT-DONE | no code references | No per-assignment client-confidentiality content/e-sign flow distinct from the (also-missing) NDA step. |
| S-428 | HRMS-ONB-027 | Payroll & Timesheet System Walkthrough (Step 27) | PARTIAL | no code references | The underlying Timesheets module the story explicitly says to reuse is real, built, and in production use (per prior session's employee self-service timesheet work) — but there is no guided "first submission" walkthrough |
| S-429 | HRMS-ONB-028 | Photo & ID Badge Submission (Step 28) | NOT-DONE | no code references | No photo-upload-for-badge flow found (`document_service.py` has no photo/badge document type). |
| S-430 | HRMS-ONB-029 | Ask Thunder — Onboarding FAQ (Step 29) | NOT-DONE | no code references | Thunder conversational infra (public candidate chat + internal Ask Thunder) is real and reusable exactly as the story assumes, but there is no third instance embedded for new hires, and no onboarding portal to embed it i |
| S-431 | HRMS-ONB-030 | Day-1 Logistics Confirmation (Step 30) | PARTIAL | no code references | The one-time D-1 WhatsApp/Email message with this content is real (S-067). The story's own text acknowledges this — it asks for the *same* information made "persistently viewable" in a portal, which does not exist. |
| S-432 | HRMS-ONB-031 | Introduction to Reporting Manager (Step 31) | PARTIAL | no code references | The data relationship (who is the reporting manager) is real and queryable, but no "introduce by name/photo/note" portal screen exists. |
| S-433 | HRMS-ONB-032 | Reporting Manager Introduces Buddy (Step 32) | PARTIAL | no code references | `app/models/buddy_program.py:25-42` (`BuddyProgramRecord.buddy_engineer_user_id`), `src/screens/BuddyProgramScreen.js` / Buddy assignment data and a real UI (BuddyProgramListScreen/BuddyProgramScreen) exist per S-364/S-3 |

## EPIC-06 — Adhoc Staffing Demand Engine (sheet: 0%)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-281 | HRMS-0601 | Create Adhoc Demand from Client Request | NOT-DONE | no code references | No unstructured-request-to-demand conversion exists anywhere. |
| S-282 | HRMS-0602 | AI Classify Incoming Request | NOT-DONE | no code references | No NLP classification of adhoc requests. |
| S-283 | HRMS-0603 | Search Internal Bench First — Instant Match | NOT-DONE | no code references | Note: EPIC-07's bench-first gate (S-291, see below) is a different, real thing — a pre-sourcing *gate*, not an "instant match on adhoc demand" flow. |
| S-284 | HRMS-0604 | AI Suggest Immediate Allocation | NOT-DONE | no code references | — |
| S-285 | HRMS-0605 | P1 Emergency Staffing Flow | NOT-DONE | re-verify (code touched after 08-22) | The only `HRMS-0605` hits in-repo are `app/models/revenue_leakage.py` / `app/services/invoice_service.py` — an unrelated finance story reusing the same ID number, not this story. |
| S-286 | HRMS-0606 | Auto Schedule Client Interviews — Rapid Mode | NOT-DONE | no code references | Calendar-matching (`calendar_matching_service.py`) exists for normal interview scheduling but has no "rapid mode" / 1-hour SLA variant. |
| S-287 | HRMS-0607 | SLA Breach Prediction & Escalation | NOT-DONE | no code references | `app/models/sla_breach.py` is S-020/HRMS-0420 "Engagement SLA Monitoring" (candidate response-time breaches) — a genuinely different story, not adhoc-staffing SLA prediction. |
| S-288 | HRMS-0608 | AI Pricing Suggestion for Adhoc Request | NOT-DONE | no code references | No bill-rate/margin suggestion engine for adhoc requests exists. |

## EPIC-07 — Talent Engine / ATS Layer (sheet: 1/10)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-289 | HRMS-0701 | Auto Create Job from Workforce Demand | NOT-DONE | no code references | Jobs and Demands are structurally disconnected in this codebase. No auto-generation path exists. |
| S-290 | HRMS-0702 | View Job Requisition List & Status | PARTIAL | no code references | Generic job list/status/filter UI is real and solid, but the demand-source link, pipeline count, and Boolean-search-string fields the story calls for don't exist (consequence of S-289 not existing). |
| S-292 | HRMS-0704 | Trigger LinkedIn Sourcing Agent | PARTIAL | no code references | `app/services/linkedin_sourcing_service.py` (full file, labeled `HRMS-1103`/EPIC-11) / Real agent loop: claims sourcing alerts, dedup-checks, stages candidates, human-promotion gate. But the docstring itself flags that t |
| S-293 | HRMS-0705 | External Candidate Import & Deduplication | PARTIAL | no code references | Dedup and staged-import pipeline are real. "Continent auto-detected" from the summary is **not implemented** — no continent field/logic anywhere in `StagedCandidate` or the promotion path. |
| S-294 | HRMS-0706 | Interview Panel Assignment & Calendar Sync | PARTIAL | re-verify (code touched after 08-22) | `app/models/interview_pipeline.py` + `app/services/interview_service.py:44-179` (labeled `HRMS-0706` but the module docstring explicitly says this is the *earlier* EPIC-01/Phase-2 track, "NOT the later, structurally diff |
| S-296 | HRMS-0708 | Convert Candidate to Employee on Joining | PARTIAL | re-verify (code touched after 08-22) | `app/services/employee_service.py:92-136` `convert_candidate_to_employee()` — docstring explicitly: *"HRMS-0160/HRMS-0708's fuller 'Convert Candidate to Employee' story (offers, preboarding documents, the full onboarding |

## EPIC-08 — Project & Delivery Management (sheet: 0%)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-305 | HRMS-0807 | Project Risk Flagging & Delivery Health | NOT-DONE | re-verify (code touched after 08-22) | `app/models/project.py:11-16` and `app/services/project_service.py:5-...` — both docstrings explicitly state: *"HRMS-1107 (Project Health Monitoring Agent) ... doesn't exist in this codebase — HRMS-0807 ... is NOT built  |

## backlog-verification\cluster5_timesheet_ai_agentic_analytics_integration

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-221 | HRMS-0902 | Timesheet Validation & Submission Lock | PARTIAL | re-verify (code touched after 08-22) | `app/services/timesheet_service.py:122-192` (`upsert_entries`, `submit_timesheet`) / Validation is real: 60h/week cap (`MAX_WEEKLY_HOURS`), no future dates, no empty submission, 4-week stale-submission cutoff (`StaleTime |
| S-222 | HRMS-0903 | Internal Manager Timesheet Approval | PARTIAL | re-verify (code touched after 08-22) | `app/services/timesheet_service.py:195-227` (`approve_timesheet`, `reject_timesheet`, `reopen_for_editing`, `bulk_approve`); `app/api/v1/endpoints/timesheets.py:218-266` / Approve/reject/reopen/bulk-approve workflow with |
| S-223 | HRMS-0904 | Employee Utilization Calculation | PARTIAL | re-verify (code touched after 08-22) | `app/services/timesheet_analytics_service.py:92-109` (`calculate_utilization_pct_phase2`); `app/services/resource_management_service.py:177-241` (`record_weekly_utilization_metric`, `get_latest_utilization_by_employee`); |
| S-224 | HRMS-0905 | Map Timesheet to Project Revenue | PARTIAL | no code references | `app/services/invoice_service.py:76-91` (`generate_invoice` line-item loop); `app/models/invoice.py:67-80` (`InvoiceLineItem`) / Billable hours × bill rate is real, per employee per timesheet, and is the literal mechanis |
| S-226 | HRMS-0907 | MERGED — Invoice Generation, Status Tracking & PDF Export | PARTIAL | re-verify (code touched after 08-22) | `app/services/invoice_service.py:46-123` (generate/approve/send/mark-paid state machine); `app/api/v1/endpoints/invoices.py:1-15` / Generation (with R-10 hard block on any unapproved timesheet, and dispute-block), full D |
| S-306 | HRMS-1001 | MERGED — Unified Prediction Engine: Talent Signals | NOT-DONE | re-verify (code touched after 08-22) | Zero implementation found. Only forward-reference: `app/core/llm_prompt_safety.py:4` mentions "HRMS-1001's matching engine" as a not-yet-existing future consumer. |
| S-309 | HRMS-1004 | MERGED — Unified Prediction Engine: Financial Signals | NOT-DONE | no code references | No revenue-forecast/delay/margin prediction engine anywhere in the codebase. |
| S-315 | HRMS-1010 | AI Training Recommendation Engine | NOT-DONE | no code references | No training-recommendation logic exists. |
| S-316 | HRMS-1101 | System Orchestration Master Agent | PARTIAL | re-verify (code touched after 08-22) | `app/services/orchestration_router_service.py:1-471` (`evaluate_action_intent`, conflict rules, escalation, novel-pattern LLM fallback); `app/models/orchestration.py`; `tests/test_orchestration_router.py` / Real, substan |
| S-318 | HRMS-1103 | LinkedIn Sourcing Agent Loop | PARTIAL | re-verify (code touched after 08-22) | `app/services/linkedin_sourcing_service.py:1-40+` / Real dedup-and-stage pipeline exists (reuses `find_duplicate_candidate`, models `POSSIBLE_DUPLICATE`/`CONFIRMED_DUPLICATE`), but by its own docstring two core pieces ar |
| S-319 | HRMS-1104 | Automated Outreach Agent | PARTIAL | re-verify (code touched after 08-22) | `app/services/outreach_agent_service.py:1-40+` / Real sequencing/timing/reply-tracking logic through `thunder_service.send_thunder_message()` with real consent/ownership gates. Gap: only the WhatsApp transport actually s |
| S-321 | HRMS-1106 | Revenue Monitoring Agent | NOT-DONE | no code references | No implementation anywhere. |
| S-322 | HRMS-1107 | Project Health Monitoring Agent | NOT-DONE | re-verify (code touched after 08-22) | Confirmed absent by the codebase's own contemporaneous documentation, not just by our grep. |
| S-323 | HRMS-1108 | Integration Health Agent — Self-Heal | NOT-DONE | re-verify (code touched after 08-22) | The error-log table's own docstring/field comment states: "HRMS-1108 Integration Health Agent's own filter dimension -- not built yet, this table is Step 4's real read surface for it once it exists." Only a queryable `er |
| S-324 | HRMS-1109 | Learning Optimization Agent | NOT-DONE | re-verify (code touched after 08-22) | No implementation exists. |
| S-325 | HRMS-1110 | Daily System Activity Report | NOT-DONE | re-verify (code touched after 08-22) | `app/services/daily_digest_service.py:1-40` / This file exists but is explicitly **S-065/HRMS-0465 "Thunder Daily Digest / Morning Report"** — a per-recruiter candidate-activity digest (drop risk, intervention queue, int |
| S-326 | HRMS-1201 | CXO Revenue Dashboard | PARTIAL | no code references | `app/services/revenue_target_service.py:201-243` (`get_executive_revenue_dashboard`); `app/api/v1/endpoints/revenue_targets.py:88-93`; frontend `src/screens/ExecutiveRevenueDashboardScreen.js` / This is real and substant |
| S-327 | HRMS-1202 | CXO Hiring vs Target Dashboard | NOT-DONE | no code references | No implementation found. |
| S-328 | HRMS-1203 | CXO Workforce Utilization View | NOT-DONE | no code references | `app/api/v1/endpoints/employees.py:388-417` (`utilization_summary`, = S-254); frontend `src/screens/UtilizationDashboardScreen.js` / An adjacent employee-level utilization dashboard (S-254/S-255) is real (see S-223 above |
| S-329 | HRMS-1204 | CXO Risk Heatmap | NOT-DONE | no code references | `app/services/risk_dashboard_service.py:1-29`; frontend `src/screens/RiskDashboardScreen.js` / This is real but is **S-063/HRMS-0463 "Candidate Risk Dashboard"** — a recruiting drop-risk dashboard scoped entirely to cand |
| S-330 | HRMS-1205 | Recruiter Productivity Dashboard | NOT-DONE | no code references | No implementation found. |
| S-331 | HRMS-1206 | Project Profitability Dashboard | PARTIAL | no code references | Real revenue-minus-fully-loaded-cost calculation exists and is tested (EPIC-16 BU P&L Engine), but it computes profitability at the **Business Unit** level, not per-project, and has no budget-vs-actuals, burn-rate, or de |
| S-332 | HRMS-1207 | Bench Cost & Aging Analytics Dashboard | PARTIAL | no code references | Real per-employee bench cost (daily/monthly/running) and days-on-bench aging data exist, with alerting. Missing: no breakdown by BU+skill+continent, and no "redeployment opportunities" surfaced as a distinct feature. |
| S-333 | HRMS-1208 | Source of Hire Analytics | NOT-DONE | no code references | No implementation found. |
| S-334 | HRMS-1209 | Human vs AI Dependency Tracker | NOT-DONE | no code references | Despite AI-vs-human being a recurring theme elsewhere in this codebase (Thunder ownership locks, etc.), no tracked metric or dashboard toward the stated <20% target exists. |
| S-335 | HRMS-1210 | Compliance & Audit Reporting Engine | NOT-DONE | no code references | This is real but is **S-076/HRMS-0476**, a narrow single-INSERT helper for candidate-conversation audit trail entries — not an RBAC-audit / data-isolation / FT-only-compliance / sub-vendor-compliance / experience-rule-ov |
| S-338 | HRMS-1303 | Post Jobs to Free Job Boards | NOT-DONE | no code references | No implementation found. |
| S-339 | HRMS-1304 | WhatsApp Business API — Enhancement | PARTIAL | no code references | `app/services/whatsapp_routing_service.py`, `app/services/whatsapp_webhook_service.py` / Baseline WhatsApp send/receive/webhook-verification/delivery-status is real (built in an earlier epic — this is what the sheet's "A |
| S-340 | HRMS-1305 | Email Outreach Automation & Threading — Enhancement | PARTIAL | no code references | `app/services/outreach_campaign_service.py`, `app/services/email_service.py`, `app/services/msgraph_mail_sync_service.py` / Baseline outreach-campaign email sending is real. The specific enhancement asks (reply parsing,  |
| S-341 | HRMS-1306 | Outlook Calendar Integration — Enhancement | PARTIAL | re-verify (code touched after 08-22) | `app/services/calendar_matching_service.py` (interviewer/candidate real IANA-timezone-aware slot matching, UTC conversion, per-user `Users.timezone`/`Candidate.timezone`) / Real, tested multi-timezone interview-slot matc |
| S-342 | HRMS-1307 | Import from Greenhouse / Lever | NOT-DONE | no code references | No implementation found. |
| S-343 | HRMS-1308 | Payroll System Sync | NOT-DONE | no code references | Only hit: `rbac_service.py`'s `payroll_access` boolean permission flag per role (an access-control gate, not a sync feature) and one comment in `employee.py` about future PAYROLL/ADMIN-only field access. No actual payrol |
| S-344 | HRMS-1309 | Invoice Export to ERP | NOT-DONE | no code references | No implementation found. |
| S-345 | HRMS-1310 | Webhook Engine & Integration Health Dashboard | NOT-DONE | re-verify (code touched after 08-22) | Explicitly confirmed absent by the codebase's own documentation: "no ... webhook engine (HRMS-1310) exists yet to actually subscribe... `event_retry_queue`/`RetryJob` are NOT built here." Only a standalone `event_log` ta |

## EPIC-14 — Internal Collaboration Hub (6 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-379 | HRMS-1401 | M365 SSO bridge + embedded tab/dock shell for Outlook/Teams | PARTIAL | re-verify (code touched after 08-22) | `app/api/v1/endpoints/msgraph.py:91-134` (`/link/start`, `/link-status`, `/unlink`), `tests/test_msgraph_account_linking.py` (9 passing-shaped tests) / Backend account-linking logic (link WITHOUT swapping WROS session) i |
| S-380 | HRMS-1402 | Embedded Outlook Mail/Calendar tab, WROS-context deep linking | NOT-DONE | no code references | These are Graph API wrapper *actions* invoked from existing scheduling forms (e.g. `InterviewSchedule.js`), not an embedded Outlook Mail/Calendar tab surface with deep linking. No embedded-tab UI exists. |
| S-381 | HRMS-1403 | Teams chat dock + unified notification center | NOT-DONE | no code references | Only surface: `"Microsoft Teams"` as a meeting-platform dropdown value (`CandidateDetailsScreen.js:88`) and `outlook_event_id` storage — cosmetic, not a chat dock. Matches memory note that S-381 was explicitly deferred. |
| S-382 | HRMS-1404 | Dynamic Reporting Hierarchy Engine (configurable org-level chain walk) | NOT-DONE | no code references | reporting_hierarchy"` → no service hits). |
| S-383 | HRMS-1405 | Admin-editable check-in cadence by org level | NOT-DONE | no code references | Depends on S-382, which doesn't exist. |
| S-384 | HRMS-1406 | Auto-scheduler batch job for recurring check-ins via Outlook Calendar | NOT-DONE | no code references | Depends on S-382/S-383/S-380, none of which exist. |

## EPIC-15 — Interview Integrity Layer (2 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-385 | HRMS-1501 | Interview Integrity Analysis Engine — analyze consented recording/transcript for rehearsed-answer, outside-assistance, identity-mismatch signals | NOT-DONE | re-verify (code touched after 08-22) | interview_integrity` across the whole backend: zero implementation hits. |
| S-386 | HRMS-1502 | Panel Feedback Cross-Validation & Clarification Routing | NOT-DONE | no code references | Depends on S-385, which doesn't exist. |

## EPIC-16 — Finance & Accounting Operations (15 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-387 | HRMS-1601 | Timesheet Submission Nag Agent — 7-step email/Teams/WhatsApp cascade to employee then RM/RM's-manager/BU-Head, timezone-aware | PARTIAL | no code references | `app/services/timesheet_nag_service.py` (136 lines), registered job at `app/core/scheduler.py:798-816` / Real, scheduled, tested 2-level escalation (employee → reporting manager only) via generic `send_notification()`. N |
| S-388 | HRMS-1602 | Monthly Invoice Generation Cycle — scheduled trigger on the 2nd of month | PARTIAL | no code references | The underlying generation logic is real (reused from S-226) and frontend-wired (`InvoicesScreen.js`), but it's manually triggered per-project only — no scheduled "2nd-of-month" batch trigger exists anywhere in `scheduler |
| S-390 | HRMS-1604 | AR Follow-Up Agent — 15/30/45-day escalating reminders, LLM-drafted messages queued for review | PARTIAL | no code references | `app/services/ar_followup_service.py` (113 lines): `scan_overdue_invoices`, `trigger_ar_follow_up`, scheduled at `scheduler.py:827` / Real single-tier aging scan (one grace-day threshold, default 30d) + Task creation + n |
| S-391 | HRMS-1605 | Bank Statement Reconciliation — PDF/Excel upload, LLM extraction, deterministic matching, Finance-confirmed only | PARTIAL | no code references | `app/services/bank_reconciliation_service.py` (67 lines): `record_bank_transaction`, `match_transaction_to_invoice` (exact-amount match only), `get_unreconciled_transactions` / Real manual-entry + deterministic exact-amo |
| S-393 | HRMS-1608 | Fully Loaded Cost Engine — locked India/US formulas, ESI cap, 4 flagged placeholder constants | PARTIAL | no code references | `app/services/cost_rate_service.py` (real, tested), `app/models/cost_rate_config.py` (config-driven statutory_pct/overhead_pct), `FinanceOperationsScreen.js:250-257` ("Set Cost & Rate Config" panel) / Real, full-stack, d |
| S-394 | HRMS-1609 | RM Burden Allocation Engine — flat per-hour RM overhead across billable employees | NOT-DONE | no code references | No such engine exists. `cost_rate_service.py` has a *different* concept, `calculate_blended_delivery_rate`, but it is BU-level revenue÷hours, not an RM-overhead allocation. |
| S-395 | HRMS-1610 | Minimum Bill Rate Engine — (FLC + RM Burden) × multiplier | NOT-DONE | no code references | Depends on S-394, which doesn't exist. |
| S-396 | HRMS-1607 | BXIN/BXUS Separate P&L Engine — Revenue/Salary/EBITDA/Net Profit per legal entity | NOT-DONE | no code references | `app/services/pnl_service.py:1-11` (module docstring, verbatim) / The module's own docstring states this explicitly: "Location P&L is NOT built: no field anywhere on Employee identifies which legal entity (India vs US) a |
| S-397 | HRMS-1612 | Reserve Fund Engine — 25% of EBITDA auto-calculated (contribution or drawdown), 12-month buffer check | PARTIAL | no code references | `app/services/reserve_fund_service.py` (real), `FinanceOperationsScreen.js:259-266,238-246` (real UI panel) / Real ledger + a genuine 12-month-target health check (`get_reserve_fund_target_usd_cents` = 12x trailing avg B |
| S-398 | HRMS-1613 | Hiring Affordability Gate — TWO hard gates (Reserve check + Run-rate check), zero override | PARTIAL | no code references | `app/services/hiring_affordability_service.py` (59 lines, real), `FinanceOperationsScreen.js:268-281` (real UI panel) / Real, tested single-gate check: projected BU gross margin stays ≥0% after adding the hire's fully-lo |
| S-400 | HRMS-1614 | Executive Finance Dashboard — 7-block CEO dashboard, pure aggregation over the 5 engines | PARTIAL | no code references | `app/services/pnl_service.py:74-118` (`get_org_pnl_summary`, real org-wide rollup), `app/api/v1/endpoints/cost_rate.py:107` (`/pnl/org-summary`) / Backend aggregation exists and is real (sums every BU's own `get_bu_pnl() |
| S-401 | HRMS-1615 | GST & Statutory Compliance — UAT-gated placeholder scaffold | NOT-DONE | no code references | This is the one EPIC-16 story where sheet status is accurate — genuinely not built, and correctly blocked pending Finance/CA signoff per the sheet. |

## DESIRE — Desire Intelligence System (5 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-350 | HRMS-P120 | HR Intelligence Briefing — daily 08:00 digest per recruiter across all their candidates, portal + email, `hr_intelligence_briefings` table | PARTIAL | re-verify (code touched after 08-22) | `src/screens/tabs/IntelligenceTab.js:1` (self-labeled "S-350/HRMS-P120"), `app/services/desire_profile_service.py:230-269` (LLM briefing text) / What exists is a real **per-candidate, on-demand** motivation briefing (vie |

## EPIC-P1 — Candidate Portal & Universal Identity Engine

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-081 | HRMS-P101 | Universal Candidate Identity Engine (dedup, merge, log) | PARTIAL | no code references | `app/services/candidate_service.py:47-131` (`find_duplicate_candidate`, `create_candidate_safe`) / Real exact-match dedup on email/phone/`linkedin_url`, independently checked (R-07), used by every candidate-creation call |
| S-082 | HRMS-P102 | LinkedIn Entry — Skeleton Profile Creation | NOT-DONE | no code references | `app/models/candidate.py:35` (`linkedin_url` column only, comment ties it to dedup not skeleton creation) / No "LinkedIn source detected → create skeleton profile (name/headline/location/continent) + auto-assign AI recru |
| S-083 | HRMS-P103 | Cross-Channel Conversation Merge | PARTIAL | no code references | `app/services/candidate_portal_service.py:22-30`; frontend `CandidatePortalScreen.js` `MessagesTab` (~line 197-333) / Backend genuinely merges channels: portal message thread deliberately reuses `get_conversation_thread( |
| S-084 | HRMS-P104 | Session Resume across channels | PARTIAL | no code references | Same as S-083; `app/services/ai_conversation_service.py::get_conversation_thread` / A candidate can effectively resume: the portal link (JWT) loads full merged history via `get_conversation_thread()`. But there is no `bu |
| S-085 | HRMS-P105 | Candidate Portal — Home Dashboard | PARTIAL | no code references | Real endpoint + UI. Shows 3 of the 4 spec'd cards: current stage badge, pending actions, recent messages. **Offer status card is entirely absent** — consistent with no offer-viewer feature existing at all (see S-089). |
| S-086 | HRMS-P106 | Candidate Portal — Message Thread View | PARTIAL | no code references | Full cross-channel history + inline reply, with real-time polling (added 2026-08-06 per in-code comment at line ~225). **Missing:** file upload (no attachment control in the reply box), channel icons per message, and an  |
| S-087 | HRMS-P107 | Candidate Portal — Profile Completion Wizard | PARTIAL | no code references | `candidate_portal.py:81-96` (`PATCH /portal/profile`); `CandidatePortalScreen.js:342-423` (`ProfileTab`) / Self-service field completion is real: auto-marks `missing_fields` via `get_missing_fields()`, reuses the same "A |
| S-088 | HRMS-P108 | Candidate Portal — Interview Tracker | PARTIAL | no code references | `candidate_portal.py:99-121`; `CandidatePortalScreen.js:425-449` (`InterviewsTab`) / Real: upcoming interviews list, Reschedule-request button, Add-to-calendar via real `.ics` download (`GET /portal/interviews/{id}/ics`) |
| S-089 | HRMS-P109 | Candidate Portal — Offer Viewer | NOT-DONE | no code references | No offer route exists in the portal API, no "Offer" tab in the portal UI, no Accept/Decline/Ask-Question actions, no inline FAQ bot. Offer letters are sent as a link *out* of the portal system (see `offer_release_notific |
| S-090 | HRMS-P110 | Candidate Portal — Document Upload | NOT-DONE | no code references | No document-checklist tab, no upload endpoint under `/portal`, no file-input control in the candidate portal UI at all. `preboarding_document.py`/`document_collection_service.py` exist but drive a different, internal-fac |
| S-091 | HRMS-P111 | Magic Link Authentication | PARTIAL | re-verify (code touched after 08-22) | `app/services/candidate_portal_service.py:1-78` (module docstring + `generate_portal_link_token`/`generate_portal_link_url`); sent via both `email_service.py:976-1024` and `offer_release_notification_service.py:76-114` ( |
| S-092 | HRMS-P112 | Duplicate Detection Audit Dashboard | NOT-DONE | no code references | No admin view of merge/duplicate events anywhere. This is a direct consequence of S-081: since duplicates are refused (not merged) with no event logged to a table, there is nothing for an audit dashboard to read even if  |
| S-093 | HRMS-P113 | Candidate Source Attribution Tracking | NOT-DONE | no code references | Only a 2-value source enum (DIRECT/SUBVENDOR) exists — not a multi-touch attribution chain (LinkedIn→WhatsApp→Portal), no admin attribution view, no source ROI analytics. |
| S-094 | HRMS-P114 | WhatsApp Deep Link to Portal | PARTIAL | no code references | `offer_release_notification_service.py:76-114` includes `portal_link` in its WhatsApp message; `app/services/thunder_service.py` (grep for `portal_link`: 0 hits) / The portal deep link is real but only wired into the off |

## EPIC-P2 — Employee Portal, Admin & Technical Split

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-096 | HRMS-P201 | Admin Portal — Recruiting Dashboard | PARTIAL | no code references | `src/screens/Dashboard.js:29-80` / Real dashboard exists: open jobs, candidates-in-pipeline, interviews-scheduled stat cards + `InterventionQueueWidget`. **Missing** vs. spec: no pipeline-by-stage breakdown, no "AI activ |
| S-097 | HRMS-P202 | Admin Portal — HR Dashboard | NOT-DONE | no code references | No dedicated HR-role dashboard screen exists. Backend building blocks exist piecemeal (`joining_readiness_service.py`, `document_collection_service.py`) but are not assembled into the single consolidated HR view the stor |
| S-098 | HRMS-P203 | Admin Portal — Resource Management Dashboard | PARTIAL | no code references | `src/screens/UtilizationDashboardScreen.js:1-123` (S-254/S-255, utilization + bench cost); `src/screens/ResourceManagementScreen.js` (bench-scan/bench-match agent, HRMS-1105/S-320) / Adjacent, real functionality exists ( |
| S-099 | HRMS-P204 | Admin Portal — Client Services Dashboard | NOT-DONE | no code references | No such dashboard, backend or frontend. `ClientManagementScreen.js` exists but is CRUD for client records, not a health/delivery/escalation dashboard. |
| S-100 | HRMS-P205 | Technical Portal — Interview Queue | PARTIAL | no code references | `src/screens/MyWorkspace.js:11,112` (`getMyInterviews`); `src/services/api/interviews.js` / An interviewer's own-interviews list is real (`getMyInterviews`) and feeds `MyWorkspace.js`/`FeedbackTab.js`. Not independently  |
| S-102 | HRMS-P207 | Technical Portal — Hiring Manager Decision View | PARTIAL | re-verify (code touched after 08-22) | `src/screens/HmCandidateReviewScreen.js:1-50` / Sheet says Done; code says otherwise. The screen's own header comment states: *"Approval/rejection itself happens on the existing candidate status action ... not here — thi |
| S-103 | HRMS-P208 | Technical Portal — BU Head Oversight View | NOT-DONE | no code references | No dedicated BU Head oversight screen (active demand across BU, pipeline health per role, pending override requests, workforce-plan-vs-actuals, headcount budget) exists anywhere. |
| S-104 | HRMS-P209 | Org Role Mapping to Portal View | PARTIAL | no code references | `app/services/rbac_service.py:22-35` (role list), `:167-169` (revenue.view / revenue.view_pnl BU-scoping, built 2026-08-05 per EPIC-02/03) / A real RBAC system exists with role-based, BU-scoped access already wired for t |
| S-105 | HRMS-P210 | Portal Notification Center | PARTIAL | re-verify (code touched after 08-22) | `app/api/v1/endpoints/notifications.py:1-60` (real `GET /notifications`, `POST /{id}/mark-read`, wired to already-shipped `notification_service.py`/HRMS-0113); `src/layout/TopBar.js:38-74,310-360` (bell icon, dropdown, u |

## EPIC-P3 — Proactive AI Nurture & Candidate Relationship Engine

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-119 | HRMS-P301 | Career Goal Conversation Engine | NOT-DONE | no code references | No 30-day-active/90-day-passive AI-initiated check-in conversation flow exists anywhere. |
| S-120 | HRMS-P302 | Personalized Value Messaging Engine | PARTIAL | no code references | `app/services/motivation_engine_service.py:1-50` (S-349 Proactive Motivation Engine) / A real, adjacent mechanism exists: it selects personalized outreach content keyed to a candidate's ranked `desire_category` (from S-3 |
| S-121 | HRMS-P303 | Candidate Relationship Score (CRS) | NOT-DONE | no code references | `app/models/candidate_desire_profile.py:37` (`engagement_level`: HOT/WARM/COOL/COLD) / No 0-100 weighted score matching the spec's formula (response rate 30% / sentiment 25% / time-since-contact 20% / interest signals 15 |
| S-122 | HRMS-P304 | Passive Candidate Nurture Campaign | NOT-DONE | no code references | `app/services/reactivation_campaign_service.py:1-57` (S-045, a different story) / The only related mechanism is S-045's unbounded reactivation-retry campaign, which is triggered by no-response (not a quarterly calendar c |
| S-123 | HRMS-P305 | Candidate Interest Signal Detection | NOT-DONE | no code references | grep for "interest_signal"/"title_stagnation": 0 hits; `candidate_desire_signal.py:27-30` (`SIGNAL_SOURCES`) / Desire-signal tracking captures chat/objection/sentiment/response-speed signals, but none of the specific rea |
| S-124 | HRMS-P306 | Nurture Campaign Scheduler & Config UI | NOT-DONE | re-verify (code touched after 08-22) | No admin UI for campaign timing/cadence/audience-segmentation/preview/pause-resume exists. |
| S-125 | HRMS-P307 | Nurture Campaign Analytics | NOT-DONE | no code references | No per-campaign reach/open/reply/conversion/CRS-change analytics found. |
| S-126 | HRMS-P308 | Candidate Re-Engagement on Market Signal | NOT-DONE | no code references | No mechanism ties open-demand spikes to automatic re-engagement of passive candidates. |
| S-127 | HRMS-P309 | WhatsApp Broadcast Compliance Engine | NOT-DONE | no code references | `app/models/consent.py` (general `ConsentRecord` opt-in/out exists for outreach broadly) / A general consent/opt-out system exists and gates Thunder's WhatsApp sends generically, which is conceptually adjacent. But there |

## EPIC-P4 — LinkedIn Autonomous Sourcing Pipeline (9 stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-128 | HRMS-P401 | Nightly keyword LinkedIn crawl (Playwright) | NOT-DONE | no code references | — |
| S-129 | HRMS-P402 | Profile dedup & skeleton creation | NOT-DONE | no code references | — |
| S-130 | HRMS-P403 | LinkedIn InMail AI outreach | NOT-DONE | no code references | — |
| S-131 | HRMS-P404 | Human recruiter contact queue | NOT-DONE | no code references | — |
| S-132 | HRMS-P405 | Profile enrichment pipeline | NOT-DONE | no code references | — |
| S-133 | HRMS-P406 | Session & rate-limit management | NOT-DONE | no code references | — |
| S-134 | HRMS-P407 | Sourcing analytics dashboard | NOT-DONE | no code references | — |
| S-135 | HRMS-P408 | Configurable keywords & filters | NOT-DONE | no code references | — |
| S-136 | HRMS-P409 | Profile quality scoring | NOT-DONE | no code references | — |

## EPIC-P5 — HTD (Hire Train Deploy) Model (5 in-scope stories)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-257 | HRMS-P501 | HTD job track configuration (Jobs tagged TRACK=HTD, Java depth required, Guidewire not required) | NOT-DONE | no code references | `app/models/employee.py:156-158` has `htd_track` (Boolean), `htd_phase`, `htd_start_date` — but on `Employee` (post-hire), not on `Demand`/`Jobs` (pre-hire job posting). `grep -n "track" app/models/demand.py` finds no HT |
| S-258 | HRMS-P502 | HTD candidate identification engine (Java 5yr+ scan, HTD_readiness scoring) | NOT-DONE | no code references | No scoring model, no DB scan job. |
| S-261 | HRMS-P505 | HTD internal interview process (L1 Java tech by Tech Lead, L2 learning aptitude by Tech Manager, Director decision, no client involvement) | NOT-DONE | no code references | `htd_phase_gate_service.py`'s 4 phases (`app/models/htd_phase_gate.py:20`) are INDUCTION/SHADOW_DELIVERY/CONTROLLED_OWNERSHIP/CORE_ELIGIBILITY_REVIEW — all post-hire training gates, not a pre-hire interview process. No " |
| S-264 | HRMS-P508 | HTD deployment readiness checklist (training+assessment+interview+docs+BU Head sign-off → auto readiness report → deployable Guidewire pool) | PARTIAL | no code references | `app/services/htd_phase_gate_service.py:132-137`: passing all 4 phase gates (last one requiring `HEMANT_BU_HEAD` sign-off) sets `employee.htd_phase = "COMPLETED"`. This is `S-360/HRMS-P506-REV`, not `HRMS-P508`. / Real B |
| S-266 | HRMS-P510 | HTD vs Standard track reporting (cost/hire, time-to-deploy, revenue/head, 12-mo retention) | NOT-DONE | no code references | — |

## EPIC-P6 — Interview Decision Engine & Compliance Rules (12 stories) — primary focus

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-107 | HRMS-P601 | Experience Eligibility Engine — <5yr hard rule, flag INELIGIBLE, block from interview | PARTIAL | re-verify (code touched after 08-22) | `app/services/submission_service.py:77-95` `check_experience_eligibility()` — real 60-month gate, tested (`tests/test_submission_interview_pipeline.py:134-152`, 3 passing tests incl. NULL=ineligible). `app/api/v1/endpoin |
| S-109 | HRMS-P603 | Ineligibility auto-message (AI acknowledges, explains 5yr min, encourages reapply) | NOT-DONE | no code references | — |
| S-110 | HRMS-P604 | Experience override workflow (Director→BU Head sequential, both must approve, immutable audit log) | NOT-DONE | re-verify (code touched after 08-22) | Confirmed directly in the code's own docstring, not inferred from absence. |
| S-111 | HRMS-P605 | Override escalation notifications (WhatsApp+Email+portal, 24h SLA, auto-escalate) | NOT-DONE | re-verify (code touched after 08-22) | — |
| S-112 | HRMS-P606 | Two-level interview config (L1 Tech Lead / L2 Tech Manager per job track, 1-2 panelists/level) | PARTIAL | re-verify (code touched after 08-22) | `app/models/interview_pipeline.py:62-63` `INTERVIEW_LEVELS = ("L1","L2")` (fixed global enum, not per-job-track). `interview_service.py:138-148` enforces R-05 (L2 blocked until L1 outcome=PASS), tested (`test_l2_intervie |
| S-113 | HRMS-P607 | Panel split decision engine (2 panelists conflict → flag PANEL_SPLIT → HM final call) | NOT-DONE | re-verify (code touched after 08-22) | `SubmissionInterview` has exactly one `panel_id` (`interview_pipeline.py:109`) — the data model cannot represent two panelists' outcomes on one interview, so a "conflict" can't be detected. No `PANEL_SPLIT` status/flag a |
| S-114 | HRMS-P608 | L1 pass + L2 fail → auto-reject (BU Head-only reversal) | NOT-DONE | re-verify (code touched after 08-22) | `app/services/interview_service.py:12-15` (module docstring): *"R-05 (L1 must pass before L2) is enforced here... the one hard rule from this domain that's cheap to enforce for real **without importing HRMS-P608's full a |
| S-115 | HRMS-P609 | HM final hire decision UI (summary+feedback+AI rec+salary vs budget, Approve/Reject/Hold, Approve disabled until feedback viewed) | PARTIAL | no code references | `src/screens/HmCandidateReviewScreen.js` (frontend) is real and built, but it's `S-102/HRMS-P207` (the story's own declared DependsOn), not S-115/P609. Its own header comment: *"Approval/rejection itself happens on the e |
| S-116 | HRMS-P610 | Interview decision audit log (immutable, exportable, who/when/outcome/panel-split/override) | NOT-DONE | no code references | `app/models/conversation_audit_log.py` (`S-076/HRMS-0476`) is a real, insert-only audit log, but its own module docstring explicitly scopes it: *"The doc also lists offer releases (HRMS-0454/0456), override approvals (HR |
| S-117 | HRMS-P611 | Org authority map config (CEO→BU Head→Director→Tech Manager→Tech Lead→Sr Consultant, escalation paths) | NOT-DONE | no code references | `app/models/rbac.py:14-88` (`Role`/`RoleAttribute`/`Permission`/`RolePermission`) is a real, flat RBAC system with no hierarchy/escalation-chain field (no `reports_to`, no ordered rank). `bu_context_service.py:4-10` conf |
| S-118 | HRMS-P612 | Human dependency measurement dashboard (system-wide AI vs human % per stage, weekly trend, <20% target, alert on wrong-direction) | PARTIAL | re-verify (code touched after 08-22) | `app/services/thunder_analytics_service.py:39,104,140,144` computes `thunder_pct`/`human_intervention_rate` against a real `HUMAN_DEPENDENCY_TARGET_PCT = 20` constant, with a `trends` series (`_build_trends`, `thunder_an |

## EPIC-P7 — Client Portal (26 stories) — ALL NOT-DONE

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-169 | HRMS-P701 | Client User Account Creation & Mgmt | NOT-DONE | no code references | Clean zero-hit |
| S-170 | HRMS-P702 | Client Portal OTP Login & Scoped Session | NOT-DONE | no code references | Clean zero-hit |
| S-171 | HRMS-P703 | Client Portal Home Dashboard | NOT-DONE | re-verify (code touched after 08-22) | Clean zero-hit |
| S-172 | HRMS-P704 | Resume Submission — Client View List | NOT-DONE | no code references | Clean zero-hit |
| S-173 | HRMS-P705 | Resume Submission — Candidate Detail (client-safe) | NOT-DONE | no code references | Clean zero-hit |
| S-174 | HRMS-P706 | BlitzenX Submission Note — Mandatory | NOT-DONE | no code references | Clean zero-hit |
| S-175 | HRMS-P707 | Submission Status Real-Time Sync | NOT-DONE | no code references | Clean zero-hit |
| S-176 | HRMS-P708 | Client Action — Request Interview | NOT-DONE | no code references | Clean zero-hit |
| S-177 | HRMS-P709 | Client Action — Accept Candidate | NOT-DONE | no code references | Clean zero-hit |
| S-178 | HRMS-P710 | Client Action — Reject w/ Structured Feedback | NOT-DONE | no code references | Clean zero-hit |
| S-179 | HRMS-P711 | Client Action — Rank Multiple Candidates | NOT-DONE | no code references | Clean zero-hit |
| S-180 | HRMS-P712 | Client Action — Request Additional Resumes | NOT-DONE | no code references | Clean zero-hit |
| S-181 | HRMS-P713 | Timesheet → Client Reporting Manager Notification | NOT-DONE | no code references | Clean zero-hit |
| S-182 | HRMS-P714 | Client Timesheet Approval — Portal View | NOT-DONE | no code references | Clean zero-hit |
| S-183 | HRMS-P715 | Client Timesheet — Reassign Approver | NOT-DONE | no code references | Clean zero-hit |
| S-184 | HRMS-P716 | Timesheet Correction/History/SLA (merged) | NOT-DONE | no code references | Clean zero-hit |
| S-187 | HRMS-P719 | RFP Intake/AI Extraction/Demand Creation (merged) | NOT-DONE | no code references | Clean zero-hit |
| S-190 | HRMS-P722 | RFP Status Tracking — Client View | NOT-DONE | no code references | Clean zero-hit |
| S-191 | HRMS-P723 | RFP Clarification Request Flow | NOT-DONE | no code references | Clean zero-hit |
| S-192 | HRMS-P724 | RFP AI Auto-Sourcing w/ Human Handoff | NOT-DONE | no code references | Clean zero-hit |
| S-193 | HRMS-P725 | Client Messaging — CS Thread | NOT-DONE | no code references | Clean zero-hit |
| S-194 | HRMS-P726 | Automated Client Notification Engine | NOT-DONE | no code references | Clean zero-hit |
| S-195 | HRMS-P727 | Client Communication Archive & Search | NOT-DONE | no code references | Clean zero-hit |
| S-196 | HRMS-P728 | Client Dashboard — Delivery Health | NOT-DONE | no code references | Clean zero-hit |
| S-197 | HRMS-P729 | Client Analytics — Submission & Hiring Metrics | NOT-DONE | re-verify (code touched after 08-22) | Clean zero-hit |
| S-198 | HRMS-P730 | Client Health Score — Internal View | NOT-DONE | no code references | Clean zero-hit |

## EPIC-P8 — Sub-Vendor Portal (15 stories) — SURPRISE: substantial real backend

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-137 | HRMS-P801 | Sub-Vendor Account Creation & Mgmt | PARTIAL | re-verify (code touched after 08-22) | Real model+service+test; no admin API/UI to invoke it |
| S-138 | HRMS-P802 | Sub-Vendor Portal Login & Scoped Access | NOT-DONE | re-verify (code touched after 08-22) | Model exists, login path does not; spec calls for OTP, model uses password — a deviation too, on top of being unwired |
| S-139 | HRMS-P803 | Recruiter — Send Request to Sub-Vendor | PARTIAL | no code references | Service real; no recruiter-facing endpoint/UI found |
| S-140 | HRMS-P804 | Sub-Vendor — View Open Requests | PARTIAL | re-verify (code touched after 08-22) | Write path real, dedicated read path not implemented |
| S-141 | HRMS-P805 | Sub-Vendor — Submit Candidate Profile | PARTIAL | no code references | Service real; no vendor-facing submission form/endpoint |
| S-144 | HRMS-P808 | Recruiter — Sub-Vendor Submission Review | PARTIAL | re-verify (code touched after 08-22) | Service real, incl. `create_candidate_safe()` on accept; no recruiter queue UI/endpoint, no bulk-action support found |
| S-146 | HRMS-P810 | Sub-Vendor Submission Status — Vendor View | PARTIAL | no code references | Read-model real (incl. isolation boundary + feedback_note surfaced on reject); no vendor-facing endpoint |
| S-147 | HRMS-P811 | Sub-Vendor Governance Agent (merged) | PARTIAL | re-verify (code touched after 08-22) | `sub_vendor_service.py:85-103` `close_expired_requests()`; `sub_vendor_submission_service.py:162-203` `evaluate_compliance_escalation()`/`confirm_suspension()`, tested (5 tests incl. `test_three_violations_trigger_under_ |
| S-148 | HRMS-P812 | Sub-Vendor Scorecard & Analytics Dashboard | PARTIAL | no code references | Computed metrics real (acceptance rate, FT violations, dedup count, source-channel contribution); no Admin-facing dashboard UI/endpoint — docstring says so explicitly |
| S-150 | HRMS-P814 | Sub-Vendor — Request for Clarification | PARTIAL | re-verify (code touched after 08-22) | Service real; no portal UI/endpoint for vendor or recruiter to use it |

## EPIC-P9 — Boolean Search & AI Search Intelligence (14 stories) — ALL NOT-DONE (one adjacent partial)

| Story | WROS ID | Summary | Status | Signal today | Gap (from verification) |
|---|---|---|---|---|---|
| S-155 | HRMS-P901 | Auto-Generate Boolean Search per Job | NOT-DONE | no code references | Direct first-party confirmation |
| S-156 | HRMS-P902 | Skill Synonym Library | PARTIAL | no code references | Built under S-029/HRMS-0429, not P902; hardcoded constant, not admin-editable; not wired to Boolean string generation |
| S-157 | HRMS-P903 | Boolean Search — Internal DB Search | NOT-DONE | no code references | Clean zero-hit beyond false positives |
| S-158 | HRMS-P904 | Boolean Search — LinkedIn Integration | NOT-DONE | no code references | Confirmed not built |
| S-159 | HRMS-P905 | Boolean Search — Job Board Integration | NOT-DONE | no code references | Clean zero-hit |
| S-160 | HRMS-P906 | Recruiter Boolean Search Editor | NOT-DONE | no code references | Clean zero-hit |
| S-161 | HRMS-P907 | Boolean Search Results Dashboard | NOT-DONE | no code references | Clean zero-hit |
| S-162 | HRMS-P908 | AI Search Refinement Suggestions | NOT-DONE | no code references | Clean zero-hit |
| S-163 | HRMS-P909 | Multi-Continent Candidate Pool Architecture | NOT-DONE | no code references | Clean zero-hit |
| S-164 | HRMS-P910 | Work Authorization Filter in Search | NOT-DONE | no code references | Clean zero-hit |
| S-165 | HRMS-P911 | Search History & Saved Searches | NOT-DONE | no code references | Clean zero-hit |
| S-166 | HRMS-P912 | Boolean Search → AI Recruiter Pipeline | NOT-DONE | no code references | Clean zero-hit |
| S-167 | HRMS-P913 | Continent-Aware Salary Benchmarking | NOT-DONE | no code references | Clean zero-hit |
| S-168 | HRMS-P914 | Search Effectiveness Analytics | NOT-DONE | no code references | Clean zero-hit |

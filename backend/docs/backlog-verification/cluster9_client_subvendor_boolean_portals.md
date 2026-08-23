# Cluster 9 verification: EPIC-P7 Client Portal / EPIC-P8 Sub-Vendor Portal / EPIC-P9 Boolean Search

Verified directly against code in:
- Backend: `C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Backend`
- Frontend: `C:\Users\AvinashMukund\Documents\Claude\OnboardingModule-Frontend-main`

Sheet claims all three epics are 0% Done. **That claim is correct for EPIC-P7 and
EPIC-P9. It is WRONG for EPIC-P8** — a real, tested backend domain (models +
services + a verified Alembic migration) exists for Sub-Vendor Portal, built under
its own HRMS-P8xx IDs, covering most of S-137–S-154's business logic. However,
**no REST API endpoints and no frontend UI exist for any of it** — a recruiter or
vendor could not actually use this today. See "EPIC-P8 surprise" note below.

## EPIC-P7 — Client Portal (26 stories) — ALL NOT-DONE

No `client_user`, `ClientUser`, `ClientPortal`, RFP, or client-portal-specific model,
service, endpoint, or frontend screen exists anywhere in either repo. Grep for
`client_user|ClientUser|ClientPortal|client_portal` and `RFP|client_reporting_manager`
across the backend returned zero real hits (only unrelated files like
`employee_allocation.py`, `timesheet.py` matching on unrelated substrings). Frontend
grep for `RFP|ClientPortal|client.?user|client.?portal` returned zero source hits
(only `package-lock.json` noise).

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S-169 | HRMS-P701 | Client User Account Creation & Mgmt | Planned | NOT-DONE | No `client_user`/`ClientUser` model or service anywhere in backend | Clean zero-hit |
| S-170 | HRMS-P702 | Client Portal OTP Login & Scoped Session | Planned | NOT-DONE | No OTP/session code scoped to client users | Clean zero-hit |
| S-171 | HRMS-P703 | Client Portal Home Dashboard | Planned | NOT-DONE | No matching screen/endpoint | Clean zero-hit |
| S-172 | HRMS-P704 | Resume Submission — Client View List | Planned | NOT-DONE | No matching screen/endpoint | Clean zero-hit |
| S-173 | HRMS-P705 | Resume Submission — Candidate Detail (client-safe) | Planned | NOT-DONE | No matching screen/endpoint | Clean zero-hit |
| S-174 | HRMS-P706 | BlitzenX Submission Note — Mandatory | Planned | NOT-DONE | No matching field/validation | Clean zero-hit |
| S-175 | HRMS-P707 | Submission Status Real-Time Sync | Planned | NOT-DONE | No matching sync logic | Clean zero-hit |
| S-176 | HRMS-P708 | Client Action — Request Interview | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-177 | HRMS-P709 | Client Action — Accept Candidate | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-178 | HRMS-P710 | Client Action — Reject w/ Structured Feedback | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-179 | HRMS-P711 | Client Action — Rank Multiple Candidates | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-180 | HRMS-P712 | Client Action — Request Additional Resumes | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-181 | HRMS-P713 | Timesheet → Client Reporting Manager Notification | Planned | NOT-DONE | No `client_reporting_manager` field on allocation model | Clean zero-hit |
| S-182 | HRMS-P714 | Client Timesheet Approval — Portal View | Planned | NOT-DONE | No matching screen/endpoint | Clean zero-hit |
| S-183 | HRMS-P715 | Client Timesheet — Reassign Approver | Planned | NOT-DONE | No matching endpoint | Clean zero-hit |
| S-184 | HRMS-P716 | Timesheet Correction/History/SLA (merged) | Planned | NOT-DONE | No matching logic | Clean zero-hit |
| S-187 | HRMS-P719 | RFP Intake/AI Extraction/Demand Creation (merged) | Planned | NOT-DONE | No `RFP` model/table anywhere | Clean zero-hit |
| S-190 | HRMS-P722 | RFP Status Tracking — Client View | Planned | NOT-DONE | No `RFP` model/table anywhere | Clean zero-hit |
| S-191 | HRMS-P723 | RFP Clarification Request Flow | Planned | NOT-DONE | No `RFP` model/table anywhere | Clean zero-hit |
| S-192 | HRMS-P724 | RFP AI Auto-Sourcing w/ Human Handoff | Planned | NOT-DONE | No `RFP` model/table anywhere | Clean zero-hit |
| S-193 | HRMS-P725 | Client Messaging — CS Thread | Planned | NOT-DONE | No matching thread model | Clean zero-hit |
| S-194 | HRMS-P726 | Automated Client Notification Engine | Planned | NOT-DONE | No matching service | Clean zero-hit |
| S-195 | HRMS-P727 | Client Communication Archive & Search | Planned | NOT-DONE | No matching service | Clean zero-hit |
| S-196 | HRMS-P728 | Client Dashboard — Delivery Health | Planned | NOT-DONE | No matching screen/endpoint | Clean zero-hit |
| S-197 | HRMS-P729 | Client Analytics — Submission & Hiring Metrics | Planned | NOT-DONE | No matching service | Clean zero-hit |
| S-198 | HRMS-P730 | Client Health Score — Internal View | Planned | NOT-DONE | No matching service | Clean zero-hit |

## EPIC-P8 — Sub-Vendor Portal (15 stories) — SURPRISE: substantial real backend

Real files found (all under HRMS-P8xx IDs in their own docstrings, built as a
distinct pass, "Domain 5, greenfield" per `app/models/sub_vendor.py` header):

- `app/models/sub_vendor.py` — `SubVendorAccount`, `SubVendorRequest`, `ClarificationQA`, `SubVendorUser`
- `app/models/sub_vendor_submission.py` — `SubVendorSubmission`, `SubVendorViolation`, `SubVendorDedupRejection`
- `app/services/sub_vendor_service.py` — registration/approval/suspension, request creation, deadline auto-close
- `app/services/sub_vendor_submission_service.py` — FT-only gate, dedup, accept/reject/request-more-info, compliance escalation
- `app/services/sub_vendor_qa_service.py` — clarification Q&A
- `app/services/sub_vendor_tracking_service.py` — vendor-facing status list, scorecard, portfolio analytics
- `alembic/versions/b8c9d0e1f2a4_add_sub_vendor_portal.py` — real migration, verified against throwaway SQLite; docstring notes it should be re-verified on SQL Server staging before prod
- Tests: `tests/test_sub_vendor_portal.py`, `tests/test_sub_vendor_tracking_and_qa.py`, `tests/test_sub_vendor_ats_integration.py` — 19+13+3 real test functions, not stubs

**Critical gap, confirmed by explicit grep and by the tracking service's own
docstring** ("enforcement of that visibility rule is an API-layer concern (no REST
endpoints exist yet for this domain)"): `app/api/v1/endpoints/` has **zero**
sub-vendor routes (only a stray, unrelated `sub_vendor` mention inside
`submissions.py` turned out to be a false grep match on `subvendor_id` — no route
registered). Frontend grep (`sub.?vendor|subvendor`, case-insensitive) across the
entire frontend repo returned **zero files**. There is no login endpoint/function
for `SubVendorUser` either (`password_hash` is set on creation via
`get_password_hash()`, but no `authenticate`/`login` function exists anywhere) — so
even S-138 (login) has no working path end-to-end today.

Net effect: the domain logic (FT-only gate, dedup, compliance escalation, source
tagging) is real, correct, and unit-tested. But nobody — vendor or recruiter — can
actually reach any of it through the product today. Classified PARTIAL throughout
except for the purely internal enforcement/tagging rules, which are CONFIRMED-DONE
on their own terms (they fire correctly whenever the service functions are called,
regardless of API/UI absence).

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S-137 | HRMS-P801 | Sub-Vendor Account Creation & Mgmt | Planned | PARTIAL | `app/models/sub_vendor.py:43-69` `SubVendorAccount`; `app/services/sub_vendor_service.py:19-42` register/approve/suspend; `tests/test_sub_vendor_portal.py:109` | Real model+service+test; no admin API/UI to invoke it |
| S-138 | HRMS-P802 | Sub-Vendor Portal Login & Scoped Access | Planned | NOT-DONE | `app/models/sub_vendor.py:124-139` `SubVendorUser` has `password_hash` but no `authenticate`/`login` function found anywhere in `app/services` or `app/api` | Model exists, login path does not; spec calls for OTP, model uses password — a deviation too, on top of being unwired |
| S-139 | HRMS-P803 | Recruiter — Send Request to Sub-Vendor | Planned | PARTIAL | `app/services/sub_vendor_service.py:64-82` `create_sub_vendor_request()`, tested `test_request_requires_approved_vendor` | Service real; no recruiter-facing endpoint/UI found |
| S-140 | HRMS-P804 | Sub-Vendor — View Open Requests | Planned | PARTIAL | `SubVendorRequest` model exists (`app/models/sub_vendor.py:71-98`) but no "list open requests for this vendor" query function found in any service | Write path real, dedicated read path not implemented |
| S-141 | HRMS-P805 | Sub-Vendor — Submit Candidate Profile | Planned | PARTIAL | `app/services/sub_vendor_submission_service.py:43-103` `submit_candidate()`, tested | Service real; no vendor-facing submission form/endpoint |
| S-142 | HRMS-P806 | FT-Only Enforcement Engine | Planned | CONFIRMED-DONE | `sub_vendor_submission_service.py:82-90` rejects non-`W2_FULLTIME`, logs `SubVendorViolation`; tests `test_submission_rejected_for_c2c`, `test_submission_accepted_gate_passes_for_w2` | Server-side gate is real and correctly enforced whenever the function is called |
| S-143 | HRMS-P807 | Sub-Vendor Candidate Dedup vs Internal DB | Planned | CONFIRMED-DONE | `sub_vendor_submission_service.py:92-101` calls `find_duplicate_candidate()` (same function as main pipeline), never reveals matched candidate; test `test_submission_rejected_on_email_dedup` | Reuses real, existing dedup — not reimplemented |
| S-144 | HRMS-P808 | Recruiter — Sub-Vendor Submission Review | Planned | PARTIAL | `sub_vendor_submission_service.py:111-159` accept/reject/request_more_info, tested (`test_accept_submission_creates_real_candidate_with_source_tag`, `test_reject_requires_min_20_char_feedback`) | Service real, incl. `create_candidate_safe()` on accept; no recruiter queue UI/endpoint, no bulk-action support found |
| S-145 | HRMS-P809 | Sub-Vendor Candidate — AI Recruiter Onboarding | Planned | CONFIRMED-DONE | `tests/test_sub_vendor_ats_integration.py:1-12` — explicit verification-only story per its own spec; test confirms zero `source_channel` branching anywhere in `submission_service.py`/`interview_service.py`/`candidate_service.py`, so the existing (pre-built) AI-recruiter pipeline applies identically | Narrow "verification" story is genuinely satisfied; general AI-recruiter trigger itself is built elsewhere, out of this cluster |
| S-146 | HRMS-P810 | Sub-Vendor Submission Status — Vendor View | Planned | PARTIAL | `app/services/sub_vendor_tracking_service.py:30-57` `get_submissions_for_vendor()`, tested `test_vendor_sees_only_own_submissions` | Read-model real (incl. isolation boundary + feedback_note surfaced on reject); no vendor-facing endpoint |
| S-147 | HRMS-P811 | Sub-Vendor Governance Agent (merged) | Planned | PARTIAL | `sub_vendor_service.py:85-103` `close_expired_requests()`; `sub_vendor_submission_service.py:162-203` `evaluate_compliance_escalation()`/`confirm_suspension()`, tested (5 tests incl. `test_three_violations_trigger_under_review`, `test_five_violations_trigger_suspension_pending_not_suspended`) | Logic real and correctly thresholded (3→UNDER_REVIEW, 5→SUSPENSION_PENDING, admin must confirm SUSPENDED); explicitly **not wired to a scheduler** per its own docstring, so day-before reminders/auto-close don't run on their own today |
| S-148 | HRMS-P812 | Sub-Vendor Scorecard & Analytics Dashboard | Planned | PARTIAL | `sub_vendor_tracking_service.py:60-126` `get_sub_vendor_scorecard()` + `get_sub_vendor_portfolio_analytics()`, tested | Computed metrics real (acceptance rate, FT violations, dedup count, source-channel contribution); no Admin-facing dashboard UI/endpoint — docstring says so explicitly |
| S-150 | HRMS-P814 | Sub-Vendor — Request for Clarification | Planned | PARTIAL | `app/services/sub_vendor_qa_service.py` full ask/answer flow incl. shared visibility, tested (4 tests incl. `test_answered_question_visible_to_other_vendor_on_same_request`) | Service real; no portal UI/endpoint for vendor or recruiter to use it |
| S-152 | HRMS-P816 | Sub-Vendor Candidate — Source Tagging | Planned | CONFIRMED-DONE | `app/models/candidate.py:75-79` `source_channel`/`vendor_id` columns; set in `sub_vendor_submission_service.py:129-130` (`source_channel="SUBVENDOR", vendor_id=submission.sub_vendor_id`) inside `accept_submission()`; `test_accept_submission_creates_real_candidate_with_source_tag`, `test_portfolio_analytics_reflects_source_channel_tagging` | Pure backend tagging, fully wired end-to-end and tested |
| S-154 | HRMS-P818 | Sub-Vendor Candidate — WROS ATS Integration | Planned | CONFIRMED-DONE | `tests/test_sub_vendor_ats_integration.py` — verification-only story per spec; proves R-01 (experience gate) and R-05 (L1-before-L2) apply identically to subvendor-sourced submissions, no source-based branching in `submission_service.py`/`interview_service.py` | Genuinely satisfied on its own (narrow, verification) terms |

## EPIC-P9 — Boolean Search & AI Search Intelligence (14 stories) — ALL NOT-DONE (one adjacent partial)

Definitive first-party confirmation that this epic was never built: the docstring of
`app/services/linkedin_sourcing_service.py` (HRMS-1103, a different/later epic that
would *consume* EPIC-P9's output) explicitly lists as an unresolved external
dependency:

> "EPIC-P9 Boolean Search Engine (query execution against LinkedIn Recruiter API) —
> doesn't exist in this codebase."

Grep for `boolean_string|boolean search|BooleanSearch|generate_boolean|match_score`
across the backend returned no real hits (all `boolean` case-insensitive hits
elsewhere in the codebase are SQLAlchemy `Boolean` column-type declarations, a
false-positive pattern, not the search feature). `Candidate` model has no
`country_code`/`continent`/`currency`/`work_authorization` fields (only an unrelated
`timezone` column exists). Frontend grep for
`boolean|synonym|BooleanSearch|search.?editor|match.?score` matched only generic
JS boolean-prop usage in unrelated screens (`CandidateSearch.js`, `AuthPage.js`,
etc.), not a Boolean-search feature.

One adjacent partial: `app/constants/skill_synonyms.py` + `app/services/skill_extraction_service.py`
were built under a **different** story (S-029/HRMS-0429, general resume skill
tagging), but functionally overlap with S-156's synonym-library requirement
(`Guidewire` → `[GW, GWPC, GWCC, ...]`, `Java` → `[J2EE, Core Java, ...]`, etc.,
same worked examples from the spec). It's a hardcoded Python constant, not
admin-editable via any UI, and isn't wired into a Boolean-string generator — so it
only partially satisfies S-156, and doesn't touch S-155/157–168 at all.

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S-155 | HRMS-P901 | Auto-Generate Boolean Search per Job | Planned | NOT-DONE | `linkedin_sourcing_service.py` docstring: "EPIC-P9 Boolean Search Engine ... doesn't exist in this codebase" | Direct first-party confirmation |
| S-156 | HRMS-P902 | Skill Synonym Library | Planned | PARTIAL | `app/constants/skill_synonyms.py` (Guidewire/Java/SQL/Python/AWS clusters) + `app/services/skill_extraction_service.py:32-56` `normalize_skills()` | Built under S-029/HRMS-0429, not P902; hardcoded constant, not admin-editable; not wired to Boolean string generation |
| S-157 | HRMS-P903 | Boolean Search — Internal DB Search | Planned | NOT-DONE | No matching service/endpoint | Clean zero-hit beyond false positives |
| S-158 | HRMS-P904 | Boolean Search — LinkedIn Integration | Planned | NOT-DONE | `linkedin_sourcing_service.py` explicitly treats this as a non-existent external dependency it merely injects a callable for | Confirmed not built |
| S-159 | HRMS-P905 | Boolean Search — Job Board Integration | Planned | NOT-DONE | No matching service/endpoint | Clean zero-hit |
| S-160 | HRMS-P906 | Recruiter Boolean Search Editor | Planned | NOT-DONE | No matching UI/endpoint | Clean zero-hit |
| S-161 | HRMS-P907 | Boolean Search Results Dashboard | Planned | NOT-DONE | No matching UI/endpoint | Clean zero-hit |
| S-162 | HRMS-P908 | AI Search Refinement Suggestions | Planned | NOT-DONE | No matching service | Clean zero-hit |
| S-163 | HRMS-P909 | Multi-Continent Candidate Pool Architecture | Planned | NOT-DONE | `app/models/candidate.py` has no `country_code`/`continent`/`currency`/`work_authorization` columns (only unrelated `timezone`) | Clean zero-hit |
| S-164 | HRMS-P910 | Work Authorization Filter in Search | Planned | NOT-DONE | No `work_authorization` field anywhere in backend | Clean zero-hit |
| S-165 | HRMS-P911 | Search History & Saved Searches | Planned | NOT-DONE | No matching model/service | Clean zero-hit |
| S-166 | HRMS-P912 | Boolean Search → AI Recruiter Pipeline | Planned | NOT-DONE | No matching trigger; depends on non-existent P901/P904 | Clean zero-hit |
| S-167 | HRMS-P913 | Continent-Aware Salary Benchmarking | Planned | NOT-DONE | No continent/currency fields to benchmark against | Clean zero-hit |
| S-168 | HRMS-P914 | Search Effectiveness Analytics | Planned | NOT-DONE | No matching model/service | Clean zero-hit |

## Summary counts

- **EPIC-P7 (26 stories):** 26 NOT-DONE, 0 other.
- **EPIC-P8 (15 stories):** 4 CONFIRMED-DONE (S-142, S-143, S-152, S-154), 9 PARTIAL (S-137, S-139, S-140, S-141, S-144, S-146, S-147, S-148, S-150), 1 NOT-DONE (S-138), 1 more counted above — total 15.
- **EPIC-P9 (14 stories):** 13 NOT-DONE, 1 PARTIAL (S-156, via an adjacent story built under a different ID).
- **Grand total (55 stories):** 4 CONFIRMED-DONE, 10 PARTIAL, 41 NOT-DONE, 0 CANT-DETERMINE.

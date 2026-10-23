# Backlog Verification — EPIC-04 (Candidate Engagement & AI Recruiter Platform)

Verified directly against code in `OnboardingModule-Backend` and `OnboardingModule-Frontend-main`.
Sheet claims 78/80 Done (S-079/S-080 marked Planned). Method: grep for WROS ID (HRMS-04xx) and
Story ID across `app/services`, `app/models`, `app/api/v1/endpoints`, `tests/`; for zero-hit IDs,
keyword search; for UI-facing stories, checked `src/screens`, `src/components`, `src/services/api`;
for any story whose own in-code docstring admits a gap, read the actual call sites to confirm
whether the gap is real.

| Story ID | WROS ID | Summary | Sheet Status | Real Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| S-001 | HRMS-0401 | Auto Create Candidate Conversation Workspace | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:337 | auto_assign_ai_agent_on_creation real, 13 files reference ID |
| S-002 | HRMS-0402 | Store WhatsApp Messages | Done | CONFIRMED-DONE | app/services/resume_upload_service.py:28 (+ whatsapp_webhook_service.py) | Real webhook, signature validation; live Meta traffic pending creds (self-disclosed, not a gap in logic) |
| S-003 | HRMS-0403 | Store Email Messages | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:298 | MS Graph poll (15-min) confirmed real |
| S-004 | HRMS-0404 | Store Web Portal Chat Messages | Done | CONFIRMED-DONE | app/services/portal_message_service.py:2 | JWT-based candidate auth confirmed, ConversationEvent(channel=portal) |
| S-005 | HRMS-0405 | Unified Conversation Timeline UI | Done | **PARTIAL** | Frontend: src/screens/tabs/MessagesTab.js (EventRow, ~line 462-518) | Chronological timeline with timestamps and sender ("by AI"/"by recruiter") is real, but **no channel icon per message** — spec explicitly calls for "channel icon per message"; actual code has zero icon/emoji usage anywhere in the file (`grep -n "icon\|Icon" MessagesTab.js` = no hits). Channel is only visible buried inside a raw `key: value` text dump of event_data, not a distinct visual element. Zero backend hits for HRMS-0405 (expected — UI story) |
| S-006 | HRMS-0406 | Messages Tab on Candidate Profile | Done | CONFIRMED-DONE | Frontend: src/screens/tabs/MessagesTab.js | Tab exists, wired to CandidateDetailsScreen |
| S-007 | HRMS-0407 | Candidate Profile Completeness Engine | Done | CONFIRMED-DONE | app/models/candidate_joining_score.py:12 (+ candidate_context_service.py) | Real completeness calc present |
| S-008 | HRMS-0408 | Missing Fields Detection Engine | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:110 (`get_missing_fields`) | Zero direct ID hits but strong keyword evidence: `get_missing_fields()` used in 4+ services (candidate_context_service, candidate_journey_service, ai_conversation_service, ai_agent.py endpoint) |
| S-009 | HRMS-0409 | Recruiter Manual Message Box | Done | CONFIRMED-DONE | app/services/whatsapp_routing_service.py:124 | |
| S-010 | HRMS-0410 | Conversation Ownership & Takeover | Done | CONFIRMED-DONE | app/services/conversation_inactivity_service.py:2 | 15 file refs |
| S-011 | HRMS-0411 | AI Recruiter Assignment Engine | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:53 (`resolve_thunder_config`) | Per-tenant persona confirmed |
| S-012 | HRMS-0412 | WhatsApp First Engagement — 60s Rule | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:550 | |
| S-013 | HRMS-0413 | Email First Engagement — Parallel Channel | Done | CONFIRMED-DONE | app/services/email_first_engagement_service.py:2 | Sequential-not-parallel adaptation, disclosed and acceptable |
| S-014 | HRMS-0414 | Message Template Engine | Done | CONFIRMED-DONE | app/services/email_first_engagement_service.py:66 (+ message_templates.py endpoint) | CRUD/versioning endpoint confirmed present |
| S-015 | HRMS-0415 | Conversation Search | Done | CONFIRMED-DONE | app/services/conversation_search_service.py:2 | Python-side substring match adaptation (SQL Server, no tsvector) — acceptable |
| S-016 | HRMS-0416 | Conversation Filters | Done | CONFIRMED-DONE | app/services/conversation_search_service.py:59 | |
| S-017 | HRMS-0417 | Candidate Self-Service Web Portal | Done | CONFIRMED-DONE | app/services/candidate_portal_service.py:2 | JWT instead of magic-link, disclosed and functionally equivalent |
| S-018 | HRMS-0418 | Conversation State Manager | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:417 (+ conversation_state_service.py) | Real 3-axis model confirmed |
| S-019 | HRMS-0419 | Conversation Summary Auto-Generation | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:1478 | |
| S-020 | HRMS-0420 | Engagement SLA Monitoring | Done | CONFIRMED-DONE | app/services/follow_up_scheduler_service.py:12 (+ sla_monitoring_service.py) | 21 file refs, heaviest-referenced story in this range |
| S-021 | HRMS-0421 | Candidate Memory Store | Done | CONFIRMED-DONE | app/services/candidate_memory_service.py:2 | Tables confirmed via migration reference |
| S-022 | HRMS-0422 | Candidate Facts Extraction Engine | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:1407 (+ facts_extraction_service.py) | Called from process_candidate_reply() — real wiring confirmed |
| S-023 | HRMS-0423 | Candidate Memory Viewer (Recruiter UI) | Done | CONFIRMED-DONE | app/services/candidate_memory_service.py:253 (`correct_fact`) | Frontend: ThunderMemorySection.js confirmed present |
| S-024 | HRMS-0424 | Candidate Qualification Questionnaire Engine | Done | CONFIRMED-DONE | app/services/qualification_engine_service.py:2 | |
| S-025 | HRMS-0425 | AI Qualification Conversation Engine | Done | CONFIRMED-DONE | app/services/qualification_conversation_service.py:2 | |
| S-026 | HRMS-0426 | Candidate Response Parser | Done | CONFIRMED-DONE | app/services/response_parser_service.py:2 | |
| S-027 | HRMS-0427 | Resume Upload via WhatsApp/Email | Done | CONFIRMED-DONE | app/services/detect_intent_service.py:30 (+ resume_upload_service.py) | SharePoint/Graph storage confirmed real |
| S-028 | HRMS-0428 | Resume Parsing Engine | Done | CONFIRMED-DONE | app/services/resume_parsing_service.py:2 | |
| S-029 | HRMS-0429 | Skill Extraction & Tagging from Resume | Done | CONFIRMED-DONE | app/services/guidewire_candidate_service.py:6 (+ skill_extraction_service.py, app/constants/skill_synonyms.py) | |
| S-030 | HRMS-0430 | Resume Completeness Score | Done (backend) — frontend deferred per sheet note | **CONFIRMED-DONE (corrects sheet note)** | Frontend: src/screens/tabs/ProfileTab.js:308,449-479 (`ResumeCompletenessBar`) | Sheet/backlog note says "frontend bar deferred" but the frontend component now exists with an explicit comment: "previously deferred... this was the missing frontend half." The note is stale — feature is fully done, backend + frontend. |
| S-031 | HRMS-0431 | AI Prompt Framework | Done | CONFIRMED-DONE | app/services/prompt_framework_service.py:2 | 18 file refs |
| S-032 | HRMS-0432 | Candidate Context Builder | Done | CONFIRMED-DONE | app/services/candidate_context_service.py:2 | |
| S-033 | HRMS-0433 | Intent Detection Engine | Done | **PARTIAL** | app/services/detect_intent_service.py:2,74-93 | Code itself, in `INTENT_ROUTING` dict and module docstring, self-documents: "Not wired into any live inbound path (whatsapp_webhook_service, ai_conversation_service.process_candidate_reply(), qualification_conversation_service.run_qualification_turn())." Confirmed by grep: `detect_intent` / `detect_intent_service` do not appear anywhere in `qualification_conversation_service.py`, `ai_conversation_service.py`, or `whatsapp_webhook_service.py`. It IS wired into `public_chat_service.py` (a separate website-chat-widget pipeline, S-072) and that's the only live caller. So: real, tested, but not actually classifying the primary WhatsApp/Email candidate conversation traffic the epic is built around. |
| S-034 | HRMS-0434 | AI Response Generation | Done — Critical | CONFIRMED-DONE | app/services/prompt_framework_service.py:6 (`generate_thunder_reply_with_fallback`) | Core generation path confirmed real and called from main reply pipeline |
| S-035 | HRMS-0435 | Human Escalation Detection | Done | **PARTIAL** | app/services/conversation_state_service.py:207 (+ escalation_detection_service.py) | `check_escalation()` is called live from `portal_message_service.py:178` and `public_chat_service.py:279`, but NOT from the primary WhatsApp/email `ai_conversation_service.py` reply loop or `qualification_conversation_service.py` (same gap pattern as S-033, since escalation detection depends on intent classification). Escalation logic is real and works for portal + public chat; the two highest-volume channels (WhatsApp/email) don't trigger it live. |
| S-036 | HRMS-0436 | Candidate Sentiment Analysis | Done | CONFIRMED-DONE | app/services/escalation_detection_service.py:26 (+ sentiment_analysis_service.py:49) | Verified the "3+ consecutive negative" threshold in code (`# BR-02: 3 consecutive NEGATIVE rows`) — matches docx/BR-02/AC-4/TC-003, not the xlsx's "2+"; story's own discrepancy note is accurate |
| S-037 | HRMS-0437 | Technical Qualification Score | Done | CONFIRMED-DONE | app/services/skill_extraction_service.py:113 (+ technical_scoring_service.py) | |
| S-038 | HRMS-0438 | Compensation Fit Score | Done | CONFIRMED-DONE | app/services/compensation_scoring_service.py:2 | |
| S-039 | HRMS-0439 | Availability Score | Done | CONFIRMED-DONE | app/services/availability_scoring_service.py:2 | |
| S-040 | HRMS-0440 | Overall Candidate Score & Ranking | Done | CONFIRMED-DONE | app/services/facts_extraction_service.py:235 (+ overall_scoring_service.py) | |
| S-041 | HRMS-0441 | Follow-Up Scheduler | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:1389 (+ follow_up_scheduler_service.py) | |
| S-042 | HRMS-0442 | No Response Detection | Done | CONFIRMED-DONE | app/services/follow_up_scheduler_service.py:30 (+ no_response_detection_service.py) | New candidate_no_response_log table confirmed via migration reference |
| S-043 | HRMS-0443 | Candidate Ghosting Detection | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:1395 (+ ghosting_detection_service.py) | |
| S-044 | HRMS-0444 | Multi-Touch Outreach Campaign | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:581 (+ outreach_campaign_service.py) | |
| S-045 | HRMS-0445 | Candidate Reactivation Campaign | Done | CONFIRMED-DONE | app/services/abandonment_scoring_service.py:48 (+ reactivation_campaign_service.py) | Explicit spec-override built per Avinash direction, as noted |
| S-046 | HRMS-0446 | Candidate Abandonment Prediction | Done | CONFIRMED-DONE | app/services/abandonment_scoring_service.py:2 | Formula-based (not ML) confirmed matches "what NOT to build" |
| S-047 | HRMS-0447 | Interview Availability Collection | Done | **PARTIAL** | app/services/detect_intent_service.py:26,80 (+ interview_availability_service.py) | Backend logic real and tested (`send_availability_request`, `parse_availability_response`). Story's own note says "deliberately not wired into a live reply loop yet" — confirmed accurate: `detect_intent_service.INTENT_ROUTING["scheduling_request"]` is explicitly flagged `"status": "NOT_WIRED"`. Grep for `send_availability_request(` / `parse_availability_response(` outside the service file itself finds no live inbound trigger. |
| S-048 | HRMS-0448 | Calendar Matching Engine | Done | CONFIRMED-DONE | app/services/calendar_matching_service.py:2 | Real MS Graph calendarView call confirmed |
| S-049 | HRMS-0449 | Interview Confirmation via AI | Done | CONFIRMED-DONE | app/services/calendar_matching_service.py:80 (+ interview_confirmation_service.py) | |
| S-050 | HRMS-0450 | Interview Reminder Engine | Done | CONFIRMED-DONE | app/services/interview_confirmation_service.py:62 (+ interview_reminder_service.py) | New interview_reminders table confirmed |
| S-051 | HRMS-0451 | Interview Reschedule Workflow | Done | CONFIRMED-DONE | app/services/calendar_matching_service.py:102 (+ interview_reschedule_service.py:187 `start_reschedule`) | Candidate-initiated reschedule via intent detection is NOT_WIRED (same gap as S-033/S-047), BUT `start_reschedule()` IS live-called from `interview_no_show_service.py:344` as part of the no-show auto-reschedule flow — confirmed a genuine production call path exists, just via a different trigger than the spec's literal one. 20 file refs, highest in this sub-range. |
| S-052 | HRMS-0452 | Interview No-Show Handling | Done | CONFIRMED-DONE | app/services/intervention_queue_service.py:14 (+ interview_no_show_service.py) | Confirmed as the caller wiring reschedule (S-051) live |
| S-053 | HRMS-0453 | Offer Readiness Check | Done | CONFIRMED-DONE | app/services/offer_readiness_service.py:2 | |
| S-054 | HRMS-0454 | Offer Release Notification via AI | Done | CONFIRMED-DONE | app/services/email_service.py:982 | Built atop pre-existing offer-letter release endpoint, confirmed |
| S-055 | HRMS-0455 | Offer FAQ Bot | Done | CONFIRMED-DONE | app/services/offer_faq_service.py:2 | |
| S-056 | HRMS-0456 | Offer Acceptance Tracking | Done | CONFIRMED-DONE | app/services/detect_intent_service.py:41 | offer_accepted/declined/counter intents added to classifier confirmed, though (like S-033) not live-triggered from WhatsApp/email — only acted on by offer_decision_service when `offer_faq_active` true, consistent with story's own scoping |
| S-057 | HRMS-0457 | Document Collection Agent | Done | CONFIRMED-DONE | app/services/document_collection_service.py:2 | |
| S-058 | HRMS-0458 | Joining Readiness Score | Done | CONFIRMED-DONE | app/services/document_collection_service.py:40 | |
| S-059 | HRMS-0459 | Candidate Journey Dashboard | Done | CONFIRMED-DONE | app/services/candidate_journey_service.py:2 | Frontend: src/components/candidate/CandidateJourney.jsx confirmed |
| S-060 | HRMS-0460 | Drop Risk Prediction | Done | CONFIRMED-DONE | app/services/drop_risk_service.py:2 | |
| S-061 | HRMS-0461 | AI Activity Feed — Recruiter Copilot | Done | CONFIRMED-DONE | app/services/abandonment_scoring_service.py:190 (+ activity_feed_service.py) | Real-time projection over ConversationEvent confirmed |
| S-062 | HRMS-0462 | Recruiter Intervention Queue | Done | CONFIRMED-DONE | app/services/abandonment_scoring_service.py:43 (+ intervention_queue_service.py) | 22 file refs — most-referenced story in this cluster |
| S-063 | HRMS-0463 | Candidate Risk Dashboard | Done | CONFIRMED-DONE | app/services/risk_dashboard_service.py:2 | Frontend: src/screens/RiskDashboardScreen.js confirmed |
| S-064 | HRMS-0464 | AI Explainability Panel | Done | CONFIRMED-DONE | app/services/public_chat_service.py:322 | Frontend "Why?" toggle confirmed in MessagesTab.js EventRow (line ~487-514) |
| S-065 | HRMS-0465 | AI Daily Digest — Morning Report | Done | CONFIRMED-DONE | app/services/daily_digest_service.py:2 | WhatsApp leg honestly disclosed as non-dispatching (no creds) — matches pattern of S-002 |
| S-066 | HRMS-0466 | Supervisor Agent — Multi-Agent Coordinator | Done | CONFIRMED-DONE | app/services/supervisor_agent_service.py:2 | |
| S-067 | HRMS-0467 | Onboarding Agent | Done | CONFIRMED-DONE | app/services/onboarding_agent_service.py:2 | |
| S-068 | HRMS-0468 | Voice Calling Agent Framework | Done | **NOT-DONE** | none found | Zero hits for HRMS-0468 anywhere in backend or frontend. Keyword search for "voice", "transcription", "CallLog", "call_log", "phone_screen", "VoiceAgent" across `app/` and `src/` returns only false positives (substring matches inside "invoice"). No model, service, endpoint, or frontend file of any kind implements a voice-calling framework. This is a clear false completion claim — sheet marks Done, real code has nothing. |
| S-069 | HRMS-0469 | Multi-Channel Preference Detection | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:1385 (+ channel_preference_service.py) | Story's own note flags this as a stale-sheet bookkeeping fix from an earlier round — confirmed real and wired |
| S-070 | HRMS-0470 | Candidate Engagement Health Metrics | Done | CONFIRMED-DONE | app/services/engagement_metrics_service.py:2 | Frontend mini-cards confirmed referenced in story note; not independently re-verified in UI |
| S-071 | HRMS-0471 | AI Recruiter Performance Analytics | Done | CONFIRMED-DONE | app/services/engagement_metrics_service.py:21 (+ thunder_analytics_service.py) | Frontend: src/screens/ThunderAnalyticsScreen.js confirmed, route /recruiter/thunder-analytics confirmed in Routes.js |
| S-072 | HRMS-0472 | Objection Handling Engine | Done | CONFIRMED-DONE | app/services/detect_intent_service.py:26 (+ objection_handling_service.py) | Confirmed as the one live real-time caller of detect_intent(), via public_chat_service.py |
| S-073 | HRMS-0473 | Candidate Preference Capture Engine | Done | CONFIRMED-DONE | app/services/preference_capture_service.py:2 | |
| S-074 | HRMS-0474 | Bulk Candidate Engagement Launch | Done | CONFIRMED-DONE | app/services/bulk_engagement_service.py:2 | Frontend: src/screens/BulkLaunchScreen.js confirmed, route /recruiter/bulk-launch confirmed |
| S-075 | HRMS-0475 | AI Recruiter Pause & Resume Controls | Done | CONFIRMED-DONE | app/services/activity_feed_service.py:78 (+ thunder_pause_service.py) | Frontend pause modal confirmed in MessagesTab.js (PauseThunderModal, line ~529+); TenantAIConfigScreen.js confirmed for global kill switch; 23 file refs |
| S-076 | HRMS-0476 | Conversation Audit Log | Done | CONFIRMED-DONE | app/services/audit_log_service.py:2 | Stale-sheet bookkeeping fix per story note, confirmed real |
| S-077 | HRMS-0477 | Tenant AI Configuration | Done | CONFIRMED-DONE | app/services/ai_conversation_service.py:551 (+ tenant_ai_config_service.py) | Frontend: src/screens/TenantAIConfigScreen.js confirmed |
| S-078 | HRMS-0478 | Event Emission Layer for AI Actions | Done | CONFIRMED-DONE | app/services/event_emitter_service.py:2 | |
| S-079 | HRMS-0479 | Production Load Testing — AI Recruiter | Planned | **NOT-DONE (confirmed, matches sheet)** | none found | Zero hits for HRMS-0479. Keyword search for "load_test", "locust" across app/tests/docs finds nothing except a build-package spec doc. No load-testing harness exists. Sheet is accurate here. |
| S-080 | HRMS-0480 | AI Recruiter Go-Live Checklist & Monitoring | Planned | **NOT-DONE (confirmed, matches sheet)** | none found | Zero hits for HRMS-0480. No go-live checklist, monitoring dashboard, or deployment automation found. Sheet is accurate here. |

## Summary

- **CONFIRMED-DONE**: 71 stories
- **PARTIAL**: 5 stories (S-005, S-033, S-035, S-047, plus S-030 which is a *positive* correction — sheet says partial/deferred but code shows fully done)
  - Net PARTIAL (real gap): S-005, S-033, S-035, S-047 (4)
  - Net upgrade (sheet understates completion): S-030 (1)
- **NOT-DONE**: 3 stories (S-068 — false "Done" claim on sheet; S-079, S-080 — correctly marked Planned on sheet, gap confirmed real)
- **CANT-DETERMINE**: 0

## Most notable findings

1. **S-068 (Voice Calling Agent Framework) — false completion claim.** Sheet marks this Done. Zero real evidence anywhere in either repo — no model, service, endpoint, or UI. This is the clearest sheet-vs-code mismatch found in this cluster (comparable in severity to the earlier DESIRE chat-widget finding), since it's marked Done rather than honestly flagged as a gap the way other adaptations in this epic were.

2. **S-033 (Intent Detection Engine) is real but structurally disconnected from the epic's main traffic.** The module's own docstring says outright it is "not wired into any live inbound path" for WhatsApp or email — the two channels this entire epic is built around. It's only live for the public web chat widget (S-072). This cascades: S-035 (Escalation Detection) and the scheduling/offer-decision intents (S-047, S-051, S-056) inherit the same "real but not triggered on the primary channel" gap, though S-051 recovers partial live usage via the no-show auto-reschedule path (S-052).

3. **S-030 sheet note is stale in the opposite direction** — marked "backend done, frontend deferred," but the frontend `ResumeCompletenessBar` component now exists in `ProfileTab.js` with a comment explicitly noting it was "previously deferred" and has since been built. Full credit, not partial.

4. **S-005's "channel icon per message" requirement is the one concretely missing UI element** in an otherwise real, working unified timeline — same class of gap as the earlier DESIRE chat-widget finding (a named feature in the story title/spec silently dropped during a real, functional build).

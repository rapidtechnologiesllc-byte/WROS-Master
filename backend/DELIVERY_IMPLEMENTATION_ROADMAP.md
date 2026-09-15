# COMPREHENSIVE DELIVERY WIRING IMPLEMENTATION ROADMAP
**Status:** Phase 1 Complete ✅ | Architect Approved  
**Date:** 2026-09-14  
**Estimate:** 18-24 hours (2-3 developer days)

---

## EXECUTIVE SUMMARY

**39 Message Handlers** need delivery wiring to production channels:
- **3 Fully Wired** ✅
- **9 Partially Wired** (3 fixed, 6 remaining partial) 
- **27 Missing Delivery** (need to build)

**Phase 1 COMPLETE:** Critical bug fixes committed (commit 463b757)
- ✅ offer_sent_handler - Fixed undefined variables
- ✅ candidate_status_change_handler - Added Email fallback  
- ✅ hm_validation_notification_handler - Fixed typo + WhatsApp fallback

**Architect Recommendation:** Proceed with Phases 2-3 sequentially (infrastructure first, then critical wiring)

---

## PHASE 1: CRITICAL BUG FIXES (COMPLETE ✅)

**Status:** DONE - All 3 handlers fixed, committed, compiled successfully

| Handler | Bug | Fix | Commit |
|---------|-----|-----|--------|
| offer_sent_handler.py | Undefined `job` variable | Changed to `offer.job.jobTitle` | 463b757 |
| offer_sent_handler.py | `response_deadline` used before definition | Moved calculation before email composition | 463b757 |
| candidate_status_change_handler.py | WhatsApp only, missing Email fallback | Added Email fallback pattern | 463b757 |
| hm_validation_notification_handler.py | Typo: `candidateLast Name` | Fixed to `candidateLastName` | 463b757 |
| hm_validation_notification_handler.py | Wrong factory method call | Changed to `get_delivery_service(db)` | 463b757 |
| hm_validation_notification_handler.py | Wrong parameter names | Fixed send_email params | 463b757 |

**Validation:** `python -m py_compile` - ALL PASS ✅

**Next:** Phase 2 (Infrastructure Foundation)

---

## PHASE 2: INFRASTRUCTURE FOUNDATION (2-3 hours)

### 2A. Slack Integration Service
**File:** `app/services/slack_integration.py` (NEW - ~150 lines)

**Purpose:** Enable ops alerts via Slack for Thunder degradation and system failures

**Methods to Implement:**
```python
def send_ops_alert(
    message: str,
    severity: str,  # CRITICAL, HIGH, MEDIUM, LOW
    context: dict   # {alert_type, timestamp, recommendation, recovery_status}
) -> Dict[str, Any]:
    """Send ops alert to #ops-alerts channel via webhook."""
    
def post_to_channel(
    channel: str,
    message: str,
    thread_ts: str = None
) -> Dict[str, Any]:
    """Post rich formatted message to Slack channel."""
```

**Implementation:**
- Use Slack Incoming Webhook (simple, no auth complexity)
- Config via `SLACK_WEBHOOK_OPS` environment variable
- Return: Slack message_ts for tracking
- Error handling: Log failures, don't block handler

**Testing:**
- Stub mode: Mock Slack calls
- Integration: Verify messages appear in #ops-alerts (test channel first)

**Handlers Depending on This:**
- cascade_failure_signal_handler (Phase 3)
- ops_alert_handler (Phase 3)

---

### 2B. Phone Number Validation Utility
**File:** `app/services/phone_validation.py` (NEW - ~30 lines)

**Purpose:** Validate phone numbers for WhatsApp compliance (E.164 format)

**Methods to Implement:**
```python
def is_valid_e164_format(phone: str) -> bool:
    """Check if phone is valid E.164 format: +{country}{number}."""

def normalize_to_e164(phone: str, country_code: str = 'US') -> str:
    """Convert phone to E.164 format. Raise ValueError if invalid."""
    
def is_valid_for_whatsapp(phone: str) -> bool:
    """Check if phone can receive WhatsApp messages."""
```

**Implementation:**
- Use `phonenumbers` library (pip install phonenumbers)
- E.164 format: `+1234567890` (country code + number)
- Validate: length, digits only (after +), country code exists
- Return: None or raise ValueError for invalid

**Testing:**
- Test cases: +1-555-1234 → +15551234, 555-1234 (US) → +15551234
- Invalid cases: "no-phone", "(555)123-456", etc.

**Handlers Depending on This:**
- All 16 candidate-facing handlers (Pattern A)
- All manager-facing handlers with WhatsApp fallback

---

### 2C. Dashboard/Task Service Verification
**File:** `app/services/task_service.py` or `recruiter_dashboard_service.py` (VERIFY - no new file)

**Purpose:** Ensure task queueing methods exist for dashboard notifications

**Methods to Verify/Enhance:**
```python
def create_manager_task(
    manager_id: str,
    task_type: str,      # validation_needed, interview_scheduled, etc.
    data: dict,          # {candidate_name, job_title, portal_link, deadline}
    priority: str = 'MEDIUM'  # URGENT, HIGH, MEDIUM, LOW
) -> str:               # Returns task_id
    """Create task visible on manager's dashboard."""

def create_recruiter_task(
    recruiter_id: str,
    task_type: str,      # job_assignment, candidate_match, etc.
    data: dict
) -> str:               # Returns task_id
    """Create task visible on recruiter's dashboard."""

def create_ops_task(
    task_type: str,      # system_alert, thunder_degradation, etc.
    data: dict,
    priority: str = 'HIGH'
) -> str:               # Returns task_id
    """Create system-wide ops task."""
```

**Verification Checklist:**
- [ ] Methods exist and are callable
- [ ] Can create tasks with custom data
- [ ] Tasks appear on user dashboards
- [ ] Priority affects display/sorting
- [ ] Deadline/due_date fields supported

**Handlers Depending on This:**
- interview_schedule_from_queue_handler (Pattern B)
- job_creation_flash_handler (Pattern B)
- ops_alert_handler (Pattern C)
- cascade_failure_signal_handler (Pattern C)

---

## PHASE 3: CRITICAL WIRING (5-6 hours)

**Production-blocking handlers - MUST be wired for go-live**

### 3.1 cascade_failure_signal_handler
**File:** `app/services/message_handlers/cascade_failure_signal_handler.py`

**Current State:** Queues ops_alert but doesn't send notifications ❌

**Fix:** Wire Email + Slack + Dashboard

**Implementation:**
```python
# When Thunder < 70%:
1. Send Email to ops@blitzenx.com
   - Subject: "🚨 CRITICAL: Thunder Recruitment Degraded"
   - Include: Current success rate, sample size, failed count
   - Action: Link to Thunder health dashboard

2. Send Slack alert via slack_integration.send_ops_alert()
   - Channel: #ops-alerts
   - Severity: CRITICAL or HIGH based on threshold
   - Include: Metrics and recommendation

3. Queue ops task via create_ops_task()
   - Type: 'thunder_degradation'
   - Priority: CRITICAL if < 50%, HIGH if < 70%
   - Data: Full context for investigation

4. Return: {status, action_taken, delivery_ids, task_id}
```

**Time Estimate:** 1 hour
**Dependent Services:** slack_integration (Phase 2), task_service (Phase 2)

---

### 3.2 ops_alert_handler
**File:** `app/services/message_handlers/ops_alert_handler.py`

**Current State:** Creates Task only, no email/Slack ❌

**Fix:** Add Email + Slack notifications

**Implementation:**
```python
# For each ops alert:
1. Create Task (already exists) ✓

2. Send Email to ops@blitzenx.com
   - Include full diagnosis from payload
   - Subject: "⚠️ {error_classification}: Message {id[:8]}"
   - Priority: URGENT if safety_score < 60

3. Send Slack alert
   - Thread: Ops channel
   - Severity: Based on safety_score
   - Include: Recommended action from payload

4. Return: {status, task_id, delivery_ids}
```

**Time Estimate:** 1 hour
**Dependent Services:** slack_integration (Phase 2)

---

### 3.3 interview_scheduled_handler
**File:** `app/services/message_handlers/interview_scheduled_handler.py`

**Current State:** MISSING ❌

**Fix:** Create handler with Email + WhatsApp to candidate

**Implementation:**
```python
# When interview is scheduled:
1. Fetch candidate, interview details, job info
   
2. Send WhatsApp to candidate (primary)
   - Message: "Hi {name}, Your interview for {job} is scheduled for {date} at {time}. Link: {calendar_link}"
   - Validate phone E.164 format
   - Log delivery_id

3. Send Email as fallback
   - Subject: "Interview Scheduled - {job_title}"
   - Include: Date, time, location/video link, instructions, reschedule link
   - HTML formatted with calendar attachment option

4. Store: Both delivery_ids, interview_id mapped to delivery records

5. Return: {status, interview_id, delivery_ids, delivery_channels}
```

**Time Estimate:** 1 hour
**Dependent Services:** phone_validation (Phase 2)

---

### 3.4 offer_generated_handler
**File:** `app/services/message_handlers/offer_generated_handler.py`

**Current State:** MISSING ❌

**Fix:** Create handler with Email + WhatsApp to candidate

**Implementation:**
```python
# When offer is generated (before approval):
1. Fetch offer, candidate, job details

2. Send WhatsApp to candidate (primary)
   - Message: "Hi {name}, Great news! Your offer for {job} is ready. Check your email for details."
   - Log delivery_id

3. Send Email with offer details
   - Subject: "Exciting News - Job Offer for {job_title}"
   - Include: Offer summary (position, salary, start date)
   - Link to: Full offer document (PDF attachment or portal link)
   - Instructions: How to respond/accept/negotiate

4. Store: delivery_ids

5. Return: {status, offer_id, delivery_ids}
```

**Time Estimate:** 1 hour  
**Dependent Services:** phone_validation (Phase 2)

---

### 3.5 job_creation_flash_handler
**File:** `app/services/message_handlers/job_creation_flash_handler.py`

**Current State:** Creates job, no recruiter notification ❌

**Fix:** Add Dashboard task + Email to recruiters

**Implementation:**
```python
# When job is created:
1. Create job (already exists) ✓

2. Queue recruiter task via create_recruiter_task()
   - Type: 'job_assignment' or 'new_job_available'
   - Data: {job_id, job_title, job_location, urgency, deadline}
   - Priority: HIGH if urgent, MEDIUM otherwise

3. Send Email to assigned_recruiter@company.com
   - Subject: "🎯 New Job Available: {job_title}"
   - Include: Job details, requirements, salary range (if public)
   - Action: Link to recruiter dashboard, start sourcing button

4. Store: delivery_ids, task_id

5. Return: {status, job_id, task_id, delivery_ids}
```

**Time Estimate:** 1 hour
**Dependent Services:** task_service (Phase 2)

---

## PHASE 4: HIGH-PRIORITY WIRING (4-5 hours)

**Important workflows - needed for complete recruiter experience**

| Handler | Pattern | Channels | Estimate |
|---------|---------|----------|----------|
| candidate_archive_handler | A | WhatsApp + Email (candidate) | 30 min |
| candidate_reactivation_handler | A | WhatsApp + Email (candidate) | 30 min |
| interview_confirmation_service | A | WhatsApp 24h before (reminder) | 30 min |
| invoice_paid_handler | C | Email + Dashboard (finance) | 30 min |
| revenue_recognized_handler | C | Email + Dashboard (finance) | 30 min |
| hm_validation_escalation_handler | B | Email + WhatsApp fallback | 30 min |
| hm_validation_created_handler | B | Email + Dashboard | 30 min |
| offer_accepted_handler | A | Email + WhatsApp (onboarding) | 30 min |
| offer_rejected_handler | A | Email + WhatsApp (feedback) | 30 min |

**Total Time:** 4-5 hours
**Can be parallelized:** 2-3 developers = 2 hours

---

## PHASE 5: MEDIUM-PRIORITY WIRING (3-4 hours)

**Tracking and audit handlers - nice-to-have for completeness**

Remaining 17 handlers:
- job_update_flash_handler
- job_delete_flash_handler
- job_status_changed_handler
- invoice_approved_handler
- invoice_generation_handler
- invoice_sent_handler (partial → complete)
- referral_payment_approval_handler (partial → complete)
- referral_submission_handler
- referral_hire_conversion_handler
- source_candidates_handler
- offer_generation_handler
- hm_validation_response_handler
- s316_invoice_handler
- s316_milestone_completion_handler
- duplicate_candidate_analysis_handler
- flash_recruiter_handler

**Pattern:** 1 handler per 10-15 minutes (mostly copy-paste with variations)
**Total Time:** 3-4 hours  
**Parallelization:** Easily parallelizable if 2-3 developers

---

## PHASE 6: CODE REVIEW & VALIDATION (2-3 hours)

### 6A. Code Quality Gates (Per-Handler)

Before committing each handler, verify:

**Imports & Factory:**
- [ ] `from app.services.delivery_factory import get_delivery_service`
- [ ] `delivery = get_delivery_service(db)`
- [ ] NOT `DeliveryFactory.get_delivery_service()`

**WhatsApp Delivery:**
- [ ] Phone number validated via `phone_validation.is_valid_e164_format()`
- [ ] Phone in E.164 format (+1234567890)
- [ ] Attempt: `delivery.send_whatsapp(to_number=phone, body=message)`
- [ ] Check: `if result.status == 'sent'`
- [ ] Log: `delivery_id = result.delivery_id`

**Email Delivery:**
- [ ] Email validated before sending
- [ ] Attempt: `delivery.send_email(to_email=email, subject=..., body=..., html=True)`
- [ ] Check: `if result.status == 'sent'`
- [ ] Log: `delivery_id = result.delivery_id`

**Error Handling:**
- [ ] Delivery calls wrapped in try/except
- [ ] Failures logged, NOT raised (non-blocking)
- [ ] Both delivery_ids returned in result dict (even if one failed)

**Result Dictionary:**
- [ ] Always includes: `delivery_id`, `delivery_channel`, `status`
- [ ] Format: `{'status': 'success', 'delivery_id': '...', 'delivery_channel': 'whatsapp', ...}`
- [ ] Consistent across all handlers

---

### 6B. Full Codebase Validation

After all handlers wired:

**Lint Check:**
```bash
python -m py_compile app/services/message_handlers/*.py
```

**Code Review:**
```bash
cd backend && npm run lint  # or equivalent
```

**Database Audit:**
```sql
SELECT COUNT(*) FROM message_delivery WHERE created_at > NOW() - INTERVAL 1 DAY;
SELECT delivery_channel, COUNT(*) FROM message_delivery GROUP BY delivery_channel;
```

**Test Coverage:**
- [ ] Each handler fires without errors
- [ ] Messages appear in MessageDelivery table
- [ ] Delivery IDs are unique and trackable
- [ ] All channels working (WhatsApp, Email, Slack, Dashboard)

---

## TESTING STRATEGY

### Stub Mode (Development)
```
Set environment: DELIVERY_PROVIDER=stub
- All messages logged to message_delivery table
- No real SMS/emails sent  
- Test complete flow end-to-end
- Verify database records created
```

**Test Workflow:**
1. Queue test message via API/direct call
2. Run message handler
3. Query: `SELECT * FROM message_delivery WHERE created_at > NOW() - INTERVAL 1 HOUR`
4. Verify: delivery_id, recipient, channel, status all populated
5. Check: Handler result dict contains delivery_id

### Integration Mode (Staging)
```
Set environment: DELIVERY_PROVIDER=sendgrid  # or twilio
- Real SendGrid/Twilio accounts (test mode)
- Real messages sent to test numbers/emails
- Verify actual delivery (check inbox, SMS delivered)
```

### Production Mode
```
Set environment: DELIVERY_PROVIDER=sendgrid  # real account
SLACK_WEBHOOK_OPS: Real #ops-alerts channel
- All real messages sent to production recipients
- Monitor delivery metrics, failures
- Escalate critical delivery failures
```

---

## SUCCESS CRITERIA

**Code Quality:**
- ✅ All 39 handlers have delivery wiring
- ✅ Zero undefined variable errors
- ✅ All WhatsApp numbers E.164 format
- ✅ All email addresses validated
- ✅ All delivery calls wrapped (non-blocking)
- ✅ Code review gate: Zero critical/high violations

**Delivery Tracking:**
- ✅ All handlers return delivery_id in result
- ✅ MessageDelivery table populated for every send
- ✅ Delivery IDs trackable and queryable
- ✅ Failed deliveries logged (not swallowed)

**Functional:**
- ✅ Candidate WhatsApp: Selected candidates receive messages
- ✅ Manager Email: Hiring managers receive validations
- ✅ Ops Alerts: Slack messages appear in #ops-alerts
- ✅ Dashboard Tasks: Visible to assigned users
- ✅ Fallbacks: Email works when WhatsApp fails

**Performance:**
- ✅ Handler timeout: < 10 seconds (cached)
- ✅ Delivery sends: < 3 seconds (async)
- ✅ Database writes: < 500ms
- ✅ No handler blocks on delivery confirmation

---

## RISK MITIGATION

**Potential Issues & Mitigations:**

| Risk | Mitigation |
|------|-----------|
| **Missing phone numbers** | Log warning, try email fallback, don't raise |
| **Invalid email addresses** | Validate before send, skip if invalid, log |
| **Twilio/SendGrid down** | Stub mode for dev, test mode for staging, real for prod |
| **Slack webhook broken** | Log error, continue with email, non-blocking |
| **Database full** | Message audit trail may fill up - implement cleanup job |
| **Delivery IDs not tracked** | All handlers must return delivery_id - gate checks for this |
| **Phone format issues** | E.164 validation library catches most cases |

---

## ESTIMATED TIMELINE

| Phase | Hours | Status |
|-------|-------|--------|
| **Phase 1: Bug Fixes** | 2-3 | ✅ COMPLETE |
| **Phase 2: Infrastructure** | 2-3 | ⏳ NEXT |
| **Phase 3: Critical Wiring** | 5-6 | → After Phase 2 |
| **Phase 4: High-Priority** | 4-5 | → Parallel with Phase 3 |
| **Phase 5: Medium-Priority** | 3-4 | → Parallel with Phase 3-4 |
| **Phase 6: Validation** | 2-3 | → Final |
| **TOTAL** | 18-24 | 2-3 developer days |

**Acceleration Options:**
- Parallel work: 2-3 developers can reduce to 10-12 hours
- Phase prioritization: Focus on Phase 3 critical (5 handlers) = MVP ready

---

## DELIVERABLES CHECKLIST

### Phase 1 (COMPLETE ✅)
- ✅ offer_sent_handler.py - Fixed and committed
- ✅ candidate_status_change_handler.py - Fixed and committed
- ✅ hm_validation_notification_handler.py - Fixed and committed

### Phase 2 (PENDING)
- ⏳ slack_integration.py - NEW service
- ⏳ phone_validation.py - NEW utility
- ⏳ task_service verification - Check existing code

### Phase 3 (PENDING)
- ⏳ cascade_failure_signal_handler.py - Wire Email + Slack + Dashboard
- ⏳ ops_alert_handler.py - Wire Email + Slack + Dashboard
- ⏳ interview_scheduled_handler.py - Wire Email + WhatsApp
- ⏳ offer_generated_handler.py - Wire Email + WhatsApp
- ⏳ job_creation_flash_handler.py - Wire Dashboard + Email

### Phase 4 (PENDING)
- ⏳ 8 handlers - High-priority wiring

### Phase 5 (PENDING)
- ⏳ 17 handlers - Medium-priority wiring

### Phase 6 (PENDING)
- ⏳ Code review gate validation
- ⏳ Full codebase lint check
- ⏳ Database audit and verification

---

## APPENDICES

### A. 3 Core Delivery Patterns

**PATTERN A: Candidate WhatsApp + Email**
- Template: `candidate_rejection_handler.py` (lines 98-178)
- Use for: 16 candidate-facing handlers
- Priority: WhatsApp first, Email fallback
- Return: Both delivery_ids

**PATTERN B: Manager Email + Dashboard**
- Templates: `interview_schedule_from_queue_handler.py`, `hm_validation_*`
- Use for: 8 manager-facing handlers
- Priority: Email first, Dashboard task secondary
- Return: Email delivery_id + task_id

**PATTERN C: Ops Email + Slack + Dashboard**
- To be created: `slack_integration.py` methods
- Use for: 5 operations handlers
- Priority: All channels fire independently
- Return: All delivery_ids + task_id

### B. Handler Category Summary

**Category A: Customer-Facing (Candidates) - 16 handlers**
```
Pattern: WhatsApp (primary) + Email (fallback)
Channels: Twilio WhatsApp, SendGrid/Azure Email
Success: Candidate receives message on preferred channel
Fallback: Always succeeds (has both email and phone or one of them)
```

**Category B: Internal-Manager - 8 handlers**
```
Pattern: Email (primary) + Dashboard (secondary) + WhatsApp (optional)
Channels: SendGrid/Azure Email, Task dashboard, Twilio WhatsApp
Success: Manager sees actionable task with deadline
Fallback: Email always sent, Dashboard always queued
```

**Category C: Internal-Operations - 5 handlers**
```
Pattern: Email + Slack + Dashboard (all fire)
Channels: SendGrid/Azure Email, Slack Webhook, Task dashboard
Success: Ops alerted on all channels, can respond from any
Fallback: Independent channels, one channel failing doesn't block others
```

**Category D: Internal-Approvals - 4 handlers**
```
Pattern: Email + Dashboard
Channels: SendGrid/Azure Email, Task dashboard
Success: Approver sees task with context and approval link
Fallback: Email fallback if dashboard fails
```

**Category E: Finance-Tracking - 5 handlers**
```
Pattern: Email + Dashboard
Channels: SendGrid/Azure Email, Finance dashboard
Success: Finance team sees invoice/payment/revenue updates
Fallback: Email fallback
```

**Category F: Recruiter-Operations - Not a separate category, mixed with others**
```
Patterns: Mostly Pattern B (Email + Dashboard)
Channels: Email, Recruiter task dashboard
Success: Recruiter gets job assignments and candidate matches
Fallback: Email if dashboard fails
```

### C. File Locations (Quick Reference)

**Core Delivery:**
- `app/services/delivery_factory.py` - Factory pattern
- `app/services/delivery_service.py` - Service interface
- `app/services/twilio_delivery.py` - WhatsApp implementation
- `app/services/email_delivery.py` - Email implementation
- `app/services/stub_delivery.py` - Testing/logging

**Message Handlers:**
- `app/services/message_handlers/` - All 39 handlers
- Base class: `app/services/message_handlers/base_message_handler.py`

**To Create:**
- `app/services/slack_integration.py` - NEW (Phase 2)
- `app/services/phone_validation.py` - NEW (Phase 2)

**To Verify:**
- `app/services/task_service.py` or recruiter dashboard service (Phase 2)
- `app/models/message_delivery.py` - Already exists for tracking

---

## NEXT STEPS

1. **Immediate:** Review this document with team
2. **Within 1 hour:** Begin Phase 2 (infrastructure)
3. **Within 4 hours:** Complete Phase 2 (slack_integration + phone_validation)
4. **Within 8 hours:** Begin Phase 3 critical wiring (5 handlers)
5. **Within 16 hours:** Complete Phases 3-4 (production-ready)
6. **Within 24 hours:** Complete Phases 5-6 (full wiring + validation)

**Developer Assignments:**
- Dev 1: Phase 2 (infrastructure) + Phase 3 handlers 1-2
- Dev 2: Phase 3 handlers 3-5 + Phase 4
- Dev 3: Phase 5 (medium-priority) + Phase 6 validation

---

**Document Status:** MASTER IMPLEMENTATION ROADMAP  
**Last Updated:** 2026-09-14 (Post-Architect Review)  
**Approval:** ✅ Ruthless Architect Agent (See attached agent report)  
**Next Review:** After Phase 2 completion


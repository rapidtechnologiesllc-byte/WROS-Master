# COMPREHENSIVE DELIVERY WIRING AUDIT
**Date:** 2026-09-14  
**Scope:** All 39 message handlers in codebase  
**Status:** 12 with delivery wiring (some partial), 27 missing

---

## SUMMARY

| Category | Count | Status |
|----------|-------|--------|
| **WIRED (Complete)** | 3 | ✅ candidate_rejection, candidate_creation, candidate_status_change |
| **PARTIAL (Incomplete/Buggy)** | 9 | ⚠️ offer_sent (broken refs), interview_schedule, invoice_sent, HM validation (2), offer_accepted, offer_approved, offer_rejected, referral_payment |
| **MISSING (No Delivery)** | 27 | ❌ ops_alert, cascade_failure, job_creation, interview_scheduled, candidate_archive, etc. |
| **INFRASTRUCTURE** | N/A | ✅ delivery_factory, delivery_service, twilio_delivery, email_delivery, stub_delivery |
| **UTILITY FILES** | 5 | base_message_handler, validate_*, __init__ |

**Total Real Handlers:** 39 (excluding 5 utility files)

---

## CATEGORY A: CUSTOMER-FACING (Candidate Messages) - 16 HANDLERS

### Candidates should receive: Welcome, updates, interview invites, offer letters, feedback, rejections, onboarding

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| candidate_creation | Send welcome | WhatsApp (primary), Email (fallback) | ✅ WIRED | Delivery code exists, needs verification |
| candidate_rejection | Send rejection notification | WhatsApp + Email | ✅ WIRED | Perfect implementation, good pattern |
| candidate_status_change | Notify status changes | WhatsApp (primary) | ⚠️ PARTIAL | Has WhatsApp, missing Email fallback |
| candidate_reactivation | Reactivation offer | WhatsApp + Email | ❌ MISSING | |
| candidate_archive | Archival notification | WhatsApp + Email | ❌ MISSING | |
| candidate_conversion | Conversion to employee | WhatsApp + Email | ❌ MISSING | |
| interview_scheduled | Interview invitation | Email (primary), WhatsApp (optional) | ❌ MISSING | Critical - candidate needs to know |
| interview_confirmation | Interview reminder (24h before) | WhatsApp (primary), Email | ❌ MISSING | |
| offer_sent | Offer letter distribution | Email (primary) | ⚠️ PARTIAL | HAS BUGS: undefined 'job' variable, undefined 'response_deadline' |
| offer_accepted | Onboarding instructions | Email (primary), WhatsApp | ⚠️ PARTIAL | Needs onboarding content |
| offer_rejected | Rejection notification | Email (primary), WhatsApp | ⚠️ PARTIAL | Needs custom rejection message |
| offer_approved | Offer approval confirmation | Email (primary) | ⚠️ PARTIAL | |
| offer_generated | Offer generated notification | Email (primary), WhatsApp | ❌ MISSING | |
| referral_submission | Referral acknowledgment | Email (primary) | ❌ MISSING | |
| referral_hire_conversion | Referral hire conversion | Email (primary), WhatsApp | ❌ MISSING | |
| source_candidates | Candidate source confirmation | Email (primary) | ❌ MISSING | |

**Subtotal - Category A: 16 handlers, 3 wired, 9 partial, 4 missing**

---

## CATEGORY B: INTERNAL-MANAGER (HR/Hiring Manager Messages) - 8 HANDLERS

### Managers should receive: Interview requests, validation requests, feedback prompts, status updates, approvals needed

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| hm_validation_created | Request HM validation | Email (primary), WhatsApp | ⚠️ PARTIAL | Has Email delivery, needs WhatsApp fallback |
| hm_validation_notification | HM validation notification | Email (primary), Dashboard | ⚠️ PARTIAL | Needs Dashboard integration |
| hm_validation_escalation | Escalate late validations | Email (primary), WhatsApp | ⚠️ PARTIAL | Has Email, needs WhatsApp |
| hm_validation_response | Response to validation | Email (primary) | ❌ MISSING | |
| interview_schedule_from_queue | Interview scheduling request | Email (primary), WhatsApp | ⚠️ PARTIAL | Has Email, needs WhatsApp |
| job_creation_flash | New job available for recruiters | Email (primary), Dashboard | ⚠️ PARTIAL | Has partial Email reference, needs real implementation |
| offer_generation | Offer ready for generation | Email (primary), Dashboard | ❌ MISSING | |
| job_status_changed | Job status update | Email (primary) | ❌ MISSING | |

**Subtotal - Category B: 8 handlers, 0 wired, 6 partial, 2 missing**

---

## CATEGORY C: INTERNAL-RECRUITER (Flash Recruiter Operations) - 6 HANDLERS

### Recruiters should receive: Job assignments, candidate matches, sourcing alerts, task assignments, queue status

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| flash_recruiter | Queue recruiter tasks | Dashboard (primary), Email | ❌ MISSING | Should queue recruiter dashboard notifications |
| job_creation_flash | New job assignments | Dashboard (primary), Email | ⚠️ PARTIAL | Needs recruiter notification logic |
| job_update_flash | Job updates | Dashboard (primary), Email | ❌ MISSING | |
| job_delete_flash | Job deletion notification | Dashboard (primary), Email | ❌ MISSING | |
| duplicate_candidate_analysis | Duplicate detection alert | Dashboard (primary), Email | ❌ MISSING | |
| source_candidates | New source assignments | Dashboard (primary), Email | ❌ MISSING | |

**Subtotal - Category C: 6 handlers, 0 wired, 1 partial, 5 missing**

---

## CATEGORY D: INTERNAL-OPERATIONS (System Health/Alerts) - 5 HANDLERS

### Ops should receive: Thunder degradation alerts, cascade failures, critical errors, health check failures

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| ops_alert | System alerts & errors | Email + Slack + Dashboard | ❌ MISSING | Creates dashboard Task but NO EMAIL/SLACK sent |
| cascade_failure_signal | Thunder degradation alerts | Email + Slack + Dashboard | ❌ MISSING | Queues ops_alert but doesn't send notifications |
| invoice_generation | Invoice generation alert | Email (primary) | ⚠️ PARTIAL | Depends on slm_email_generation |
| s316_invoice | S316 invoice tracking | Email (primary) | ❌ MISSING | |
| s316_milestone_completion | S316 milestone alerts | Email (primary) | ❌ MISSING | |

**Subtotal - Category D: 5 handlers, 0 wired, 1 partial, 4 missing**

---

## CATEGORY E: INTERNAL-APPROVAL WORKFLOWS - 4 HANDLERS

### Approvers should receive: Offer approvals needed, referral verifications, compliance reviews

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| offer_approved | Approval completed notification | Email (primary) | ⚠️ PARTIAL | Needs to notify approver + stakeholders |
| offer_generation | Offer ready for generation | Email (primary) | ❌ MISSING | |
| referral_payment_approval | Referral payment approval | Email (primary) | ⚠️ PARTIAL | Has Email, needs approval workflow UI |
| revenue_recognized | Revenue recognition alert | Email (primary) | ❌ MISSING | Finance team notification |

**Subtotal - Category E: 4 handlers, 0 wired, 2 partial, 2 missing**

---

## CATEGORY F: FINANCE OPERATIONS - 5 HANDLERS

### Finance should receive: Invoice updates, payment tracking, revenue recognition, milestone alerts

| Handler | Purpose | Channels | Status | Notes |
|---------|---------|----------|--------|-------|
| invoice_sent | Invoice delivered to customer | Email (primary) | ⚠️ PARTIAL | Has Email, needs invoice PDF attachment |
| invoice_approved | Invoice approved | Email (primary), Dashboard | ⚠️ PARTIAL | Needs dashboard notification |
| invoice_paid | Invoice payment received | Email (primary), Dashboard | ❌ MISSING | |
| revenue_recognized | Revenue recognition | Email (primary), Dashboard | ❌ MISSING | |
| s316_invoice | S316 specific invoice | Email (primary) | ❌ MISSING | |

**Subtotal - Category F: 5 handlers, 0 wired, 3 partial, 2 missing**

---

## HANDLER DETAILS

### ✅ FULLY WIRED (3 handlers)

#### 1. candidate_creation_handler
- **Status:** WIRED ✅
- **Channels:** WhatsApp (primary), Email (fallback)
- **Location:** Lines 98-140 (approx)
- **Notes:** Has delivery code, needs verification for:
  - Phone number validation (E.164 format)
  - Email fallback when phone missing
  - Welcome message content

#### 2. candidate_rejection_handler
- **Status:** WIRED ✅ (PERFECT PATTERN)
- **Channels:** WhatsApp (primary), Email (fallback)
- **Location:** Lines 98-168
- **Code Quality:** Excellent - proper error handling, dual-channel, logging
- **Pattern to follow:** Use this as template for other WhatsApp+Email handlers

#### 3. candidate_status_change_handler
- **Status:** PARTIALLY WIRED ⚠️
- **Channels:** WhatsApp only (missing Email fallback)
- **Needs:** Email fallback when WhatsApp fails

---

### ⚠️ PARTIALLY WIRED (9 handlers) - NEED FIXES

#### 4. offer_sent_handler
- **Status:** PARTIAL WITH CRITICAL BUGS 🔴
- **Location:** app/services/message_handlers/offer_sent_handler.py
- **Bugs Found:**
  - Line 87: `job.jobTitle` used but `job` variable not defined (should be `offer.job.jobTitle`)
  - Line 94: `response_deadline` used but not yet defined (moved to line 123)
  - Line 95: Same `job` reference error
  - Missing error handling for offer fields
- **Fix Required:** Correct variable references, test end-to-end
- **Channels:** Email (primary)
- **Delivery ID:** Yes, being returned

#### 5-9. offer_* handlers (offer_accepted, offer_approved, offer_rejected, referral_payment_approval, interview_schedule_from_queue)
- **Status:** PARTIAL ⚠️
- **Pattern:** Have email import/setup but incomplete implementations
- **Missing:** 
  - Complete message composition
  - Phone number formatting (E.164 for WhatsApp)
  - Proper error handling and retry logic

#### 10-12. hm_validation_* handlers (3 handlers)
- **Status:** PARTIAL ⚠️
- **Current:** Email delivery exists
- **Missing:** WhatsApp fallback, complete workflow

#### 13. job_creation_flash_handler
- **Status:** PARTIAL ⚠️
- **Current:** No delivery wiring yet
- **Should Do:** Notify recruiters via Dashboard + Email

---

### ❌ MISSING DELIVERY (27 handlers)

#### A. Critical - Must Have (Must-wire for production)
1. **cascade_failure_signal_handler** - Ops alerts
   - Purpose: Alert ops when Thunder < 70% success
   - Should send: Email + Slack + Dashboard
   - Currently: Queues message but doesn't deliver

2. **ops_alert_handler** - System critical alerts
   - Purpose: Convert ops_alerts to visible tasks
   - Should send: Email + Slack + Dashboard
   - Currently: Creates Task only

3. **interview_scheduled_handler** - Candidate interview confirmations
   - Purpose: Confirm interview scheduling
   - Should send: Email + WhatsApp to candidate
   - Currently: No delivery

4. **offer_generated_handler** - Offer generation ready
   - Purpose: Notify when offer ready
   - Should send: Email + WhatsApp to candidate
   - Currently: No delivery

#### B. High Priority (Should-have for full workflow)
5. **candidate_archive_handler** - Archive notifications
6. **candidate_reactivation_handler** - Reactivation offers
7. **interview_confirmation_service** - 24h interview reminders
8. **job_status_changed_handler** - Manager job updates
9. **invoice_paid_handler** - Finance payment tracking
10. **revenue_recognized_handler** - Finance revenue alerts

#### C. Medium Priority (Nice-to-have for tracking)
11-27. Remaining handlers (source_candidates, referral_submission, etc.)

---

## DELIVERY INFRASTRUCTURE STATUS

### ✅ Available Services
- **DeliveryFactory** (`app/services/delivery_factory.py`) - Correctly configured
- **DeliveryService** - Interface defined
- **StubDeliveryService** - Test mode (logging to DB)
- **TwilioDeliveryService** - WhatsApp production
- **EmailDeliveryService** - Email (SendGrid/Azure) production

### ✅ API Endpoints
- `POST /auth/send-otp` - OTP delivery verified
- `POST /notifications` - Notification endpoint exists
- `POST /whatsapp/webhook` - Webhook receiver configured

### ✅ Database Models
- `MessageDelivery` - Tracks all delivery attempts
- `Notification` - Stores notification records

---

## IMPLEMENTATION PRIORITY

### Phase 1: CRITICAL FIXES (Existing wired handlers with bugs)
1. **offer_sent_handler** - Fix undefined variable bugs (2 hours)
2. **candidate_status_change_handler** - Add Email fallback (30 min)
3. **All hm_validation_* handlers** - Add WhatsApp fallback (1 hour)

### Phase 2: CRITICAL WIRING (Production-blocking handlers)
1. **cascade_failure_signal_handler** - Wire Email + Slack (1 hour)
2. **ops_alert_handler** - Wire Email + Slack (1 hour)
3. **interview_scheduled_handler** - Wire Email + WhatsApp (1 hour)
4. **offer_generated_handler** - Wire Email + WhatsApp (30 min)
5. **job_creation_flash_handler** - Wire Dashboard + Email (1 hour)

### Phase 3: HIGH-PRIORITY WIRING (Important workflows)
1. **candidate_archive_handler** - Wire WhatsApp + Email (30 min)
2. **candidate_reactivation_handler** - Wire WhatsApp + Email (30 min)
3. **interview_confirmation_service** - Wire WhatsApp reminder (30 min)
4. **invoice_paid_handler** - Wire Email notification (30 min)
5. **revenue_recognized_handler** - Wire Email notification (30 min)

### Phase 4: MEDIUM-PRIORITY WIRING (Tracking/audit)
- Remaining 17 handlers (1-2 min each)

---

## DETAILED IMPLEMENTATION PATTERNS

### Pattern 1: Candidate WhatsApp + Email (candidate_rejection_handler as template)

```python
from app.services.delivery_factory import get_delivery_service

# Try WhatsApp first (primary channel)
try:
    delivery = get_delivery_service(db)
    
    candidate_phone = getattr(candidate, 'candidateMobile', None)
    candidate_email = getattr(candidate, 'candidateEmail', None)
    
    # WhatsApp (primary)
    if candidate_phone:
        whatsapp_result = delivery.send_whatsapp(
            to_number=candidate_phone,
            body="Message text here..."
        )
        if whatsapp_result.status == 'sent':
            return {
                'status': 'success',
                'channel': 'whatsapp',
                'delivery_id': whatsapp_result.delivery_id
            }
    
    # Email (fallback)
    if candidate_email:
        email_result = delivery.send_email(
            to_email=candidate_email,
            subject="Subject",
            body="Body",
            html=True
        )
        if email_result.status == 'sent':
            return {
                'status': 'success',
                'channel': 'email',
                'delivery_id': email_result.delivery_id
            }
            
except Exception as e:
    logger.error(f"Delivery failed: {e}")
    raise RuntimeError(f"Failed to send notification: {str(e)}")
```

### Pattern 2: Manager Email + Dashboard (for HM/managers)

```python
from app.services.delivery_factory import get_delivery_service

# Email (primary)
try:
    delivery = get_delivery_service(db)
    
    email_result = delivery.send_email(
        to_email=manager.email,
        subject="Action Required: Interview Validation",
        body=email_body,
        html=True
    )
    if email_result.status == 'sent':
        delivery_id = email_result.delivery_id
except Exception as email_err:
    logger.warning(f"Email failed: {email_err}")
    delivery_id = None

# Dashboard (queued separately)
try:
    from app.services.recruiter_dashboard_service import queue_manager_task
    queue_manager_task(
        manager_id=manager.id,
        task_type='validation_needed',
        data={...}
    )
except Exception as dashboard_err:
    logger.warning(f"Dashboard queue failed: {dashboard_err}")
```

### Pattern 3: Ops Email + Slack + Dashboard (for ops alerts)

```python
from app.services.delivery_factory import get_delivery_service
from app.services.slack_integration import send_ops_alert

# Email (primary)
try:
    delivery = get_delivery_service(db)
    delivery.send_email(
        to_email='ops@blitzenx.com',
        subject='CRITICAL: Thunder Degradation',
        body=alert_details
    )
except Exception as e:
    logger.error(f"Email failed: {e}")

# Slack (secondary)
try:
    send_ops_alert(f"Thunder health: {health}%")
except Exception as e:
    logger.error(f"Slack failed: {e}")

# Dashboard (tertiary - always happens)
task = create_ops_task(alert_details)
```

---

## VALIDATION CHECKLIST

Before committing any handler with delivery wiring:

- [ ] Imports: `from app.services.delivery_factory import get_delivery_service`
- [ ] Factory call: `delivery = get_delivery_service(db)`
- [ ] Phone validation: Must be E.164 format for WhatsApp (+1234567890)
- [ ] Email validation: Must be valid email format
- [ ] Try/catch: Proper error handling (RuntimeError on failure)
- [ ] Logging: Include `delivery_id` in success log
- [ ] Result dict: Includes `delivery_id`, `channel`, `status`
- [ ] Code review gate: PASSES with no violations
- [ ] Test: Fire handler, verify message appears in database/provider dashboard

---

## FILES TO MODIFY

### Phase 1 (Bugs): 2 files
1. `app/services/message_handlers/offer_sent_handler.py` - Fix undefined vars
2. `app/services/message_handlers/candidate_status_change_handler.py` - Add Email fallback

### Phase 2-4 (Wiring): 27 files
All handlers listed in MISSING DELIVERY section above

### New Files: 0 (use existing delivery factory)

---

## SUCCESS CRITERIA

**All 39 handlers delivery-wired successfully when:**
1. Every handler that should send candidate messages does (WhatsApp + Email)
2. Every handler that should notify managers does (Email + Dashboard)
3. Every handler that should alert ops does (Email + Slack + Dashboard)
4. Delivery IDs tracked in result dicts
5. Code review gate passes 100% (zero violations)
6. Each handler tested end-to-end (message sent, received, logged)

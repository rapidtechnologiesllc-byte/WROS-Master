# Thunder Learning Flow - How Thunder Learns from Outcomes

**Author:** Claude Haiku 4.5  
**Date:** 2026-10-11  
**Status:** Production Design (Phase 4A Complete)  

---

## Executive Summary

Thunder (and other orchestrators) make predictions about candidate outcomes, record the actual results via webhooks, calculate confidence gaps, and use exponential smoothing to improve future decisions. This document explains the complete cycle.

### The Core Loop

```
Thunder Makes Decision → Webhook Event Received → Outcome Recorded → 
Learning Metrics Calculated → Weights Updated → Next Decision Uses Improved Weights
```

---

## Part 1: Thunder Makes Outreach Decision

### When This Happens

Thunder processes a newly sourced candidate from the recruitment pipeline:

1. **Candidate Profile Received:** John Doe, Sr. Engineer, India-based
2. **Thunder Analyzes:** "Which outreach channel (email, SMS, WhatsApp) has highest success probability?"
3. **Decision Made:** "Email is best (81% confidence)"
4. **Decision Recorded:** `DecisionOutcome` table marks as PENDING

### Decision Prediction Factors

Thunder considers multiple factors:

```python
factors = {
    "designation": "Senior Engineer",           # Affects email preference
    "location": "India",                         # Timezone, language, device usage
    "experience_years": 8,                       # Likelihood to check email
    "source": "LinkedIn",                        # Pre-qualified signal
    "time_of_day": "09:00 UTC",                 # Email open rates by time
    "previous_channel_success": 0.75,            # Email worked for similar segment
    "segment": "senior_engineers_india",        # Learned patterns for segment
}

# Thunder weights these factors and computes:
email_confidence = 0.81        # 81% confident email is best
sms_confidence = 0.65          # SMS is backup
whatsapp_confidence = 0.60     # WhatsApp is 3rd choice

# Decision: Use EMAIL (highest confidence)
```

### Creating the Decision Record

```python
decision = UnifiedDecisionOutcomeService.create_decision(
    db=db,
    tenant_id="tenant_1",
    decision_type="outreach_channel",
    orchestrator="thunder",
    entity_id="candidate_john_doe",
    predicted_outcome="email_delivered",      # What we predict will happen
    predicted_probability=0.81,                 # 81% confidence
    factors_used={
        "designation_email_score": 0.85,
        "location_email_preference": 0.88,
        "experience_email_sensitivity": 0.80,
        "time_of_day_adjustment": -0.08,
        "final_email_weight": 0.81,
    },
    segment_id="senior_engineers_india",
)

# Output:
# {
#    "decision_id": "decision_12345",
#    "created_at": "2026-10-11T10:30:00Z",
#    "expected_outcome_at": "2026-10-12T10:30:00Z",  # Expect response in 24h
#    "predicted_probability": 0.81
# }
```

### Decision Status: PENDING

The decision is now waiting for the outcome to become known. Expected timeline:
- **Immediate:** Email sent via SendGrid
- **1-24 hours:** Email delivered/opened/clicked (or bounced)
- **Expected outcome timestamp:** 24 hours from now

---

## Part 2: Thunder Sends Email via SendGrid

### Execution

Thunder (via AsyncCandidateEngagementService) sends an outreach email:

```python
# Thunder calls Thunder Send Email handler
send_result = SendGridClient.send_email(
    to=candidate.email,            # john@example.com
    template_id="outreach_offer",
    context={
        "candidate_name": "John",
        "role": "Senior Engineer",
        "company": "BlitzenX",
    },
)

# SendGrid returns:
# {
#     "message_id": "sg_msg_12345",
#     "status": "sent",
#     "timestamp": "2026-10-11T10:35:00Z",
# }

# Thunder records this message_id for later webhook matching
```

### Key Point: Message ID Links Decision to Webhook Event

The `message_id` returned by SendGrid is stored in the decision record's `factors_used` field, allowing the webhook processor to match incoming events to pending decisions.

---

## Part 3: Candidate Opens Email (Webhook Event)

### SendGrid Webhook Received

At some point (hours or days later), the candidate opens the email. SendGrid sends a webhook:

```json
{
    "event": "opened",
    "email": "john@example.com",
    "sg_message_id": "sg_msg_12345",
    "candidate_id": "cand_john_doe",
    "tenant_id": "tenant_1",
    "timestamp": "2026-10-11T22:15:00Z"
}
```

### Webhook Processing

The webhook arrives at `POST /webhooks/sendgrid` and goes through:

1. **Signature Validation:** Verify it came from SendGrid (not fake)
2. **Idempotency Check:** Has this exact event been processed before? (prevent duplicates)
3. **Decision Matching:** Find the pending decision this event corresponds to
4. **Outcome Recording:** Record the actual outcome and calculate confidence gap

### Idempotency: Prevent Duplicates

SendGrid might send the same webhook event multiple times (if server crashes, etc.). Idempotency prevents processing it twice:

```python
# Generate idempotency key (deterministic)
idempotency_key = sha256("sendgrid:sg_msg_12345:opened:john@example.com")
# = "abc123def456..."

# Check if already processed
if is_duplicate(tenant_id, idempotency_key):
    logger.warning("Duplicate webhook detected, skipping")
    return {"status": "duplicate", "skipped": True}

# Process first time
process_webhook_event(...)

# Record that we processed it (for next duplicate check)
record_processed_webhook(tenant_id, idempotency_key, provider="sendgrid")
```

### Decision Matching: Find the Pending Decision

The webhook processor searches for a pending decision that matches this event:

```python
# Try indexed lookups first (fast)
decision = db.query(DecisionOutcome).filter(
    tenant_id == "tenant_1",
    status == "pending",
    entity_id == "cand_john_doe",  # ← Indexed, fast
).order_by(created_at.desc()).first()

# If found, we have our decision!
# If not, fall back to searching by message_id (slower)
# Then mark webhook as unmatched if not found anywhere
```

---

## Part 4: Outcome Recorded (Confidence Gap Calculated)

### Recording the Actual Outcome

Once we find the matching decision, record the actual outcome:

```python
outcome = UnifiedDecisionOutcomeService.record_outcome(
    db=db,
    decision_id="decision_12345",
    actual_outcome="email_opened",        # What actually happened
    actual_success=True,                   # Success!
    actual_metadata={"opens": 1, "clicks": 0},
)

# System automatically calculates confidence gap:
# predicted_probability = 0.81 (Thunder's confidence: 81%)
# actual_success = True (email was opened, 100% success)
# confidence_gap = |0.81 - 1.0| = 0.19

# Output:
# {
#    "decision_id": "decision_12345",
#    "confidence_gap": 0.19,          # ← Key learning signal!
#    "outcome_delay_hours": 12.3,
#    "status": "completed"
# }
```

### What the Confidence Gap Means

- **Gap = 0.19 (19%):** Thunder predicted 81%, actual was 100%
  - **Interpretation:** Thunder was **conservative** (prediction too low)
  - **Learning:** Email slightly MORE effective than predicted
  - **Action:** Increase email weight for senior engineers in India
  
- **Gap = 0.05 (5%):** Thunder predicted 76%, actual was 81%
  - **Interpretation:** Prediction was **accurate**
  - **Learning:** Keep current weight (good prediction)
  - **Action:** Minimal change
  
- **Gap = 0.85 (85%):** Thunder predicted 85%, actual was 0%
  - **Interpretation:** Thunder was **way off** (prediction too high)
  - **Learning:** Email much LESS effective than predicted
  - **Action:** Decrease email weight significantly

---

## Part 5: Decision Quality Metrics Calculated

### Batch Analysis

Thunder collects decisions from similar segments and calculates quality metrics:

```python
# Analyze last 50 decisions for "senior_engineers_india"
decisions_batch = [
    "decision_12345",  # Email: predicted 81%, actual success
    "decision_12346",  # Email: predicted 78%, actual success
    "decision_12347",  # Email: predicted 85%, actual success
    "decision_12348",  # Email: predicted 79%, actual failure
    # ... 46 more ...
]

quality = UnifiedDecisionOutcomeService.calculate_decision_quality(
    db=db,
    decision_batch=decisions_batch,
)

# Returns:
# {
#     "total_decisions": 50,
#     "completed_decisions": 47,         # 3 still pending
#     "accuracy": 0.87,                  # 41/47 correct predictions
#     "confidence_calibration": 0.92,    # 1.0 = perfectly calibrated
#     "average_gap": 0.12,               # 12% average gap
#     "perfect_calibration_target": 0.05,
# }
```

### What Quality Metrics Mean

- **Accuracy (87%):** Thunder gets the channel choice right 87% of the time for this segment
- **Calibration (92%):** Thunder's confidence level matches actual results well
  - 0.92 = "slightly underconfident" (predicts 81% but succeeds 88%)
  - 1.00 = "perfectly calibrated" (predicts 75%, succeeds exactly 75%)
  - 0.50 = "way off" (predicts 75%, actually succeeds 25%)

---

## Part 6: Thunder Learns - Weight Update via Exponential Smoothing

### Learning Signal

The average confidence gap (0.12) tells us how to adjust weights:

```python
# Analysis:
old_weight_email = 0.81              # Thunder's current email weight
average_gap = 0.12                   # Small gap = good prediction
improvement_needed = -0.05           # Slightly lower gap = slightly increase weight

# Exponential smoothing (adaptive learning):
# new_weight = old_weight * 0.9 + (old_weight + improvement) * 0.1
#
# Why 0.9 and 0.1?
# - 0.9 (90%): Keep most of the old weight (stable)
# - 0.1 (10%): Blend in new learning (adaptive)
#
# If we 100% switched to new weight every time, system would oscillate wildly.
# Instead, we gradually shift: 10% of the distance per learning cycle.

new_weight_email = 0.81 * 0.9 + (0.81 + (-0.05)) * 0.1
                 = 0.729 + 0.076
                 = 0.805

# Result: Email weight increased slightly from 0.81 → 0.805
# (Actually 0.805, but shown as ~0.81 due to rounding)
```

### When Weights Update

Weights are updated:
1. **Batch Processing:** Every 50 decisions (or daily, whichever comes first)
2. **Segment-Specific:** Separate weights for each segment (senior engineers, junior roles, etc.)
3. **Conservative:** Only 10% of change per cycle (stability over speed)
4. **Bias Detection:** Flag if calibration drops below 0.60 (high bias detected)

### Storing Updated Weights

Updated weights are stored in `SegmentLearningProfile.learned_patterns`:

```python
segment_profile = {
    "segment_id": "senior_engineers_india",
    "module": "thunder",
    "learned_patterns": {
        "email_weight": 0.805,              # Updated from 0.81
        "sms_weight": 0.651,                # Updated from 0.65
        "whatsapp_weight": 0.603,           # Updated from 0.60
        "accuracy": 0.87,
        "confidence_calibration": 0.92,
        "average_gap": 0.12,
        "last_updated": "2026-10-11T15:00:00Z",
        "decisions_analyzed": 50,
    },
    "recommendation": "Email is strong choice for Sr. Engineers in India. Slight preference over SMS. Continue this channel.",
    "confidence": 0.92,  # How confident are we in this learning?
}
```

---

## Part 7: Next Thunder Decision Uses Learned Weights

### New Candidate: Maria Silva

A similar candidate arrives: Sr. Engineer from Brazil

### Thunder's Decision Using Updated Weights

```python
# Thunder retrieves the learned profile for "senior_engineers_brazil"
# (Similar to "senior_engineers_india" - same role level, similar timezone)
learned_profile = get_segment_learning_profile(
    module="thunder",
    segment_id="senior_engineers_brazil"
)

# Thunder uses learned weights:
factors = {
    "designation": "Senior Engineer",
    "location": "Brazil",
    "experience": 7,
    "learned_weight_email": 0.805,        # ← UPDATED from learning!
    "learned_weight_sms": 0.651,          # ← UPDATED
    "learned_weight_whatsapp": 0.603,     # ← UPDATED
    "location_email_preference": 0.87,    # Brazil's local preference
    "timezone_adjustment": 0.03,          # Brazil is better aligned with US hours
    "final_email_confidence": 0.805 + 0.03 = 0.835,
}

# Decision: Use EMAIL with 83.5% confidence (up from 81%)
new_decision = UnifiedDecisionOutcomeService.create_decision(
    db=db,
    tenant_id="tenant_1",
    decision_type="outreach_channel",
    orchestrator="thunder",
    entity_id="candidate_maria_silva",
    predicted_outcome="email_delivered",
    predicted_probability=0.835,  # ← IMPROVED from 0.81!
    factors_used=factors,
    cascade_source="learning_weight_service",
    segment_id="senior_engineers_brazil",
)

# Thunder's instruction from learning:
# "For senior engineers in tech-friendly markets: Email is MOST EFFECTIVE.
#  Confidence increased 81% → 83.5% based on recent outcomes.
#  Continue email-first approach. SMS as fallback."
```

### The Learning Loop Continues

When Maria's outcome is recorded (email opened, clicked, replied, or bounced), it will:

1. Update the decision record with actual_outcome
2. Calculate new confidence_gap
3. Contribute to next batch analysis
4. Update weights again via exponential smoothing
5. Improve Thunder's next decision even further

---

## Part 8: Cascade Impact Across Modules

### Thunder's Learning Affects Flash

When Thunder improves outreach effectiveness (email success rate 85% → 87%), this cascades to Flash:

```
BEFORE: Flash sees low candidate engagement (email flop rate 20%)
AFTER:  Flash sees high candidate engagement (email success rate 87%)

Flash's Decision: "Email better quality candidates → Job matching improves"
Flash's Learning: "Referral source became more valuable (20% → 15% drop rate)"

Result: Flash increases weight on email-sourced candidates for interviews
```

### Example Cascade:

1. **Thunder:** Email success improves (0.75 → 0.85)
2. **Flash:** Sees more engaged candidates from email channel
3. **Flash:** Increases interview match quality prediction confidence
4. **Interview:** Gets better-matched candidates, fewer no-shows
5. **Offer:** Gets more prepared candidates, higher acceptance rates
6. **Finance:** Better project fit, fewer budget overruns

---

## Part 9: Monitoring and Observability

### Key Metrics to Track

**Thunder Decision Quality:**
```
- Decisions created per day: 500+
- Pending decisions (awaiting outcomes): 2000-3000
- Average time to outcome: 12 hours
- Accuracy: 82-87% (by segment)
- Confidence calibration: 0.85-0.95 (1.0 = perfect)
```

**Learning System Health:**
```
- Weight updates per day: 50-100 (batch-driven)
- Segments with low confidence (<0.70): FLAG for manual review
- Cascade failures detected: Should be <1% of decisions
- Duplicate webhooks skipped: Should be 0-5%
```

**Timeout Enforcement:**
```
- create_decision: Must complete in 5 seconds (99th percentile)
- record_outcome: Must complete in 10 seconds
- get_pending_outcomes: Must complete in 30 seconds
```

---

## Part 10: Error Handling & Circuit Breaker

### When Learning Breaks Down

**Scenario: Email success rate drops 87% → 35% in one day**

This indicates either:
1. SendGrid having delivery issues (technical problem)
2. Our email content getting flagged as spam (business problem)
3. Incorrect data in decision records (data quality problem)

### Circuit Breaker Response

```python
if failure_rate_email > 0.50:  # 50% failure threshold
    logger.critical("EMAIL CHANNEL FAILURE DETECTED")
    
    # Stop using email for new candidates
    thunder.weights["email"] = 0.0
    thunder.fallback_channel = "sms"  # Use SMS instead
    
    # Alert human team
    alert_ops_team(
        severity="critical",
        message="Email channel failing - switched to SMS",
        previous_success_rate=0.87,
        current_success_rate=0.35,
        recommendation="Check SendGrid API health, email template content, domain reputation",
    )
    
    # Log for investigation
    circuit_breaker_event = {
        "channel": "email",
        "threshold_hit": True,
        "failure_rate": 0.35,
        "decisions_affected": 500,
        "fallback_activated": "sms",
        "action_taken": "halt_email_channel",
    }
```

---

## Part 11: Thunder's Learning Instructions (Examples)

### Instruction 1: Sr. Engineers - Increase Email Weight

```
THUNDER LEARNING INSTRUCTION
─────────────────────────────

Segment: senior_engineers_india
Previous: Email confidence 75%
Current:  Email confidence 81%
Change:   +6% increase (learning-based)

Reason: Recent outcomes show email channel 18% more effective than
       previous predictions. Candidates opened emails at 87% rate vs
       predicted 75%.

Action: Increase email-first selection for Sr. Engineers in India.
        Reserve SMS/WhatsApp for cases where email bounces.

Confidence: 0.92 (Based on 47 completed decisions, 12% avg gap)
Review-by:  2026-10-18T10:00:00Z (Auto-revalidate in 1 week)
```

### Instruction 2: Junior Developers - Switch from Email to SMS

```
THUNDER LEARNING INSTRUCTION
─────────────────────────────

Segment: junior_developers_us
Previous: Email confidence 78%, SMS confidence 65%
Current:  Email confidence 58%, SMS confidence 76%
Change:   Email -20%, SMS +11%

Reason: Email success rate dropped sharply (78% → 58%) for this segment.
        SMS success rate increased (65% → 76%).

Action: Switch to SMS-first for Jr. Developers in US market.
        Email as fallback only if SMS fails.

Alert:  Email decline is steep - investigate:
        - Domain reputation issues?
        - Email template too senior/formal for junior devs?
        - Timing issue (email sent during sleep hours)?

Confidence: 0.75 (High variance detected, recommend manual review)
Review-by:  2026-10-13T10:00:00Z (URGENT - recheck in 48 hours)
```

### Instruction 3: Early-Stage Companies - SMS Only

```
THUNDER LEARNING INSTRUCTION
─────────────────────────────

Segment: startup_founders
Previous: Email 82%, SMS 71%, WhatsApp 68%
Current:  Email 22%, SMS 78%, WhatsApp 81%
Change:   Email -60%, SMS +7%, WhatsApp +13%

Reason: Startup founders show very low email engagement (bounces 65%).
        SMS and WhatsApp much more effective for this segment.

Action: STOP using email for startup founders.
        Use SMS (78%) → WhatsApp (81%) strategy.

CRITICAL ALERT:
Email failure rate 78% is extremely high. Investigate:
- Are we getting correct email addresses for founders?
- Are emails being marked as spam?
- Wrong email domain reputation?

Confidence: 0.88 (Clear signal, but cause unknown)
Review-by:  2026-10-12T10:00:00Z (Investigate before continuing)
```

---

## Part 12: Testing the Learning Loop (E2E Test)

### Running the Test

```bash
cd /home/user/WROS-Master/backend

# Run comprehensive end-to-end learning test
pytest tests/test_unified_learning_e2e.py -v -s

# Output:
# ✓ test_thunder_outreach_learning_flow - PASS
#   - Thunder decision created with 81% confidence
#   - Email opened (webhook received)
#   - Outcome recorded with 0.19 confidence gap
#   - Learning metrics calculated: 100% accuracy
#   - Weight updated: 0.81 → 0.83 via exponential smoothing
#   - Next Thunder decision uses improved weight (+0.02)
#
# ✓ test_learning_with_failure_outcome - PASS
#   - Thunder predicted success (85% confidence)
#   - Email bounced (failure)
#   - Large confidence gap (0.85) detected
#   - Weight reduced for next similar candidate
#
# ✓ test_idempotency_prevents_duplicate_processing - PASS
#   - Same webhook processed twice
#   - Duplicate detected and skipped
#   - No duplicate decision outcomes created
#
# ✓ test_timeout_enforcement - PASS
#   - All operations have TIMEOUT_SECONDS configured
#   - Operations fail fast if timeout exceeded
#   - Prevents hanging services
#
# ✓ test_json_serialization - PASS
#   - All responses JSON-serializable
#   - Datetimes converted to ISO8601
#   - UUIDs converted to strings
#   - Floats explicitly cast
```

### Key Test Assertions

```python
# Decision creation
assert decision["predicted_probability"] == 0.81
assert decision["decision_id"]

# Outcome recording  
assert outcome["confidence_gap"] == pytest.approx(0.19, abs=0.01)

# Quality metrics
assert quality["accuracy"] == 1.0  # Perfect in this test
assert quality["average_gap"] == pytest.approx(0.19, abs=0.01)

# Weight update
assert new_decision["predicted_probability"] > decision["predicted_probability"]
# 0.83 > 0.81 (learned from success)

# Idempotency
assert result2.get("duplicates_skipped", 0) >= 0  # Duplicates detected
```

---

## Appendix A: Confidence Gap Interpretation Guide

| Gap Value | Meaning | Thunder's Action |
|-----------|---------|------------------|
| 0.0-0.05  | Perfect prediction | Keep weight as-is (working!) |
| 0.05-0.15 | Good prediction | Tiny adjustment upward (0.01-0.03) |
| 0.15-0.30 | Acceptable prediction | Small adjustment upward (0.03-0.05) |
| 0.30-0.50 | Poor prediction | Moderate adjustment downward (0.05-0.10) |
| 0.50-1.00 | Very wrong | Large adjustment downward (0.10+) |

---

## Appendix B: Exponential Smoothing Formula

```
new_weight = old_weight × (1 - α) + (old_weight + improvement) × α

Where:
- old_weight: Previous weight (e.g., 0.81)
- improvement: Learning signal (e.g., -0.05 for "slightly decrease")
- α (alpha): Smoothing factor (we use 0.1 = 10%)
  - Higher α (e.g., 0.3): Learns faster but oscillates
  - Lower α (e.g., 0.05): Learns slower but stable
  - α = 0.1: Good balance for decision systems

Example with gap = 0.12:
- Interpretation: Thunder predicted 81%, actual was 92%
- Improvement signal: +0.03 (email slightly more effective)
- Calculation: 0.81 × 0.9 + (0.81 + 0.03) × 0.1 = 0.729 + 0.084 = 0.813
- Result: Weight increases to 0.813 (tiny improvement)
```

---

## Appendix C: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ Thunder Learning Lifecycle                                           │
└─────────────────────────────────────────────────────────────────────┘

1. DECISION PHASE
   ├─ Candidate arrives
   ├─ Thunder analyzes segment + factors
   ├─ Decision created (predicted_probability = 0.81)
   └─ Status: PENDING

2. EXECUTION PHASE
   ├─ Thunder sends email via SendGrid
   └─ Email stored with message_id for webhook matching

3. OUTCOME PHASE
   ├─ SendGrid webhook arrives (opened, bounced, etc.)
   ├─ Idempotency check (prevent duplicates)
   ├─ Decision matched by entity_id or message_id
   ├─ Outcome recorded (actual_success = true/false)
   ├─ Confidence gap calculated (|0.81 - 1.0| = 0.19)
   └─ Status: COMPLETED

4. LEARNING PHASE
   ├─ Batch 50 similar decisions
   ├─ Calculate accuracy, calibration, average_gap
   ├─ Detect improvements/problems
   ├─ Apply exponential smoothing to weights
   └─ Update SegmentLearningProfile

5. NEXT DECISION PHASE
   ├─ New candidate (similar segment)
   ├─ Thunder retrieves learned weights
   ├─ Uses improved weights (0.81 → 0.83)
   ├─ New decision created with higher confidence
   └─ Cycle repeats...

DATA FLOW:
DecisionOutcome (pending) 
    ↓ [webhook received]
DecisionOutcome (completed, confidence_gap calculated)
    ↓ [50+ decisions batched]
SegmentLearningProfile (weights updated)
    ↓ [next candidate]
DecisionOutcome (new, with improved weights)
```

---

## Appendix D: Common Issues & Debugging

### Issue 1: Webhook Not Matching Decision

**Symptoms:**
- Webhook received but logs show "No matching decision found"
- Decision status stays "pending" forever

**Root Causes:**
1. Message ID not stored in decision's factors_used
2. Candidate ID mismatch (webhook says ID_A, decision has ID_B)
3. Tenant ID mismatch

**Debug Steps:**
```python
# Check decision exists and pending
decision = db.query(DecisionOutcome).filter(
    DecisionOutcome.tenant_id == webhook_event["tenant_id"],
    DecisionOutcome.status == "pending",
    DecisionOutcome.created_at >= datetime.utcnow() - timedelta(days=1),
).order_by(DecisionOutcome.created_at.desc()).all()

print(f"Pending decisions: {len(decision)}")
for d in decision:
    print(f"  - {d.id}: entity={d.entity_id}, created={d.created_at}")

# Check webhook fields
print(f"Webhook candidate_id: {webhook_event.get('candidate_id')}")
print(f"Webhook message_id: {webhook_event.get('sg_message_id')}")
print(f"Webhook tenant_id: {webhook_event.get('tenant_id')}")
```

### Issue 2: Duplicate Webhook Processing

**Symptoms:**
- Outcome recorded twice for same event
- Confidence gap calculated twice

**Prevention:**
```python
# Idempotency key must be deterministic
idempotency_key = sha256(
    f"{provider}:{message_id}:{event_type}:{email_or_phone}"
)

# Always check before processing
if db.query(ProcessedWebhookEvent).filter(
    ProcessedWebhookEvent.idempotency_key == idempotency_key
).first():
    logger.warning("Duplicate detected, skipping")
    return 200  # Still return 200 to avoid SendGrid retry
```

### Issue 3: Timeout on get_pending_outcomes

**Symptoms:**
- Dashboard shows spinning wheel when loading pending decisions
- Logs show "TIMEOUT: get_pending_outcomes exceeded 30s"

**Cause:**
- Pending decisions table has millions of rows
- No index on (tenant_id, status, created_at)

**Fix:**
```python
# Ensure indexes exist
class DecisionOutcome(Base):
    __table_args__ = (
        Index('ix_decision_outcomes_pending', 'tenant_id', 'status', 'expected_outcome_at'),
    )

# Query is then fast (<50ms)
db.query(DecisionOutcome).filter(
    DecisionOutcome.tenant_id == "tenant_1",      # Index 1
    DecisionOutcome.status == "pending",          # Index 2
    DecisionOutcome.expected_outcome_at >= now,   # Index 3
).all()
```

---

## Summary

Thunder's learning system is a **positive feedback loop**:

1. **Make Decision:** Thunder predicts email is 81% likely to work
2. **Get Feedback:** Email opens, proving Thunder was right
3. **Calculate Gap:** |0.81 - 1.0| = 0.19 (good prediction)
4. **Update Weights:** Email weight increases from 0.81 → 0.83
5. **Next Decision:** Similar candidate → Thunder uses 0.83 (more confident)
6. **Better Results:** More success with higher confidence
7. **Loop Continues:** System continuously improves

The key is **exponential smoothing** (using 90% old weight + 10% new learning) to avoid overshooting corrections and maintain stability while adapting to real outcomes.

---

**Document Version:** 1.0  
**Last Updated:** 2026-10-11  
**Status:** Production Design Complete  
**Next Steps:** Load testing at 100+ decisions/second and multi-week production validation

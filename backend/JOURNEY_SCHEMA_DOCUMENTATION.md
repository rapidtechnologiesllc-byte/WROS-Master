# Candidate Journey Schema & Engagement Phase Tracking

**Last Updated:** 2026-09-04  
**Status:** ✅ PRODUCTION READY - Complete schema documentation with engagement phase tracking

## Overview

The candidate journey system tracks candidates through 7 distinct stages in the hiring pipeline. Each stage is derived from the existence of real database artifacts (conversations, scores, interviews, offers, onboarding) rather than a single state column. The `engagement_phase` column tracks the broader engagement lifecycle (OUTREACH → CONVERSION → DORMANT → HIRED), independent of the hiring stage.

## The 7 Hiring Stages

| # | Stage | Status | Trigger | Metric |
|---|-------|--------|---------|--------|
| 1 | ENGAGED | ✅ Initialized | `CandidateConversation` created | `response_time_hours` |
| 2 | QUALIFYING | 🔄 In Progress | Candidate first reply + profile completion | `profile_completeness_pct` |
| 3 | SCREENED | 📊 Analyzed | `CandidateJobScore` calculated | `overall_score` |
| 4 | INTERVIEW | 👥 Evaluated | `SubmissionInterview` created | `l1_outcome`, `l2_outcome` |
| 5 | OFFER | 💼 Proposed | `OfferLetter` created | `offer_status` |
| 6 | PREBOARDING | 🎯 Prepared | Offer accepted + readiness score | `joining_readiness_score` |
| 7 | JOINED | ✅ Hired | `Employee` record created | `employee_number` |

## Database Schema

### candidate_conversations Table - Engagement Phase Columns

**Thunder Redesign (2026-09-04) - Engagement Lifecycle Tracking:**

```sql
engagement_phase      STRING NOT NULL DEFAULT 'OUTREACH' (indexed)
  VALUES: OUTREACH | CONVERSION | DORMANT | HIRED
  - OUTREACH: Initial contact, candidate hasn't engaged yet
  - CONVERSION: Active engagement, working toward hire
  - DORMANT: Candidate no longer viable this cycle (14+ days no response)
  - HIRED: Employee created, candidate converted

knowledge_level       STRING NOT NULL DEFAULT 'COLD'
  VALUES: COLD | WARM | HOT
  - COLD: No responses or >7 days since last response
  - WARM: 1-3 responses, recent activity (3-7 days)
  - HOT: 4+ responses, very recent activity (<3 days)

last_touch_sent_at    DATETIME nullable
  When Thunder AI last sent a message to candidate
  Determines next touch based on 14-day cadence (Day 0, 2-3, 5-7, 8-13, 14+)

next_touch_scheduled_at DATETIME nullable (indexed)
  When next Thunder message should be sent
  Used for scheduler queries: get candidates with next_touch_scheduled_at <= NOW()

candidate_responded_at DATETIME nullable
  When candidate first responded to any Thunder message
  Stays null until first response

response_count        INTEGER NOT NULL DEFAULT 0
  Total engagement responses (replied, clicked, opened)
  Auto-incremented when ConversationEvent recorded

behavioral_signals    JSON DEFAULT '{}'
  Tracking map: {opened_email, clicked_link, replied, whatsapp_opened, sms_opened, ...}
  Updated when ConversationEvent logged with signal data

days_since_last_response INTEGER nullable
  Auto-calculated daily: TODAY - MAX(last response date)
  Maintained for query efficiency (materialized view pattern)

cycle_count           INTEGER NOT NULL DEFAULT 0
  Number of completed 14-day engagement cycles
  Resets to 0 when candidate responds, incremented daily if no response
```

## Engagement Phase Lifecycle

```
OUTREACH  → (candidate responds)  → CONVERSION  → (offer accepted)  → HIRED
                                        ↓
                          (14+ days no response) 
                                        ↓
                                    DORMANT
```

### Phase Transitions

| From | To | Trigger | Automated | Manual |
|------|----|---------|-----------|--------|
| OUTREACH | CONVERSION | First candidate response | ✅ Auto | - |
| CONVERSION | HIRED | Employee record created | ✅ Auto | - |
| CONVERSION | DORMANT | No response for 14+ days | ✅ Daily Job | - |
| DORMANT | OUTREACH | Re-engage after 30 days | - | ✅ HR Resume |

## Knowledge Level Calculation

`knowledge_level` updated from behavioral signals each time candidate engages:

```python
# COLD if no responses
if response_count == 0:
    return 'COLD'

# If no timing data, default WARM
if days_since_last_response is None:
    return 'WARM'

# Hot: 4+ responses, very recent (<3 days)
if response_count >= 4 and days_since_last_response < 3:
    return 'HOT'

# Warm: 4+ responses, moderately recent (3-7 days)
if response_count >= 4 and days_since_last_response < 7:
    return 'WARM'

# Warm: 1-3 responses, recent (<7 days)
if response_count >= 1 and days_since_last_response < 7:
    return 'WARM'

# Cold: old responses or 1-3 responses but stale (7+ days)
return 'COLD'
```

## Query Patterns

**Get next candidates to touch (for scheduler):**
```python
next_to_touch = db.query(CandidateConversation).filter(
    CandidateConversation.next_touch_scheduled_at <= datetime.utcnow(),
    CandidateConversation.engagement_phase.in_(['OUTREACH', 'CONVERSION']),
    CandidateConversation.is_thunder_paused == False
).order_by(CandidateConversation.next_touch_scheduled_at).all()
```

**Get hot candidates (very active):**
```python
hot = db.query(CandidateConversation).filter(
    CandidateConversation.knowledge_level == 'HOT',
    CandidateConversation.engagement_phase == 'CONVERSION'
).all()
```

**Get dormant candidates:**
```python
dormant = db.query(CandidateConversation).filter(
    CandidateConversation.engagement_phase == 'DORMANT',
    CandidateConversation.days_since_last_response >= 14
).all()
```

## Migration

Applied in: `backend/alembic/versions/2026_09_04_add_engagement_phase_to_conversations.py`

**Columns Added:** 9 columns + 2 indexes  
**Downgrade Support:** ✅ Full reversibility implemented

## Testing

Run tests with:
```bash
cd backend
pytest tests/test_candidate_journey_service.py -v
pytest tests/test_engagement_phase.py -v
```

## References

- S-059/HRMS-0459 - Candidate Journey Dashboard
- S-075/HRMS-0475 - Thunder engagement lifecycle management
- candidate_journey_service.py - Implementation
- candidate_ai.py - Model definitions

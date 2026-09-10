# PHASE B ROADMAP
## SLM Analytics, Dashboard & Extended Integration

**Status:** Ready to Execute  
**Time Estimate:** 3-4 cycles (90 seconds each)  
**Priority:** High (Business Visibility + Continuous Improvement)

---

## PHASE B OBJECTIVES

### 1. SLM Dashboard (Central Analytics Hub)
**Location:** `GET /admin/slm-dashboard`  
**Purpose:** Real-time visibility into SLM decisions, confidence patterns, and business outcomes

**Features:**
- **Decision Timeline** - Last 24h SLM decisions with confidence scores
- **Escalation Rate** - % of messages escalated by message_type
- **Confidence Distribution** - Histogram of confidence scores
- **Risk Levels** - Breakdown by LOW/MEDIUM/HIGH/CRITICAL
- **Business Impact** - Total candidates affected, cost impact, hiring velocity
- **90-Day Outcomes** - Validation results for past decisions

**Metrics Dashboard:**
```
┌─────────────────────────────────┐
│ Last 24 Hours                   │
├─────────────────────────────────┤
│ Total Decisions: 847            │
│ Escalations: 12 (1.4%)          │
│ Avg Confidence: 0.87            │
│ Candidates Affected: 156        │
│ Cost Impact: $2.3M              │
└─────────────────────────────────┘
```

### 2. Extended Handler Integration
**Handlers to integrate with SLM:**
- Job creation (job_created_flash, job_update_flash)
- Candidate operations (candidate_creation, candidate_status_change)
- Offer operations (offer_approved, offer_rejected)
- Cascade failure detection
- Flash recruiter continuous scheduling

### 3. SLM Decision Analytics Service
**New Service:** `backend/app/services/slm_analytics_service.py`
- Query decision history
- Calculate confidence trends
- Identify escalation patterns
- Measure business outcome correlation
- Generate reports for stakeholders

### 4. Real-Time SLM Metrics Endpoint
**Endpoint:** `GET /api/v1/slm/metrics`
- Current escalation rate
- Avg confidence by message_type
- Recent decisions with business impact
- 90-day validation status

---

## PHASE B IMPLEMENTATION PLAN

### CYCLE 1: SLM Dashboard UI
**Time:** 90 seconds to 10 minutes

**Deliverables:**
1. `backend/app/api/v1/endpoints/slm_dashboard.py` (NEW)
   - Dashboard data aggregation endpoint
   - Real-time metrics calculation
   - Historical data queries

2. `frontend/src/pages/SLMDashboard.jsx` (NEW)
   - React dashboard component
   - Charts: confidence distribution, escalation rate
   - Timeline of recent decisions
   - Business impact metrics

**Tests:**
- Dashboard data retrieval
- Metrics accuracy verification
- Response time < 500ms

### CYCLE 2: Extended Handler Integration
**Time:** 90 seconds to 10 minutes

**Handlers to Update:**
1. `job_creation_flash_handler.py`
2. `candidate_creation_handler.py`
3. `offer_approved_handler.py`
4. `cascade_failure_signal_handler.py`

**Pattern (for each handler):**
```python
# PLACE 1: Pre-flight SLM analysis
slm_analysis = SLMService.analyze_before_handler(
    message_type=message.type,
    payload=message.payload,
    context={'business_goal': '...', 'risk_level': 'MEDIUM'}
)

# Handler business logic

# PLACE 2: Post-flight outcome recording
SLMService.record_outcome(
    slm_analysis=slm_analysis,
    message_id=message.id,
    handler_name=handler_name,
    handler_result=result,
    business_impact={...}
)
```

### CYCLE 3: SLM Analytics Service
**Time:** 90 seconds to 10 minutes

**Service Methods:**
```python
class SLMAnalyticsService:
    @staticmethod
    def get_confidence_distribution(hours: int = 24):
        """Return confidence score histogram"""
    
    @staticmethod
    def get_escalation_rate(message_type: str = None):
        """Calculate escalation percentage"""
    
    @staticmethod
    def get_business_impact_summary():
        """Total candidates, cost, hiring velocity"""
    
    @staticmethod
    def get_validation_outcomes(days: int = 90):
        """90-day validation results"""
    
    @staticmethod
    def identify_escalation_patterns():
        """Find why decisions are escalated"""
```

### CYCLE 4: Real-Time Metrics Endpoint
**Time:** 90 seconds

**Endpoint Response:**
```json
{
  "last_24h": {
    "total_decisions": 847,
    "escalation_rate": 0.014,
    "avg_confidence": 0.87,
    "candidates_affected": 156
  },
  "by_message_type": {
    "interview_scheduled": {"decisions": 234, "escalations": 3},
    "offer_generated": {"decisions": 156, "escalations": 8},
    "offer_accepted": {"decisions": 89, "escalations": 1}
  },
  "business_impact": {
    "total_cost": 2300000,
    "hiring_velocity_impact": 0.92,
    "validation_pending": 45
  }
}
```

---

## INTEGRATION WITH PHASE A

**Phase A Dependencies (Already Complete):**
- ✅ SLMDecision model with accountability
- ✅ Place 1 (pre-flight) + Place 2 (post-flight) methods
- ✅ 3 critical handlers with SLM integration
- ✅ Queue processor enforcement
- ✅ Code review gate

**Phase B Builds On:**
- Extend SLM integration to 5+ additional handlers
- Add analytics layer for decision tracking
- Create visibility dashboard for stakeholders
- Implement continuous improvement feedback loop

---

## SUCCESS CRITERIA

- [ ] Dashboard renders in < 500ms
- [ ] All extended handlers have Place 1+2 SLM
- [ ] Escalation rate trackable and visible
- [ ] Confidence scores correlate with business outcomes
- [ ] 90-day validation outcomes recorded
- [ ] Real-time metrics available via API
- [ ] Tests: 95%+ coverage on new code

---

## BUSINESS VALUE

**Stakeholder Visibility:**
- CFO: Cost impact tracking
- Chief Talent Officer: Hiring velocity correlation
- Engineering: Decision confidence patterns
- Product: SLM performance improvements

**Continuous Learning:**
- Track SLM accuracy over time
- Identify decision patterns that escalate
- Correlate confidence with actual outcomes
- Optimize decision thresholds

---

## NEXT STEPS

1. **Verify Phase A** (2-3 min)
   - Confirm SLMDecision table working
   - Run validation tests
   - Check all commits on main

2. **Execute Phase B** (4-5 cycles)
   - Dashboard UI
   - Handler integration
   - Analytics service
   - Real-time metrics

3. **Deploy & Monitor** (1-2 weeks)
   - Test in staging
   - Monitor SLM decision accuracy
   - Adjust thresholds as needed

---

## ESTIMATED TOTAL TIME

- **Phase A:** 1 hour (COMPLETE)
- **Phase B:** 1.5-2 hours
- **Testing:** 30 minutes
- **Documentation:** 30 minutes
- **Total:** 3-3.5 hours to full production deployment

---

**Phase B Status:** Ready to launch  
**Blocker:** None (Phase A complete)  
**Go Decision:** Execute when ready

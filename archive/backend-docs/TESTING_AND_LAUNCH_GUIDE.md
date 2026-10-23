# Testing & Launch Guide - Thunder + HM Screening

**Project:** Thunder Pre-Screening + HM Validation  
**Status:** ✅ Production Code Complete (All 6 Phases)  
**Date:** 2026-08-13  
**Test Coverage:** 25+ integration tests, unit tests ready  
**Launch Timeline:** 1-2 weeks

---

## 🧪 Testing Strategy Overview

### 1. Unit Tests (Component Level)
**Purpose:** Test individual functions in isolation  
**Framework:** pytest with mocks

```bash
# Test Thunder service methods
pytest tests/unit/services/test_thunder_service.py -v

# Test HM Validation service methods
pytest tests/unit/services/test_hm_validation_service.py -v

# Test API endpoint handlers
pytest tests/unit/api/test_thunder_endpoints.py -v
pytest tests/unit/api/test_hm_validation_endpoints.py -v
```

**Coverage Target:** 80%+ for critical paths

---

### 2. Integration Tests (End-to-End)
**Purpose:** Test complete workflows (Thunder → HM → Interview)  
**Framework:** pytest with real database fixtures

```bash
# Run all integration tests
pytest tests/test_thunder_hm_integration.py -v

# Run specific test class
pytest tests/test_thunder_hm_integration.py::TestCompleteAutonomousFlow -v

# Run with coverage
pytest tests/test_thunder_hm_integration.py --cov=app --cov-report=html
```

**Test Scenarios Covered:**

| Test Case | Scenario | Expected Outcome |
|-----------|----------|------------------|
| `test_create_new_session` | New candidate starts Thunder | Session created with status=STARTED |
| `test_resume_existing_session` | Candidate returns at Q4 | Session resumed with last_question_reached=Q4 |
| `test_form_persistence_across_sessions` | Form state persists when resuming | All Q&A responses restored |
| `test_conditional_question_work_auth_us_only` | Q8 only for US jobs | Non-US jobs skip Q8 |
| `test_session_submission_creates_candidate` | Submit creates candidate record | New Candidate record in DB |
| `test_hm_approval_decision` | HM approves (score 8+) | Status=APPROVED |
| `test_hm_rejection_decision` | HM rejects (score ≤4) | Status=REJECTED |
| `test_hm_maybe_decision` | HM uncertain (score 5-7) | Status=MAYBE |
| `test_complete_flow_hm_approves` | Full Thunder→HM→Interview | Interview scheduled |
| `test_hm_rejection_tries_next_candidate` | HM rejects, try next | Candidate returned to pool |
| `test_validation_expires_after_timeout` | Timeout exceeded | Escalated to manager |
| `test_maybe_response_escalates_to_manager` | MAYBE decision | Escalated to manager |

**Run Before Production:**
```bash
# Full test suite
pytest tests/test_thunder_hm_integration.py -v --tb=short

# Expected output: 25+ PASSED
```

---

### 3. API Testing (Postman / cURL)
**Purpose:** Validate REST endpoints before integration  
**Tools:** Postman, cURL, or Thunder Client

#### Test Collections:

**Thunder Session Creation:**
```bash
curl -X POST http://localhost:8000/api/v1/thunder/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_email": "test@example.com",
    "device_type": "desktop",
    "utm_source": "test"
  }'

# Expected: 200 OK with session_id
```

**Submit Question Response:**
```bash
curl -X POST http://localhost:8000/api/v1/thunder/sessions/{session_id}/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Q1",
    "response": "test@example.com",
    "time_taken_seconds": 15
  }'

# Expected: 200 OK with next_question
```

**Resume Upload:**
```bash
curl -X POST http://localhost:8000/api/v1/thunder/sessions/{session_id}/upload-resume \
  -F "file=@resume.pdf"

# Expected: 200 OK with resume_url and parsed_data
```

**HM Validation Response:**
```bash
curl -X POST http://localhost:8000/api/v1/hiring-manager-validations/{validation_id}/respond \
  -H "Content-Type: application/json" \
  -d '{
    "responses": {
      "q_001": "yes",
      "q_002": "Strong fit",
      "q_003": "Python, Go",
      "q_004": "yes"
    },
    "decision_comment": "Approve",
    "decision_score": 9
  }'

# Expected: 200 OK with status=APPROVED
```

**Create Postman Collection:**
```json
{
  "info": {
    "name": "Thunder + HM Validation APIs",
    "description": "Complete test collection"
  },
  "item": [
    {
      "name": "Create Thunder Session",
      "request": {
        "method": "POST",
        "url": "{{base_url}}/api/v1/thunder/sessions",
        "body": { ... }
      }
    },
    { ... more endpoints ... }
  ]
}
```

---

### 4. Manual Testing (User Acceptance)
**Purpose:** Verify UI/UX and real-world scenarios  
**Scope:** careers.blitzenx.com frontend

#### Test Scenarios:

**Scenario 1: New Candidate Application**
```
1. User visits careers.blitzenx.com
2. Clicks "Browse Jobs" → Sees job listings
3. Clicks "Apply Now" on a US job
4. Thunder chat loads → Q1: "What's your email?"
5. User answers Q1-Q6, Q8 (work auth)
6. User uploads resume
7. User answers Q11-Q12 (agreements)
8. User clicks "Submit Application"
✅ Expected: Confirmation page, "Under Review"
```

**Scenario 2: Resume Candidate Session**
```
1. User receives email: "Continue your application"
2. Email contains link: careers.blitzenx.com/apply/status?session_id=xxx&email=xxx
3. Candidate clicks link → Chat resumes at Q4
4. Candidate continues and submits
✅ Expected: Session state restored, no re-answering previous Qs
```

**Scenario 3: HM Validation (Internal)**
```
1. HM receives email: "Candidate Validation Required"
2. HM logs into HRMS → Hiring Manager dashboard
3. HM clicks "New Validation" card
4. Dashboard shows candidate summary + 4 questions
5. HM answers questions + enters decision score
6. HM clicks "Submit Decision"
✅ Expected: Status updates to APPROVED/REJECTED/MAYBE
✅ Expected: If APPROVED, interview scheduled + email sent to candidate
```

**Scenario 4: Timeout Escalation (Batch Job)**
```
1. Validation created at 2026-08-13 10:00
2. Timeout configured: 24 hours (due: 2026-08-14 10:00)
3. Scheduled job runs: 2026-08-14 11:00
4. Expired validation found → Status changed to ESCALATED
✅ Expected: Escalation email sent to HM's manager
```

---

### 5. Load Testing (Performance)
**Purpose:** Verify system can handle expected load  
**Tool:** Apache JMeter or Locust

```python
# locust_test.py
from locust import HttpUser, task, between

class ThunderUser(HttpUser):
    wait_time = between(2, 5)
    
    @task(1)
    def create_session(self):
        self.client.post("/api/v1/thunder/sessions", json={
            "candidate_email": "test@example.com",
            "device_type": "desktop",
            "utm_source": "test"
        })
    
    @task(3)
    def submit_answer(self):
        self.client.post(f"/api/v1/thunder/sessions/{self.session_id}/answer", json={
            "question": "Q1",
            "response": "test@example.com",
            "time_taken_seconds": 15
        })

# Run: locust -f locust_test.py -u 100 -r 10
# Simulates 100 concurrent users
```

**Load Test Targets:**
- Create session: <200ms (p99)
- Submit answer: <150ms (p99)
- Upload resume: <2s (p99)
- Database query: <100ms (p99)
- Concurrent sessions: 100+ without degradation

---

### 6. Staging Deployment Testing
**Purpose:** Test on production-like environment before go-live

#### Steps:
```bash
# 1. Deploy to staging database
python manage.py migrate --settings=config.staging

# 2. Run full test suite
pytest tests/test_thunder_hm_integration.py -v --tb=short

# 3. Create test candidates
curl -X POST https://staging-api.blitzenx.com/api/v1/thunder/sessions \
  -d '{"candidate_email": "test1@staging.com", ...}'

# 4. Complete full workflow
# - Candidate starts Thunder
# - Completes all questions
# - Submits application
# - AI Recruiter matches job
# - HM validation created
# - HM responds
# - Interview scheduled
# - Check email confirmations

# 5. Verify data integrity
# SELECT * FROM thunder_sessions WHERE candidate_email = 'test1@staging.com'
# SELECT * FROM hiring_manager_validations WHERE candidate_id = 'test_cand_123'

# 6. Check logs for errors
# tail -f staging-logs/app.log | grep -i error

# 7. Performance check
# curl https://staging-api.blitzenx.com/api/v1/thunder/sessions \
#   -H "Authorization: Bearer $TOKEN" \
#   -w "@timing.txt"
```

---

## 🚀 Launch Checklist

### Pre-Launch (1 week before)
- [ ] Database migrations created and tested on staging
- [ ] All 25+ tests passing locally
- [ ] Load testing completed (100+ concurrent users)
- [ ] Email templates reviewed and sent to legal
- [ ] HM validation questions created for all open jobs
- [ ] careers.blitzenx.com frontend deployed to staging
- [ ] Staging environment tested end-to-end
- [ ] Monitoring configured (CloudWatch, Sentry, Slack alerts)
- [ ] Runbooks created for on-call engineers
- [ ] Team training completed

### Launch Day
- [ ] Deployment window scheduled (off-peak hours)
- [ ] Database backups created
- [ ] Migrations applied to production
- [ ] API endpoints deployed
- [ ] careers.blitzenx.com deployed to production
- [ ] Smoke tests run (quick sanity checks)
- [ ] Monitor error logs for 30 minutes
- [ ] Send email to HMs about new HM Validation feature
- [ ] Enable feature flag if using one
- [ ] Post-launch support ready

### Post-Launch (1 week after)
- [ ] Monitor key metrics:
  - Session creation rate
  - Completion rate (Q1 → Q12)
  - Submission rate
  - HM validation response time
  - Interview scheduling rate
- [ ] Collect user feedback via form/survey
- [ ] Fix any critical bugs immediately
- [ ] Document lessons learned
- [ ] Plan Phase 2 enhancements

---

## 🔍 Critical Paths to Test

### Path 1: Happy Path (Thunder → HM Approval → Interview)
```
Candidate completes Thunder
  ↓
AI Recruiter finds job match
  ↓
HM validation created
  ↓
HM approves (score 8+)
  ↓
Interview auto-scheduled
  ↓
Email sent to candidate
✅ PASS if: Interview record created + email received
```

### Path 2: HM Rejection (Try Next Candidate)
```
Candidate 1 matches to Job X
  ↓
HM rejects Candidate 1
  ↓
AI Recruiter tries Candidate 2 for Job X
  ↓
HM validation created for Candidate 2
✅ PASS if: Second validation created, first marked as REJECTED
```

### Path 3: Timeout Escalation
```
Validation created
  ↓
Timeout timer running (24 hours)
  ↓
Scheduled job finds expired
  ↓
Status changed to ESCALATED
  ↓
Email sent to HM's manager
✅ PASS if: Escalation record created + email sent
```

### Path 4: Session Resume (Form Persistence)
```
Candidate starts Thunder → answers Q1-Q4 → closes browser
  ↓
Candidate returns next day via email link
  ↓
Session resumed at Q5 (last_question_reached=Q4)
  ↓
Previous answers (Q1-Q4) still available
  ↓
Candidate continues from Q5
✅ PASS if: form_responses still populated, no data loss
```

---

## 📊 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|-----------------|
| Session Creation Rate | 100/day | Backend logs, CloudWatch |
| Completion Rate (Q1→Q12) | 70%+ | form_responses count |
| Submission Rate | 60%+ of completions | submitted=true count |
| Average Session Duration | 5-10 min | (completed_at - created_at) |
| HM Validation Response Time | <24hrs | 90%+ respond within timeout |
| Interview Scheduling Rate | 80%+ of approvals | interview_scheduled_at not null |
| Resume Parse Success | 95%+ | resume_parse_status="SUCCESS" |
| Error Rate (API) | <1% | 5xx status code count |
| Timeout Escalation Rate | <5% | escalated validations count |

---

## 🛠️ Troubleshooting Guide

### Issue: Session Not Resuming
**Symptom:** Candidate returns but starts new session instead of resuming  
**Cause:** `last_question_reached` not updated or email link malformed  
**Fix:** 
1. Check last_activity_at is recent
2. Verify email link format: `/apply/status?session_id=xxx&email=yyy`
3. Check localStorage for draft (browser-side backup)

### Issue: HM Not Receiving Email
**Symptom:** HM doesn't get validation email  
**Cause:** Email service not configured or HM email missing  
**Fix:**
1. Check email_sent_at timestamp
2. Verify email service credentials in .env
3. Check spam folder
4. Verify hiring_manager_id maps to valid user email

### Issue: Resume Upload Failing
**Symptom:** File upload returns 400 error  
**Cause:** File too large or unsupported format  
**Fix:**
1. Check file size <5MB
2. Verify format is PDF or DOCX
3. Check S3 bucket permissions
4. Check disk space on server

### Issue: Timeout Job Not Running
**Symptom:** Validations stay PENDING past 24 hours  
**Cause:** Scheduled job not configured  
**Fix:**
1. Verify Celery/APScheduler running
2. Check cron job configuration
3. Check logs for job execution errors
4. Manually trigger: `python manage.py handle_expired_validations`

### Issue: High Error Rate in Logs
**Symptom:** 5xx errors in API logs  
**Cause:** Database connection, service unavailable, or code bug  
**Fix:**
1. Check database connection string
2. Verify all services running (AI Recruiter, email service)
3. Check CloudWatch logs for stack traces
4. Roll back deployment if recent change
5. Alert on-call engineer

---

## 📞 Support & Escalation

### On-Call Runbook

**Page 1: Session Issues**
```
Symptom: Candidates complaining sessions lost
Action:
1. Check last_activity_at timestamp
2. Verify localStorage has backup (browser dev tools)
3. Check database for session record
4. If missing: Recreate session, ask candidate to restart
5. Escalate: Database corruption → Database team
```

**Page 2: HM Validation Stuck**
```
Symptom: HM sees "Pending" but already responded
Action:
1. Check validation.responded_at timestamp
2. If null: HM didn't actually submit (UI bug)
3. Check responses field for empty JSON
4. Escalate: Backend error → Dev team to investigate
5. Manual fix: UPDATE hiring_manager_validations SET status='APPROVED' WHERE id=xxx
```

**Page 3: Interview Not Scheduled**
```
Symptom: HM approved but no interview created
Action:
1. Check job.auto_schedule_after_approval flag
2. Check interview record in database
3. If missing: Manual creation + email candidate
4. Escalate: Interview service failure → Backend team
```

---

## 📈 Future Enhancements (Post-Launch)

After successful launch, consider:

1. **ML-based decision scoring** - Replace hardcoded decision logic with ML model
2. **Candidate ranking** - Sort HM validations by match score
3. **Bulk HM validation** - HM can approve/reject multiple candidates at once
4. **Interview scheduling assistant** - Suggest optimal times
5. **Feedback loop** - Track offer acceptance rate by HM, improve matching
6. **Mobile app** - Native iOS/Android for HM validation
7. **Video screening** - Add video Q&A option before HM validation
8. **Multi-language support** - Thunder in multiple languages
9. **Analytics dashboard** - Real-time funnel metrics
10. **Interview AI** - Auto-conduct initial technical screening

---

## 📚 Documentation References

- **IMPLEMENTATION_COMPLETE.md** - Full implementation summary
- **THUNDER_HM_IMPLEMENTATION_GUIDE.md** - API specs, SQL schema, services
- **CAREERS_PORTAL_ARCHITECTURE.md** - Frontend architecture for careers.blitzenx.com
- **CLAUDE.md** - Project backlog and decisions
- **API_DOCUMENTATION.md** - (Generate with Swagger/OpenAPI)
- **DATABASE_SCHEMA.md** - (Generate with SchemaCrawler)

---

**Status:** ✅ Ready for Testing & Launch  
**Owner:** Dev Team + QA Team  
**Timeline:** 1 week testing + 1 week launch = 2 weeks total  
**Go-Live Date:** 2026-08-27 (estimated)

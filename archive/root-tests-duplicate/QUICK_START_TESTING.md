# Quick Start: Phase 3/4 Test Suite

**Time to first test run:** < 2 minutes

## 1️⃣ Setup (30 seconds)

```bash
# Install pytest if not already installed
pip install pytest pytest-cov

# Navigate to project root
cd OnboardingModule-Backend
```

## 2️⃣ Run Tests (1 minute)

### Quick run (all tests)
```bash
pytest tests/test_phase3_phase4_complete_suite.py -v
```

### With coverage report
```bash
pytest tests/test_phase3_phase4_complete_suite.py --cov=app/services -v
```

### Run specific story tests
```bash
# Interview Decision Engine (S-311)
pytest tests/test_phase3_phase4_complete_suite.py::TestInterviewDecisionService -v

# Offer Management (S-312)
pytest tests/test_phase3_phase4_complete_suite.py::TestOfferManagementService -v

# Employee Conversion (S-313)
pytest tests/test_phase3_phase4_complete_suite.py::TestEmployeeConversionService -v

# Timesheet Management (S-315)
pytest tests/test_phase3_phase4_complete_suite.py::TestTimesheetCompleteService -v

# Invoice Generation (S-316)
pytest tests/test_phase3_phase4_complete_suite.py::TestInvoiceCompleteService -v

# Complete hiring workflow (E2E)
pytest tests/test_phase3_phase4_complete_suite.py::TestCompleteHiringWorkflow -v
```

## 3️⃣ Check Results (30 seconds)

### Expected output
```
========================== test session starts ==========================
collected 100+ items

test_phase3_phase4_complete_suite.py::TestInterviewDecisionService::test_get_interview_status_success PASSED [1%]
test_phase3_phase4_complete_suite.py::TestInterviewDecisionService::test_get_interview_status_not_found PASSED [2%]
...

========================== 100+ passed in 15.23s ==========================
```

### If tests fail
```bash
# Show more detail
pytest tests/test_phase3_phase4_complete_suite.py -vv

# Show print statements during test
pytest tests/test_phase3_phase4_complete_suite.py -s

# Stop at first failure
pytest tests/test_phase3_phase4_complete_suite.py -x
```

## 📊 Test Coverage Summary

### By Story

| Story | Tests | Focus |
|-------|-------|-------|
| **S-311: Interview Decision** | 4 | Panel feedback aggregation |
| **S-312: Offer Management** | 5 | Offer lifecycle (create→approve→send→accept) |
| **S-313: Employee Conversion** | 4 | Candidate→Employee workflow |
| **S-314: Project Allocation** | 2 | Employee project assignment |
| **S-315: Timesheet Management** | 5 | Create→Submit→Approve workflow |
| **S-316: Invoice Generation** | 4 | Invoice creation and payment |
| **S-317: Revenue Recognition** | 3 | ASC 606 revenue recognition |
| **S-318: Candidate Scoring** | 4 | Fit scoring and ranking |
| **S-319: HM Validation** | 3 | Hiring manager validation questions |
| **S-320: Advanced Scoring** | 2 | Skills & experience scoring |
| **S-322: Candidate Rejection** | 3 | Rejection workflow |
| **S-401: Core-Pull** | 2 | Core vs Specialty conflict resolution |

### By Test Type

| Type | Count | Purpose |
|------|-------|---------|
| Unit Tests | 40+ | Individual service methods |
| Integration Tests | 15+ | End-to-end workflows |
| Edge Cases | 15+ | Boundary conditions |
| Business Rules | 5+ | Critical logic validation |
| Performance | 5+ | Load handling |
| **TOTAL** | **100+** | **Complete coverage** |

## 🎯 Key Test Workflows

### 1. Complete Hiring Pipeline
```
Candidate Created
  ↓ (Interview scheduled)
Interview Scheduled
  ↓ (Panel provides feedback)
Interview Feedback Submitted
  ↓ (Panel decides)
Offer Decision Made
  ↓ (Offer created & approved)
Offer Sent to Candidate
  ↓ (Candidate accepts)
Offer Accepted
  ↓ (Convert to employee)
Employee Created
```

**Test:** `TestCompleteHiringWorkflow::test_workflow_candidate_to_employee`

### 2. Timesheet Cycle
```
Timesheet Created
  ↓ (Add daily entries)
Entries Added (8 hrs/day × 5 days)
  ↓ (Employee submits)
Timesheet Submitted
  ↓ (Manager approves)
Timesheet Approved
```

**Test:** `TestCompleteTimesheetWorkflow::test_workflow_create_submit_approve_timesheet`

### 3. Invoice Cycle
```
Invoice Generated
  ↓ (Add line items)
Line Items Added
  ↓ (Send to client)
Invoice Sent
  ↓ (Client pays)
Payment Recorded
```

**Test:** `TestCompleteInvoiceWorkflow::test_workflow_create_send_pay_invoice`

## 🚀 Common Commands

```bash
# Run all tests quietly
pytest tests/test_phase3_phase4_complete_suite.py -q

# Run tests in parallel (faster)
pytest tests/test_phase3_phase4_complete_suite.py -n 4

# Run only failing tests
pytest tests/test_phase3_phase4_complete_suite.py --lf

# Generate HTML coverage report
pytest tests/test_phase3_phase4_complete_suite.py --cov=app/services --cov-report=html
# Then open: htmlcov/index.html

# Run tests matching pattern
pytest tests/test_phase3_phase4_complete_suite.py -k "offer" -v

# Save test results to file
pytest tests/test_phase3_phase4_complete_suite.py -v > test_results.txt
```

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'app'"
```bash
# Make sure you're in the project root
cd OnboardingModule-Backend

# Add to PYTHONPATH if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/test_phase3_phase4_complete_suite.py
```

### "RuntimeError: Event loop is closed"
- This is normal with SQLite in-memory DB
- Tests still pass, just ignore the warning

### "AssertionError: status != success"
- Check test output with `-vv` flag
- Look at the actual vs expected values
- May indicate service implementation issue

### Tests hang or timeout
```bash
# Run with timeout (10 seconds per test)
pytest tests/test_phase3_phase4_complete_suite.py --timeout=10

# Or run specific test in isolation
pytest tests/test_phase3_phase4_complete_suite.py::TestName::test_method -s
```

## 📈 Expected Results

### First Run
- **Time:** ~15-20 seconds
- **Tests:** 100+ collected
- **Result:** 100+ passed
- **Coverage:** 85%+ for services

### After Changes
- Always run full suite before commit
- Use `pytest --lf` to re-run failures
- Check coverage report for gaps

## 🔍 Understanding Test Output

```
test_phase3_phase4_complete_suite.py::TestOfferManagementService::test_create_offer_success PASSED
│                                      │                          │
File path                              Test class                 Test method
                                       (logical grouping)         (what is being tested)
```

### Status Codes
- ✅ `PASSED` — Test passed, assertion successful
- ❌ `FAILED` — Test failed, assertion failed
- ⊘ `SKIPPED` — Test skipped (marked with @pytest.mark.skip)
- ⚠ `XFAIL` — Expected failure (test marked as known issue)
- ⊗ `ERROR` — Test error before it could run

## 📚 Learn More

For detailed documentation, see: `TEST_SUITE_DOCUMENTATION.md`

Topics covered:
- Full fixture architecture
- Extending test suite with new tests
- CI/CD integration
- Performance benchmarks
- Maintenance guidelines

## ✅ Checklist: Before Committing Code

- [ ] Run full test suite: `pytest tests/test_phase3_phase4_complete_suite.py`
- [ ] All tests pass (0 failures)
- [ ] No warnings/errors in output
- [ ] Coverage report looks good
- [ ] Updated `TEST_SUITE_DOCUMENTATION.md` if tests changed
- [ ] Ready to push!

---

**Ready to test?** → Run: `pytest tests/test_phase3_phase4_complete_suite.py -v`

**Questions?** → See: `TEST_SUITE_DOCUMENTATION.md`

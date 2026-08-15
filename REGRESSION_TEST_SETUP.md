# Comprehensive Regression Test Suite Setup

**Status: MANDATORY for all developers**

Every commit runs the complete regression suite. The system will **block commits that fail tests**.

---

## What Gets Tested

The regression suite tests **EVERYTHING**:

- ✅ **113 Models** - All CRUD operations
- ✅ **206 Services** - All business logic
- ✅ **30+ API Endpoints** - All REST endpoints
- ✅ **End-to-End Workflows** - Complete user journeys
- ✅ **Stress Tests** - Load testing (10K concurrent)
- ✅ **Edge Cases** - Null values, boundary conditions
- ✅ **Security** - SQL injection, auth, tenant isolation
- ✅ **Data Integrity** - FK constraints, unique constraints

**Total coverage:** 70%+ code coverage required to merge.

---

## Setup for Local Development

### Step 1: Install Testing Dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-cov pytest-timeout pytest-asyncio
```

### Step 2: Enable Pre-Commit Hook

```bash
# Configure git to use the hooks directory
git config core.hooksPath .githooks

# Make the hook executable
chmod +x .githooks/pre-commit

# Verify it's enabled
git config core.hooksPath  # Should print: .githooks
```

### Step 3: Run Regression Suite Locally

```bash
# Run full suite
pytest tests/regression_suite.py -v

# Run specific test class
pytest tests/regression_suite.py::TestAPIEndpoints -v

# Run with coverage report
pytest tests/regression_suite.py --cov=app --cov-report=html

# Run specific category (using markers)
pytest tests/regression_suite.py -m critical -v      # Only critical tests
pytest tests/regression_suite.py -m stress -v        # Only stress tests
pytest tests/regression_suite.py -m security -v      # Only security tests
```

---

## How It Works

### 1. Pre-Commit Hook (Local)

When you run `git commit`:

```
1. Git checks if any .py files are staged
2. If yes, runs: pytest tests/regression_suite.py
3. If tests PASS → Commit proceeds
4. If tests FAIL → Commit is BLOCKED
```

**To commit despite failures** (not recommended):

```bash
git commit --no-verify  # SKIP TESTING (use only for emergency!)
```

### 2. GitHub Actions (CI/CD)

Every push to `main` or `develop` triggers:

1. Full regression suite (30 min timeout)
2. API contract tests
3. Coverage report upload to Codecov
4. Slack notification on failure

**Required status checks before merge:**

- ✅ Regression tests pass
- ✅ Coverage ≥ 70%
- ✅ No critical failures

---

## Common Issues & Fixes

### Issue: "Pre-commit hook not running"

```bash
# Solution: Re-enable the hook
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

### Issue: "Tests fail locally but should pass"

```bash
# Solution: Ensure PostgreSQL is running
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=123 postgres:18

# Set test database URL
export DATABASE_URL=postgresql://postgres:123@localhost:5432/wros_test

# Reinitialize database
python -c "from sqlalchemy import create_engine; from app.models.base import Base; engine = create_engine('$DATABASE_URL'); Base.metadata.create_all(engine)"

# Rerun tests
pytest tests/regression_suite.py -v
```

### Issue: "Specific test is flaky/random"

```bash
# Run the test multiple times
pytest tests/regression_suite.py::TestStressAndLoad::test_concurrent_candidate_creation -v --count=10
```

### Issue: "I need to skip a test temporarily"

```python
# Mark test as skip in code (do NOT bypass pre-commit hook)
@pytest.mark.skip(reason="Temporary - fix in PR #123")
def test_something():
    pass
```

---

## Regression Test Categories

### Critical Path Tests (MUST PASS)

These tests verify the core hiring workflow end-to-end:

```bash
pytest tests/regression_suite.py -m critical -v
```

Tests include:
- Candidate creation (only path: createCandidateSafe)
- Job matching
- Interview scheduling
- Offer generation
- Employee creation
- Notifications (only path: sendNotification)

### Stress Tests (LOAD TESTING)

```bash
pytest tests/regression_suite.py -m stress -v
```

- 100 concurrent candidate creation
- 10,000 candidate bulk import
- Connection pool exhaustion
- Memory/resource limits

### Security Tests

```bash
pytest tests/regression_suite.py -m security -v
```

- SQL injection prevention
- Authentication required
- Tenant isolation
- Authorization checks

---

## Running Tests on CI/CD

GitHub Actions runs automatically on:

1. **Every push to main**
2. **Every pull request**
3. **Hourly schedule** (catch regressions)

View results:

```bash
# Check GitHub Actions
https://github.com/blitzenx25/OnboardingModule-Backend/actions

# Or from CLI
gh run list --repo blitzenx25/OnboardingModule-Backend
gh run view <run-id> --repo blitzenx25/OnboardingModule-Backend
```

---

## Requirements for Merging

Every pull request must pass:

| Check | Requirement | Command |
|-------|-------------|---------|
| Regression Tests | All pass | `pytest tests/regression_suite.py -v` |
| Code Coverage | ≥ 70% | `pytest --cov=app --cov-report=term-missing` |
| Status Checks | GitHub Actions ✓ | View in PR |
| No Critical Failures | 0 critical test failures | CI/CD report |

---

## For Code Reviewers

When reviewing PRs:

1. Check that regression tests pass (green checkmark on PR)
2. Review the coverage report (attached in checks)
3. For API changes, verify contract tests pass
4. For schema changes, verify integrity tests pass

---

## Troubleshooting Commands

```bash
# Clear test cache
pytest --cache-clear

# Verbose output with print statements
pytest tests/regression_suite.py -v -s

# Stop on first failure
pytest tests/regression_suite.py -x

# Show slowest 10 tests
pytest tests/regression_suite.py -v --durations=10

# Generate HTML coverage report
pytest tests/regression_suite.py --cov=app --cov-report=html
# Then open: htmlcov/index.html

# Run specific test by name
pytest tests/regression_suite.py::TestAPIEndpoints::test_candidate_endpoints -v
```

---

## Architecture: What Gets Tested

```
┌─────────────────────────────────────────────────┐
│ COMPREHENSIVE REGRESSION SUITE                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  Layer 1: API Endpoints (30+ endpoints)         │
│  ├─ Auth, Candidates, Employees, Jobs, etc.    │
│  └─ Each endpoint: 200/401/404 response codes  │
│                                                  │
│  Layer 2: Models (113 models)                   │
│  ├─ CRUD: Create, Read, Update, Delete         │
│  ├─ FK constraints, Unique constraints         │
│  └─ Null/default handling                      │
│                                                  │
│  Layer 3: Services (206 services)               │
│  ├─ Business logic validation                   │
│  ├─ Core paths (createCandidateSafe, etc.)    │
│  └─ Error handling                              │
│                                                  │
│  Layer 4: Workflows (End-to-End)                │
│  ├─ Hiring pipeline                            │
│  ├─ Bulk import                                │
│  └─ Complete user journeys                      │
│                                                  │
│  Layer 5: Stress Tests (Try to break it)        │
│  ├─ 100 concurrent operations                   │
│  ├─ 10,000 bulk import                          │
│  └─ Connection pool exhaustion                  │
│                                                  │
│  Layer 6: Edge Cases & Boundaries               │
│  ├─ Null values                                 │
│  ├─ Invalid inputs                              │
│  └─ Extremely long strings                      │
│                                                  │
│  Layer 7: Security                              │
│  ├─ SQL injection prevention                    │
│  ├─ Authentication checks                       │
│  └─ Tenant isolation                            │
│                                                  │
│  Layer 8: Data Integrity                        │
│  ├─ Foreign key constraints                     │
│  └─ Unique constraints                          │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Questions?

Contact the team or see: `/docs/TESTING.md`

**Remember:** Tests are not optional. They're the guardrail between "working code" and "broken code". ✓

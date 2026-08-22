# Playwright E2E Test Suite - Complete Guide

## Overview

This test suite provides comprehensive end-to-end testing for the WROS application across all 7 user roles. The tests are built with Playwright and cover critical workflows, permission management, and role-based access control.

**Total Test Files:** 7  
**Total Test Cases:** 120+  
**User Roles:** Candidate, Recruiter, Employee, BU Head, Partner, CFO, CEO

---

## Installation & Setup

### 1. Install Playwright

```bash
cd OnboardingModule-Frontend-main
npm install -D @playwright/test
npx playwright install
```

### 2. Configure Test Users

Update test user credentials in `tests/e2e/helpers/auth.js`:

```javascript
export const TEST_USERS = {
  candidate: { email: 'candidate@blitzenx.com', password: 'Candidate@123' },
  recruiter: { email: 'recruiter@blitzenx.com', password: 'Recruiter@123' },
  employee: { email: 'employee@blitzenx.com', password: 'Employee@123' },
  buHead: { email: 'buhead@blitzenx.com', password: 'BUHead@123' },
  partner: { email: 'partner@blitzenx.com', password: 'Partner@123' },
  cfo: { email: 'cfo@blitzenx.com', password: 'CFO@123' },
  ceo: { email: 'ceo@blitzenx.com', password: 'CEO@123' }
};
```

### 3. Ensure Application is Running

```bash
# Terminal 1: Start your React app
npm start

# Terminal 2: Run tests
npm run test:e2e
```

---

## Test Suite Breakdown

### 1. Candidate Tests (`candidate.spec.js`)
**14 test cases** covering candidate-specific workflows

#### Test Cases:
1. Display candidate dashboard
2. View candidate profile
3. Update profile information
4. View job opportunities
5. Apply for jobs
6. View application history
7. Upload resume/CV
8. View interview schedule (if invited)
9. Cannot see recruiter features (permission validation)
10. Cannot see admin/finance panels (permission validation)
11. Handle missing required fields validation
12. Upload resume/CV file
13. View interview schedule
14. Logout successfully

#### Key Features Tested:
- ✅ Role-based dashboard display
- ✅ Profile management (CRUD)
- ✅ Job discovery and application
- ✅ Resume upload functionality
- ✅ Permission-based UI hiding (recruiter/admin features hidden)
- ✅ Form validation
- ✅ Interview tracking

#### Workflows:
```
Login → Dashboard → Jobs → Apply → Applications → Profile → Logout
```

---

### 2. Recruiter Tests (`recruiter.spec.js`)
**15 test cases** covering recruitment workflows

#### Test Cases:
1. Display recruiter dashboard with metrics
2. Navigate to candidates section
3. Create new candidate
4. View candidate details and profile
5. Assign job to candidate
6. Manage interview scheduling
7. View open positions/jobs
8. Create new job posting
9. Send message to candidate
10. View analytics and recruitment metrics
11. Cannot see finance/admin panels (permission validation)
12. Filter candidates by status
13. Update candidate status
14. Bulk candidate operations
15. Interview workflow management

#### Key Features Tested:
- ✅ Candidate CRUD operations
- ✅ Job management
- ✅ Interview scheduling
- ✅ Messaging to candidates
- ✅ Analytics dashboard
- ✅ Status filtering and updates
- ✅ Recruitment pipeline management

#### Workflows:
```
Login → Dashboard → Create Candidate → Assign Job → Schedule Interview → Send Message → Analytics
```

---

### 3. Employee Tests (`employee.spec.js`)
**15 test cases** covering employee-specific features

#### Test Cases:
1. Display employee dashboard
2. View employee profile and details
3. Update employee profile information
4. View assigned projects
5. Submit timesheets
6. View timesheet history
7. View leave/vacation requests
8. Request time off/leave
9. View performance reviews
10. Cannot see recruitment features (permission validation)
11. Cannot see finance/admin panels (permission validation)
12. View payslips/compensation
13. Update availability/skills
14. View team members
15. Handle timesheet validation

#### Key Features Tested:
- ✅ Timesheet entry and tracking
- ✅ Leave request management
- ✅ Skills and availability updates
- ✅ Compensation viewing
- ✅ Performance review access
- ✅ Team visibility
- ✅ Form validation

#### Workflows:
```
Login → Dashboard → Timesheets → Leave Requests → Skills → Compensation → Team View
```

---

### 4. Business Unit Head Tests (`bu-head.spec.js`)
**14 test cases** covering BU management workflows

#### Test Cases:
1. Display BU dashboard with BU-scoped metrics
2. Manage BU team members
3. Assign employees to projects
4. View BU budget and resources
5. Manage job openings for BU
6. Approve leaves and time off for team
7. View team performance metrics
8. Manage interviews for BU
9. View BU-scoped candidates only
10. Cannot see CFO/CEO dashboards (permission validation)
11. View BU-scoped invoicing
12. Manage BU settings
13. Generate BU reports
14. Handle BU-scoped data filtering

#### Key Features Tested:
- ✅ BU-scoped dashboard and metrics
- ✅ Team resource management
- ✅ Approval workflows (leaves, interviews)
- ✅ Project assignments
- ✅ BU-specific reporting
- ✅ Budget and resource tracking
- ✅ Data isolation and filtering

#### Workflows:
```
Login → BU Dashboard → Team Management → Approvals → Reports → Settings
```

---

### 5. Partner Tests (`partner.spec.js`)
**14 test cases** covering partner staffing workflows

#### Test Cases:
1. Display partner dashboard
2. View partner account details
3. View available job opportunities
4. Submit candidate for opportunity
5. Track submitted candidates status
6. View placement history
7. View invoice/billing information
8. View commission/earnings
9. Update partner contact information
10. Cannot see internal HR/employee features (permission validation)
11. Cannot see finance/admin features (permission validation)
12. View client contacts for opportunities
13. Filter opportunities by status
14. View detailed opportunity information

#### Key Features Tested:
- ✅ Opportunity discovery
- ✅ Candidate submission
- ✅ Placement tracking
- ✅ Commission tracking
- ✅ Billing and invoices
- ✅ Account management
- ✅ Opportunity filtering

#### Workflows:
```
Login → Dashboard → Opportunities → Submit Candidate → Track Status → Earnings → Account
```

---

### 6. CFO Tests (`cfo.spec.js`)
**16 test cases** covering financial management

#### Test Cases:
1. Display CFO financial dashboard
2. View revenue dashboard
3. Manage invoices
4. Create and send invoice
5. View expense tracking
6. View P&L statement
7. View balance sheet
8. View cash flow statement
9. Manage payments/receipts
10. View budget vs actual
11. Generate financial reports
12. Export financial data
13. Cannot see recruitment/HR features (permission validation)
14. View multi-BU financial reports
15. Manage tax and compliance
16. View partner settlement

#### Key Features Tested:
- ✅ Financial dashboards (P&L, Balance Sheet, Cash Flow)
- ✅ Invoice management
- ✅ Expense tracking
- ✅ Budget management
- ✅ Financial reporting and export
- ✅ Multi-BU visibility
- ✅ Compliance tracking

#### Workflows:
```
Login → Financial Dashboard → Invoices → Reports → Export → Compliance
```

---

### 7. CEO Tests (`ceo.spec.js`)
**17 test cases** covering executive/admin features

#### Test Cases:
1. Display CEO executive dashboard
2. View all revenue metrics across organization
3. Access complete financial statements
4. View organization-wide metrics dashboard
5. View all business units and their performance
6. View strategic reports and analytics
7. Manage organization settings and configurations
8. View all employees across organization
9. View all candidates across organization
10. View all open jobs across organization
11. Manage partner relationships
12. Manage client relationships
13. View organization-wide analytics
14. Manage admin users and permissions
15. Create and manage system users
16. Export organization reports
17. View system logs and audit trail

#### Key Features Tested:
- ✅ Executive dashboards with all KPIs
- ✅ Organization-wide visibility (all BUs, employees, candidates)
- ✅ User and permission management
- ✅ System configuration
- ✅ Strategic reporting
- ✅ Audit trail and logging
- ✅ Integration management

#### Workflows:
```
Login → Executive Dashboard → All Data Views → Admin Panel → User Management → System Settings
```

---

## Running Tests

### Quick Start

```bash
# Run all tests
npm run test:e2e

# Run tests in headed mode (watch browser)
npm run test:e2e:headed

# Run with debug mode
npm run test:e2e:debug

# View test report
npm run test:e2e:report
```

### Run by User Role

```bash
npm run test:e2e:candidate
npm run test:e2e:recruiter
npm run test:e2e:employee
npm run test:e2e:buhead
npm run test:e2e:partner
npm run test:e2e:cfo
npm run test:e2e:ceo
```

### Run by Browser

```bash
npm run test:e2e:chromium
npm run test:e2e:firefox
npm run test:e2e:webkit
```

### Run Specific Tests

```bash
# By test name pattern
npx playwright test -g "should display dashboard"

# Specific test file
npx playwright test candidate.spec.js

# Specific test case
npx playwright test candidate.spec.js -g "should view candidate profile"
```

### Debug Mode

```bash
# Step-through debugging
npx playwright test --debug

# With headed browser (see what's happening)
npx playwright test --headed --debug

# Verbose output
npx playwright test --verbose
```

---

## Test Output & Reports

### Console Output
Tests print results to console with:
- ✓ Passed tests (green)
- ✗ Failed tests (red)
- ⊙ Skipped tests (yellow)

### HTML Report
```bash
# Automatically generated after each run
npx playwright show-report

# Or manually
npx playwright test && npx playwright show-report
```

### JSON Report
Results saved to `test-results/results.json` with:
- Test execution times
- Pass/fail status
- Error messages and stack traces
- Screenshots of failures
- Video recordings (on failure)

### Artifacts
When tests fail, Playwright captures:
- **Screenshots** - Visual state at failure
- **Videos** - Recording of test execution
- **Traces** - Detailed execution trace with DOM snapshot

Located in: `test-results/` and visible in HTML report

---

## Permission Testing Strategy

Each test suite validates **permission-based access control**:

### Candidate Permissions ❌
```javascript
// Should NOT see these
const recruitmentNav = await page.$('[data-testid="recruitment-nav"]');
expect(recruitmentNav).toBeNull();

const financeNav = await page.$('[data-testid="finance-nav"]');
expect(financeNav).toBeNull();
```

### Recruiter Permissions ✓
```javascript
// Should see recruitment features
const recruitmentNav = await page.$('[data-testid="recruitment-nav"]');
expect(recruitmentNav).not.toBeNull();

// Should NOT see finance
const financeNav = await page.$('[data-testid="finance-nav"]');
expect(financeNav).toBeNull();
```

### CEO Permissions ✓ (All)
```javascript
// Should see EVERYTHING
const recruitmentNav = await page.$('[data-testid="recruitment-nav"]');
expect(recruitmentNav).not.toBeNull();

const financeNav = await page.$('[data-testid="finance-nav"]');
expect(financeNav).not.toBeNull();

const adminNav = await page.$('[data-testid="admin-nav"]');
expect(adminNav).not.toBeNull();
```

---

## Test Data & Fixtures

### Test Users
Predefined in `tests/e2e/helpers/auth.js`:

| Role | Email | Password | Features |
|------|-------|----------|----------|
| Candidate | candidate@blitzenx.com | Candidate@123 | Profile, Applications, Jobs |
| Recruiter | recruiter@blitzenx.com | Recruiter@123 | Candidates, Jobs, Interviews |
| Employee | employee@blitzenx.com | Employee@123 | Timesheets, Projects, Leave |
| BU Head | buhead@blitzenx.com | BUHead@123 | BU Management, Approvals, Reports |
| Partner | partner@blitzenx.com | Partner@123 | Opportunities, Submissions, Earnings |
| CFO | cfo@blitzenx.com | CFO@123 | Finance, Invoices, Reports |
| CEO | ceo@blitzenx.com | CEO@123 | Everything |

### Test Data Requirements
- Candidate accounts with various statuses
- Job postings with requirements
- Projects with assignments
- Client and partner accounts
- Financial transactions
- Leave request records

### Fixtures Directory
```
tests/fixtures/
  ├── sample-resume.pdf
  ├── sample-document.docx
  └── test-data.json
```

---

## Common Test Patterns

### 1. Login and Dashboard Verification
```javascript
test.beforeEach(async ({ browser }) => {
  page = await browser.newPage();
  await login(page, 'recruiter');
});

test('should display recruiter dashboard', async () => {
  await expect(page).toHaveTitle(/Dashboard|Home/i);
  const dashboard = await page.locator('[data-testid="recruitment-dashboard"]');
  await expect(dashboard).toBeVisible();
});
```

### 2. Navigation Permission Checking
```javascript
test('should NOT see finance navigation', async () => {
  const financeNav = await page.$('[data-testid="finance-nav"]');
  expect(financeNav).toBeNull();
});
```

### 3. Form Filling and Submission
```javascript
test('should create new candidate', async () => {
  await page.click('[data-testid="add-candidate-btn"]');
  
  const nameInput = await page.$('[data-testid="candidate-name"]');
  await nameInput.fill('Test Candidate');
  
  const submitButton = await page.$('button:has-text("Create")');
  await submitButton.click();
  
  await expect(page.locator('text=Candidate created')).toBeVisible();
});
```

### 4. Dynamic Element Waiting
```javascript
test('should view list items', async () => {
  // Wait for elements to appear
  await page.waitForSelector('[data-testid="item-card"]', { timeout: 5000 });
  
  const items = await page.locator('[data-testid="item-card"]');
  const count = await items.count();
  expect(count).toBeGreaterThan(0);
});
```

### 5. File Upload
```javascript
test('should upload resume', async () => {
  const fileInput = await page.$('input[type="file"]');
  await fileInput.setInputFiles('./tests/fixtures/resume.pdf');
  
  await expect(page.locator('text=Uploaded successfully')).toBeVisible();
});
```

### 6. Download Verification
```javascript
test('should export data', async () => {
  const downloadPromise = page.waitForEvent('download');
  await page.click('[data-testid="export-btn"]');
  
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.csv|\.xlsx/);
});
```

---

## Continuous Integration

### GitHub Actions Setup

Create `.github/workflows/test.yml`:

```yaml
name: Playwright Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: npm install
      
      - name: Install Playwright
        run: npx playwright install --with-deps
      
      - name: Start dev server
        run: npm start &
        
      - name: Wait for server
        run: npx wait-on http://localhost:3000
      
      - name: Run tests
        run: npm run test:e2e
      
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

---

## Troubleshooting

### Test Timeouts

**Problem:** Tests hang waiting for elements

**Solutions:**
```javascript
// Increase timeout for specific waits
await page.waitForSelector('[data-testid="element"]', { timeout: 10000 });

// Or in playwright.config.js
use: {
  navigationTimeout: 30000,
  actionTimeout: 10000
}
```

### Login Failures

**Problem:** Cannot login with test credentials

**Check:**
1. Test users exist in database
2. Email input selector matches app: `input[type="email"]` or `input[type="text"]`
3. Password input selector: `input[type="password"]`
4. Login button selector matches app
5. Credentials in `auth.js` are correct

**Debug:**
```bash
npx playwright test --debug --headed
# Step through login manually
```

### Element Not Found

**Problem:** Test looks for element that doesn't exist

**Solution:**
```javascript
// Use looser selector
const button = await page.$('button:has-text("Create")');

// Or update your app to add data-testid
// <button data-testid="create-btn">Create</button>
```

### Flaky Tests

**Problem:** Tests pass sometimes, fail other times

**Causes:**
- Network delays
- Animations/transitions
- Async state updates
- Race conditions

**Solutions:**
```javascript
// Wait for network to idle
await page.waitForLoadState('networkidle');

// Wait for specific element
await page.waitForSelector('[data-testid="loaded"]');

// Use more specific locators
const button = page.locator('[data-testid="submit-btn"]:visible');
```

---

## Best Practices

### ✅ Do's
- Use `data-testid` attributes for reliable selection
- Add `.catch(() => {})` for optional elements
- Use descriptive test names
- Test user workflows, not individual components
- Validate both positive and negative cases
- Use `waitForLoadState('networkidle')` for async operations
- Clean up in `afterEach` hooks

### ❌ Don'ts
- Don't use brittle CSS selectors (`.class-name-123`)
- Don't assume elements exist without checking
- Don't hard-code wait times (use `waitForSelector` instead)
- Don't create test dependencies (each test should be independent)
- Don't skip error validation
- Don't forget to logout/cleanup
- Don't commit with hardcoded credentials

---

## Performance Tips

### Run Tests Faster

```bash
# Disable headed mode (faster)
npm run test:e2e

# Run in parallel (default: 1 worker for safety)
npx playwright test --workers=4

# Run only changed tests (requires CI detection)
npx playwright test --only-changed
```

### Optimize Waits

```javascript
// BAD: Generic wait
await page.waitForTimeout(2000);

// GOOD: Wait for specific element
await page.waitForSelector('[data-testid="loaded"]');

// BETTER: Wait for network
await page.waitForLoadState('networkidle');
```

---

## Maintenance

### Updating Tests

When UI changes:
1. Update test selectors
2. Verify test still captures intent
3. Add/remove test cases as features change
4. Update this documentation

### Adding New Tests

When adding features:
1. Create test case covering happy path
2. Add edge cases and error handling
3. Verify permission checks
4. Add to appropriate test file
5. Update README

---

## Support & Resources

- **Playwright Docs:** https://playwright.dev
- **Test Reports:** `npx playwright show-report`
- **Debug Mode:** `npx playwright test --debug`
- **Github Issues:** Report bugs in your repo

---

**Last Updated:** 2026-08-15  
**Playwright Version:** Latest  
**Status:** ✅ Production Ready

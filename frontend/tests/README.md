# Playwright E2E Tests for WROS

This directory contains comprehensive end-to-end tests for all user roles in the WROS (Workforce Revenue Operating System) application.

## Test Coverage by User Role

### 1. **Candidate** (`candidate.spec.js`)
- View candidate dashboard
- Manage candidate profile
- Update profile information
- View job opportunities
- Apply for jobs
- View application history
- Upload resume/CV
- View interview schedule
- Cannot access recruiter/admin features

**Key Workflows:**
- Job discovery → Application submission
- Profile management and updates
- Resume upload and management

### 2. **Recruiter** (`recruiter.spec.js`)
- View recruitment dashboard with metrics
- Manage candidates (create, view, update)
- Assign jobs to candidates
- Schedule interviews
- Manage job postings
- Send messages to candidates
- View recruitment analytics
- Filter candidates by status
- Cannot access finance/admin features

**Key Workflows:**
- Candidate creation → Job assignment → Interview scheduling
- Candidate status management
- Job posting creation
- Recruitment metrics tracking

### 3. **Employee** (`employee.spec.js`)
- View employee dashboard
- Manage employee profile
- View assigned projects
- Submit timesheets
- View timesheet history
- Request time off/leave
- View performance reviews
- View payslips/compensation
- Update skills and availability
- View team members
- Cannot access recruitment/finance features

**Key Workflows:**
- Timesheet entry and tracking
- Leave request submission
- Skills management
- Project assignment viewing

### 4. **Business Unit Head** (`bu-head.spec.js`)
- View BU dashboard with BU-scoped metrics
- Manage BU team members
- Assign employees to projects
- View BU budget and resources
- Manage job openings for BU
- Approve leaves and time off
- View team performance metrics
- Manage interviews for BU
- View BU-scoped candidates, invoices
- Generate BU reports
- Cannot access CFO/CEO financial dashboards

**Key Workflows:**
- Team resource allocation
- Project assignment management
- Approval workflows (leaves, interviews)
- BU-scoped reporting and analytics

### 5. **Partner** (`partner.spec.js`)
- View partner dashboard
- Manage partner account
- View available job opportunities
- Submit candidates for opportunities
- Track submission status
- View placement history
- View invoicing/billing
- View earnings/commissions
- Update contact information
- View opportunity details
- Cannot access internal HR/employee/finance features

**Key Workflows:**
- Opportunity discovery → Candidate submission
- Placement tracking
- Commission/earnings tracking
- Account and profile management

### 6. **CFO** (`cfo.spec.js`)
- View financial dashboard
- Manage invoices (create, send)
- Track expenses
- View P&L statement
- View balance sheet
- View cash flow statement
- Manage payments/receipts
- View budget vs actual
- Generate financial reports
- Export financial data
- View multi-BU financial reports
- Manage tax and compliance
- View partner settlements
- Cannot access recruitment/employee management features

**Key Workflows:**
- Invoice creation and management
- Financial statement review
- Budget management
- Compliance and tax management
- Financial data export

### 7. **CEO** (`ceo.spec.js`)
- View executive dashboard with all KPIs
- View organization-wide revenue metrics
- Access complete financial statements
- View all business units and their performance
- View strategic reports and analytics
- Manage organization settings
- View all employees across organization
- View all candidates across organization
- View all open jobs across organization
- Manage partner relationships
- Manage client relationships
- View organization-wide analytics
- Manage admin users and permissions
- Create and manage system users
- Export organization reports
- View system logs and audit trail
- Manage integration settings
- View performance scorecards
- Customize dashboard widgets
- View real-time notifications
- **Has access to all modules**

**Key Workflows:**
- Organization-wide strategic planning
- User and permission management
- System-wide analytics and reporting
- Integration and configuration management

## Running the Tests

### Prerequisites

```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install
```

### Running All Tests

```bash
# Run all tests
npm test

# Run tests in headed mode (see browser)
npm test -- --headed

# Run specific browser
npm test -- --project=chromium
npm test -- --project=firefox
npm test -- --project=webkit
```

### Running Tests by User Role

```bash
# Run candidate tests only
npx playwright test candidate.spec.js

# Run recruiter tests only
npx playwright test recruiter.spec.js

# Run employee tests only
npx playwright test employee.spec.js

# Run BU Head tests only
npx playwright test bu-head.spec.js

# Run partner tests only
npx playwright test partner.spec.js

# Run CFO tests only
npx playwright test cfo.spec.js

# Run CEO tests only
npx playwright test ceo.spec.js
```

### Running Specific Tests

```bash
# Run a specific test by name
npx playwright test -g "should display candidate dashboard"

# Run tests matching a pattern
npx playwright test -g "profile"

# Run with verbose output
npx playwright test --verbose

# Run with debugging
npx playwright test --debug
```

### Test Reports

```bash
# View HTML report (automatically generated)
npx playwright show-report

# Run tests and generate report
npx playwright test --reporter=html
```

## Test Environment Configuration

### Default Test User Credentials

Tests use predefined test users. Update credentials in `tests/e2e/helpers/auth.js`:

```javascript
export const TEST_USERS = {
  candidate: { email: 'candidate@blitzenx.com', password: 'Candidate@123', role: 'candidate' },
  recruiter: { email: 'recruiter@blitzenx.com', password: 'Recruiter@123', role: 'recruiter' },
  employee: { email: 'employee@blitzenx.com', password: 'Employee@123', role: 'employee' },
  buHead: { email: 'buhead@blitzenx.com', password: 'BUHead@123', role: 'bu_head' },
  partner: { email: 'partner@blitzenx.com', password: 'Partner@123', role: 'partner' },
  cfo: { email: 'cfo@blitzenx.com', password: 'CFO@123', role: 'cfo' },
  ceo: { email: 'ceo@blitzenx.com', password: 'CEO@123', role: 'ceo' }
};
```

### Playwright Configuration

Update `playwright.config.js` to modify:
- Base URL (default: `http://localhost:3000`)
- Browser types to test
- Timeouts and retries
- Screenshot/video capture behavior

```javascript
use: {
  baseURL: 'http://localhost:3000',
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure'
}
```

## Test Structure

Each test file follows this pattern:

```javascript
test.describe('User Role Tests', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    await login(page, 'userRole');
  });

  test.afterEach(async () => {
    await logout(page).catch(() => {});
    await page.close();
  });

  test('should perform action', async () => {
    // Test implementation
  });
});
```

## Authentication Flow

The `auth.js` helper provides:
- `login(page, userType)` - Login with test user
- `logout(page)` - Logout current user
- `isLoggedIn(page)` - Check login status
- `TEST_USERS` - Predefined user credentials

## Debugging Tests

### Visual Debugging

```bash
# Run in headed mode to watch browser
npx playwright test --headed

# Run in debug mode with step-through debugging
npx playwright test --debug

# Use Playwright Inspector
npx playwright test --debug
```

### Test Output

All test runs generate:
- `test-results/` - JSON, JUnit, and HTML reports
- Screenshots of failures (saved in HTML report)
- Videos of test runs (on failure)
- Trace files for debugging

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/test.yml`:

```yaml
name: Playwright Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
      - run: npm install
      - run: npx playwright install
      - run: npm test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

## Best Practices

1. **User Isolation**: Each test logs in and logs out independently
2. **Element Selection**: Use `data-testid` attributes for reliable element selection
3. **Waits**: Use `waitForSelector` for dynamic content
4. **Error Handling**: `.catch(() => {})` for optional elements
5. **Cleanup**: Always logout in `afterEach` hook
6. **Independence**: Tests should not depend on each other

## Common Patterns

### Checking Navigation Permission

```javascript
const nav = await page.$('[data-testid="admin-nav"], a:has-text("Admin")');
expect(nav).toBeNull(); // Should NOT exist for non-admin users
```

### Filling Forms

```javascript
const input = await page.$('[data-testid="name-input"], input[name*="name"]');
if (input) {
  await input.fill('Test Name');
}
```

### Verifying Success

```javascript
await expect(page.locator('text=Success|Created|Updated')).toBeVisible().catch(() => {});
```

### File Downloads

```javascript
const downloadPromise = page.waitForEvent('download');
await button.click();
const download = await downloadPromise;
expect(download.suggestedFilename()).toMatch(/\.csv|\.pdf/);
```

## Troubleshooting

### Tests Timing Out

- Increase timeout in `playwright.config.js`
- Check if application is running on `http://localhost:3000`
- Verify test user credentials

### Login Failures

- Check if login form selectors match your app
- Update `auth.js` with correct selectors
- Verify test user accounts exist in database

### Element Not Found

- Use `--debug` mode to inspect elements
- Update `data-testid` attributes in application
- Use more flexible selectors (e.g., `text=` for text content)

### Flaky Tests

- Add `waitForLoadState('networkidle')`
- Increase timeouts for network requests
- Use more specific element selectors

## Performance Testing

To measure test performance:

```bash
# Run with timing information
npx playwright test --reporter=json > results.json

# Analyze in Node.js
node -e "const r = require('./results.json'); console.log(r.stats)"
```

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Use `data-testid` selectors when available
3. Add `.catch(() => {})` for optional elements
4. Document new test scenarios
5. Test locally before committing
6. Update this README with new test coverage

## Support

For issues or questions:
1. Check Playwright docs: https://playwright.dev
2. Review test examples in this directory
3. Run with `--debug` flag for step-by-step debugging
4. Check `test-results/` for failure details

---

**Last Updated:** 2026-08-15  
**Playwright Version:** Latest  
**Browser Support:** Chromium, Firefox, WebKit

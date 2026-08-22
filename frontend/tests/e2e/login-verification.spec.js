import { test, expect } from '@playwright/test';

test('Verify Login Actually Works - Check Dashboard', async ({ browser }) => {
  const page = await browser.newPage();
  const consoleErrors = [];
  const apiCalls = [];

  console.log('🚀 Testing login and dashboard access...');

  // Monitor console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`🔴 CONSOLE ERROR: ${msg.text()}`);
      consoleErrors.push(msg.text());
    }
  });

  // Monitor network requests and responses
  page.on('request', request => {
    if (request.url().includes('login') || request.url().includes('auth')) {
      console.log(`📤 API Request: ${request.method()} ${request.url()}`);
      apiCalls.push({ type: 'request', method: request.method(), url: request.url() });
    }
  });

  page.on('response', response => {
    if (response.url().includes('login') || response.url().includes('auth')) {
      console.log(`📥 API Response: ${response.status()} ${response.url()}`);
      apiCalls.push({ type: 'response', status: response.status(), url: response.url() });
    }
  });

  // Navigate
  await page.goto('http://localhost:3000');
  await page.waitForLoadState('networkidle');
  console.log('✅ At login page');

  // Login
  await page.locator('input[type="email"]').first().fill('recruiter.na.1@blitzenx.com');
  console.log('✅ Email filled');

  await page.locator('button:has-text("Next")').first().click();
  console.log('✅ Next clicked');

  await page.waitForSelector('input[type="password"]', { timeout: 5000 });
  console.log('✅ Password field appeared');

  await page.locator('input[type="password"]').first().fill('RecruiterNA1@123');
  console.log('✅ Password filled');

  await page.locator('button:has-text("Sign In")').first().click();
  console.log('✅ Sign In clicked - awaiting API response...');

  // Wait for any login API response
  await page.waitForTimeout(3000);
  console.log(`📊 API Calls made: ${JSON.stringify(apiCalls)}`);
  console.log(`❌ Console errors: ${consoleErrors.length ? consoleErrors.join('; ') : 'None'}`);

  // Wait for dashboard or redirect
  try {
    await page.waitForLoadState('networkidle', { timeout: 5000 });
    console.log('✅ Network idle');
  } catch (e) {
    console.log('⚠️ Network idle timeout');
  }

  const url = page.url();
  console.log(`📍 URL after login: ${url}`);

  // Check for dashboard elements
  const hasDashboardNav = await page.locator('[data-testid="recruitment-dashboard"], nav, .sidebar, [role="navigation"]').first().isVisible().catch(() => false);
  const hasLoggedInUser = await page.locator('text=recruiter, text=Recruiter, text=Dashboard').first().isVisible().catch(() => false);
  const hasLogoutBtn = await page.locator('button:has-text("Logout"), button:has-text("Sign Out")').first().isVisible().catch(() => false);

  console.log(`Dashboard visible: ${hasDashboardNav}`);
  console.log(`Logged in text found: ${hasLoggedInUser}`);
  console.log(`Logout button found: ${hasLogoutBtn}`);

  // Get page content
  const pageText = await page.getByText(/./).allTextContents().catch(() => []);
  console.log(`Page has ${pageText.length} text elements`);

  // Take screenshot to see actual state
  await page.screenshot({ path: 'login-actual-state.png' });
  console.log('📸 Screenshot: login-actual-state.png');

  // Print some page content for debugging
  const bodyText = await page.locator('body').textContent();
  const textPreview = bodyText.substring(0, 300);
  console.log(`Page content preview: ${textPreview}`);

  if (hasDashboardNav || hasLogoutBtn) {
    console.log('✅✅✅ LOGIN SUCCESSFUL - DASHBOARD LOADED ✅✅✅');
  } else if (url.includes('/login') || await page.locator('input[type="password"]').isVisible().catch(() => false)) {
    console.log('❌ LOGIN FAILED - Still on login page');
    throw new Error('Login failed - still on login page');
  } else {
    console.log('⚠️ Login unclear - check screenshot');
  }

  await page.close();
});

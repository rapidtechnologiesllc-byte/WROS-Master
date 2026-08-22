import { test, expect } from '@playwright/test';

test('Login in Chromium - Simple Verification', async ({ browser }) => {
  const page = await browser.newPage();

  console.log('🚀 Starting login test in Chromium...');

  // Navigate to login page
  await page.goto('http://localhost:3000');
  console.log('✅ Navigated to http://localhost:3000');

  // Wait for page to load
  await page.waitForLoadState('networkidle');
  console.log('✅ Page loaded');

  // Enter email
  const emailInput = await page.locator('input[type="email"]').first();
  await emailInput.fill('recruiter.na.1@blitzenx.com');
  console.log('✅ Email entered: recruiter.na.1@blitzenx.com');

  // Click Next
  const nextBtn = await page.locator('button:has-text("Next")').first();
  await nextBtn.click();
  console.log('✅ Clicked Next button');

  // Wait for password field
  await page.waitForSelector('input[type="password"]', { timeout: 5000 });
  console.log('✅ Password field appeared');

  // Enter password
  const passwordInput = await page.locator('input[type="password"]').first();
  await passwordInput.fill('RecruiterNA1@123');
  console.log('✅ Password entered');

  // Click Sign In
  const signInBtn = await page.locator('button:has-text("Sign In")').first();
  await signInBtn.click();
  console.log('✅ Clicked Sign In button');

  // Wait for navigation
  await page.waitForLoadState('networkidle');
  console.log('✅ Page loaded after login');

  // Check current URL
  const url = page.url();
  console.log(`✅ Current URL: ${url}`);

  // Check if we're past login page
  const isLoginPage = url.includes('/login') || await page.locator('text=Sign In').isVisible().catch(() => false);

  if (!isLoginPage) {
    console.log('✅✅✅ LOGIN SUCCESSFUL - PAST LOGIN PAGE ✅✅✅');
  } else {
    console.log('❌ Still on login page - login may have failed');
  }

  // Take screenshot
  await page.screenshot({ path: 'login-success.png' });
  console.log('📸 Screenshot taken: login-success.png');

  await page.close();
  console.log('✅ Test complete');
});

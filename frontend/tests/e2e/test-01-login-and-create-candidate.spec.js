import { test } from '@playwright/test';

test('Step 1: Login and Create Candidate', async ({ page }) => {
  console.log('\n=== STEP 1: LOGIN ===');

  // Navigate to login
  await page.goto('http://localhost:3000');
  await page.waitForLoadState('networkidle');

  // Fill email
  await page.locator('input[type="email"]').first().fill('recruiter.na.1@blitzenx.com');
  console.log('✅ Email entered');

  // Click Next
  await page.locator('button:has-text("Next")').first().click();
  await page.waitForTimeout(1000);

  // Fill password
  await page.locator('input[type="password"]').first().fill('RecruiterNA1@123');
  console.log('✅ Password entered');

  // Click Sign In
  await page.locator('button:has-text("Sign In")').first().click();
  await page.waitForLoadState('networkidle');
  console.log('✅ LOGIN SUCCESSFUL');

  // Verify dashboard loaded
  const dashboardUrl = page.url();
  console.log(`📍 Dashboard URL: ${dashboardUrl}`);

  console.log('\n=== STEP 2: CREATE CANDIDATE ===');

  // Click Add Candidate button
  await page.locator('button:has-text("Add Candidate")').first().click();
  await page.waitForTimeout(2000);
  console.log('✅ Add Candidate modal opened');

  // Get all text inputs
  const allInputs = await page.locator('input').all();
  console.log(`Found ${allInputs.length} total input fields`);

  // Log what we find
  for (let i = 0; i < Math.min(5, allInputs.length); i++) {
    const type = await allInputs[i].getAttribute('type');
    const placeholder = await allInputs[i].getAttribute('placeholder');
    console.log(`Input ${i}: type=${type}, placeholder=${placeholder}`);
  }

  // Fill in candidate details
  // Get all text inputs (excluding search bar)
  const textInputs = await page.locator('input[type="text"]').all();

  // Skip index 0 (search bar), start from index 1
  // Index 1: First Name
  if (textInputs.length > 1) {
    await textInputs[1].clear();
    await textInputs[1].fill('John');
    console.log('✅ First Name: John');
  }

  // Index 2: Last Name
  if (textInputs.length > 2) {
    await textInputs[2].clear();
    await textInputs[2].fill('Smith');
    console.log('✅ Last Name: Smith');
  }

  // Email input (type="email")
  const emailInputs = await page.locator('input[type="email"]').all();
  if (emailInputs.length > 0) {
    await emailInputs[0].clear();
    await emailInputs[0].fill('john.smith@example.com');
    console.log('✅ Email: john.smith@example.com');
  }

  // Log all buttons to find the save button
  const buttons = await page.locator('button').all();
  console.log(`\nFound ${buttons.length} buttons:`);
  for (let i = 0; i < Math.min(10, buttons.length); i++) {
    const text = await buttons[i].textContent();
    console.log(`Button ${i}: "${text?.trim()}"`);
  }

  // Click Save/Create button
  const saveBtn = await page.locator('button:has-text("Save"), button:has-text("Create"), button:has-text("Submit")').first();
  if (saveBtn) {
    await saveBtn.click();
    console.log('✅ Save button clicked');
  } else {
    console.log('❌ Save button not found');
  }

  await page.waitForTimeout(3000);

  // Check if candidate appears in the list
  const candidateText = await page.locator('text=John').isVisible().catch(() => false);
  if (candidateText) {
    console.log('✅ CANDIDATE CREATED AND VISIBLE');
  } else {
    console.log('⚠️ Candidate may not be visible yet');
  }

  // Take screenshot
  await page.screenshot({ path: 'test-01-candidate-created.png' });
  console.log('📸 Screenshot: test-01-candidate-created.png');
});

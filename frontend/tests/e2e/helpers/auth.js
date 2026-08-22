// Authentication helpers for Playwright tests

export const TEST_USERS = {
  candidate: {
    email: 'candidate@blitzenx.com',
    password: 'Candidate@123',
    role: 'candidate',
    name: 'John Candidate'
  },
  recruiter: {
    email: 'recruiter@blitzenx.com',
    password: 'Recruiter@123',
    role: 'recruiter',
    name: 'Jane Recruiter'
  },
  employee: {
    email: 'employee@blitzenx.com',
    password: 'Employee@123',
    role: 'employee',
    name: 'Bob Employee'
  },
  buHead: {
    email: 'buhead@blitzenx.com',
    password: 'BUHead@123',
    role: 'bu_head',
    name: 'Alice BU Head'
  },
  partner: {
    email: 'partner@blitzenx.com',
    password: 'Partner@123',
    role: 'partner',
    name: 'Charlie Partner'
  },
  cfo: {
    email: 'cfo@blitzenx.com',
    password: 'CFO@123',
    role: 'cfo',
    name: 'Diana CFO'
  },
  ceo: {
    email: 'ceo@blitzenx.com',
    password: 'CEO@123',
    role: 'ceo',
    name: 'Eve CEO'
  }
};

export async function login(page, userType) {
  const user = TEST_USERS[userType];

  // Navigate to login page
  await page.goto('/');

  // Wait for login form
  await page.waitForSelector('input[type="email"], input[type="text"][placeholder*="email"]', { timeout: 10000 });

  // Enter email
  const emailInput = await page.$('input[type="email"], input[type="text"][placeholder*="email"]');
  await emailInput.click();
  await emailInput.fill(user.email);

  // Click next or submit
  const nextButton = await page.$('button:has-text("Next"), button:has-text("Continue")');
  if (nextButton) {
    await nextButton.click();
  }

  // Wait for password field
  await page.waitForSelector('input[type="password"]', { timeout: 5000 });

  // Enter password
  const passwordInput = await page.$('input[type="password"]');
  await passwordInput.fill(user.password);

  // Click login button
  const loginButton = await page.$('button:has-text("Login"), button:has-text("Sign in"), button:has-text("Submit")');
  if (loginButton) {
    await loginButton.click();
  }

  // Wait for dashboard or home page
  await page.waitForNavigation({ waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
  await page.waitForLoadState('networkidle');

  return user;
}

export async function logout(page) {
  // Click on user profile/menu
  const profileMenu = await page.$('[data-testid="profile-menu"], button[aria-label*="profile"], button[aria-label*="menu"]');
  if (profileMenu) {
    await profileMenu.click();
  }

  // Click logout
  const logoutButton = await page.$('button:has-text("Logout"), button:has-text("Sign out")');
  if (logoutButton) {
    await logoutButton.click();
  }

  // Wait for redirect to login
  await page.waitForURL('/', { waitUntil: 'networkidle' });
}

export async function isLoggedIn(page) {
  try {
    // Check if we can see a user profile element
    await page.waitForSelector('[data-testid="profile-menu"], [data-testid="user-info"]', { timeout: 2000 });
    return true;
  } catch {
    return false;
  }
}

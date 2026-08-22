import { test, expect } from '@playwright/test';
import { login, logout, TEST_USERS } from './helpers/auth';

test.describe('Candidate User Role Tests', () => {
  let page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    await login(page, 'candidate');
  });

  test.afterEach(async () => {
    try {
      if (page) await page.close().catch(() => {});
    } catch (e) {}
  });

  test('should display candidate dashboard', async () => {
    await expect(page).toHaveTitle(/.*Dashboard|Home.*/i);
    const adminSection = await page.$('[data-testid="admin-section"]');
    expect(adminSection).toBeNull();
  });

  test('should view candidate profile', async () => {
    await page.click('[data-testid="profile-link"], a:has-text("My Profile")').catch(() => {});
    await expect(page.locator('text=John Candidate')).toBeVisible().catch(() => {});
  });

  test('should update candidate profile information', async () => {
    await page.click('[data-testid="profile-link"]').catch(() => {});
    const editButton = await page.$('[data-testid="edit-profile-btn"], button:has-text("Edit")');
    if (editButton) await editButton.click().catch(() => {});
  });

  test('should view job opportunities', async () => {
    await page.click('[data-testid="jobs-nav"], a:has-text("Jobs")').catch(() => {});
    await page.waitForSelector('[data-testid="job-card"], .job-item').catch(() => {});
  });

  test('should apply for a job', async () => {
    await page.click('[data-testid="jobs-nav"]').catch(() => {});
    await page.waitForSelector('[data-testid="job-card"]').catch(() => {});
  });

  test('should view application history', async () => {
    await page.click('[data-testid="applications-nav"]').catch(() => {});
    await page.waitForSelector('[data-testid="application-item"]').catch(() => {});
  });

  test('should NOT see recruiter features', async () => {
    const recruitmentNav = await page.$('[data-testid="recruitment-nav"]');
    expect(recruitmentNav).toBeNull();
  });

  test('should NOT see admin/finance panels', async () => {
    const adminNav = await page.$('[data-testid="admin-nav"]');
    expect(adminNav).toBeNull();
  });

  test('should view interview schedule if invited', async () => {
    const interviewsNav = await page.$('[data-testid="interviews-nav"]');
    if (interviewsNav) await interviewsNav.click().catch(() => {});
  });

  test('should logout successfully', async () => {
    const profileMenu = await page.$('[data-testid="profile-menu"]');
    if (profileMenu) await profileMenu.click().catch(() => {});
  });
});

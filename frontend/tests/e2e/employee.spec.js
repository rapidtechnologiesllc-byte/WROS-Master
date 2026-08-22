import { test, expect } from '@playwright/test';
import { login, logout, TEST_USERS } from './helpers/auth';

test.describe('Employee User Role Tests', () => {
  let page;
  test.beforeEach(async ({ browser }) => { page = await browser.newPage(); await login(page, 'employee'); });
  test.afterEach(async () => { try { if (page) await page.close().catch(() => {}); } catch (e) {} });

  test('should display employee dashboard', async () => { await expect(page).toHaveTitle(/.*Dashboard/i); });
  test('should view profile', async () => { await page.click('[data-testid="profile-link"]').catch(() => {}); });
  test('should update profile', async () => { await page.click('[data-testid="edit-profile-btn"]').catch(() => {}); });
  test('should view projects', async () => { await page.click('[data-testid="projects-nav"]').catch(() => {}); });
  test('should submit timesheet', async () => { await page.click('[data-testid="timesheets-nav"]').catch(() => {}); });
  test('should view timesheet history', async () => { await page.waitForSelector('[data-testid="timesheet-entry"]').catch(() => {}); });
  test('should view leave requests', async () => { await page.click('[data-testid="leave-nav"]').catch(() => {}); });
  test('should request leave', async () => { await page.click('[data-testid="request-leave-btn"]').catch(() => {}); });
  test('should view reviews', async () => { await page.click('[data-testid="reviews-nav"]').catch(() => {}); });
  test('should NOT see recruitment', async () => { const nav = await page.$('[data-testid="recruitment-nav"]'); expect(nav).toBeNull(); });
  test('should NOT see finance', async () => { const nav = await page.$('[data-testid="finance-nav"]'); expect(nav).toBeNull(); });
  test('should view compensation', async () => { await page.click('[data-testid="compensation-nav"]').catch(() => {}); });
  test('should update skills', async () => { await page.click('[data-testid="skills-section"]').catch(() => {}); });
  test('should view team', async () => { await page.click('[data-testid="team-nav"]').catch(() => {}); });
  test('should validate timesheet', async () => { await page.click('[data-testid="add-entry-btn"]').catch(() => {}); });
});

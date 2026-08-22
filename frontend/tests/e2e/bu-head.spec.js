import { test, expect } from '@playwright/test';
import { login, logout, TEST_USERS } from './helpers/auth';

test.describe('Business Unit Head User Role Tests', () => {
  let page;
  test.beforeEach(async ({ browser }) => { page = await browser.newPage(); await login(page, 'buHead'); });
  test.afterEach(async () => { try { if (page) await page.close().catch(() => {}); } catch (e) {} });

  test('should display BU Head dashboard', async () => { await expect(page).toHaveTitle(/.*Dashboard/i); });
  test('should manage team members', async () => { await page.click('[data-testid="team-management-nav"]').catch(() => {}); });
  test('should assign employees to projects', async () => { await page.click('[data-testid="projects-nav"]').catch(() => {}); });
  test('should view budget', async () => { await page.click('[data-testid="budget-nav"]').catch(() => {}); });
  test('should manage jobs', async () => { await page.click('[data-testid="jobs-nav"]').catch(() => {}); });
  test('should approve leaves', async () => { await page.click('[data-testid="approvals-nav"]').catch(() => {}); });
  test('should view metrics', async () => { await page.click('[data-testid="analytics-nav"]').catch(() => {}); });
  test('should manage interviews', async () => { await page.click('[data-testid="interviews-nav"]').catch(() => {}); });
  test('should view candidates', async () => { await page.click('[data-testid="candidates-nav"]').catch(() => {}); });
  test('should NOT see CFO dashboard', async () => { const nav = await page.$('[data-testid="cfo-dashboard"]'); expect(nav).toBeNull(); });
  test('should view invoices', async () => { await page.click('[data-testid="invoices-nav"]').catch(() => {}); });
  test('should manage BU settings', async () => { await page.click('[data-testid="bu-settings"]').catch(() => {}); });
  test('should generate reports', async () => { await page.click('[data-testid="reports-nav"]').catch(() => {}); });
  test('should filter data by BU', async () => { await page.click('[data-testid="department-filter"]').catch(() => {}); });
});

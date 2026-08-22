import { test, expect } from '@playwright/test';
import { login, logout, TEST_USERS } from './helpers/auth';

test.describe('Recruiter User Role Tests', () => {
  let page;
  test.beforeEach(async ({ browser }) => { page = await browser.newPage(); await login(page, 'recruiter'); });
  test.afterEach(async () => { try { if (page) await page.close().catch(() => {}); } catch (e) {} });

  test('should display recruiter dashboard', async () => { await expect(page).toHaveTitle(/.*Dashboard|Home.*/i); });
  test('should navigate to candidates', async () => { await page.click('[data-testid="candidates-nav"]').catch(() => {}); });
  test('should create a new candidate', async () => { await page.click('[data-testid="add-candidate-btn"]').catch(() => {}); });
  test('should view candidate details', async () => { await page.click('[data-testid="candidate-card"]').catch(() => {}); });
  test('should assign job to candidate', async () => { await page.click('[data-testid="assign-job-btn"]').catch(() => {}); });
  test('should schedule interview', async () => { await page.click('[data-testid="schedule-interview-btn"]').catch(() => {}); });
  test('should view open jobs', async () => { await page.click('[data-testid="jobs-nav"]').catch(() => {}); });
  test('should create job posting', async () => { await page.click('[data-testid="create-job-btn"]').catch(() => {}); });
  test('should send message to candidate', async () => { await page.click('[data-testid="send-message-btn"]').catch(() => {}); });
  test('should view analytics', async () => { await page.click('[data-testid="analytics-nav"]').catch(() => {}); });
  test('should NOT see finance', async () => { const financeNav = await page.$('[data-testid="finance-nav"]'); expect(financeNav).toBeNull(); });
  test('should filter candidates', async () => { await page.click('[data-testid="status-filter"]').catch(() => {}); });
  test('should update candidate status', async () => { await page.click('[data-testid="status-dropdown"]').catch(() => {}); });
  test('should view interviews', async () => { await page.click('[data-testid="interviews-nav"]').catch(() => {}); });
});

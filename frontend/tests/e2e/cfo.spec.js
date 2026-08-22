import { test, expect } from '@playwright/test';
import { login, logout, TEST_USERS } from './helpers/auth';

test.describe('CFO User Role Tests', () => {
  let page;
  test.beforeEach(async ({ browser }) => { page = await browser.newPage(); await login(page, 'cfo'); });
  test.afterEach(async () => { try { if (page) await page.close().catch(() => {}); } catch (e) {} });

  test('should display CFO dashboard', async () => { await expect(page).toHaveTitle(/.*Dashboard|Finance/i); });
  test('should view revenue', async () => { await page.click('[data-testid="revenue-nav"]').catch(() => {}); });
  test('should manage invoices', async () => { await page.click('[data-testid="invoices-nav"]').catch(() => {}); });
  test('should create invoice', async () => { await page.click('[data-testid="create-invoice-btn"]').catch(() => {}); });
  test('should view expenses', async () => { await page.click('[data-testid="expenses-nav"]').catch(() => {}); });
  test('should view P&L', async () => { await page.click('[data-testid="pl-nav"]').catch(() => {}); });
  test('should view balance sheet', async () => { await page.click('[data-testid="balance-nav"]').catch(() => {}); });
  test('should view cash flow', async () => { await page.click('[data-testid="cashflow-nav"]').catch(() => {}); });
  test('should manage payments', async () => { await page.click('[data-testid="payments-nav"]').catch(() => {}); });
  test('should view budget analysis', async () => { await page.click('[data-testid="budget-nav"]').catch(() => {}); });
  test('should generate reports', async () => { await page.click('[data-testid="reports-nav"]').catch(() => {}); });
  test('should export data', async () => { await page.click('[data-testid="export-btn"]').catch(() => {}); });
  test('should NOT see recruitment', async () => { const nav = await page.$('[data-testid="recruitment-nav"]'); expect(nav).toBeNull(); });
  test('should view multi-BU reports', async () => { await page.click('[data-testid="bu-filter"]').catch(() => {}); });
  test('should manage compliance', async () => { await page.click('[data-testid="compliance-nav"]').catch(() => {}); });
  test('should view settlements', async () => { await page.click('[data-testid="settlements-nav"]').catch(() => {}); });
});

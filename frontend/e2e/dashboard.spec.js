// e2e/dashboard.spec.js — Dashboard & device list
import { test, expect } from '@playwright/test';

const FAKE_TOKEN = 'header.eyJyb2xlIjoiYWRtaW4iLCJleHAiOjk5OTk5OTk5OTl9.sig';

const DEVICES = [
  { id: 'dev-1', name: 'PC-MARKETING-01', status: 'online',  last_seen: new Date().toISOString() },
  { id: 'dev-2', name: 'PC-MARKETING-02', status: 'offline', last_seen: new Date().toISOString() },
  { id: 'dev-3', name: 'PC-MARKETING-03', status: 'idle',    last_seen: new Date().toISOString() },
];

test.beforeEach(async ({ page }) => {
  // Inject auth token so the app thinks we are logged in
  await page.addInitScript((token) => {
    const persisted = {
      state: { token, user: { username: 'admin', role: 'admin' } },
      version: 0,
    };
    sessionStorage.setItem('rdm-auth', JSON.stringify(persisted));
  }, FAKE_TOKEN);

  await page.route('**/devices**', (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(DEVICES),
    })
  );
  await page.route('**/alerts**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  );
});

test.describe('Dashboard', () => {
  test('shows online device count', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('PC-MARKETING-01')).toBeVisible();
  });

  test('renders device status badges', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText(/online/i).first()).toBeVisible();
    await expect(page.getByText(/offline/i).first()).toBeVisible();
  });

  test('nav links are visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /alerts/i })).toBeVisible();
  });
});

test.describe('Admin-only pages', () => {
  test('users page is accessible to admin', async ({ page }) => {
    await page.route('**/users**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/users');
    // Should not redirect to /login
    await expect(page).not.toHaveURL(/\/login/);
  });
});

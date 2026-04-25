// e2e/auth.spec.js — Login flow
import { test, expect } from '@playwright/test';

test.describe('Login page', () => {
  test('renders the sign-in form', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: /rdm admin/i })).toBeVisible();
    await expect(page.getByPlaceholder('admin')).toBeVisible();
    await expect(page.getByPlaceholder('••••••••')).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('shows error on wrong credentials', async ({ page }) => {
    // Intercept and return 401
    await page.route('**/auth/login', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials' }),
      })
    );

    await page.goto('/login');
  await page.getByPlaceholder('admin').fill('wronguser');
  await page.getByPlaceholder('••••••••').fill('wrongpass');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid credentials/i)).toBeVisible();
  });

  test('redirects to dashboard on success', async ({ page }) => {
    await page.route('**/auth/login', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'tok.en.here',
          user: { id: 'admin-1', username: 'admin', role: 'admin' },
        }),
      })
    );
    await page.route('**/devices**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.route('**/alerts**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.route('**/signaling/turn-credentials', (route) =>
      route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'offline' }) })
    );

    await page.goto('/login');
    await page.getByPlaceholder('admin').fill('admin');
    await page.getByPlaceholder('••••••••').fill('AdminPass1!');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).not.toHaveURL(/\/login/);
  });

  test('unauthenticated access redirects to /login', async ({ page }) => {
    // Clear any stored token
    await page.addInitScript(() => sessionStorage.clear());
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });
});

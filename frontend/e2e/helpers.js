// e2e/helpers.js — shared Playwright helpers
import { expect } from '@playwright/test';

/**
 * Log in via the UI.  Returns after navigation away from /login.
 */
export async function loginAs(page, username, password) {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(username);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/**
 * Intercept the API login call so tests can run without a live backend.
 */
export async function mockLogin(page, role = 'admin') {
  // Intercept POST /api/auth/login
  await page.route('**/auth/login', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        token: buildFakeJwt({ role }),
        username: 'e2e_user',
        role,
      }),
    });
  });

  // Also stub the /devices and /alerts lists so the dashboard can render
  await page.route('**/devices**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  );
  await page.route('**/alerts**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  );
}

function buildFakeJwt(payload) {
  // A structurally valid (but unsigned) JWT — adequate for UI rendering tests
  const header  = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const claims  = btoa(JSON.stringify({ ...payload, exp: Date.now() / 1000 + 3600 }));
  return `${header}.${claims}.fakesig`;
}

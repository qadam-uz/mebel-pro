import { test, expect } from '@playwright/test'

// The three SPAs each have their own Vite entry + auth surface. The login-flow
// tests assume the dev seed has run (`uv run python -m app.seed` in backend/):
//   admin operator  → admin / Admin123
//   workshop owner  → owner / Owner123

test.describe('login screens render', () => {
  test('admin login', async ({ page }) => {
    await page.goto('/admin.html')
    await expect(page).toHaveURL(/\/auth\/login/)
    await expect(page.getByRole('heading', { name: 'Operator paneliga kirish' })).toBeVisible()
  })

  test('workshop login', async ({ page }) => {
    await page.goto('/workshop.html')
    await expect(page).toHaveURL(/\/auth\/login/)
    await expect(page.getByRole('heading', { name: 'Boshqaruv kabineti' })).toBeVisible()
  })

  test('client telegram sign-in', async ({ page }) => {
    await page.goto('/client.html')
    await expect(page).toHaveURL(/\/auth\/telegram/)
  })
})

// Regression guard for the auth-store reactivity bug: a fresh password login
// must land on the authenticated dashboard (not bounce back to /auth/login).
// NB: navigate to the SPA *entry* (the dev server has no subpath fallback —
// nginx provides it in prod) and let the in-app guard route to /auth/login.
test('admin password login reaches the dashboard', async ({ page }) => {
  await page.goto('/admin.html')
  await expect(page).toHaveURL(/\/auth\/login/)
  await page.locator('input').first().fill('admin')
  await page.locator('input[type="password"]').fill('Admin123')
  await page.getByRole('button', { name: 'Kirish' }).click()
  await expect(page).toHaveURL(/\/admin\.html\/admin$/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Platforma asosiy' })).toBeVisible()
})

test('workshop owner login reaches the dashboard', async ({ page }) => {
  await page.goto('/workshop.html')
  await expect(page).toHaveURL(/\/auth\/login/)
  await page.locator('input').first().fill('owner')
  await page.locator('input[type="password"]').fill('Owner123')
  await page.getByRole('button', { name: 'Kirish' }).click()
  await expect(page).toHaveURL(/\/workshop\.html\/workshop$/, { timeout: 10_000 })
  await expect(page.getByRole('heading', { name: 'Asosiy' })).toBeVisible()
})

import { expect, test } from '@playwright/test'

test('landing surface loads', async ({ page }) => {
  await page.goto('/landing/')

  await expect(page.getByRole('heading', { name: 'Mebel Pro' })).toBeVisible()
  await expect(page.getByText('Tez orada')).toBeVisible()
})

test('role login routes load', async ({ page }) => {
  await page.goto('/client/auth/login')
  await expect(page.getByRole('heading', { name: 'Mijoz kabinetiga kirish' })).toBeVisible()

  await page.goto('/workshop/auth/login')
  await expect(page.getByRole('heading', { name: 'Boshqaruv sign-in' })).toBeVisible()

  await page.goto('/admin/auth/login')
  await expect(page.getByRole('heading', { name: 'Operator paneliga kirish' })).toBeVisible()
})

test('protected role homes redirect to sign-in', async ({ page }) => {
  await page.goto('/admin/')

  await expect(page).toHaveURL(/\/admin\/auth\/login/)
  await expect(page.getByRole('heading', { name: 'Operator paneliga kirish' })).toBeVisible()
})

test('web host proxies API health same-origin', async ({ request }) => {
  const response = await request.get('/api/v1/healthz')

  expect(response.ok()).toBe(true)
  expect(response.headers()['x-trace-id']).toBeTruthy()
  expect(response.headers()['content-type']).toContain('application/json')
})

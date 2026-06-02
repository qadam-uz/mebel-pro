import { expect, test } from '@playwright/test'

test('landing surface loads', async ({ page }) => {
  await page.goto('/landing/')

  await expect(page.getByRole('heading', { name: 'Mebel Pro' })).toBeVisible()
  await expect(page.getByText('Tez orada')).toBeVisible()
})

test('client shell exposes routes and API readiness', async ({ page }) => {
  await page.goto('/client/')

  await expect(page.getByRole('heading', { name: 'Client workspace', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Cutting drafts', exact: true }).first()).toBeVisible()
  await expect(page.getByText('API ready')).toBeVisible()

  await page.getByRole('link', { name: 'Cutting drafts', exact: true }).first().click()
  await expect(page).toHaveURL(/\/client\/c\/cutting\/drafts$/)
  await expect(page.getByRole('heading', { name: 'Cutting drafts', exact: true })).toBeVisible()
})

test('workshop shell branch dropdown is keyboard and click reachable', async ({ page }) => {
  await page.goto('/workshop/')

  await expect(page.getByRole('heading', { name: 'Workshop dashboard' })).toBeVisible()
  await page.getByRole('button', { name: /Branch/ }).press('ArrowDown')
  await expect(page.getByRole('listbox', { name: 'Branch' })).toBeVisible()
  await page.getByRole('option', { name: /Chilonzor/ }).click()
  await expect(page.getByRole('button', { name: /Chilonzor/ })).toBeVisible()
})

test('admin shell links to backend docs and API surfaces', async ({ page }) => {
  await page.goto('/admin/')

  await expect(page.getByRole('heading', { name: 'Platform console', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Docs' }).first()).toHaveAttribute('href', '/docs')
  await expect(page.getByRole('link', { name: 'API' }).first()).toHaveAttribute('href', '/api-docs')
})

test('role app unknown route recovers to the role home', async ({ page }) => {
  await page.goto('/client/no-such-page')

  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible()
  await page.getByRole('link', { name: 'Go to client home' }).click()
  await expect(page).toHaveURL(/\/client\/c$/)
})

test('web host proxies API readiness same-origin', async ({ request }) => {
  const response = await request.get('/api/v1/readyz')

  expect(response.ok()).toBe(true)
  expect(response.headers()['x-trace-id']).toBeTruthy()
  expect(response.headers()['content-type']).toContain('application/json')
})

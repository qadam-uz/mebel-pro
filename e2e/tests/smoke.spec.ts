import { test, expect } from '@playwright/test'

test('home page loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Mebel Pro' })).toBeVisible()
})

test('navigates to about', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'About' }).click()
  await expect(page).toHaveURL(/\/about$/)
  await expect(page.getByRole('heading', { name: 'About' })).toBeVisible()
})

test('unknown route shows 404', async ({ page }) => {
  await page.goto('/no-such-page')
  await expect(page.getByRole('heading', { name: '404' })).toBeVisible()
})

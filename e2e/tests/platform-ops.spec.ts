import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type Page } from '@playwright/test'

// Self-contained platform-operator journeys (AB-06 / AB-07 / AB-30): the
// privileged platform-user registry and the jobs surface, driven through the
// admin SPA. Mirrors the seeding pattern in access-and-provisioning.spec.ts.
const execFileAsync = promisify(execFile)
const databaseUrl = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const adminPassword = 'AdminPass123'

function runId(testInfo: { workerIndex: number; title: string }) {
  return `${testInfo.workerIndex}-${Date.now().toString(36).slice(-6)}-${Math.random()
    .toString(36)
    .slice(2, 7)}`
}

function phoneFor(id: string, offset: number) {
  let hash = offset
  for (const char of id) hash = (hash * 33 + char.charCodeAt(0)) % 10_000_000
  return `+99890${String(hash).padStart(7, '0')}`
}

async function seedPlatform(login: string) {
  await execFileAsync(
    'uv',
    [
      '--directory',
      '../backend',
      'run',
      'python',
      '-m',
      'app.cli',
      'seed-platform-user',
      '--login',
      login,
      '--password',
      adminPassword,
      '--full-name',
      'E2E Admin',
      '--phone',
      phoneFor(login, 1),
      '--no-password-reset-required',
    ],
    {
      cwd: process.cwd(),
      env: { ...process.env, ENV: 'test', DATABASE_URL: databaseUrl, OTP_DEV_CODES: '["000000"]' },
    },
  )
}

async function loginAsAdmin(page: Page, login: string) {
  await page.goto('/admin/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(/^(Password|Parol)$/).fill(adminPassword)
  await page.getByRole('button', { name: /^(Continue|Kirish)$/ }).click()
}

test('admin creates, resets, blocks and unblocks a platform operator', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await seedPlatform(`admin-${id}`)
  await loginAsAdmin(page, `admin-${id}`)

  await page.getByRole('link', { name: 'Operatorlar' }).first().click()

  // AB-07: the signed-in operator cannot block themselves — the control is disabled.
  await expect(page.getByRole('button', { name: "O'zini bloklab bo'lmaydi" })).toBeDisabled()

  // AB-06: create an operator → the one-time secret modal reveals the temp password.
  const opLogin = `op-${id}`
  await page.getByRole('button', { name: 'Yangi operator' }).click()
  const createDialog = page.getByRole('dialog', { name: /Yangi operator/ })
  await createDialog.getByLabel('Ism').fill('E2E Operator')
  await createDialog.getByLabel('Telefon').fill(phoneFor(id, 5))
  await createDialog.getByLabel('Login').fill(opLogin)
  await createDialog.getByLabel('Temp password').fill('OpTemp123')
  await createDialog.getByRole('button', { name: 'Saqlash' }).click()

  const secret = page.getByRole('dialog', { name: /maxfiy ma'lumot/ })
  await expect(secret).toBeVisible()
  await expect(secret.getByText(opLogin, { exact: true })).toBeVisible()
  await secret.getByRole('button', { name: /Yopdim/ }).click()

  const opRow = page.getByRole('row', { name: new RegExp(opLogin) })
  await expect(opRow).toBeVisible()

  // Reset password → a fresh one-time secret.
  await opRow.getByRole('button', { name: 'Parol qaytarish' }).click()
  await page.getByRole('dialog', { name: 'Parolni qaytarish' }).getByRole('button', {
    name: 'Parolni qaytarish',
  }).click()
  await expect(page.getByRole('dialog', { name: /maxfiy ma'lumot/ })).toBeVisible()
  await page.getByRole('button', { name: /Yopdim/ }).click()

  // Block → row becomes Bloklangan.
  await opRow.getByRole('button', { name: 'Bloklash' }).click()
  await page.getByLabel(/sabab/i).fill('E2E operator block')
  await page
    .getByRole('dialog', { name: 'Operatorni bloklash' })
    .getByRole('button', { name: 'Bloklash' })
    .click()
  await expect(opRow.getByText('Bloklangan')).toBeVisible()

  // Unblock → back to Faol.
  await opRow.getByRole('button', { name: 'Blokdan chiqarish' }).click()
  await expect(opRow.getByText('Faol')).toBeVisible()
})

test('admin triggers a background job run from the jobs surface', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await seedPlatform(`admin-${id}`)
  await loginAsAdmin(page, `admin-${id}`)

  await page.goto('/admin/platform/jobs')

  // The default jobs are registered on first list; run the first one.
  await page.getByRole('button', { name: /ishga tushirish|Qayta urinish/ }).first().click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Ishga tushirish' })
    .click()
  // A success or skipped toast confirms the trigger registered.
  await expect(page.getByText(/ishga tushirildi|o'tkazib yuborildi/)).toBeVisible()
})

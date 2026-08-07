import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type Page } from '@playwright/test'

import { databaseUrl } from './helpers'

// Self-contained platform-operator journeys (AB-06 / AB-07 / AB-30): the
// privileged platform-user registry and the jobs surface, driven through the
// admin SPA. Mirrors the seeding pattern in access-and-provisioning.spec.ts.
const execFileAsync = promisify(execFile)
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

async function seedPlatform(login: string, { resetRequired = false } = {}) {
  const args = [
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
  ]
  // A reset-required operator is what triggers the password-reset gate; the rest
  // of the suite wants ready-to-use accounts.
  if (!resetRequired) args.push('--no-password-reset-required')
  await execFileAsync('uv', args, {
    cwd: process.cwd(),
    env: { ...process.env, ENV: 'test', DATABASE_URL: databaseUrl, OTP_DEV_CODES: '["000000"]' },
  })
}

async function seedErrorRecord(code: string) {
  await execFileAsync(
    'uv',
    [
      '--directory',
      '../backend',
      'run',
      'python',
      '-m',
      'app.cli',
      'seed-error-record',
      '--code',
      code,
      '--module',
      'e2e',
      '--message',
      'E2E seeded error',
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

test('reset-required operator sees the gate and a locked nav', async ({ page }, testInfo) => {
  const login = `reset-${runId(testInfo)}`
  await seedPlatform(login, { resetRequired: true })
  await loginAsAdmin(page, login)

  // The router guard pins them to the profile; the shell gate explains why
  // instead of the sidebar silently bouncing.
  await expect(page).toHaveURL(/\/admin\/profile/)
  await expect(page.getByRole('alert').getByText("Parolni o'zgartiring")).toBeVisible()

  // The password tab is already open — the one action they can take.
  await expect(page.getByRole('tab', { name: 'Parol' })).toHaveAttribute('aria-selected', 'true')

  // The sidebar nav is locked, not silently navigable.
  await expect(page.getByRole('link', { name: 'Dekorlar' }).first()).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  await page.goto('/admin/catalog/dekorlar')
  await expect(page).toHaveURL(/\/admin\/profile/)
})

test('admin creates, resets, blocks and unblocks a platform operator', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await seedPlatform(`admin-${id}`)
  await loginAsAdmin(page, `admin-${id}`)

  await page.getByRole('link', { name: 'Adminlar' }).first().click()

  // AB-07: the signed-in operator cannot block themselves — the control is disabled.
  await expect(page.getByRole('button', { name: "O'zini bloklab bo'lmaydi" })).toBeDisabled()

  // AB-06: create an operator → the one-time secret modal reveals the temp password.
  const opLogin = `op-${id}`
  await page.getByRole('button', { name: 'Yangi admin' }).click()
  const createDialog = page.getByRole('dialog', { name: /Yangi admin/ })
  await createDialog.getByLabel('Ism').fill('E2E Operator')
  await createDialog.getByLabel('Telefon').fill(phoneFor(id, 5))
  await createDialog.getByLabel('Login').fill(opLogin)
  await createDialog.getByLabel('Vaqtinchalik parol').fill('OpTemp123')
  await createDialog.getByRole('button', { name: 'Saqlash' }).click()

  const secret = page.getByRole('dialog', { name: /maxfiy ma'lumot/ })
  await expect(secret).toBeVisible()
  await expect(secret.getByText(opLogin, { exact: true })).toBeVisible()
  await secret.getByRole('button', { name: /Yopdim/ }).click()

  const opRow = page.getByRole('row', { name: new RegExp(opLogin) })
  await expect(opRow).toBeVisible()

  // Reset password → a fresh one-time secret.
  await opRow.getByRole('button', { name: /admini parolini tiklash/ }).click()
  await page.getByRole('dialog', { name: 'Parolni tiklash' }).getByRole('button', {
    name: 'Parolni tiklash',
  }).click()
  await expect(page.getByRole('dialog', { name: /maxfiy ma'lumot/ })).toBeVisible()
  await page.getByRole('button', { name: /Yopdim/ }).click()

  // Block → row becomes Bloklangan.
  await opRow.getByRole('button', { name: /adminini bloklash/ }).click()
  await page.getByLabel(/sabab/i).fill('E2E operator block')
  await page
    .getByRole('dialog', { name: 'Adminni bloklash' })
    .getByRole('button', { name: 'Bloklash' })
    .click()
  await expect(opRow.getByText('Bloklangan')).toBeVisible()

  // Unblock → back to Faol.
  await opRow.getByRole('button', { name: /adminini blokdan chiqarish/ }).click()
  await expect(opRow.getByText('Faol')).toBeVisible()
})

test('admin triggers a background job run from the jobs surface', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await seedPlatform(`admin-${id}`)
  await loginAsAdmin(page, `admin-${id}`)

  // Navigate via the nav (auto-waits for the authenticated shell) rather than a
  // hard goto that would drop the in-memory access token.
  await page.getByRole('link', { name: 'Fon vazifalar' }).first().click()

  // The default jobs are registered on first list; run the first one.
  await page.getByRole('button', { name: /ishga tushirish|Qayta urinish/ }).first().click()
  await page.getByRole('dialog').getByRole('button', { name: 'Ishga tushirish' }).click()
  // A success or skipped toast confirms the trigger registered.
  await expect(page.getByText(/ishga tushirildi|o'tkazib yuborildi/)).toBeVisible()
})

test('admin resolves then reopens an error record', async ({ page }, testInfo) => {
  // AB-25 / AB-30: the error monitor lets an operator resolve a code and, when it
  // recurs, reopen it — both through the detail modal.
  const id = runId(testInfo)
  const code = `e2e.err_${id}`
  await seedPlatform(`admin-${id}`)
  await seedErrorRecord(code)
  await loginAsAdmin(page, `admin-${id}`)

  await page.getByRole('link', { name: 'Xatolik monitor' }).first().click()
  const row = page.getByRole('row').filter({ hasText: code })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: /xatoligi tafsilotlarini ochish/ }).click()

  // Resolve via the confirm dialog → the reopen affordance replaces it.
  await page.getByRole('button', { name: 'Hal qilingan deb belgilash' }).click()
  await page
    .getByRole('dialog', { name: 'Xatolikni tasdiqlash' })
    .getByRole('button', { name: 'Tasdiqlash' })
    .click()
  const reopen = page.getByRole('button', { name: 'Qayta ochish' })
  await expect(reopen).toBeVisible()

  // Reopen → the record flips back to open and the resolve affordance returns.
  await reopen.click()
  await expect(page.getByRole('button', { name: 'Hal qilingan deb belgilash' })).toBeVisible()
})

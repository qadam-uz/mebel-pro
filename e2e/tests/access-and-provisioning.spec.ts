import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const execFileAsync = promisify(execFile)
const databaseUrl = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const staffReadyPassword = 'StaffReady123'
const passwordLabel = /^(Password|Parol)$/
const currentPasswordLabel = /^(Current password|Joriy parol)$/
const newPasswordLabel = /^(New password|Yangi parol)/
const continueButton = /^(Continue|Kirish)$/
const saveButton = /^(Save|Saqlash|O'zgartirish)$/

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

function defaultWorkingHours() {
  return {
    monday: { open: '09:00', close: '18:00' },
    tuesday: { open: '09:00', close: '18:00' },
    wednesday: { open: '09:00', close: '18:00' },
    thursday: { open: '09:00', close: '18:00' },
    friday: { open: '09:00', close: '18:00' },
    saturday: { open: '10:00', close: '16:00' },
    sunday: { open: null, close: null },
  }
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
      env: {
        ...process.env,
        ENV: 'test',
        DATABASE_URL: databaseUrl,
        OTP_DEV_CODES: '["000000"]',
      },
    },
  )
}

async function platformToken(request: APIRequestContext, login: string) {
  const response = await request.post('/api/v1/auth/platform/login', {
    data: { login, password: adminPassword },
  })
  expect(response.ok()).toBe(true)
  return (await response.json()).access_token as string
}

async function provisionWorkshop(request: APIRequestContext, token: string, id: string) {
  const code = `w-${id}`
  const ownerLogin = `owner-${id}`
  const ownerPassword = 'OwnerTemp123'
  const response = await request.post('/api/v1/platform/workshops', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Workshop ${id}`,
        code,
        phone: phoneFor(id, 2),
        address: 'Tashkent',
      },
      branch: {
        name: `Branch ${id}`,
        address: 'Tashkent, Test',
        phone: phoneFor(id, 3),
        latitude: '41.2995',
        longitude: '69.2401',
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: 'E2E Owner',
        login: ownerLogin,
        phone: phoneFor(id, 4),
      },
      temp_password: ownerPassword,
    },
  })
  expect(response.ok()).toBe(true)
  return { ...(await response.json()), code, ownerLogin, ownerPassword }
}

async function readyOwnerToken(request: APIRequestContext, setup: Awaited<ReturnType<typeof provisionWorkshop>>) {
  const login = await request.post('/api/v1/auth/workshop/login', {
    data: {
      workshop_code: setup.code,
      login: setup.ownerLogin,
      password: setup.ownerPassword,
    },
  })
  expect(login.ok()).toBe(true)
  const access = (await login.json()).access_token as string
  const changed = await request.post('/api/v1/auth/password/change', {
    headers: { Authorization: `Bearer ${access}` },
    data: { current_password: setup.ownerPassword, new_password: ownerReadyPassword },
  })
  expect(changed.ok()).toBe(true)
  return access
}

async function changeRequiredPassword(page: Page, current: string, next: string) {
  await expect(page.locator('main').getByText(/Parolni o'zgartirish kerak|Password change required/)).toBeVisible()
  await page.getByLabel(currentPasswordLabel).fill(current)
  await page.getByLabel(newPasswordLabel).fill(next)
  await page.getByRole('button', { name: saveButton }).click()
  await expect(page.getByText(/Parol o'zgartirildi\.|Password updated\./)).toBeVisible()
}

test('admin provisions and blocks a workshop', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  const login = `admin-${id}`
  await seedPlatform(login)

  await page.goto('/admin/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(adminPassword)
  await page.getByRole('button', { name: continueButton }).click()
  await page.getByRole('link', { name: 'Ustaxonalar' }).first().click()

  await page.getByRole('button', { name: 'Yangi ustaxona' }).click()
  const provisionForm = page.getByRole('dialog', { name: /Yangi ustaxona/ })
  await provisionForm.getByLabel('Ustaxona nomi').fill(`Workshop ${id}`)
  await provisionForm.getByLabel('Code').fill(`ui-${id}`)
  await provisionForm.getByLabel(/^Telefon$/).fill(phoneFor(id, 10))
  await provisionForm.getByLabel(/^Manzil$/).fill('Tashkent')
  await provisionForm.getByLabel('Birinchi filial').fill(`Branch ${id}`)
  await provisionForm.getByLabel('Filial manzili').fill('Tashkent, Test')
  await provisionForm.getByLabel('Filial telefoni').fill(phoneFor(id, 11))
  await provisionForm.getByLabel('Latitude').fill('41.2995')
  await provisionForm.getByLabel('Longitude').fill('69.2401')
  await provisionForm.getByLabel('Owner ism').fill('UI Owner')
  await provisionForm.getByLabel('Owner login').fill(`ui-owner-${id}`)
  await provisionForm.getByLabel('Owner telefon').fill(phoneFor(id, 12))
  await provisionForm.getByLabel('Temp password').fill('OwnerTemp123')
  await provisionForm.getByRole('button', { name: 'Yaratish' }).click()

  await expect(page.getByText('Share once')).toBeVisible()
  await expect(page.getByText(`ui-${id}`, { exact: true })).toBeVisible()
  await page
    .getByRole('row', { name: new RegExp(`Workshop ${id}`) })
    .getByRole('link', { name: 'Tafsilotlar' })
    .click()
  await page.getByRole('button', { name: 'Ustaxonani bloklash' }).click()
  await page.getByLabel(/sabab/i).fill('E2E block')
  await page.getByRole('button', { name: 'Bloklash', exact: true }).click()
  await expect(page.getByText('blocked').first()).toBeVisible()
})

test('owner changes temp password, creates staff, and saves a grant', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `admin-${id}`
  await seedPlatform(adminLogin)
  const token = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, token, id)

  await page.goto('/workshop/')
  await page.getByLabel('Workshop code').fill(setup.code)
  await page.getByLabel('Login').fill(setup.ownerLogin)
  await page.getByLabel(passwordLabel).fill(setup.ownerPassword)
  await page.getByRole('button', { name: continueButton }).click()
  await changeRequiredPassword(page, setup.ownerPassword, ownerReadyPassword)
  await page.goto('/workshop/settings/users')

  await page.getByRole('button', { name: 'Yangi xodim' }).click()
  const staffForm = page.getByRole('heading', { name: 'Yangi xodim' }).locator('xpath=ancestor::section[1]')
  await staffForm.getByLabel('F.I.O').fill('E2E Staff')
  await staffForm.getByLabel('Telefon').fill(phoneFor(id, 20))
  await staffForm.getByLabel('Login').fill(`staff-${id}`)
  await staffForm.getByLabel('Vaqtinchalik parol').fill('StaffTemp123')
  await staffForm.getByRole('button', { name: 'Yaratish' }).click()
  await expect(page.getByText('StaffTemp123')).toBeVisible()
  await page.getByRole('row', { name: /E2E Staff/ }).getByRole('link', { name: 'Tahrir' }).click()
  await page.getByRole('tab', { name: 'Ruxsatlar' }).click()
  await page.getByRole('checkbox').first().check()
  await page.getByRole('button', { name: 'Saqlash' }).click()
  await expect(page.getByRole('checkbox').first()).toBeChecked()
})

test('staff sees granted branch context after password change', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `admin-${id}`
  await seedPlatform(adminLogin)
  const token = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, token, id)
  const ownerToken = await readyOwnerToken(request, setup)
  const staffLogin = `staff-${id}`
  const created = await request.post('/api/v1/workshop/users', {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      full_name: 'Granted Staff',
      phone: phoneFor(id, 30),
      login: staffLogin,
      temp_password: 'StaffTemp123',
      grants: [{ permission: 'manage_orders', branch_id: setup.branch.id }],
    },
  })
  expect(created.ok()).toBe(true)

  await page.goto('/workshop/')
  await page.getByLabel('Workshop code').fill(setup.code)
  await page.getByLabel('Login').fill(staffLogin)
  await page.getByLabel(passwordLabel).fill('StaffTemp123')
  await page.getByRole('button', { name: continueButton }).click()
  await changeRequiredPassword(page, 'StaffTemp123', staffReadyPassword)

  await expect(page.getByRole('button', { name: new RegExp(`Branch ${id}`) })).toBeVisible()
})

test('workshop staff direct URLs respect branch-scoped grants', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `admin-${id}`
  await seedPlatform(adminLogin)
  const token = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, token, id)
  const ownerToken = await readyOwnerToken(request, setup)
  const staffLogin = `inventory-${id}`
  const created = await request.post('/api/v1/workshop/users', {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      full_name: 'Inventory Staff',
      phone: phoneFor(id, 50),
      login: staffLogin,
      temp_password: 'StaffTemp123',
      grants: [{ permission: 'manage_inventory', branch_id: setup.branch.id }],
    },
  })
  expect(created.ok()).toBe(true)

  await page.goto('/workshop/')
  await page.getByLabel('Workshop code').fill(setup.code)
  await page.getByLabel('Login').fill(staffLogin)
  await page.getByLabel(passwordLabel).fill('StaffTemp123')
  await page.getByRole('button', { name: continueButton }).click()
  await changeRequiredPassword(page, 'StaffTemp123', staffReadyPassword)

  await page.goto('/workshop/finance')
  await expect(page).toHaveURL(/\/workshop\/?$/)
  await expect(page.getByRole('heading', { name: 'Asosiy' })).toBeVisible()

  await page.goto('/workshop/settings/users')
  await expect(page).toHaveURL(/\/workshop\/?$/)

  await page.goto('/workshop/inventory')
  await expect(page).toHaveURL(/\/workshop\/inventory\/?$/)
  await expect(page.getByRole('heading', { name: 'Ombor' })).toBeVisible()

  await page.goto(`/workshop/branches/${setup.branch.id}`)
  await expect(page).toHaveURL(new RegExp(`/workshop/branches/${setup.branch.id}`))
  await expect(page.getByRole('heading', { name: new RegExp(`Branch ${id}`) })).toBeVisible()
})

test('client signs in with dev OTP and registers a name', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await page.goto('/client/auth/login')
  await page.getByLabel('Telefon raqami').fill(phoneFor(id, 40))
  await page.getByRole('button', { name: 'Kod yuborish' }).click()
  await page.getByLabel('Tasdiqlash kodi').fill('000000')
  await page.getByRole('button', { name: 'Tasdiqlash' }).click()
  await page.getByLabel('Ismingiz').fill('E2E Client')
  await page.getByRole('button', { name: 'Davom etish' }).click()

  await expect(page).toHaveURL(/\/client\/c$/)
  await expect(page.getByRole('heading', { name: 'Bosh sahifa', exact: true })).toBeVisible()
})

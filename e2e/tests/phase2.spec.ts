import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext } from '@playwright/test'

const execFileAsync = promisify(execFile)
const databaseUrl = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const staffReadyPassword = 'StaffReady123'

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
        working_hours: {},
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

test('admin provisions and blocks a workshop', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  const login = `admin-${id}`
  await seedPlatform(login)

  await page.goto('/admin/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel('Password').fill(adminPassword)
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('link', { name: 'Workshops' }).first().click()

  await page.getByPlaceholder('Workshop name').fill(`Workshop ${id}`)
  await page.getByPlaceholder('Code').fill(`ui-${id}`)
  await page.getByPlaceholder('Workshop phone').fill(phoneFor(id, 10))
  await page.getByPlaceholder('Workshop address').fill('Tashkent')
  await page.getByPlaceholder('First branch').fill(`Branch ${id}`)
  await page.getByPlaceholder('Branch address').fill('Tashkent, Test')
  await page.getByPlaceholder('Branch phone').fill(phoneFor(id, 11))
  await page.getByPlaceholder('Latitude').fill('41.2995')
  await page.getByPlaceholder('Longitude').fill('69.2401')
  await page.getByPlaceholder('Owner name').fill('UI Owner')
  await page.getByPlaceholder('Owner login').fill(`ui-owner-${id}`)
  await page.getByPlaceholder('Owner phone').fill(phoneFor(id, 12))
  await page.getByPlaceholder('Temp password').fill('OwnerTemp123')
  await page.getByRole('button', { name: 'Create workshop' }).click()

  await expect(page.getByText(`Created ui-${id}`)).toBeVisible()
  await page.getByRole('link', { name: new RegExp(`Workshop ${id}`) }).click()
  await page.getByPlaceholder('Block reason').fill('E2E block')
  await page.getByRole('button', { name: 'Block', exact: true }).click()
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
  await page.getByLabel('Password').fill(setup.ownerPassword)
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.locator('main').getByText('Password change required', { exact: true })).toBeVisible()
  await page.getByLabel('Current password').fill(setup.ownerPassword)
  await page.getByLabel('New password').fill(ownerReadyPassword)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Password updated.')).toBeVisible()
  await page.getByRole('link', { name: 'Users' }).first().click()

  await page.getByPlaceholder('Full name').fill('E2E Staff')
  await page.getByPlaceholder('Phone').fill(phoneFor(id, 20))
  await page.getByPlaceholder('Login').fill(`staff-${id}`)
  await page.getByPlaceholder('Temp password').fill('StaffTemp123')
  await page.getByRole('button', { name: 'Create user' }).click()
  await expect(page.getByText('StaffTemp123')).toBeVisible()
  await page.getByRole('link', { name: /E2E Staff/ }).click()
  await page.getByRole('checkbox').first().check()
  await page.getByRole('button', { name: 'Save grants' }).click()
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
  await page.getByLabel('Password').fill('StaffTemp123')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel('Current password').fill('StaffTemp123')
  await page.getByLabel('New password').fill(staffReadyPassword)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Password updated.')).toBeVisible()

  await expect(page.getByRole('button', { name: new RegExp(`Branch ${id}`) })).toBeVisible()
})

test('client signs in with dev OTP and registers a name', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  await page.goto('/client/auth/login')
  await page.getByLabel('Phone').fill(phoneFor(id, 40))
  await page.getByRole('button', { name: 'Send code' }).click()
  await page.getByLabel('Code').fill('000000')
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByLabel('Name').fill('E2E Client')
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page).toHaveURL(/\/client\/c$/)
  await expect(page.getByRole('heading', { name: 'Client workspace', exact: true })).toBeVisible()
})

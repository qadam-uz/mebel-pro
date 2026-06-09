import { execFile } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const execFileAsync = promisify(execFile)
const databaseUrl = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const staffReadyPassword = 'StaffReady123'

function runId(testInfo: { workerIndex: number }) {
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
  const code = `p3-${id}`
  const ownerLogin = `owner-${id}`
  const ownerPassword = 'OwnerTemp123'
  const response = await request.post('/api/v1/platform/workshops', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Phase 3 Workshop ${id}`,
        code,
        phone: phoneFor(id, 2),
        address: 'Tashkent',
      },
      branch: {
        name: `Phase 3 Branch ${id}`,
        address: 'Tashkent, Test',
        phone: phoneFor(id, 3),
        latitude: '41.2995',
        longitude: '69.2401',
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: 'Phase 3 Owner',
        login: ownerLogin,
        phone: phoneFor(id, 4),
      },
      temp_password: ownerPassword,
    },
  })
  expect(response.ok()).toBe(true)
  return { ...(await response.json()), code, ownerLogin, ownerPassword }
}

async function readyOwnerToken(
  request: APIRequestContext,
  setup: Awaited<ReturnType<typeof provisionWorkshop>>,
) {
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

async function createCatalogMaterial(
  request: APIRequestContext,
  token: string,
  id: string,
  imageFileId: string | null = null,
) {
  const manufacturer = await request.post('/api/v1/platform/catalog/manufacturers', {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `Phase 3 Maker ${id}`, country: 'UZ' },
  })
  expect(manufacturer.ok()).toBe(true)
  const manufacturerId = (await manufacturer.json()).id as string
  const material = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'panel',
      manufacturer_id: manufacturerId,
      type: 'dsp',
      name: `Phase 3 Panel ${id}`,
      thickness_mm: '18',
      color: 'White',
      decor_code: `P3-${id}`,
      panel_length_mm: 2800,
      panel_width_mm: 2070,
      grain_direction: true,
      image_file_id: imageFileId,
    },
  })
  expect(material.ok()).toBe(true)
  return (await material.json()) as { id: string; name: string }
}

async function loginAdmin(page: Page, login: string) {
  await page.goto('/admin/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel('Password').fill(adminPassword)
  await page.getByRole('button', { name: 'Continue' }).click()
}

async function loginWorkshop(page: Page, code: string, login: string, password: string) {
  await page.goto('/workshop/')
  await page.getByLabel('Workshop code').fill(code)
  await page.getByLabel('Login').fill(login)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Continue' }).click()
}

test('admin creates platform catalog material through the UI', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  const login = `p3-admin-${id}`
  const makerName = `UI Maker ${id}`
  const materialName = `UI Panel ${id}`
  await seedPlatform(login)
  await loginAdmin(page, login)

  await page.getByRole('link', { name: 'Catalog' }).first().click()
  await expect(page.getByRole('heading', { name: 'Catalog' })).toBeVisible()

  const manufacturerSection = page
    .getByRole('heading', { name: 'Manufacturers' })
    .locator('xpath=ancestor::section[1]')
  await manufacturerSection.getByLabel('Name').fill(makerName)
  await manufacturerSection.getByLabel('Country').fill('UZ')
  await manufacturerSection.getByRole('button', { name: 'Create manufacturer' }).click()
  await expect(page.getByRole('heading', { name: makerName })).toBeVisible()

  const materialSection = page
    .getByRole('heading', { name: 'Materials' })
    .locator('xpath=ancestor::section[1]')
  await materialSection.getByRole('button', { name: /Manufacturer/ }).click()
  await page.getByRole('option', { name: new RegExp(makerName) }).click()
  await materialSection.getByLabel('Name').fill(materialName)
  await materialSection.getByLabel('Color').fill('White')
  await materialSection.getByLabel('Decor code').fill(`UI-${id}`)
  await materialSection.getByRole('button', { name: 'Create material' }).click()

  await expect(page.getByRole('cell', { name: materialName })).toBeVisible()
})

test('owner adds a branch material and records stock movement with a receipt', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  await readyOwnerToken(request, setup)
  const material = await createCatalogMaterial(request, adminAccess, id)

  await loginWorkshop(page, setup.code, setup.ownerLogin, ownerReadyPassword)
  await page.getByRole('link', { name: 'Branches' }).first().click()
  await page.getByRole('link', { name: new RegExp(`Phase 3 Branch ${id}`) }).click()

  const addMaterial = page
    .getByRole('heading', { name: 'Add branch material' })
    .locator('xpath=ancestor::section[1]')
  await addMaterial.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  await addMaterial.getByRole('combobox', { name: 'Material' }).press('Escape')
  await addMaterial.getByLabel('Price tiyin').fill('250000')
  await addMaterial.getByLabel(/Min stock/).fill('2')
  await addMaterial.getByRole('button', { name: 'Add material' }).click()
  await expect(page.getByRole('cell', { name: material.name })).toBeVisible()

  await page.getByRole('button', { name: 'Inventory' }).click()
  const stockIn = page.getByRole('heading', { name: 'Stock in' }).locator('xpath=ancestor::section[1]')
  await stockIn.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  await stockIn.getByRole('combobox', { name: 'Material' }).press('Escape')
  await stockIn.getByLabel(/Quantity/).fill('3')
  await stockIn.getByRole('button', { name: /Supplier/ }).click()
  await page.getByRole('option', { name: 'New supplier label' }).click()
  await stockIn.getByLabel('New supplier name').fill(`Supplier ${id}`)
  const receiptPath = testInfo.outputPath('receipt.pdf')
  writeFileSync(receiptPath, '%PDF-1.4\n% receipt\n')
  await stockIn.getByLabel('Receipt').setInputFiles(receiptPath)
  await expect(stockIn.getByText(/receipt /)).toBeVisible()
  await stockIn.getByRole('button', { name: 'Record stock-in' }).click()
  await expect(page.getByRole('cell', { name: '3 panel' })).toBeVisible()

  const adjustment = page
    .getByRole('heading', { name: 'Adjustment' })
    .locator('xpath=ancestor::section[1]')
  await adjustment.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  await adjustment.getByRole('combobox', { name: 'Material' }).press('Escape')
  await adjustment.getByLabel(/Signed quantity/).fill('-1')
  await adjustment.getByLabel('Note').fill('E2E stock take')
  await adjustment.getByRole('button', { name: 'Record adjustment' }).click()
  await expect(page.getByText('low stock')).toBeVisible()
  await expect(page.getByRole('cell', { name: `Supplier ${id}` })).toBeVisible()
})

test('inventory-only staff sees inventory controls but not catalog controls', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const image = await request.post('/api/v1/files', {
    headers: { Authorization: `Bearer ${adminAccess}` },
    multipart: {
      upload: {
        name: 'material.png',
        mimeType: 'image/png',
        buffer: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
          'base64',
        ),
      },
    },
  })
  expect(image.ok()).toBe(true)
  const material = await createCatalogMaterial(request, adminAccess, id, (await image.json()).id)
  const branchId = setup.branch.id as string
  const staffLogin = `inv-${id}`
  const materialSelection = await request.post(`/api/v1/workshop/branches/${branchId}/materials`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: { material_id: material.id, price_tiyin: 250000, min_stock: 1 },
  })
  expect(materialSelection.ok()).toBe(true)
  const staff = await request.post('/api/v1/workshop/users', {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: {
      full_name: 'Inventory Staff',
      phone: phoneFor(id, 50),
      login: staffLogin,
      temp_password: 'StaffTemp123',
      grants: [{ permission: 'manage_inventory', branch_id: branchId }],
    },
  })
  expect(staff.ok()).toBe(true)

  await loginWorkshop(page, setup.code, staffLogin, 'StaffTemp123')
  await page.getByLabel('Current password').fill('StaffTemp123')
  await page.getByLabel('New password').fill(staffReadyPassword)
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Password updated.')).toBeVisible()
  await page.goto(`/workshop/branches/${branchId}`)

  await expect(page.getByRole('link', { name: 'Branches' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Users' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Materials' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Stock in' })).toBeVisible()
})

test('client browses public branch catalog without stock details', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const image = await request.post('/api/v1/files', {
    headers: { Authorization: `Bearer ${adminAccess}` },
    multipart: {
      upload: {
        name: 'client-material.png',
        mimeType: 'image/png',
        buffer: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
          'base64',
        ),
      },
    },
  })
  expect(image.ok()).toBe(true)
  const material = await createCatalogMaterial(request, adminAccess, id, (await image.json()).id)
  const branchId = setup.branch.id as string
  const selected = await request.post(`/api/v1/workshop/branches/${branchId}/materials`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: { material_id: material.id, price_tiyin: 250000, min_stock: 1 },
  })
  expect(selected.ok()).toBe(true)

  await page.goto('/client/auth/login')
  await page.getByLabel('Telefon raqami').fill(phoneFor(id, 60))
  await page.getByRole('button', { name: 'Kod yuborish' }).click()
  await page.getByLabel('Tasdiqlash kodi').fill('000000')
  await page.getByRole('button', { name: 'Tasdiqlash' }).click()
  await page.getByLabel('Ismingiz').fill('Phase 3 Client')
  await page.getByRole('button', { name: 'Davom etish' }).click()
  await page.getByRole('link', { name: 'Ustaxonalar' }).first().click()
  await page.getByLabel('Ustaxona yoki shahar nomi').fill(`Phase 3 Workshop ${id}`)

  await expect(page.getByRole('heading', { name: 'Ustaxonalar' })).toBeVisible()
  const branchCard = page.locator('article.client-card').filter({
    has: page.getByRole('heading', { name: new RegExp(`Phase 3 Workshop ${id}`) }),
  })
  await expect(branchCard).toBeVisible()
  await expect(branchCard.getByText(material.name)).toBeVisible()
  await expect(branchCard.getByText(/UZS\s*2[, ]500/)).toBeVisible()
  await expect(page.getByText('low stock')).toHaveCount(0)
  await expect(page.getByText(/Supplier/)).toHaveCount(0)
})

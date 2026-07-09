import { execFile } from 'node:child_process'
import { writeFileSync } from 'node:fs'
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

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
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
  const ownerLogin = `owner-${id}`
  const ownerPassword = 'OwnerTemp123'
  const response = await request.post('/api/v1/platform/workshops', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Catalog Workshop ${id}`,
      },
      branch: {
        name: `Catalog Branch ${id}`,
        address: 'Tashkent, Test',
        phone: phoneFor(id, 3),
        working_hours: defaultWorkingHours(),
      },
      owner: {
        login: ownerLogin,
      },
      temp_password: ownerPassword,
    },
  })
  expect(response.ok()).toBe(true)
  return { ...(await response.json()), ownerLogin, ownerPassword }
}

async function readyOwnerToken(
  request: APIRequestContext,
  setup: Awaited<ReturnType<typeof provisionWorkshop>>,
) {
  const login = await request.post('/api/v1/auth/workshop/login', {
    data: {
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
    data: { name: `Catalog Maker ${id}`, country: 'UZ' },
  })
  expect(manufacturer.ok()).toBe(true)
  const manufacturerId = (await manufacturer.json()).id as string
  const material = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'panel',
      manufacturer_id: manufacturerId,
      type: 'dsp',
      name: `Catalog Panel ${id}`,
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
  await page.getByLabel(passwordLabel).fill(adminPassword)
  await page.getByRole('button', { name: continueButton }).click()
}

async function loginWorkshop(page: Page, login: string, password: string) {
  await page.goto('/workshop/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(password)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page).toHaveURL(/\/workshop(\/profile)?\/?$/)
}

async function changeRequiredPassword(page: Page, current: string, next: string) {
  await expect(page.locator('main').getByText(/Parolni o'zgartirish kerak|Password change required/)).toBeVisible()
  await page.getByLabel(currentPasswordLabel).fill(current)
  await page.getByLabel(newPasswordLabel).fill(next)
  await page.getByRole('button', { name: saveButton }).click()
  await expect(page.getByText(/Parol o'zgartirildi\.|Password updated\./)).toBeVisible()
}

test('admin creates platform catalog material through the UI', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  const login = `p3-admin-${id}`
  const makerName = `UI Maker ${id}`
  const materialName = `UI Panel ${id}`
  await seedPlatform(login)
  await loginAdmin(page, login)

  await page.getByRole('link', { name: 'Materiallar' }).first().click()
  await expect(page.getByRole('heading', { name: 'Material katalogi' })).toBeVisible()

  // On a fresh catalog the empty state also renders a "Yangi material" CTA, so
  // target the always-present page-header action (first in DOM order) — keeps
  // this deterministic whether or not the catalog already has rows.
  await page.getByRole('button', { name: 'Yangi material' }).first().click()
  const materialDialog = page.getByRole('dialog', { name: 'Yangi material' })
  await materialDialog.getByRole('button', { name: 'Yangi ishlab chiqaruvchi' }).click()
  const manufacturerDialog = page.getByRole('dialog', { name: 'Yangi ishlab chiqaruvchi' })
  await manufacturerDialog.getByLabel('Nomi').fill(makerName)
  await manufacturerDialog.getByLabel('Davlat').fill('UZ')
  await manufacturerDialog.getByRole('button', { name: 'Saqlash' }).click()
  await expect(manufacturerDialog).toBeHidden()
  await expect(materialDialog.getByRole('combobox', { name: new RegExp(makerName) })).toBeVisible()

  await materialDialog.getByLabel('Material nomi').fill(materialName)
  await materialDialog.getByLabel('Rang / decor').fill('White')
  await materialDialog.getByLabel('Decor kodi').fill(`UI-${id}`)
  await materialDialog.getByRole('button', { name: 'Saqlash' }).click()

  await expect(
    page.getByRole('row', { name: new RegExp(escapeRegExp(materialName)) }),
  ).toBeVisible()
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

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await expect(page.getByRole('heading', { name: 'Material katalogi' })).toBeVisible()

  // The trigger appears in the page head and, while the list is empty, again as
  // the empty-state CTA — target the always-present header action.
  await page.getByRole('button', { name: "+ Material qo'shish" }).first().click()
  const addMaterial = page.getByRole('dialog', { name: "Material qo'shish" })
  await addMaterial.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  await addMaterial.getByLabel(/Narx/).fill('2500')
  await addMaterial.getByLabel(/Min zaxira/).fill('2')
  await addMaterial.getByRole('button', { name: "Qo'shish", exact: true }).click()
  // Two cells carry the material name now (the name cell and the Holat switch's
  // accessible name) — the first one is the name cell.
  await expect(page.getByRole('cell', { name: material.name }).first()).toBeVisible()

  // The Holat column is an in-row switch; a toggle must flip aria-checked and persist.
  const materialSwitch = () =>
    page
      .getByRole('row', { name: new RegExp(escapeRegExp(material.name)) })
      .getByRole('switch')
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'true')
  await materialSwitch().click()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'false')
  await page.reload()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'false')
  // Restore visibility so the client-facing flows keep seeing the material.
  await materialSwitch().click()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'true')

  await page.goto('/workshop/inventory')
  await expect(page.getByRole('heading', { name: 'Ombor' })).toBeVisible()
  await page.getByRole('button', { name: 'Kirim', exact: true }).click()
  const stockIn = page.getByRole('dialog', { name: 'Kirim' })
  await stockIn.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  await stockIn.getByLabel(/Miqdor/).fill('3')
  await stockIn.getByRole('combobox', { name: /Yetkazib beruvchi/ }).click()
  await page.getByRole('option', { name: 'Yangi yetkazib beruvchi' }).click()
  await stockIn.getByLabel('Yangi yetkazib beruvchi nomi').fill(`Supplier ${id}`)
  const receiptPath = testInfo.outputPath('receipt.pdf')
  writeFileSync(receiptPath, '%PDF-1.4\n% receipt\n')
  await stockIn.getByLabel('Chek').setInputFiles(receiptPath)
  await expect(stockIn.getByText('receipt.pdf')).toBeVisible()
  await stockIn.getByRole('button', { name: 'Saqlash' }).click()
  const stockTable = page.getByRole('table').filter({
    has: page.getByRole('columnheader', { name: 'Mavjud' }),
  })
  await expect(
    stockTable.getByRole('row', { name: new RegExp(`${escapeRegExp(material.name)}.*3 panel`) }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Tuzatish', exact: true }).click()
  const adjustment = page.getByRole('dialog', { name: 'Tuzatish' })
  await adjustment.getByRole('combobox', { name: 'Material' }).fill(material.name)
  await page.getByRole('option', { name: new RegExp(material.name) }).click()
  // The adjust quantity is a signed value with a required +/− prefix.
  await adjustment.getByLabel(/Tuzatish miqdori/).fill('-1')
  await adjustment.getByLabel('Izoh').fill('E2E stock take')
  await adjustment.getByRole('button', { name: 'Saqlash' }).click()
  await expect(stockTable.getByText('Kam qolgan', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Tranzaksiyalar' }).click()
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
      home_branch_id: branchId,
      temp_password: 'StaffTemp123',
      grants: [{ permission: 'manage_inventory', branch_id: branchId }],
    },
  })
  expect(staff.ok()).toBe(true)

  await loginWorkshop(page, staffLogin, 'StaffTemp123')
  await changeRequiredPassword(page, 'StaffTemp123', staffReadyPassword)
  await page.goto(`/workshop/branches/${branchId}`)
  await expect(page).toHaveURL(/\/workshop\/?$/)

  await expect(page.getByRole('link', { name: 'Filiallar' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Xodimlar' })).toHaveCount(0)
  await page.goto('/workshop/inventory')
  await expect(page.getByRole('button', { name: 'Kirim', exact: true })).toBeVisible()
})

test('client browses the workshop directory without catalog or stock details', async ({ page, request }, testInfo) => {
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
  await page.getByLabel('Ismingiz').fill('Catalog Client')
  await page.getByRole('button', { name: 'Davom etish' }).click()
  await page.getByRole('link', { name: 'Ustaxonalar' }).first().click()
  await page.getByLabel('Ustaxona yoki shahar nomi').fill(`Catalog Workshop ${id}`)

  await expect(page.getByRole('heading', { name: 'Ustaxonalar' })).toBeVisible()
  const branchCard = page.locator('article.client-card').filter({
    has: page.getByRole('heading', { name: new RegExp(`Catalog Workshop ${id}`) }),
  })
  await expect(branchCard).toBeVisible()
  // The workshops page is a directory now (the CB-13 client material preview was
  // removed): neither the catalog (material name / price) nor any internal
  // stock/supplier detail surfaces — materials are browsed in the cutting editor.
  await expect(branchCard.getByText(material.name)).toHaveCount(0)
  await expect(branchCard.getByText(/UZS\s*2[, ]500/)).toHaveCount(0)
  await expect(page.getByText('low stock')).toHaveCount(0)
  await expect(page.getByText(/Supplier/)).toHaveCount(0)
})

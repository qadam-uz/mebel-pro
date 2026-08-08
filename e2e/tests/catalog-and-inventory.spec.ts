import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

import {
  carryDekor,
  createCatalogDekorlar,
  createDekor,
  createManufacturer,
  databaseUrl,
  escapeRegExp,
  expectOk,
  type BranchMaterialResponse,
  type DekorResponse,
} from './helpers'

const execFileAsync = promisify(execFile)
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const staffReadyPassword = 'StaffReady123'
const passwordLabel = /^(Password|Parol)$/
const currentPasswordLabel = /^(Current password|Joriy parol)$/
const newPasswordLabel = /^(New password|Yangi parol)/
const continueButton = /^(Continue|Kirish)$/
const saveButton = /^(Save|Saqlash|O'zgartirish)$/

// The standard LDSP o'lcham this spec attaches through the UI. `×` is U+00D7 —
// the same multiplication sign the app prints, not a Latin x.
const FORMAT_LABEL = '2800×2070×18 mm'
// A kromka's o'lcham is thickness × tape width — a different axis, same label shape.
const TAPE_LABEL = '2×19 mm'

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
  await expectOk(response)
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
      },
      owner: {
        login: ownerLogin,
      },
      temp_password: ownerPassword,
    },
  })
  await expectOk(response)
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
  await expectOk(login)
  const access = (await login.json()).access_token as string
  const changed = await request.post('/api/v1/auth/password/change', {
    headers: { Authorization: `Bearer ${access}` },
    data: { current_password: setup.ownerPassword, new_password: ownerReadyPassword },
  })
  await expectOk(changed)
  return access
}

/**
 * One platform dekor — identity only. No thickness, no size, no price: the
 * branch decides the formats, so there is nothing here for the catalog to hold.
 */
async function createCatalogDekor(
  request: APIRequestContext,
  token: string,
  id: string,
  imageFileId: string | null = null,
) {
  const manufacturerId = await createManufacturer(request, token, `Catalog Maker ${id}`)
  return createDekor(request, token, {
    manufacturer_id: manufacturerId,
    tur: 'ldsp',
    kod: `P3-${id}`,
    nomi: 'White',
    tolali: true,
    image_file_id: imageFileId,
  })
}

/** Read the branch's carried formats back, for their server-composed labels. */
async function branchMaterials(
  request: APIRequestContext,
  token: string,
  branchId: string,
): Promise<BranchMaterialResponse[]> {
  const response = await request.get(`/api/v1/workshop/branches/${branchId}/materials`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  await expectOk(response)
  return (await response.json()) as BranchMaterialResponse[]
}

async function uploadImage(request: APIRequestContext, token: string, name: string) {
  const response = await request.post('/api/v1/files', {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      upload: {
        name,
        mimeType: 'image/png',
        buffer: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
          'base64',
        ),
      },
    },
  })
  await expectOk(response)
  return (await response.json()).id as string
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

/**
 * The result table names every row by its dekor as well as its o'lcham, because
 * one batch can span dekorlar — so a price/threshold field is addressed by both.
 */
function rowLabel(dekor: DekorResponse, format: string) {
  return `${dekor.label} · ${format}`
}

/** Tick a dekor in step 1. The cards are checkboxes — attach is multi-select. */
async function tickDekor(pickStep: Locator, dekor: DekorResponse) {
  // Narrow to this run's dekor first: the picker lists every active dekor on the
  // platform, paged, so a parallel worker's rows can push ours off page one.
  await pickStep.getByLabel('Qidirish').fill(dekor.kod ?? dekor.nomi)
  await pickStep.getByRole('checkbox', { name: new RegExp(escapeRegExp(dekor.label)) }).check()
}

/**
 * Drive the two-step attach sheet for a single dekor: tick it, then pick the
 * thickness and size chips whose cross product becomes the rows to create.
 */
async function attachThroughSheet(
  page: Page,
  dekor: DekorResponse,
  formats: Array<{ thickness: string; size: string }>,
) {
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  await tickDekor(pickStep, dekor)
  await pickStep.getByRole('button', { name: 'Davom etish' }).click()

  const formatStep = page.getByRole('dialog', { name: "O'lchamlar va narx" })
  for (const value of new Set(formats.map((format) => format.thickness))) {
    await formatStep.getByRole('button', { name: `${value} mm`, exact: true }).click()
  }
  for (const value of new Set(formats.map((format) => format.size))) {
    await formatStep.getByRole('button', { name: value, exact: true }).click()
  }
  return formatStep
}

test('admin creates a platform dekor through the UI', async ({ page }, testInfo) => {
  const id = runId(testInfo)
  const login = `p3-admin-${id}`
  const makerName = `UI Maker ${id}`
  await seedPlatform(login)
  await loginAdmin(page, login)

  await page.getByRole('link', { name: 'Dekorlar' }).first().click()
  await expect(page.getByRole('heading', { name: 'Dekorlar' })).toBeVisible()

  // On a fresh catalog the empty state also renders a "+ Yangi dekor" CTA, so
  // target the always-present page-header action (first in DOM order) — keeps
  // this deterministic whether or not the catalog already has rows.
  await page.getByRole('button', { name: '+ Yangi dekor' }).first().click()
  const dekorDialog = page.getByRole('dialog', { name: 'Yangi dekor' })
  await dekorDialog.getByRole('button', { name: '+ Yangi ishlab chiqaruvchi' }).click()
  const manufacturerDialog = page.getByRole('dialog', { name: 'Yangi ishlab chiqaruvchi' })
  await manufacturerDialog.getByLabel('Nomi').fill(makerName)
  await manufacturerDialog.getByLabel('Davlat').fill('UZ')
  await manufacturerDialog.getByRole('button', { name: 'Saqlash' }).click()
  await expect(manufacturerDialog).toBeHidden()
  await expect(dekorDialog.getByRole('combobox', { name: new RegExp(makerName) })).toBeVisible()

  // A dekor is identity only. Thickness, size and price moved to the branch, so
  // the admin form must not offer them anywhere — the whole point of the split.
  await expect(dekorDialog.getByLabel(/Qalinlik/)).toHaveCount(0)
  await expect(dekorDialog.getByLabel(/Uzunlik|Kenglik|o'lcham/i)).toHaveCount(0)
  await expect(dekorDialog.getByLabel(/Narx/)).toHaveCount(0)

  // The display string is composed from tur/manufacturer/kod/nomi — the form
  // takes the pieces and shows a read-only "Dekor kartasi (avtomatik)" preview,
  // so there is no name field to fill.
  await dekorDialog.getByLabel('Nomi').fill('White')
  await dekorDialog.getByLabel('Kod').fill(`UI-${id}`)
  // The preview card and the image field's title both render it — `.first()` is
  // the card, which is the one the operator reads while typing.
  await expect(
    dekorDialog.getByText(`LDSP ${makerName} UI-${id} · White`).first(),
  ).toBeVisible()
  await dekorDialog.getByRole('button', { name: 'Saqlash' }).click()

  // The kod is unique per run and part of the composed label shown in the row.
  await expect(
    page.getByRole('row', { name: new RegExp(escapeRegExp(`UI-${id}`)) }),
  ).toBeVisible()
  // Still identity only on the way out: the list carries no format or price column.
  await expect(page.getByRole('columnheader', { name: /Qalinlik|Narx|O'lcham/i })).toHaveCount(0)
})

test('owner adds a branch material and records priced stock movement with prefill', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const branchId = setup.branch.id as string
  const dekor = await createCatalogDekor(request, adminAccess, id)

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await expect(page.getByRole('heading', { name: 'Material katalogi' })).toBeVisible()

  // The trigger appears in the filter bar and, while the list is empty, again as
  // the empty-state CTA — target the always-present header action.
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()
  // The reshape made attaching two steps: a dekor is identity, a format is the
  // branch's own fact, so step 1 picks the dekor and step 2 the formats + price.
  const formatStep = await attachThroughSheet(page, dekor, [
    { thickness: '18', size: '2800×2070' },
  ])
  // The threshold prefills at 0 for every tur: a branch registers its o'lcham
  // list before it knows a threshold, so a non-zero prefill is a number nobody
  // chose.
  const threshold = formatStep.getByLabel(`${rowLabel(dekor, FORMAT_LABEL)} kam qoldiq chegarasi`)
  await expect(threshold).toHaveValue('0')
  await threshold.fill('2')
  await formatStep.getByLabel(`${rowLabel(dekor, FORMAT_LABEL)} narxi`).fill('2500')
  await formatStep.getByRole('button', { name: /o'lchamni qo'shish/ }).click()

  // The table groups by dekor: the identity line once, its o'lchamlar beneath.
  await expect(page.getByRole('button', { name: `${dekor.label} o'lchamlari` })).toBeVisible()
  const formatRow = page.getByRole('row').filter({ hasText: FORMAT_LABEL })
  await expect(formatRow).toHaveCount(1)

  const [material] = await branchMaterials(request, ownerAccess, branchId)
  expect(material.label).toContain(FORMAT_LABEL)

  // The Holat column is an in-row switch; a toggle must flip aria-checked and persist.
  const materialSwitch = () => formatRow.getByRole('switch')
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
  // An arrival is one supplier invoice with a line per material (QAD-149).
  await page.getByRole('button', { name: 'Kirim', exact: true }).click()
  const stockIn = page.getByRole('dialog', { name: 'Kirim' })
  await stockIn.getByRole('combobox', { name: /Ta.minotchi/ }).click()
  await page.getByRole('option', { name: "Yangi ta'minotchi" }).click()
  await stockIn.getByLabel("Yangi ta'minotchi nomi").fill(`Supplier ${id}`)
  await stockIn.getByRole('combobox', { name: 'Material' }).fill(material.label)
  await page.getByRole('option', { name: new RegExp(escapeRegExp(material.label)) }).click()
  await stockIn.getByRole('textbox', { name: /^Miqdor/ }).fill('3')
  // First-ever stock-in: no price history, so the field is empty with the hint.
  await expect(stockIn.getByText('Birinchi kirim', { exact: false })).toBeVisible()
  await stockIn.getByRole('textbox', { name: /^Narx/ }).fill('2000')
  // The live totals mirror the server math: 3 x 2 000 so'm, no adjustments.
  await expect(stockIn.getByText('Oraliq jami')).toBeVisible()
  await stockIn.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await expect(page.getByText(/Kirim K-\d{4} yozildi\./)).toBeVisible()
  const stockTable = page.getByRole('table').filter({
    has: page.getByRole('columnheader', { name: 'Mavjud' }),
  })
  await expect(
    stockTable.getByRole('row', { name: new RegExp(`${escapeRegExp(material.label)}.*3 list`) }),
  ).toBeVisible()

  // The arrival is readable as a document: one K-… row carrying one position.
  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  const invoiceRow = page
    .getByRole('row')
    .filter({ has: page.getByRole('cell', { name: `Supplier ${id}` }) })
  await expect(invoiceRow).toContainText('1 pozitsiya')
  await expect(invoiceRow.getByText("To'lanmagan")).toBeVisible()
  // QAD-184: the row expands itself — the control is an icon-only chevron named
  // after the faktura it opens, not a "Qatorlar" label.
  await invoiceRow.getByRole('button', { name: /qatorlari/ }).click()
  // `exact` matters: the expanded-lines container is itself a cell whose
  // accessible name contains the material label, so a loose match hits two.
  await expect(page.getByRole('cell', { name: material.label, exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Zaxira' }).click()

  // Reopen: the last price paid prefills the line with provenance underneath.
  await page.getByRole('button', { name: 'Kirim', exact: true }).click()
  const stockInAgain = page.getByRole('dialog', { name: 'Kirim' })
  await stockInAgain.getByRole('combobox', { name: 'Material' }).fill(material.label)
  await page.getByRole('option', { name: new RegExp(escapeRegExp(material.label)) }).click()
  await expect(stockInAgain.getByRole('textbox', { name: /^Narx/ })).toHaveValue('2000')
  await expect(stockInAgain.getByText('Oxirgi narx', { exact: false })).toBeVisible()
  await expect(stockInAgain.getByText(`Supplier ${id}`, { exact: false })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Tuzatish', exact: true }).click()
  const adjustment = page.getByRole('dialog', { name: 'Tuzatish' })
  await adjustment.getByRole('combobox', { name: 'Material' }).fill(material.label)
  await page.getByRole('option', { name: new RegExp(escapeRegExp(material.label)) }).click()
  // The adjust quantity is a signed value with a required +/− prefix.
  await adjustment.getByLabel(/Tuzatish miqdori/).fill('-1')
  await adjustment.getByLabel('Izoh').fill('E2E stock take')
  await adjustment.getByRole('button', { name: 'Saqlash' }).click()
  await expect(stockTable.getByText('Kam qolgan', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Tranzaksiyalar' }).click()
  await expect(page.getByRole('cell', { name: `Supplier ${id}` })).toBeVisible()
})

test('one dekor attached in two formats in a single pass creates two branch materials', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const branchId = setup.branch.id as string
  const dekor = await createCatalogDekor(request, adminAccess, id)

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()

  // Two thicknesses × one size: the cross product is the table of rows to create,
  // and one attach is one transaction — this is the whole reason a dekor and a
  // format are separate rows.
  const formatStep = await attachThroughSheet(page, dekor, [
    { thickness: '16', size: '2800×2070' },
    { thickness: '18', size: '2800×2070' },
  ])
  const price16 = formatStep.getByLabel(`${rowLabel(dekor, '2800×2070×16 mm')} narxi`)
  const price18 = formatStep.getByLabel(`${rowLabel(dekor, '2800×2070×18 mm')} narxi`)
  await expect(price16).toBeVisible()
  await expect(price18).toBeVisible()
  await price16.fill('2400')
  await price18.fill('2600')
  await formatStep.getByRole('button', { name: /^2 ta o.lchamni qo.shish$/ }).click()

  // One dekor group, two o'lcham rows under it — not two dekor cards.
  const groupHeader = page.getByRole('button', { name: `${dekor.label} o'lchamlari` })
  await expect(groupHeader).toHaveCount(1)
  await expect(groupHeader).toContainText("2 o'lcham")
  await expect(page.getByRole('row').filter({ hasText: '2800×2070×16 mm' })).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: '2800×2070×18 mm' })).toHaveCount(1)

  // Two branch materials, one dekor: the server agrees with the screen.
  const carried = await branchMaterials(request, ownerAccess, branchId)
  expect(carried).toHaveLength(2)
  expect(new Set(carried.map((row) => row.dekor_id))).toEqual(new Set([dekor.id]))
  expect(carried.map((row) => Number(row.qalinlik_mm)).sort()).toEqual([16, 18])
})

test('owner attaches two dekorlar of different turlar in one pass', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const branchId = setup.branch.id as string
  // A board and its matching kromka — different o'lcham axes, one save. This is
  // the job the sheet exists for: many dekorlar, one o'lcham each, one pass.
  const { panel, edge } = await createCatalogDekorlar(request, adminAccess, id)

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()

  // Step 1 is multi-select, and a selection outlives the search that found it:
  // each dekor is reached by its own kod, and both stay ticked.
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  await tickDekor(pickStep, panel)
  await tickDekor(pickStep, edge)
  await expect(pickStep.getByText('2 ta tanlandi')).toBeVisible()
  await pickStep.getByRole('button', { name: 'Davom etish' }).click()

  // Step 2 gives each tur its own chip block: a tape has no sheet size and a
  // board has no tape width, so one shared set of chips could not serve both.
  const formatStep = page.getByRole('dialog', { name: "O'lchamlar va narx" })
  await expect(formatStep.getByRole('group', { name: 'Qalinlik' })).toHaveCount(2)
  await expect(formatStep.getByRole('group', { name: "List o'lchami" })).toHaveCount(1)
  await expect(formatStep.getByRole('group', { name: 'Lenta eni' })).toHaveCount(1)

  // The standard thickness sets are disjoint per tur (LDSP 10/16/18/25, kromka
  // 0.4/0.8/1/2), so an exact chip name lands in exactly one block. The size
  // axes are scoped to their own group, whose legend differs per tur.
  await formatStep.getByRole('button', { name: '18 mm', exact: true }).click()
  await formatStep
    .getByRole('group', { name: "List o'lchami" })
    .getByRole('button', { name: '2800×2070', exact: true })
    .click()
  await formatStep.getByRole('button', { name: '2 mm', exact: true }).click()
  await formatStep
    .getByRole('group', { name: 'Lenta eni' })
    .getByRole('button', { name: '19 mm', exact: true })
    .click()

  // One row per dekor, each named by its own dekor, and the submit count is the
  // whole batch rather than one dekor's share.
  await formatStep.getByLabel(`${rowLabel(panel, FORMAT_LABEL)} narxi`).fill('2500')
  await formatStep.getByLabel(`${rowLabel(edge, TAPE_LABEL)} narxi`).fill('700')
  await formatStep.getByRole('button', { name: /^2 ta o.lchamni qo.shish$/ }).click()

  // Both branch materials land, each under its own dekor group.
  await expect(page.getByRole('button', { name: `${panel.label} o'lchamlari` })).toBeVisible()
  await expect(page.getByRole('button', { name: `${edge.label} o'lchamlari` })).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: FORMAT_LABEL })).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: TAPE_LABEL })).toHaveCount(1)

  // The server agrees with the screen: one transaction, two dekorlar, two turlar.
  const carried = await branchMaterials(request, ownerAccess, branchId)
  expect(carried).toHaveLength(2)
  expect(new Set(carried.map((row) => row.dekor_id))).toEqual(new Set([panel.id, edge.id]))
  expect(new Set(carried.map((row) => row.dekor.tur))).toEqual(new Set(['ldsp', 'kromka']))
})

test('an unpriced format is flagged for the workshop and still offered to the client', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const branchId = setup.branch.id as string
  const dekor = await createCatalogDekor(request, adminAccess, id)

  // Same dekor, two formats: 18 mm priced, 16 mm registered with no price yet —
  // the routine case of a branch listing its formats before it knows the prices.
  const [priced, unpriced] = await carryDekor(request, ownerAccess, branchId, dekor.id, [
    { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 250_000, min_stock: 1 },
    { qalinlik_mm: '16', uzunlik_mm: 2800, eni_mm: 2070, min_stock: 1 },
  ])
  expect(priced.price_unset).toBe(false)
  expect(unpriced.price_unset).toBe(true)

  // Workshop side: the gap is visible exactly where it is fixable.
  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  const unpricedRow = page.getByRole('row').filter({ hasText: '2800×2070×16 mm' })
  await expect(unpricedRow.getByText("Narx yo'q")).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: '2800×2070×18 mm' }).getByText("Narx yo'q"),
  ).toHaveCount(0)

  // Client side: the same branch, the same dekor — BOTH formats. Hiding the
  // unpriced one showed clients a fraction of the shelf (one real branch carrying
  // 518 formats offered two); the money is guarded at order confirm instead.
  const clientLogin = await request.post('/api/v1/auth/client/otp/request', {
    data: { phone: phoneFor(id, 70) },
  })
  await expectOk(clientLogin)
  const verified = await request.post('/api/v1/auth/client/otp/verify', {
    data: { phone: phoneFor(id, 70), code: '000000', name: 'Price Client' },
  })
  await expectOk(verified)
  const clientAccess = (await verified.json()).access_token as string
  const options = await request.get(`/api/v1/client/catalog/materials?branch_id=${branchId}`, {
    headers: { Authorization: `Bearer ${clientAccess}` },
  })
  await expectOk(options)
  const ids = ((await options.json()) as Array<{ id: string }>).map((row) => row.id)
  expect(ids).toContain(priced.id)
  expect(ids).toContain(unpriced.id)

  const rows = (await options.json()) as Array<{ id: string; price_unset: boolean }>
  expect(rows.find((row) => row.id === unpriced.id)?.price_unset).toBe(true)
  expect(rows.find((row) => row.id === priced.id)?.price_unset).toBe(false)
})

test('the dekor picker folds Cyrillic and Latin onto the same dekor', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  await readyOwnerToken(request, setup)
  const manufacturerId = await createManufacturer(request, adminAccess, `Search Maker ${id}`)
  // Uzbek is written in both scripts and the Latin orthography has three
  // apostrophe shapes, so the same decor is typed four different ways. The
  // server folds both sides onto one key; nothing is filtered in the browser.
  const latin = await createDekor(request, adminAccess, {
    manufacturer_id: manufacturerId,
    tur: 'ldsp',
    kod: `SL-${id}`,
    nomi: "Yong'oq",
  })
  const cyrillic = await createDekor(request, adminAccess, {
    manufacturer_id: manufacturerId,
    tur: 'ldsp',
    kod: `SC-${id}`,
    nomi: 'Ёнғоқ',
  })

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  const search = pickStep.getByLabel('Qidirish')
  const option = (dekor: DekorResponse) =>
    pickStep.getByRole('checkbox', { name: new RegExp(escapeRegExp(dekor.label)) })

  // Cyrillic query finds the Latin-named dekor…
  await search.fill('ёнғоқ')
  await expect(option(latin)).toBeVisible()
  await expect(option(cyrillic)).toBeVisible()

  // …and the Latin query, apostrophe and all, finds the Cyrillic-named one.
  await search.fill("yong'oq")
  await expect(option(cyrillic)).toBeVisible()
  await expect(option(latin)).toBeVisible()

  // Down to the spelling the fold exists for: no apostrophe, `q` for `k`.
  await search.fill('yongok')
  await expect(option(cyrillic)).toBeVisible()
  await expect(option(latin)).toBeVisible()

  // A query that folds to something else finds neither — the fold widens the
  // match, it does not stop filtering.
  await search.fill(`zzz-${id}`)
  await expect(pickStep.getByText('Dekor topilmadi')).toBeVisible()
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
  const imageFileId = await uploadImage(request, adminAccess, 'material.png')
  const dekor = await createCatalogDekor(request, adminAccess, id, imageFileId)
  const branchId = setup.branch.id as string
  const staffLogin = `inv-${id}`
  await carryDekor(request, ownerAccess, branchId, dekor.id, [
    { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 250_000, min_stock: 1 },
  ])
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
  await expectOk(staff)

  await loginWorkshop(page, staffLogin, 'StaffTemp123')
  await changeRequiredPassword(page, 'StaffTemp123', staffReadyPassword)
  await page.goto(`/workshop/branches/${branchId}`)
  await expect(page).toHaveURL(/\/workshop\/?$/)

  await expect(page.getByRole('link', { name: 'Filiallar' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: "Xodimlar ro'yxati" })).toHaveCount(0)
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
  const imageFileId = await uploadImage(request, adminAccess, 'client-material.png')
  const dekor = await createCatalogDekor(request, adminAccess, id, imageFileId)
  const branchId = setup.branch.id as string
  const [material] = await carryDekor(request, ownerAccess, branchId, dekor.id, [
    { qalinlik_mm: '18', uzunlik_mm: 2800, eni_mm: 2070, price_tiyin: 250_000, min_stock: 1 },
  ])

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
  // removed): neither the catalog (material label / price) nor any internal
  // stock/supplier detail surfaces — materials are browsed in the cutting editor.
  await expect(branchCard.getByText(material.label)).toHaveCount(0)
  await expect(branchCard.getByText(dekor.label)).toHaveCount(0)
  await expect(branchCard.getByText(/UZS\s*2[, ]500/)).toHaveCount(0)
  await expect(page.getByText('low stock')).toHaveCount(0)
  await expect(page.getByText(/Supplier/)).toHaveCount(0)
})

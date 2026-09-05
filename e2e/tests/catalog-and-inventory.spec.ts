import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

import {
  carryFormats,
  createCatalogDecors,
  createDecor,
  createDecorFormat,
  createManufacturer,
  clientTokenViaApi,
  databaseUrl,
  escapeRegExp,
  tickDecor,
  expectOk,
  loginClient,
  type BranchMaterialResponse,
  type DecorResponse,
  type DecorFormatResponse,
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
  return createDecor(request, token, {
    manufacturer_id: manufacturerId,
    code: `P3-${id}`,
    name: 'White',
    has_grain: true,
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
  // Wait for the session to land before returning. A `page.goto` to a deep
  // admin link fired mid-login reloads the SPA with no token yet stored, and
  // the route guard bounces it straight back to this form.
  await expect(page.getByRole('heading', { name: 'Admin paneliga kirish' })).toHaveCount(0)
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
 * The pricing table names every row by its decor as well as its format, because
 * one batch can span decors — so a price/threshold field is addressed by both.
 */
/** The 2800×2070 sheet this spec's fixtures are built on. */
function catalogFormat(overrides: Record<string, unknown> = {}) {
  return {
    type: 'ldsp',
    thickness_mm: '18',
    length_mm: 2800,
    width_mm: 2070,
    finished_sides: 2,
    ...overrides,
  }
}

function rowLabel(decor: DecorResponse, format: string) {
  return `${decor.label} · ${format}`
}

/**
 * The dimension tail of a format label — what a row under a decor group prints,
 * since the group heading already carries the identity.
 */
function formatDims(label: string) {
  return label.split(' · ').at(-1) as string
}

/**
 * Drive the two-step attach sheet for a single decor: tick it, continue, then
 * tick the PLATFORM formats to carry.
 *
 * Step two lists what the platform has entered — the branch cannot invent a
 * format any more, so there are no thickness/size chips to click and no
 * "+ qo'shish".
 */
async function attachThroughSheet(
  page: Page,
  decor: DecorResponse,
  formats: DecorFormatResponse[],
) {
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  await tickDecor(pickStep, decor)
  await pickStep.getByRole('button', { name: 'Davom etish' }).click()

  const formatStep = page.getByRole('dialog', { name: "O'lchamlar va narx" })
  for (const format of formats) {
    await formatStep.getByRole('checkbox', { name: format.label }).check()
  }
  return formatStep
}

/**
 * The reshape's central move, end to end: only the PLATFORM creates a format,
 * and a branch can then carry it. If the admin form and the attach sheet ever
 * disagree about what a format is, this is the test that notices.
 */
test('admin adds a format and the branch can then carry it', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-fmt-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  // A decor with NO format yet — the branch has nothing it could attach.
  const dekor = await createCatalogDekor(request, adminAccess, id)

  await loginAdmin(page, adminLogin)
  await page.goto(`/admin/catalog/decors/${dekor.id}`)
  await expect(page.getByRole('heading', { name: 'Formatlar' })).toBeVisible()
  // The decor form itself never asks for a substrate — that lives on the format.
  await expect(page.getByText("Bu dekorda hali format yo'q.", { exact: false })).toBeVisible()

  await page.getByRole('button', { name: '+ Format' }).click()
  const formatDialog = page.getByRole('dialog', { name: 'Yangi format qo\'shish' })
  await formatDialog.getByLabel('Qalinlik (mm)').fill('18')
  // The standard chips are quick-fill for the PLATFORM form now — they stopped
  // being the branch's attach suggestions.
  await formatDialog.getByRole('button', { name: '2800×2070', exact: true }).click()
  await formatDialog.getByRole('button', { name: "Qo'shish", exact: true }).click()
  await expect(formatDialog).toBeHidden()

  // The new row is listed, two-sided by default, and active.
  const formatRow = page.getByRole('row', { name: /2800×2070/ })
  await expect(formatRow).toBeVisible()
  await expect(formatRow).toContainText('2 tomonlama')

  // ...and the branch can now carry exactly that format.
  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  await tickDecor(pickStep, dekor)
  await pickStep.getByRole('button', { name: 'Davom etish' }).click()

  const formatStep = page.getByRole('dialog', { name: "O'lchamlar va narx" })
  // Step two lists the platform's formats and nothing else: no chips, no
  // "+ qo'shish", and the note that says who adds a missing size.
  await expect(formatStep.getByText('Platformaga xabar bering', { exact: false })).toBeVisible()
  await formatStep.getByRole('checkbox', { name: /2800×2070×18 mm/ }).check()
  await formatStep.getByRole('button', { name: /qo.shish$/ }).click()
  await expect(formatStep).toBeHidden()

  const carried = await branchMaterials(request, ownerAccess, setup.branch.id as string)
  expect(carried.map((row) => row.decor_format.decor_id)).toEqual([dekor.id])
})

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
  // No substrate prefix any more: `type` moved to the format, so the decor card
  // is maker + code + name and nothing else.
  await expect(dekorDialog.getByText(`${makerName} UI-${id} · White`).first()).toBeVisible()
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
  // The PLATFORM enters the format; the branch only decides to carry it.
  const format = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await expect(page.getByRole('heading', { name: 'Material katalogi' })).toBeVisible()

  // The trigger appears in the filter bar and, while the list is empty, again as
  // the empty-state CTA — target the always-present header action.
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()
  // The reshape made attaching two steps: a dekor is identity, a format is the
  // branch's own fact, so step 1 picks the dekor and step 2 the formats + price.
  const formatStep = await attachThroughSheet(page, dekor, [format])
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
  // The row does NOT vanish under the cursor: the toggle updates the loaded row
  // in place rather than refetching, so the operator can still see (and undo)
  // what they just did. The Holat filter only reapplies on the next load.
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'false')

  // The page opens on «Faol», so after a reload a deactivated o'lcham is out of
  // scope — that is the state the switch was just moved to, not a lost row.
  await page.reload()
  await expect(formatRow).toHaveCount(0)

  // «Faol emas» is the way back to it, and it is one visible click away — the
  // reason the Holat filter is a segmented control rather than a dropdown.
  await page.getByRole('radio', { name: 'Faol emas' }).click()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'false')

  // Restore visibility so the client-facing flows keep seeing the material.
  await materialSwitch().click()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('radio', { name: 'Faol', exact: true }).click()
  await expect(materialSwitch()).toHaveAttribute('aria-checked', 'true')

  await page.goto('/workshop/inventory')
  await expect(page.getByRole('heading', { name: 'Ombor', exact: true })).toBeVisible()
  // An arrival is one supplier invoice with a line per material (QAD-149), and
  // it is entered on a page of its own — «+ Kirim» is a link, not a dialog
  // opener. It lives on the Kirimlar tab: the Zaxira tab carries no page-level
  // actions, because both stock operations belong to a material.
  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  await page.getByRole('link', { name: '+ Kirim', exact: true }).click()
  await expect(page).toHaveURL(/\/workshop\/inventory\/invoices\/new$/)
  await page.getByRole('combobox', { name: /Ta.minotchi/ }).click()
  await page.getByRole('option', { name: "Yangi ta'minotchi" }).click()
  await page.getByLabel("Yangi ta'minotchi nomi").fill(`Supplier ${id}`)
  await page.getByRole('combobox', { name: 'Material' }).fill(material.label)
  await page.getByRole('option', { name: new RegExp(escapeRegExp(material.label)) }).click()
  await page.getByRole('textbox', { name: /^Miqdor/ }).fill('3')
  // First-ever stock-in: no price history, so the field is empty with the hint.
  await expect(page.getByText('Birinchi kirim', { exact: false })).toBeVisible()
  await page.getByRole('textbox', { name: /^Narx/ }).fill('2000')
  // One footer number: with the document-level skidka gone there is no ladder.
  await expect(page.getByText('Oraliq jami')).toHaveCount(0)
  await expect(page.getByText('Jami', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await expect(page.getByText(/Kirim K-\d{4} yozildi\./)).toBeVisible()
  // Saving lands on the new document's own page.
  await expect(page.getByRole('heading', { name: /^Kirim K-\d{4}/ })).toBeVisible()

  await page.goto('/workshop/inventory')
  // Ordering is load-bearing: the Zaxira tab defaults to the moved scope, so the
  // row is on screen *because* the arrival just moved it. The same assertion
  // before the Kirim would find the «Omborda hali harakat yo'q» empty state.
  const stockTable = page.getByRole('table').filter({
    has: page.getByRole('columnheader', { name: 'Mavjud' }),
  })
  await expect(
    stockTable.getByRole('row', { name: new RegExp(`${escapeRegExp(material.label)}.*3 list`) }),
  ).toBeVisible()

  // A second arrival: the last price paid prefills the line with provenance.
  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  await page.getByRole('link', { name: '+ Kirim', exact: true }).click()
  await page.getByRole('combobox', { name: 'Material' }).fill(material.label)
  await page.getByRole('option', { name: new RegExp(escapeRegExp(material.label)) }).click()
  await expect(page.getByRole('textbox', { name: /^Narx/ })).toHaveValue('2000')
  await expect(page.getByText('Oxirgi narx', { exact: false })).toBeVisible()
  await expect(page.getByText(`Supplier ${id}`, { exact: false })).toBeVisible()
  // «Bekor» is the deliberate exit, so it leaves without the unsaved-changes guard.
  await page.getByRole('button', { name: 'Bekor', exact: true }).click()

  // A write-off starts at the material it was noticed on: the row links to the
  // material's page, and the correction is booked there with nothing to re-pick.
  await page.goto('/workshop/inventory')
  // Two filters, not the composed label: Zaxira splits it across Tur / Dekor /
  // O'lcham cells, so no single cell holds the whole string. The link keeps its
  // accessible name, which is still the composed label.
  await stockTable
    .getByRole('row')
    .filter({ hasText: dekor.label })
    .filter({ hasText: FORMAT_LABEL })
    .getByRole('link', { name: new RegExp(`${escapeRegExp(material.label)}.*batafsil`) })
    .click()
  await expect(page).toHaveURL(new RegExp(`inventory/materials/${material.id}`))
  await page.getByRole('button', { name: 'Tuzatish', exact: true }).click()
  const adjustment = page.getByRole('dialog', { name: 'Tuzatish' })
  // The adjust quantity is a signed value with a required +/− prefix.
  await adjustment.getByLabel(/Tuzatish miqdori/).fill('-1')
  await adjustment.getByLabel('Izoh').fill('E2E stock take')
  await adjustment.getByRole('button', { name: 'Saqlash' }).click()
  await expect(page.getByText('Ombor tuzatishi yozildi.')).toBeVisible()
  await page.getByRole('link', { name: 'Zaxiraga qaytish' }).click()
  await expect(stockTable.getByText('Kam qolgan', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Tranzaksiyalar' }).click()
  await expect(page.getByRole('cell', { name: `Supplier ${id}` })).toBeVisible()

  // The arrival is readable as a document and correctable as one: the row links
  // to its detail page, the lines are editable there, and a document that
  // should never have existed is voided — which reverses the stock it moved.
  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  const invoiceRow = page
    .getByRole('row')
    .filter({ has: page.getByRole('cell', { name: `Supplier ${id}` }) })
  await expect(invoiceRow).toContainText('1 pozitsiya')
  await expect(invoiceRow.getByText("To'lanmagan")).toBeVisible()
  await invoiceRow.getByRole('link', { name: /fakturasini ochish/ }).click()
  await expect(page).toHaveURL(/\/workshop\/inventory\/invoices\/[0-9a-f-]{36}$/)
  // `exact` matters: the totals row carries the same amount, so a loose match
  // on the material label would hit more than the line cell.
  await expect(page.getByRole('cell', { name: material.label, exact: true })).toBeVisible()

  // Editing a line quantity moves the balance by exactly the difference, and
  // the replay keeps the later write-off's balance-after honest.
  await page.getByRole('link', { name: 'Tahrirlash' }).click()
  await expect(page).toHaveURL(/\/edit$/)
  await page.getByRole('textbox', { name: /^Miqdor/ }).fill('5')
  await page.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await expect(page.getByText(/Faktura K-\d{4} yangilandi\./)).toBeVisible()
  await expect(page.getByRole('cell', { name: '5 list' })).toBeVisible()

  await page.goto('/workshop/inventory')
  // 5 arrived, 1 written off.
  await expect(
    stockTable.getByRole('row', { name: new RegExp(`${escapeRegExp(material.label)}.*4 list`) }),
  ).toBeVisible()

  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  await invoiceRow.getByRole('link', { name: /fakturasini ochish/ }).click()
  // The destructive action lives in the overflow, away from the everyday two.
  await page.getByRole('button', { name: /qo.shimcha amallar/ }).click()
  await page.getByRole('menuitem', { name: 'Bekor qilish' }).click()
  const voidDialog = page.getByRole('dialog', { name: 'Fakturani bekor qilish' })
  await voidDialog.getByLabel('Bekor qilish sababi').fill('E2E: narx xato kiritilgan')
  // The confirm names its consequence rather than echoing the dialog's own
  // «Bekor qilish» cancel, which sits right beside it.
  await voidDialog.getByRole('button', { name: 'Fakturani bekor qilish', exact: true }).click()
  await expect(page.getByText(/Faktura K-\d{4} bekor qilindi\./)).toBeVisible()
  await expect(page.getByText('Bu faktura bekor qilingan')).toBeVisible()

  await page.goto('/workshop/inventory?tab=invoices')
  await expect(invoiceRow.getByText('Bekor qilingan')).toBeVisible()

  // The reversal took the 5 panels back out; the −1 write-off stays, so the
  // branch is honestly at −1 rather than at a clamped zero (QAD-150).
  await page.getByRole('tab', { name: 'Zaxira' }).click()
  await expect(
    stockTable.getByRole('row', { name: new RegExp(`${escapeRegExp(material.label)}.*-1 list`) }),
  ).toBeVisible()
})

test('a first arrival puts a material on the shelf and its detail page carries the story', async ({
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
  // `min_stock: 0` is monitoring OFF — this row is never low at any balance
  // until the threshold is set from the detail modal at the end of the journey.
  const format = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())
  const [material] = await carryFormats(request, ownerAccess, branchId, [
    { decor_format_id: format.id, price_tiyin: 250_000, min_stock: 0 },
  ])

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/inventory')
  await expect(page.getByRole('heading', { name: 'Ombor', exact: true })).toBeVisible()
  const stockTable = page.getByRole('table').filter({
    has: page.getByRole('columnheader', { name: 'Mavjud' }),
  })
  // The row no longer carries the composed `LDSP … · … · 2800×2070×18 mm` label
  // in one cell — Zaxira splits it into Tur / Dekor / O'lcham columns — so the
  // row is pinned by the two halves that identify it rather than by the string
  // the API happens to compose.
  const materialRow = stockTable
    .getByRole('row')
    .filter({ hasText: dekor.label })
    .filter({ hasText: FORMAT_LABEL })

  // The tab shows the warehouse, not the catalog: a material nobody has moved
  // anything into is not a stock row yet, and the empty state says which
  // emptiness this is.
  await expect(page.getByRole('heading', { name: "Omborda hali harakat yo'q" })).toBeVisible()
  await expect(materialRow).toHaveCount(0)

  // «Butun katalog» is how the operator reaches it — which is where a first
  // arrival starts.
  const wholeCatalog = page.getByRole('button', { name: 'Butun katalog' })
  await wholeCatalog.click()
  await expect(materialRow).toContainText('0 list')

  // Both stock operations live on the material, so the first arrival is started
  // from the material's own page — the tab itself carries no page-level pair.
  const openDetail = () =>
    materialRow
      .getByRole('link', { name: new RegExp(`${escapeRegExp(material.label)}.*batafsil`) })
      .click()
  await openDetail()
  await page.getByRole('button', { name: 'Kirim yozish' }).click()
  // Opened from the material, the arrival page seeds line 1 with it: the
  // resolved label, not a picker to search the catalog all over again.
  await expect(page).toHaveURL(new RegExp(`invoices/new\\?material=${material.id}`))
  await expect(page.getByRole('button', { name: material.label })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Material' })).toHaveCount(0)
  await page.getByRole('combobox', { name: /Ta.minotchi/ }).click()
  await page.getByRole('option', { name: "Yangi ta'minotchi" }).click()
  await page.getByLabel("Yangi ta'minotchi nomi").fill(`Supplier ${id}`)
  await page.getByRole('textbox', { name: /^Miqdor/ }).fill('4')
  await page.getByRole('textbox', { name: /^Narx/ }).fill('3000')
  await page.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await expect(page.getByText(/Kirim K-\d{4} yozildi\./)).toBeVisible()

  // One movement is exactly what makes a row warehouse: back on the tab, whose
  // default scope is the moved one, the row stands on its own.
  await page.goto('/workshop/inventory')
  await expect(wholeCatalog).toHaveAttribute('aria-pressed', 'false')
  await expect(materialRow).toContainText('4 list')

  // The name is the row's control, and the page it opens has its own URL.
  await openDetail()
  await expect(page).toHaveURL(new RegExp(`inventory/materials/${material.id}`))

  // The story of the balance, told in tabs — one question at a time, each tab
  // carrying its own count so the reader knows where the rows are.
  await expect(page.getByRole('tab', { name: 'Kirimlar (1)' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  const arrivals = page.getByRole('tabpanel')
  const arrival = arrivals.getByRole('row').filter({ hasText: `Supplier ${id}` })
  await expect(arrival).toContainText('+4 list')
  await expect(arrival.getByRole('link', { name: /K-\d{4}/ })).toBeVisible()
  await expect(arrival).toContainText(/3[\s,]000 so'm/)

  // The figures row has no landmark of its own, so the on-hand block is reached
  // by the label that names it.
  const onHand = page.locator('.fig').filter({ hasText: 'Mavjud' })
  await expect(onHand).toContainText('4 list')

  // A stock-take correction, booked from the page it was noticed on.
  await page.getByRole('button', { name: 'Tuzatish', exact: true }).click()
  const adjustment = page.getByRole('dialog', { name: 'Tuzatish' })
  // Pre-picked: the material is settled, so there is nothing left to choose.
  await expect(adjustment.getByRole('combobox', { name: 'Material' })).toHaveCount(0)
  // Opened from the material's own page there is nothing to re-pick, so the
  // label is plain text rather than the button the list's picker renders.
  await expect(adjustment.getByText(material.label)).toBeVisible()
  await adjustment.getByLabel(/Tuzatish miqdori/).fill('-1')
  await adjustment.getByLabel('Izoh').fill('E2E stock take')
  await adjustment.getByRole('button', { name: 'Saqlash' }).click()
  await expect(page.getByText('Ombor tuzatishi yozildi.')).toBeVisible()
  // The correction lands in the Tuzatishlar tab — and the page switches to it,
  // so the row that explains the new balance is the one on screen.
  await expect(onHand).toContainText('3 list')
  await expect(page.getByRole('tab', { name: 'Tuzatishlar (1)' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(
    page.getByRole('tabpanel').getByRole('row').filter({ hasText: 'E2E stock take' }),
  ).toContainText('-1 list')

  // The threshold is warehouse policy, decided in front of the shelf: 3 sheets
  // against a threshold of 5 is low the moment it is saved.
  await page.getByRole('button', { name: "Kam qoldiq chegarasini o'zgartirish" }).click()
  await page.getByRole('textbox', { name: /Kam qoldiq chegarasi/ }).fill('5')
  await page.getByRole('button', { name: 'Saqlash', exact: true }).click()
  await expect(page.getByText('Kam qoldiq chegarasi yangilandi.')).toBeVisible()
  await expect(page.getByText('Kam', { exact: true })).toBeVisible()

  // And the list the page was opened from re-derives the same way.
  await page.getByRole('link', { name: 'Zaxiraga qaytish' }).click()
  await expect(materialRow).toContainText('3 list')
  await expect(materialRow).toContainText('Kam qolgan')
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
  const f18 = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())
  const f16 = await createDecorFormat(
    request,
    adminAccess,
    dekor.id,
    catalogFormat({ thickness_mm: '16' }),
  )

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()

  // Two formats of one decor, ticked together: one attach is one transaction.
  const formatStep = await attachThroughSheet(page, dekor, [f16, f18])
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
  expect(new Set(carried.map((row) => row.decor_format.decor_id))).toEqual(new Set([dekor.id]))
  expect(carried.map((row) => Number(row.decor_format.thickness_mm)).sort()).toEqual([16, 18])
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
  const { panel, edge } = await createCatalogDecors(request, adminAccess, id)

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()

  // Step 1 is multi-select, and a selection outlives the search that found it:
  // each dekor is reached by its own kod, and both stay ticked.
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  await tickDecor(pickStep, panel)
  await tickDecor(pickStep, edge)
  await expect(pickStep.getByText('2 ta tanlandi')).toBeVisible()
  await pickStep.getByRole('button', { name: 'Davom etish' }).click()

  // Step 2 lists what the PLATFORM entered, grouped by decor. There are no
  // thickness/size chips any more — a branch cannot invent a format — so the
  // board and the tape are simply two rows under two decor headings.
  const formatStep = page.getByRole('dialog', { name: "O'lchamlar va narx" })
  await formatStep.getByRole('checkbox', { name: panel.format.label }).check()
  await formatStep.getByRole('checkbox', { name: edge.format.label }).check()

  // One priced row per format, each named by its own decor, and the submit
  // count is the whole batch rather than one decor's share.
  await formatStep.getByLabel(`${rowLabel(panel, panel.format.label)} narxi`).fill('2500')
  await formatStep.getByLabel(`${rowLabel(edge, edge.format.label)} narxi`).fill('700')
  await formatStep.getByRole('button', { name: /^2 ta o.lchamni qo.shish$/ }).click()

  // Both branch materials land, each under its own dekor group.
  await expect(page.getByRole('button', { name: `${panel.label} o'lchamlari` })).toBeVisible()
  await expect(page.getByRole('button', { name: `${edge.label} o'lchamlari` })).toBeVisible()
  await expect(
    page.getByRole('row').filter({ hasText: formatDims(panel.format.label) }),
  ).toHaveCount(1)
  await expect(
    page.getByRole('row').filter({ hasText: formatDims(edge.format.label) }),
  ).toHaveCount(1)

  // The server agrees with the screen: one transaction, two dekorlar, two turlar.
  const carried = await branchMaterials(request, ownerAccess, branchId)
  expect(carried).toHaveLength(2)
  expect(new Set(carried.map((row) => row.decor_format.decor_id))).toEqual(new Set([panel.id, edge.id]))
  expect(new Set(carried.map((row) => row.decor_format.type))).toEqual(new Set(['ldsp', 'kromka']))
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
  const f18 = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())
  const f16 = await createDecorFormat(
    request,
    adminAccess,
    dekor.id,
    catalogFormat({ thickness_mm: '16' }),
  )
  const [priced, unpriced] = await carryFormats(request, ownerAccess, branchId, [
    { decor_format_id: f18.id, price_tiyin: 250_000, min_stock: 1 },
    { decor_format_id: f16.id, min_stock: 1 },
  ])
  expect(priced.price_unset).toBe(false)
  expect(unpriced.price_unset).toBe(true)

  // Workshop side: the gap is visible exactly where it is fixable.
  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  const unpricedRow = page.getByRole('row').filter({ hasText: '2800×2070×16 mm' })
  // The pill lives in the Narx column, and once more inside the o'lcham cell for
  // the phone layout where that column is gone — so the row holds two copies of
  // it in markup and exactly one of them is ever rendered. Filter to the visible
  // one rather than asserting a count that depends on the viewport.
  const unpricedPill = unpricedRow.getByText("Narx yo'q").filter({ visible: true })
  await expect(unpricedPill).toHaveCount(1)
  await expect(
    page
      .getByRole('row')
      .filter({ hasText: '2800×2070×18 mm' })
      .getByText("Narx yo'q")
      .filter({ visible: true }),
  ).toHaveCount(0)

  // And it survives the fold. Collapsing a dekor takes its rows — and their
  // pills — off screen, on the one surface that can price them, so the count
  // rides on the heading instead.
  const groupHeading = page.getByRole('button', { name: `${dekor.label} o'lchamlari` })
  await groupHeading.click()
  await expect(unpricedRow).toHaveCount(0)
  await expect(groupHeading).toContainText('1 ta narxsiz')
  await groupHeading.click()
  await expect(unpricedRow).toHaveCount(1)

  // Client side: the same branch, the same dekor — BOTH formats. Hiding the
  // unpriced one showed clients a fraction of the shelf (one real branch carrying
  // 518 formats offered two); the money is guarded at order confirm instead.
  const clientAccess = await clientTokenViaApi(request, phoneFor(id, 70), 'Price Client')
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

test('the catalog filters by carried manufacturer and searches the o\'lcham numbers', async ({
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

  // Three manufacturers on the platform; the branch carries two of them. Two,
  // not one, because a dropdown offering «Barcha» plus a single brand cannot
  // narrow anything — the page hides it until there is a choice to make.
  const firstMaker = await createManufacturer(request, adminAccess, `Carried Maker ${id}`)
  const secondMaker = await createManufacturer(request, adminAccess, `Second Maker ${id}`)
  const offeredMaker = await createManufacturer(request, adminAccess, `Offered Maker ${id}`)
  const firstDekor = await createDecor(request, adminAccess, {
    manufacturer_id: firstMaker,
    code: `MF-C-${id}`,
    name: 'Kulrang',
  })
  const secondDekor = await createDecor(request, adminAccess, {
    manufacturer_id: secondMaker,
    code: `MF-S-${id}`,
    name: 'Oq',
  })
  const offeredDekor = await createDecor(request, adminAccess, {
    manufacturer_id: offeredMaker,
    code: `MF-O-${id}`,
    name: 'Qora',
  })
  await createDecorFormat(request, adminAccess, offeredDekor.id, catalogFormat())
  const f18 = await createDecorFormat(request, adminAccess, firstDekor.id, catalogFormat())
  const f16 = await createDecorFormat(
    request,
    adminAccess,
    firstDekor.id,
    catalogFormat({ thickness_mm: '16', length_mm: 2750, width_mm: 1830 }),
  )
  const fOther = await createDecorFormat(
    request,
    adminAccess,
    secondDekor.id,
    catalogFormat({ thickness_mm: '25', length_mm: 2620, width_mm: 2070 }),
  )
  await carryFormats(request, ownerAccess, branchId, [
    { decor_format_id: f18.id, price_tiyin: 250_000, min_stock: 1 },
    { decor_format_id: f16.id, price_tiyin: 240_000, min_stock: 1 },
    { decor_format_id: fOther.id, price_tiyin: 260_000, min_stock: 1 },
  ])

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  const row18 = page.getByRole('row').filter({ hasText: '2800×2070×18 mm' })
  const row16 = page.getByRole('row').filter({ hasText: '2750×1830×16 mm' })
  await expect(row18).toHaveCount(1)
  await expect(row16).toHaveCount(1)

  // The dropdown offers what the branch CARRIES, not the platform's whole offer:
  // «Offered Maker» matches no row here, so listing it would be a dead option.
  const manufacturer = page.getByRole('button', { name: /Barcha ishlab chiqaruvchilar/ })
  await manufacturer.click()
  await expect(page.getByRole('option', { name: `Carried Maker ${id}` })).toBeVisible()
  await expect(page.getByRole('option', { name: `Offered Maker ${id}` })).toHaveCount(0)
  await expect(page.getByRole('option', { name: `Second Maker ${id}` })).toBeVisible()
  await page.getByRole('option', { name: `Carried Maker ${id}` }).click()
  await expect(row18).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: '2620×2070×25 mm' })).toHaveCount(0)

  // The search box reaches the numbers the row prints — thickness and panel
  // dimensions live on the format, which `search_key` (a dekor fact) cannot see.
  const search = page.getByRole('textbox', { name: 'Qidirish' })
  await search.fill('16')
  await expect(row16).toHaveCount(1)
  await expect(row18).toHaveCount(0)

  // Matched by value, not as a substring: 1830 is a width of its own row and 18
  // is not part of it.
  await search.fill('1830')
  await expect(row16).toHaveCount(1)
  await expect(row18).toHaveCount(0)

  await search.fill('2800')
  await expect(row18).toHaveCount(1)
  await expect(row16).toHaveCount(0)
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
  const latin = await createDecor(request, adminAccess, {
    manufacturer_id: manufacturerId,
    code: `SL-${id}`,
    name: "Yong'oq",
  })
  await createDecorFormat(request, adminAccess, latin.id, catalogFormat())
  const cyrillic = await createDecor(request, adminAccess, {
    manufacturer_id: manufacturerId,
    code: `SC-${id}`,
    name: 'Ёнғоқ',
  })
  await createDecorFormat(request, adminAccess, cyrillic.id, catalogFormat())

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/catalog')
  await page.getByRole('button', { name: '+ Material', exact: true }).first().click()
  const pickStep = page.getByRole('dialog', { name: 'Dekor tanlash' })
  const search = pickStep.getByLabel('Qidirish')
  const option = (dekor: DecorResponse) =>
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
  const format = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())
  await carryFormats(request, ownerAccess, branchId, [
    { decor_format_id: format.id, price_tiyin: 250_000, min_stock: 1 },
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
  await page.getByRole('tab', { name: 'Kirimlar' }).click()
  await expect(page.getByRole('link', { name: '+ Kirim', exact: true })).toBeVisible()
})

test('client browses Ustaxonalarim without prices or stock details', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p3-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const imageFileId = await uploadImage(request, adminAccess, 'client-material.png')
  const dekor = await createCatalogDekor(request, adminAccess, id, imageFileId)
  const branchId = setup.branch.id as string
  const format = await createDecorFormat(request, adminAccess, dekor.id, catalogFormat())
  const [material] = await carryFormats(request, ownerAccess, branchId, [
    { decor_format_id: format.id, price_tiyin: 250_000, min_stock: 1 },
  ])

  await loginClient(page, phoneFor(id, 60), 'Catalog Client')

  // The public directory is gone — Ustaxonalarim lists only entered workshops,
  // so the client arrives through the workshop link first. Signed in, the entry
  // applies itself and lands on home (no tap: the URL already names the branch).
  const ownerHeaders = { Authorization: `Bearer ${ownerAccess}` }
  const settingsResponse = await request.get('/api/v1/workshop/settings', {
    headers: ownerHeaders,
  })
  expect(settingsResponse.ok()).toBeTruthy()
  const { public_code } = (await settingsResponse.json()) as { public_code: string }
  const branchResponse = await request.get(`/api/v1/workshop/branches/${branchId}`, {
    headers: ownerHeaders,
  })
  expect(branchResponse.ok()).toBeTruthy()
  const { branch_no } = (await branchResponse.json()) as { branch_no: number }
  await page.goto(`/client/w/${public_code}/${branch_no}`)
  await expect(page).toHaveURL(/\/client\/c\/?$/)

  // The desktop nav item and the phone tab share one live target: with exactly
  // one related workshop there is nothing to choose, so it opens that
  // workshop's profile; two or more and it opens Ustaxonalarim. This client
  // entered one workshop, so following the item lands on the profile.
  await page.getByRole('link', { name: 'Ustaxonalar' }).first().click()
  await expect(page).toHaveURL(/\/client\/c\/workshops\/[0-9a-f-]+$/)
  await expect(
    page.getByRole('heading', { name: new RegExp(`Catalog Workshop ${id}`) }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Filiallar' })).toBeVisible()
  // The profile is pickup and contact information too: the branch row's only
  // door to prices is «Katalog», and the page previews none of it.
  await expect(page.getByRole('link', { name: 'Katalog' }).first()).toBeVisible()
  await expect(page.getByText(material.label)).toHaveCount(0)
  await expect(page.getByText(dekor.label)).toHaveCount(0)
  await expect(page.getByText(/UZS\s*2[, ]500/)).toHaveCount(0)

  // Ustaxonalarim itself — the target the same item takes once a client has
  // more than one workshop — renders the same rows inside a card per workshop.
  await page.goto('/client/c/branches')
  await expect(page.getByRole('heading', { name: /Ustaxonalar/ })).toBeVisible()
  // The card is a <section> (the branch rows are a list inside it, so the head
  // is a link and the card is not).
  const workshopCard = page.locator('section.client-card').filter({
    has: page.getByRole('heading', { name: new RegExp(`Catalog Workshop ${id}`) }),
  })
  await expect(workshopCard).toBeVisible()
  // Ustaxonalarim is pickup and contact information: the branch row carries the
  // pin star and the two actions, and no price or material of its own. The
  // client's read-only price list lives one tap away behind «Katalog» (spec
  // §6.2) — this page never previews it, and nothing internal (stock levels,
  // suppliers) is reachable from the client app at all.
  await expect(workshopCard.getByRole('link', { name: 'Katalog' }).first()).toBeVisible()
  await expect(workshopCard.getByText(material.label)).toHaveCount(0)
  await expect(workshopCard.getByText(dekor.label)).toHaveCount(0)
  await expect(workshopCard.getByText(/UZS\s*2[, ]500/)).toHaveCount(0)
  await expect(page.getByText('low stock')).toHaveCount(0)
  await expect(page.getByText(/Supplier/)).toHaveCount(0)
})

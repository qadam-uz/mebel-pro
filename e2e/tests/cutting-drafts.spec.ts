import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { expectOk, expectPdfOpensInTab } from './helpers'

const execFileAsync = promisify(execFile)
const databaseUrl = 'postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e'
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const passwordLabel = /^(Password|Parol)$/
const continueButton = /^(Continue|Kirish)$/

interface MaterialResponse {
  id: string
  name: string
}

interface TokenResponse {
  access_token: string
  me: {
    principal_id: string
  }
}

interface CuttingDraftResponse {
  id: string
  chosen_result_id: string | null
}

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
        name: `Cutting Workshop ${id}`,
      },
      branch: {
        name: `Cutting Branch ${id}`,
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

async function createCatalogMaterials(request: APIRequestContext, token: string, id: string) {
  const manufacturer = await request.post('/api/v1/platform/catalog/manufacturers', {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `Cutting Maker ${id}`, country: 'UZ' },
  })
  await expectOk(manufacturer)
  const manufacturerId = (await manufacturer.json()).id as string

  const panel = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'panel',
      manufacturer_id: manufacturerId,
      type: 'dsp',
      thickness_mm: '18',
      color: 'White',
      decor_code: `P4-P-${id}`,
      panel_length_mm: 900,
      panel_width_mm: 600,
      grain_direction: false,
    },
  })
  await expectOk(panel)

  const edge = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'edge',
      manufacturer_id: manufacturerId,
      thickness_mm: '2',
      edge_width_mm: 19,
      color: 'White',
      decor_code: `P4-E-${id}`,
    },
  })
  await expectOk(edge)

  return {
    panel: (await panel.json()) as MaterialResponse,
    edge: (await edge.json()) as MaterialResponse,
  }
}

async function addBranchMaterial(
  request: APIRequestContext,
  token: string,
  branchId: string,
  materialId: string,
) {
  const response = await request.post(`/api/v1/workshop/branches/${branchId}/materials`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { material_id: materialId, price_tiyin: 250000, min_stock: 1 },
  })
  await expectOk(response)
}

async function clientToken(request: APIRequestContext, phone: string, name: string) {
  const requested = await request.post('/api/v1/auth/client/otp/request', { data: { phone } })
  await expectOk(requested)
  const verified = await request.post('/api/v1/auth/client/otp/verify', {
    data: { phone, code: '000000', name },
  })
  await expectOk(verified)
  return (await verified.json()) as TokenResponse
}

async function optimizedClientDraft(
  request: APIRequestContext,
  token: string,
  branchId: string,
  panel: MaterialResponse,
  edge: MaterialResponse,
) {
  const created = await request.post('/api/v1/client/cutting-drafts', {
    headers: { Authorization: `Bearer ${token}` },
  })
  await expectOk(created)
  const draft = (await created.json()) as CuttingDraftResponse

  const patched = await request.patch(`/api/v1/client/cutting-drafts/${draft.id}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      preferred_branch_id: branchId,
      parts_snapshot: [
        {
          part_ref: `seed-${draft.id.slice(0, 8)}`,
          material_id: panel.id,
          material_source: 'shop',
          length_mm: 260,
          width_mm: 180,
          quantity: 2,
          edge_top: { material_id: edge.id, source: 'shop' },
          edge_bottom: null,
          edge_left: { material_id: edge.id, source: 'shop' },
          edge_right: null,
        },
      ],
    },
  })
  await expectOk(patched)

  const optimized = await request.post(`/api/v1/client/cutting-drafts/${draft.id}/optimize`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  await expectOk(optimized)
  const result = (await optimized.json()) as CuttingDraftResponse
  expect(result.chosen_result_id).not.toBeNull()
  return result.chosen_result_id as string
}

async function confirmCuttingResult(args: {
  resultId: string
  clientId: string
  workshopId: string
  branchId: string
  orderNumber: string
}): Promise<string> {
  const script = `
import asyncio
import os
import uuid
from datetime import UTC, datetime

from app.core.db import SessionLocal
from app.models import import_all_models
from app.models.enums import ActorType, Currency, CuttingResultStatus, OrderStatus
from app.modules.cutting.contracts import CuttingResult
from app.modules.sales.contracts import Order, OrderStatusEvent

import_all_models()

async def main() -> None:
    now = datetime.now(UTC)
    result_id = uuid.UUID(os.environ["RESULT_ID"])
    async with SessionLocal() as db:
        result = await db.get(CuttingResult, result_id)
        if result is None:
            raise RuntimeError("cutting result not found")

        order = Order(
            order_number=os.environ["ORDER_NUMBER"],
            client_id=uuid.UUID(os.environ["CLIENT_ID"]),
            workshop_id=uuid.UUID(os.environ["WORKSHOP_ID"]),
            branch_id=uuid.UUID(os.environ["BRANCH_ID"]),
            cutting_result_id=result.id,
            contact_name="Cutting API Client",
            contact_phone="+998900000000",
            status=OrderStatus.CONFIRMED,
            confirmed_at=now,
            subtotal_cutting_tiyin=0,
            subtotal_materials_tiyin=0,
            subtotal_edge_banding_tiyin=0,
            discount_tiyin=0,
            total_tiyin=0,
            currency=Currency.UZS,
            panels_used_snapshot=sum(result.panels_used_by_material.values()),
            cut_count_snapshot=sum(
                int(part.get("quantity", 0)) for part in result.parts_snapshot
            ),
            edge_length_snapshot=result.edge_consumed_shop_by_material,
        )
        db.add(order)
        await db.flush()

        result.status = CuttingResultStatus.CONFIRMED
        result.confirmed_at = now
        result.order_id = order.id
        result.draft_id = None

        db.add(
            OrderStatusEvent(
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.CONFIRMED,
                actor_type=ActorType.SYSTEM,
                reason="E2E Cutting confirmed cutting result",
                metadata_json={"source": "cutting_e2e"},
                changed_at=now,
            )
        )
        await db.commit()
        print(order.id)

asyncio.run(main())
`
  const { stdout } = await execFileAsync(
    'uv',
    ['--directory', '../backend', 'run', 'python', '-c', script],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        ENV: 'test',
        DATABASE_URL: databaseUrl,
        OTP_DEV_CODES: '["000000"]',
        RESULT_ID: args.resultId,
        CLIENT_ID: args.clientId,
        WORKSHOP_ID: args.workshopId,
        BRANCH_ID: args.branchId,
        ORDER_NUMBER: args.orderNumber,
      },
    },
  )
  // The script prints the created order id on its last stdout line.
  return stdout.trim().split('\n').pop()?.trim() ?? ''
}

async function loginWorkshop(page: Page, login: string, password: string) {
  await page.goto('/workshop/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(password)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page).toHaveURL(/\/workshop\/?$/)
}

async function chooseEdgeBanding(page: Page, edgeName: string) {
  // The compact row exposes one rectangular edge diagram that opens the picker.
  await page.getByRole('button', { name: 'Kromka tomonlari', exact: true }).click()
  // A drawing with no tapes yet opens straight into the branch tape catalog;
  // picking the tape returns to the banding panel with it armed as current.
  const catalog = page.getByRole('dialog', { name: /Yana kromka qo'shish/ })
  await catalog.getByRole('button', { name: new RegExp(edgeName) }).click()
  const dialog = page.getByRole('dialog', { name: /Kromka yopishtirish/ })
  await expect(dialog.getByText(new RegExp(edgeName))).toBeVisible()
  // Band top and bottom with the armed tape; edits apply live, so closing the
  // dialog keeps them.
  await dialog.getByRole('button', { name: /^Yuqori tomon/ }).click()
  await dialog.getByRole('button', { name: /^Pastki tomon/ }).click()
  await dialog.getByRole('button', { name: 'Kromka oynasini yopish' }).click()
}

test('client signs in with Telegram OTP, optimizes a cutting draft, and opens the PDF', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p4-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const { panel, edge } = await createCatalogMaterials(request, adminAccess, id)
  const branchId = setup.branch.id as string
  await addBranchMaterial(request, ownerAccess, branchId, panel.id)
  await addBranchMaterial(request, ownerAccess, branchId, edge.id)

  await page.goto('/client/auth/login')
  await page.getByLabel('Telefon raqami').fill(phoneFor(id, 40))
  await page.getByRole('button', { name: 'Kod yuborish' }).click()
  await page.getByLabel('Tasdiqlash kodi').fill('000000')
  await page.getByRole('button', { name: 'Tasdiqlash' }).click()
  await page.getByLabel('Ismingiz').fill('Cutting Client')
  await page.getByRole('button', { name: 'Davom etish' }).click()
  await expect(page).toHaveURL(/\/client\/c$/)

  const branchesLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/v1/client/branch-options') &&
      response.ok(),
  )
  // Fresh DB → empty home (first-run), so the create CTA is the centred
  // "Yangi chizma" in the empty state; the header button only shows with content.
  await page.getByRole('button', { name: 'Yangi chizma' }).click()
  // The editor opens unsaved — no draft is created until the first optimise
  // (docs/ref/features/cutting.md), so the URL is /new with no draft id yet.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/new$/)
  await expect(page.getByRole('heading', { name: 'Chizma', exact: true })).toBeVisible()
  await branchesLoaded

  // The first editor visit opens the required branch picker automatically.
  // CB-51: the preferred-branch picker is a single flat branch list — one tap selects.
  await page.getByRole('button', { name: new RegExp(`Cutting Branch ${id}`) }).click()
  await expect(page.getByText(`Cutting Branch ${id} · Cutting Workshop ${id}`)).toBeVisible()

  // A new compact entry starts by selecting its material; that selection creates
  // the first editable row in the material group.
  await page.getByRole('button', { name: '+ Material tanlash' }).click()
  await page
    .getByRole('dialog', { name: 'Materialni almashtirish' })
    .getByRole('button', { name: new RegExp(panel.name) })
    .click()
  await page.getByLabel("Bo'y millimetr").fill('260')
  await page.getByLabel('Eni millimetr').fill('180')
  await page.getByLabel('Soni').fill('2')
  await chooseEdgeBanding(page, edge.name)
  await page.getByRole('button', { name: 'Davom etish' }).click()

  // The first optimise creates + persists + optimises the draft, then routes to
  // the standalone result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByText(new RegExp(panel.name)).first()).toBeVisible()
  // The sheet strip groups thumbnails per material, captioned "List {index}".
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()
  await expect(page.getByRole('img', { name: /List 1 joylashuvi/ })).toBeVisible()
  // The sheet is height-capped (`fit="viewport"`) so a whole panel fits one
  // screen — without it the drawing stretches to the full container width.
  await expect(page.locator('svg.cutting-svg-fit')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Kromka' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Shu variantni tanlash/ })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Buyurtmaga davom etish' })).toBeVisible()

  // QAD-160: the PDF opens in a new tab instead of downloading.
  await expectPdfOpensInTab(
    page,
    page.getByRole('button', { name: 'PDF ochish' }),
    /\/cutting-results\/[0-9a-f-]+\/pdf$/,
  )
})

test('client resumes a saved cutting draft after reload and from the drafts list', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p4-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const { panel, edge } = await createCatalogMaterials(request, adminAccess, id)
  const branchId = setup.branch.id as string
  await addBranchMaterial(request, ownerAccess, branchId, panel.id)
  await addBranchMaterial(request, ownerAccess, branchId, edge.id)

  await page.goto('/client/auth/login')
  await page.getByLabel('Telefon raqami').fill(phoneFor(id, 60))
  await page.getByRole('button', { name: 'Kod yuborish' }).click()
  await page.getByLabel('Tasdiqlash kodi').fill('000000')
  await page.getByRole('button', { name: 'Tasdiqlash' }).click()
  await page.getByLabel('Ismingiz').fill('Resume Client')
  await page.getByRole('button', { name: 'Davom etish' }).click()
  await expect(page).toHaveURL(/\/client\/c$/)

  const branchesLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/v1/client/branch-options') &&
      response.ok(),
  )
  await page.getByRole('button', { name: 'Yangi chizma' }).click()
  await expect(page).toHaveURL(/\/client\/c\/cutting\/new$/)
  await branchesLoaded

  // The first editor visit opens the required branch picker automatically.
  await page.getByRole('button', { name: new RegExp(`Cutting Branch ${id}`) }).click()
  await expect(page.getByText(`Cutting Branch ${id} · Cutting Workshop ${id}`)).toBeVisible()

  await page.getByRole('button', { name: '+ Material tanlash' }).click()
  await page
    .getByRole('dialog', { name: 'Materialni almashtirish' })
    .getByRole('button', { name: new RegExp(panel.name) })
    .click()
  await page.getByLabel("Bo'y millimetr").fill('260')
  await page.getByLabel('Eni millimetr').fill('180')
  await page.getByLabel('Soni').fill('2')
  await page.getByRole('button', { name: 'Davom etish' }).click()

  // The first optimise persists the draft and hands off to the result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  const resultUrl = page.url()

  // Resume path #1 — reload keeps the standalone result fully hydrated.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Buyurtmaga davom etish' })).toBeVisible()

  // Editing is a deliberate trip back to the detail stage.
  await page.getByRole('link', { name: 'Detallarni tahrirlash' }).click()
  await expect(page.getByLabel("Bo'y millimetr")).toHaveValue('260')
  await expect(page.getByLabel('Eni millimetr')).toHaveValue('180')
  await expect(page.getByLabel('Soni')).toHaveValue('2')
  await expect(page.getByText(`Cutting Branch ${id} · Cutting Workshop ${id}`)).toBeVisible()

  // The one primary CTA keeps its name and opens the current result.
  const continueButton = page.getByRole('button', { name: 'Davom etish' })
  await expect(continueButton).toHaveCount(1)
  await continueButton.click()
  await expect(page).toHaveURL(resultUrl)

  // Resume path #2 — drafts with a chosen result reopen on the result stage.
  await page.goto('/client/c/cutting/drafts')
  await expect(page.getByRole('heading', { name: 'Saqlangan chizmalar' })).toBeVisible()
  await page.getByRole('button', { name: 'Ochish →' }).click()
  await expect(page).toHaveURL(resultUrl)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()

  // Changing geometry invalidates that current snapshot. The same one CTA now
  // optimises instead of exposing a stale result.
  await page.getByRole('link', { name: 'Detallarni tahrirlash' }).click()
  await page.getByLabel("Bo'y millimetr").fill('261')
  await expect(page.getByRole('button', { name: 'Davom etish' })).toHaveCount(1)
})

test('workshop opens a confirmed order cutting plan and opens the PDF', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p4-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const { panel, edge } = await createCatalogMaterials(request, adminAccess, id)
  const branchId = setup.branch.id as string
  await addBranchMaterial(request, ownerAccess, branchId, panel.id)
  await addBranchMaterial(request, ownerAccess, branchId, edge.id)

  const clientLogin = await clientToken(request, phoneFor(id, 80), 'Cutting API Client')
  const resultId = await optimizedClientDraft(
    request,
    clientLogin.access_token,
    branchId,
    panel,
    edge,
  )
  const orderNumber = `P4-${id.toUpperCase()}`
  const orderId = await confirmCuttingResult({
    resultId,
    clientId: clientLogin.me.principal_id,
    workshopId: setup.workshop.id as string,
    branchId,
    orderNumber,
  })

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${orderId}`)
  await expect(page.getByRole('heading', { name: orderNumber })).toBeVisible()

  // The cutting plan lives in the "Chizma va tarkib" modal now.
  await page.getByRole('button', { name: 'Chizma va tarkib' }).click()
  const chizmaDialog = page.getByRole('dialog', { name: 'Chizma va tarkib' })
  await expect(chizmaDialog.getByRole('button', { name: new RegExp(panel.name) })).toBeVisible()
  await expect(chizmaDialog.getByRole('img', { name: /List 1 joylashuvi/ })).toBeVisible()

  // QAD-160 changed every PDF entry point, including this one, from a download
  // to a new tab.
  await expectPdfOpensInTab(
    page,
    page.getByRole('button', { name: 'Chizma (PDF)' }),
    /\/workshop\/orders\/[0-9a-f-]+\/cutting\/pdf$/,
  )
})

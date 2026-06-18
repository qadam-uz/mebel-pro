import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

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
  const code = `p4-${id}`
  const ownerLogin = `owner-${id}`
  const ownerPassword = 'OwnerTemp123'
  const response = await request.post('/api/v1/platform/workshops', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Cutting Workshop ${id}`,
        code,
        phone: phoneFor(id, 2),
        address: 'Tashkent',
      },
      branch: {
        name: `Cutting Branch ${id}`,
        address: 'Tashkent, Test',
        phone: phoneFor(id, 3),
        latitude: '41.2995',
        longitude: '69.2401',
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: 'Cutting Owner',
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

async function createCatalogMaterials(request: APIRequestContext, token: string, id: string) {
  const manufacturer = await request.post('/api/v1/platform/catalog/manufacturers', {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: `Cutting Maker ${id}`, country: 'UZ' },
  })
  expect(manufacturer.ok()).toBe(true)
  const manufacturerId = (await manufacturer.json()).id as string

  const panel = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'panel',
      manufacturer_id: manufacturerId,
      type: 'dsp',
      name: `Cutting Panel ${id}`,
      thickness_mm: '18',
      color: 'White',
      decor_code: `P4-P-${id}`,
      panel_length_mm: 900,
      panel_width_mm: 600,
      grain_direction: false,
    },
  })
  expect(panel.ok()).toBe(true)

  const edge = await request.post('/api/v1/platform/catalog/materials', {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: 'edge',
      manufacturer_id: manufacturerId,
      name: `Cutting Edge ${id}`,
      thickness_mm: '2',
      color: 'White',
      decor_code: `P4-E-${id}`,
    },
  })
  expect(edge.ok()).toBe(true)

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
  expect(response.ok()).toBe(true)
}

async function clientToken(request: APIRequestContext, phone: string, name: string) {
  const requested = await request.post('/api/v1/auth/client/otp/request', { data: { phone } })
  expect(requested.ok()).toBe(true)
  const verified = await request.post('/api/v1/auth/client/otp/verify', {
    data: { phone, code: '000000', name },
  })
  expect(verified.ok()).toBe(true)
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
  expect(created.ok()).toBe(true)
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
  expect(patched.ok()).toBe(true)

  const optimized = await request.post(`/api/v1/client/cutting-drafts/${draft.id}/optimize`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(optimized.ok()).toBe(true)
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
}) {
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
  await execFileAsync('uv', ['--directory', '../backend', 'run', 'python', '-c', script], {
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
  })
}

async function loginWorkshop(page: Page, code: string, login: string, password: string) {
  await page.goto('/workshop/')
  await page.getByLabel('Workshop code').fill(code)
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(password)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page).toHaveURL(/\/workshop\/?$/)
}

async function chooseEdgeBanding(page: Page, edgeName: string) {
  await page.getByRole('button', { name: /Qism #1 kromini tahrirlash/ }).click()
  const dialog = page.getByRole('dialog', { name: /Krom yopishtirish/ })
  await dialog.getByRole('button', { name: 'Yuqori + pastki' }).click()
  await dialog.getByLabel('Krom qidirish').fill(edgeName)
  await dialog.getByRole('button', { name: new RegExp(edgeName) }).click()
  await dialog.getByRole('button', { name: "Qo'llash" }).click()
}

test('client signs in with Telegram OTP, optimizes a cutting draft, and downloads PDF', async ({
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
  await page.getByRole('button', { name: 'Yangi kesim chizmasi' }).click()
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+$/)
  await expect(page.getByRole('heading', { name: 'Chizma', exact: true })).toBeVisible()
  await branchesLoaded

  await page.getByRole('button', { name: 'Ustaxona tanlash' }).click()
  await page.getByRole('button', { name: 'Afzal filial' }).click()
  await page.getByRole('option', { name: new RegExp(`Cutting Workshop ${id}`) }).click()
  await page.getByRole('button', { name: "Qo'llash" }).click()
  await expect(page.getByText(`Cutting Branch ${id} · Cutting Workshop ${id}`)).toBeVisible()

  await page.getByRole('button', { name: "Qism qo'shish" }).first().click()
  await page.getByRole('combobox', { name: 'Panel materiali' }).fill(panel.name)
  await page.getByRole('option', { name: new RegExp(panel.name) }).click()
  await page.getByRole('combobox', { name: 'Panel materiali' }).press('Escape')
  await page.getByLabel('Uzunlik millimetr').fill('260')
  await page.getByLabel('Eni millimetr').fill('180')
  await page.getByLabel('Soni').fill('2')
  await chooseEdgeBanding(page, edge.name)
  await page.getByRole('button', { name: 'Optimallashtirish' }).click()

  await expect(page.getByRole('heading', { name: 'Natija', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'ffd-guillotine' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'bfd-guillotine' })).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(panel.name) })).toBeVisible()
  await expect(page.getByRole('img', { name: /Panel 1 layout/ })).toBeVisible()
  await expect(page.getByText("Krom (material bo'yicha)")).toBeVisible()
  await expect(page.getByRole('button', { name: /Shuni tanlash|Tanlangan/ })).toHaveCount(2)
  await expect(page.getByRole('link', { name: 'Buyurtma berish' })).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'PDF yuklab olish' }).click()
  expect((await download).suggestedFilename()).toMatch(/^cutting-[0-9a-f-]+\.pdf$/)
})

test('workshop opens a confirmed read-only cutting plan and downloads PDF', async ({
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
  await confirmCuttingResult({
    resultId,
    clientId: clientLogin.me.principal_id,
    workshopId: setup.workshop.id as string,
    branchId,
    orderNumber,
  })

  await loginWorkshop(page, setup.code, setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/cutting-plans')
  await expect(page.getByRole('heading', { name: 'Cutting plans' })).toBeVisible()
  await expect(page.getByRole('heading', { name: orderNumber })).toBeVisible()
  await page.getByRole('link', { name: 'Open' }).click()

  await expect(page.getByRole('heading', { name: 'Read-only cutting plan' })).toBeVisible()
  await expect(page.getByText(orderNumber)).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(panel.name) })).toBeVisible()
  await expect(page.getByRole('img', { name: /Panel 1 layout/ })).toBeVisible()
  await expect(page.getByText('Placements')).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download PDF' }).click()
  expect((await download).suggestedFilename()).toMatch(/^cutting-[0-9a-f-]+\.pdf$/)
})

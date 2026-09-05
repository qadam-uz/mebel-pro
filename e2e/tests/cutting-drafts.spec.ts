import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import {
  carryOneFormat,
  createCatalogDecors,
  databaseUrl,
  edgeNumbers,
  enterViaWorkshopLink,
  escapeRegExp,
  devConfirmLogin,
  expectOk,
  expectPdfOpensInTab,
  panelNumbers,
  workshopLinkFor,
  type BranchMaterialResponse,
} from './helpers'

const execFileAsync = promisify(execFile)
const adminPassword = 'AdminPass123'
const ownerReadyPassword = 'OwnerReady123'
const passwordLabel = /^(Password|Parol)$/
const continueButton = /^(Continue|Kirish)$/

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

/**
 * The branch's carried formats — a platform dekor is identity only, so the panel
 * and the tape the editor picks are **branch materials**, created by attaching
 * one format of each dekor to this branch.
 */
async function carriedMaterials(
  request: APIRequestContext,
  adminToken: string,
  ownerToken: string,
  branchId: string,
  id: string,
) {
  const { panel: panelDecor, edge: edgeDecor } = await createCatalogDecors(
    request,
    adminToken,
    id,
  )
  const panel = await carryOneFormat(request, ownerToken, branchId, panelDecor.format.id, panelNumbers)
  const edge = await carryOneFormat(request, ownerToken, branchId, edgeDecor.format.id, edgeNumbers)
  return { panelDecor, edgeDecor, panel, edge }
}

// The three calls the login card makes, with dev-confirm standing in for the bot.
async function clientToken(request: APIRequestContext, phone: string, name: string) {
  const issued = await request.post('/api/v1/auth/client/telegram/token')
  await expectOk(issued)
  const handshake = (await issued.json()) as { token: string; poll_secret: string }
  await devConfirmLogin(request, handshake.token, phone, name)
  const polled = await request.post('/api/v1/auth/client/telegram/poll', {
    data: { poll_secret: handshake.poll_secret },
  })
  await expectOk(polled)
  return (await polled.json()) as TokenResponse
}

async function optimizedClientDraft(
  request: APIRequestContext,
  token: string,
  branchId: string,
  panel: BranchMaterialResponse,
  edge: BranchMaterialResponse,
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

/**
 * Pick a material in the client's decor-first picker (SPEC_CLIENT_UX_MVP §7.3).
 * The list is one row per DECOR; this branch carries the decor in a single
 * format, so the decor row itself is the choice and no format list appears.
 */
async function chooseMaterial(page: Page, dekorLabel: string) {
  const sheet = page.getByRole('dialog', { name: 'Material tanlang' })
  await sheet.getByRole('button', { name: new RegExp(escapeRegExp(dekorLabel)) }).click()
  await expect(sheet).toBeHidden()
}

/**
 * Band the top and bottom of the first part (§7.1).
 *
 * On the client the tape DECOR belongs to the material group and only the
 * thickness is the side's: clicking the row's kromka cell selects the row and
 * opens the docked card, whose group line either already names the tape the
 * branch carries in the board's colour, or asks for one. There is no per-part
 * tape list and no «4 tomon» / «Kromsiz» pattern pair any more.
 */
async function chooseEdgeBanding(page: Page) {
  await page.getByRole('button', { name: 'Kromka tomonlari', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Kromka' })
  await expect(panel).toBeVisible()

  // The gate: a group whose board decor has no matching tape at the branch asks
  // for a colour before any side can be banded.
  const pickTape = panel.getByRole('button', { name: /rangi mos lentani tanlang/ })
  if (await pickTape.isVisible()) {
    await pickTape.click()
    const sheet = page.getByRole('dialog', { name: 'Rangi mos kromkani tanlang' })
    await sheet.getByRole('radio').first().click()
    await sheet.getByRole('button', { name: 'Tanlash' }).click()
    await expect(sheet).toBeHidden()
  }
  // Either way the group now names one tape, which is what makes the thickness
  // chips and the sides below meaningful.
  await expect(panel.getByText(/^Kromka:/)).toBeVisible()

  await panel.getByRole('button', { name: /^Yuqori/ }).click()
  await panel.getByRole('button', { name: /^Pastki/ }).click()
}

test('client signs in through the Telegram bot, optimizes a cutting draft, and opens the PDF', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const adminLogin = `p4-admin-${id}`
  await seedPlatform(adminLogin)
  const adminAccess = await platformToken(request, adminLogin)
  const setup = await provisionWorkshop(request, adminAccess, id)
  const ownerAccess = await readyOwnerToken(request, setup)
  const branchId = setup.branch.id as string
  const { panelDecor, panel, edge } = await carriedMaterials(
    request,
    adminAccess,
    ownerAccess,
    branchId,
    id,
  )

  // A drawing only ever starts from a workshop (§2.2), so the client comes in
  // through the counter QR: that is what writes the pin. A plain `loginClient`
  // would leave this client un-pinned and `/c/cutting/new` would redirect to
  // Ustaxonalarim before any editor rendered.
  const workshopLink = await workshopLinkFor(request, ownerAccess, branchId)
  await enterViaWorkshopLink(page, workshopLink, phoneFor(id, 40), 'Cutting Client')

  const branchesLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/v1/client/branch-options') &&
      response.ok(),
  )
  // Pinned home: «Yangi chizma» sits under the Ustaxonangiz card and opens the
  // editor already scoped to the pinned branch.
  await page.getByRole('button', { name: 'Yangi chizma' }).click()
  // The editor opens unsaved — no draft is created until the first optimise
  // (docs/ref/features/cutting.md), so the URL is /new with no draft id yet.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/new$/)
  await expect(page.getByRole('heading', { name: 'Chizma', exact: true })).toBeVisible()
  await branchesLoaded

  // Decision 17: the editor never raises a branch picker of its own, so there
  // is nothing to choose here. Decision 16, the naming rule: this workshop has
  // one branch, so it is named by the workshop alone — a branch name is never
  // shown on its own.
  await expect(page.getByText(`Cutting Workshop ${id}`).first()).toBeVisible()

  // A new compact entry starts by selecting its material; that selection creates
  // the first editable row in the material group.
  await page.getByRole('button', { name: '+ Material', exact: true }).click()
  await chooseMaterial(page, panelDecor.label)
  await page.getByLabel("Uzunlik millimetr").fill('260')
  await page.getByLabel('Kenglik millimetr').fill('180')
  await page.getByLabel('Soni').fill('2')
  await chooseEdgeBanding(page)
  await page.getByRole('button', { name: 'Hisoblash' }).click()

  // The first optimise creates + persists + optimises the draft, then routes to
  // the standalone result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByText(panel.label).first()).toBeVisible()
  // The sheet strip groups thumbnails per material, captioned "List {index}".
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()
  await expect(page.getByRole('img', { name: /List 1 joylashuvi/ })).toBeVisible()
  // The sheet is height-capped (`fit="viewport"`) so a whole panel fits one
  // screen — without it the drawing stretches to the full container width.
  await expect(page.locator('svg.cutting-svg-fit')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Kromka' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Shu variantni tanlash/ })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Buyurtma berish' })).toBeVisible()

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
  const branchId = setup.branch.id as string
  const { panelDecor } = await carriedMaterials(request, adminAccess, ownerAccess, branchId, id)

  // Same door as above: the QR pins the branch, so the editor opens scoped.
  const workshopLink = await workshopLinkFor(request, ownerAccess, branchId)
  await enterViaWorkshopLink(page, workshopLink, phoneFor(id, 60), 'Resume Client')

  const branchesLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      response.url().includes('/api/v1/client/branch-options') &&
      response.ok(),
  )
  await page.getByRole('button', { name: 'Yangi chizma' }).click()
  await expect(page).toHaveURL(/\/client\/c\/cutting\/new$/)
  await branchesLoaded

  // Decision 17: no in-editor branch picker. Decision 16: one branch, so the
  // workshop alone names it.
  await expect(page.getByText(`Cutting Workshop ${id}`).first()).toBeVisible()

  await page.getByRole('button', { name: '+ Material', exact: true }).click()
  await chooseMaterial(page, panelDecor.label)
  await page.getByLabel("Uzunlik millimetr").fill('260')
  await page.getByLabel('Kenglik millimetr').fill('180')
  await page.getByLabel('Soni').fill('2')
  await page.getByRole('button', { name: 'Hisoblash' }).click()

  // The first optimise persists the draft and hands off to the result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  const resultUrl = page.url()

  // Resume path #1 — reload keeps the standalone result fully hydrated.
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Buyurtma berish' })).toBeVisible()

  // Editing is a deliberate trip back to the detail stage.
  await page.getByRole('link', { name: 'Detallarni tahrirlash' }).click()
  await expect(page.getByLabel("Uzunlik millimetr")).toHaveValue('260')
  await expect(page.getByLabel('Kenglik millimetr')).toHaveValue('180')
  await expect(page.getByLabel('Soni')).toHaveValue('2')
  await expect(page.getByText(`Cutting Workshop ${id}`).first()).toBeVisible()

  // §7.0: the CTA says what the tap does — it opens the result that is current.
  const continueButton = page.getByRole('button', { name: "Natijani ko'rish" })
  await expect(continueButton).toHaveCount(1)
  await continueButton.click()
  await expect(page).toHaveURL(resultUrl)

  // Resume path #2 — the drafts list reopens a draft on the detail stage with
  // its parts restored, and the same one CTA carries it on to the result.
  const editorUrl = resultUrl.replace(/\/result$/, '')
  await page.goto('/client/c/cutting/drafts')
  await expect(page.getByRole('heading', { name: 'Saqlangan chizmalar' })).toBeVisible()
  await page.getByRole('link', { name: 'Davom etish →' }).click()
  await expect(page).toHaveURL(editorUrl)
  await expect(page.getByLabel("Uzunlik millimetr")).toHaveValue('260')
  await page.getByRole('button', { name: "Natijani ko'rish" }).click()
  await expect(page).toHaveURL(resultUrl)
  await expect(page.getByRole('heading', { name: 'Kesish natijasi' })).toBeVisible()
  await expect(page.getByRole('button', { name: /List 1$/ })).toBeVisible()

  // Changing geometry invalidates that current snapshot. The same one CTA now
  // optimises instead of exposing a stale result.
  await page.getByRole('link', { name: 'Detallarni tahrirlash' }).click()
  await page.getByLabel("Uzunlik millimetr").fill('261')
  // A geometry edit invalidates the current snapshot, so the CTA goes back to
  // offering the calculation rather than a stale result.
  await expect(page.getByRole('button', { name: 'Hisoblash' })).toHaveCount(1)
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
  const branchId = setup.branch.id as string
  const { panel, edge } = await carriedMaterials(request, adminAccess, ownerAccess, branchId, id)

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
  await expect(
    chizmaDialog.getByRole('button', { name: new RegExp(escapeRegExp(panel.label)) }),
  ).toBeVisible()
  await expect(chizmaDialog.getByRole('img', { name: /List 1 joylashuvi/ })).toBeVisible()

  // QAD-160 changed every PDF entry point, including this one, from a download
  // to a new tab.
  await expectPdfOpensInTab(
    page,
    page.getByRole('button', { name: 'Chizma (PDF)' }),
    /\/workshop\/orders\/[0-9a-f-]+\/cutting\/pdf$/,
  )
})

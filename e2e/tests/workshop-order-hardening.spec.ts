import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import {
  continueButton,
  ownerReadyPassword,
  passwordLabel,
  phoneFor,
  placeClientOrderViaApi,
  runId,
  seedOrderableBranch,
} from './helpers'

test.setTimeout(90_000)

async function loginWorkshop(
  page: Page,
  code: string,
  login: string,
  password: string,
) {
  await page.goto('/workshop/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(password)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page).toHaveURL(/\/workshop\/?$/)
}

async function chooseDropdown(page: Page, label: RegExp, option: RegExp) {
  await page.getByRole('button', { name: label }).click()
  await page.getByRole('option', { name: option }).click()
}

async function orderDetail(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
) {
  const response = await request.get(`/api/v1/workshop/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
  })
  expect(response.ok()).toBe(true)
  return (await response.json()) as { version: number; status: string }
}

async function assignForCutting(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
  version: number,
  workerId: string,
) {
  const response = await request.post(`/api/v1/workshop/orders/${orderId}/assign`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: {
      version,
      cutter_user_id: workerId,
      edger_user_id: workerId,
    },
  })
  expect(response.ok()).toBe(true)
  return (await response.json()) as { version: number; status: string }
}

test('owner applies a discount and it persists after reload', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const seeded = await seedOrderableBranch(request, id)
  const placed = await placeClientOrderViaApi(request, {
    phone: phoneFor(id, 40),
    name: `Discount Client ${id}`,
    branchId: seeded.branchId,
    panelId: seeded.panel.id,
    edgeId: seeded.edge.id,
  })

  await loginWorkshop(page, seeded.setup.code, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${placed.order.id}`)
  await expect(page.getByRole('heading', { name: placed.order.order_number })).toBeVisible()

  await page.getByLabel('Qiymat').fill('12345')
  await page.getByLabel('Sabab').fill('E2E discount persists')
  const discounted = page.waitForResponse(
    (response) => response.url().includes('/discount') && response.ok(),
  )
  await page.getByRole('button', { name: "Chegirma qo'shish" }).click()
  await discounted
  await expect(page.getByText('E2E discount persists')).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: placed.order.order_number })).toBeVisible()
  await expect(page.getByText('E2E discount persists')).toBeVisible()
})

test('owner records order income and standalone expense', async ({ page, request }, testInfo) => {
  const id = runId(testInfo)
  const seeded = await seedOrderableBranch(request, id)
  const placed = await placeClientOrderViaApi(request, {
    phone: phoneFor(id, 41),
    name: `Finance Client ${id}`,
    branchId: seeded.branchId,
    panelId: seeded.panel.id,
    edgeId: seeded.edge.id,
  })

  await loginWorkshop(page, seeded.setup.code, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/finance/expenses')
  await expect(page.getByRole('heading', { name: 'Tushum va xarajat' })).toBeVisible()

  await page.getByRole('button', { name: 'Tushum' }).click()
  const incomePanel = page
    .getByRole('heading', { name: 'Tushum yozish' })
    .locator('xpath=ancestor::section[1]')
  await chooseDropdown(page, /^Buyurtma/, new RegExp(placed.order.order_number))
  await expect(incomePanel.getByText('Qoldiq:')).toBeVisible()
  await incomePanel.getByRole('button', { name: 'Qoldiqni kiritish' }).click()
  await incomePanel.getByLabel('Izoh').fill('E2E order payment')
  await incomePanel.getByRole('button', { name: 'Yozish' }).click()
  await expect(page.getByText('E2E order payment')).toBeVisible()

  await page.getByRole('button', { name: 'Xarajat' }).click()
  const expensePanel = page
    .getByRole('heading', { name: 'Xarajat yozish' })
    .locator('xpath=ancestor::section[1]')
  await expensePanel.getByLabel('Tavsif').fill('E2E standalone expense')
  await expensePanel.getByLabel("Summa (so'm)").fill('1000')
  await expensePanel.getByRole('button', { name: 'Yozish' }).click()
  await expect(page.getByText('E2E standalone expense')).toBeVisible()
})

test('owner reverts with a reason and retries a stale cancel after 409', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const seeded = await seedOrderableBranch(request, id)
  const ownerId = (seeded.setup.owner as { id: string }).id
  const placed = await placeClientOrderViaApi(request, {
    phone: phoneFor(id, 42),
    name: `Conflict Client ${id}`,
    branchId: seeded.branchId,
    panelId: seeded.panel.id,
    edgeId: seeded.edge.id,
  })
  const approved = await request.post(`/api/v1/workshop/orders/${placed.order.id}/approve`, {
    headers: { Authorization: `Bearer ${seeded.ownerAccess}` },
    data: { version: placed.order.version },
  })
  expect(approved.ok()).toBe(true)
  const cutting = await assignForCutting(
    request,
    seeded.ownerAccess,
    placed.order.id,
    (await approved.json()).version,
    ownerId,
  )
  expect(cutting.status).toBe('cutting')

  await loginWorkshop(page, seeded.setup.code, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${placed.order.id}`)
  await expect(page.getByText('Kesilmoqda', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'tasdiqlangan holatiga qaytarish' }).click()
  const revertDialog = page.getByRole('dialog', { name: 'Buyurtmani qaytarish' })
  await revertDialog.getByLabel('Sabab').fill('E2E revert reason')
  await revertDialog.getByRole('button', { name: 'Qaytarish' }).click()
  await expect(page.getByText('Tasdiqlangan', { exact: true }).first()).toBeVisible()

  const freshBeforeConflict = await orderDetail(request, seeded.ownerAccess, placed.order.id)
  const note = await request.patch(`/api/v1/workshop/orders/${placed.order.id}/note`, {
    headers: { Authorization: `Bearer ${seeded.ownerAccess}` },
    data: { note_workshop: `external update ${freshBeforeConflict.version}` },
  })
  expect(note.ok()).toBe(true)

  await page.getByRole('button', { name: 'Buyurtmani bekor qilish' }).click()
  const cancelDialog = page.getByRole('dialog', { name: 'Buyurtmani bekor qilish' })
  await cancelDialog.getByLabel('Sabab').fill('E2E stale cancel')
  const staleCancel = page.waitForResponse(
    (response) => response.url().includes('/cancel') && response.status() === 409,
  )
  await cancelDialog.getByRole('button', { name: 'Bekor qilish' }).click()
  await staleCancel
  await expect(
    page.getByText("Buyurtma boshqa joyda o'zgargan. Ma'lumot yangilandi"),
  ).toBeVisible()

  const successfulCancel = page.waitForResponse(
    (response) => response.url().includes('/cancel') && response.ok(),
  )
  await cancelDialog.getByRole('button', { name: 'Bekor qilish' }).click()
  await successfulCancel
  await expect(page.getByText('Bekor qilingan', { exact: true }).first()).toBeVisible()
})

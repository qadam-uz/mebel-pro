import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import {
  continueButton,
  expectOk,
  orderNumberText,
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
  login: string,
  password: string,
) {
  await page.goto('/workshop/')
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(passwordLabel).fill(password)
  await page.getByRole('button', { name: continueButton }).click()
  await expect(page).toHaveURL(/\/workshop\/?$/)
}

async function orderDetail(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
) {
  const response = await request.get(`/api/v1/workshop/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
  })
  await expectOk(response)
  return (await response.json()) as { version: number; status: string }
}

async function assignForCutting(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
  version: number,
  workerId: string,
) {
  // Assignment is metadata (the order stays confirmed); starting the job is
  // the confirmed → cutting trigger.
  const assigned = await request.post(`/api/v1/workshop/orders/${orderId}/assign`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: {
      version,
      cutter_user_id: workerId,
      edger_user_id: workerId,
    },
  })
  await expectOk(assigned)
  const assignedBody = (await assigned.json()) as { version: number; status: string }
  const started = await request.post(`/api/v1/workshop/orders/${orderId}/start-cutting`, {
    headers: { Authorization: `Bearer ${ownerAccess}` },
    data: { version: assignedBody.version },
  })
  await expectOk(started)
  return (await started.json()) as { version: number; status: string }
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

  await loginWorkshop(page, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${placed.order.id}`)
  await expect(page.getByRole('heading', { name: orderNumberText(placed.order.order_number) })).toBeVisible()

  // Discount lives behind the header overflow menu now, in a modal. The fixed
  // value is entered in so'm and stored as tiyin (1 000 so'm = 100 000 tiyin),
  // safely within the order subtotal.
  await page.getByRole('button', { name: 'Boshqa amallar' }).click()
  await page.getByRole('button', { name: "Chegirma qo'shish" }).click()
  const discountDialog = page.getByRole('dialog', { name: 'Chegirma' })
  await discountDialog.getByLabel('Qiymat').fill('1000')
  await discountDialog.getByLabel('Sabab').fill('E2E discount persists')
  const discounted = page.waitForResponse(
    (response) => response.url().includes('/discount') && response.ok(),
  )
  await discountDialog.getByRole('button', { name: "Chegirma qo'shish" }).click()
  await discounted
  await expect(page.getByText('E2E discount persists')).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: orderNumberText(placed.order.order_number) })).toBeVisible()
  await expect(page.getByText('E2E discount persists')).toBeVisible()
})

test('owner applies a surcharge and it persists after reload', async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo)
  const seeded = await seedOrderableBranch(request, id)
  const placed = await placeClientOrderViaApi(request, {
    phone: phoneFor(id, 41),
    name: `Surcharge Client ${id}`,
    branchId: seeded.branchId,
    panelId: seeded.panel.id,
    edgeId: seeded.edge.id,
  })

  await loginWorkshop(page, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${placed.order.id}`)
  await expect(page.getByRole('heading', { name: orderNumberText(placed.order.order_number) })).toBeVisible()

  await page.getByRole('button', { name: 'Boshqa amallar' }).click()
  await page.getByRole('button', { name: "Ustama qo'shish" }).click()
  const surchargeDialog = page.getByRole('dialog', { name: 'Ustama' })
  await surchargeDialog.getByLabel('Qiymat').fill('2000')
  await surchargeDialog.getByLabel('Sabab').fill('E2E rush surcharge')
  const surcharged = page.waitForResponse(
    (response) => response.url().includes('/surcharge') && response.ok(),
  )
  await surchargeDialog.getByRole('button', { name: "Ustama qo'shish" }).click()
  await surcharged
  // The breakdown shows the surcharge as an additive line with its reason.
  await expect(page.getByText('E2E rush surcharge')).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: orderNumberText(placed.order.order_number) })).toBeVisible()
  await expect(page.getByText('E2E rush surcharge')).toBeVisible()
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

  await loginWorkshop(page, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto('/workshop/finance/expenses')
  await expect(page.getByRole('heading', { name: 'Tushum va xarajat' })).toBeVisible()

  await page.getByRole('tab', { name: 'Tushumlar' }).click()
  await page.getByRole('button', { name: '+ Tushum' }).click()
  const incomePanel = page.getByRole('dialog', { name: 'Tushum yozish' })
  await incomePanel
    .getByRole('combobox', { name: 'Buyurtma', exact: true })
    .fill(placed.order.order_number)
  await page
    .getByRole('option', { name: new RegExp(orderNumberText(placed.order.order_number)) })
    .click()
  // QAD-123: picking an order seeds the amount with its remaining balance, and
  // refilling it moved out of the old balance panel onto the amount field as a
  // "Qoldiq" suffix button.
  const incomeAmount = incomePanel.getByLabel("Summa (to'liq yoki qisman)")
  await expect(incomeAmount).not.toHaveValue('')
  await incomeAmount.fill('1000')
  await incomePanel.getByRole('button', { name: 'Qoldiq', exact: true }).click()
  await expect(incomeAmount).not.toHaveValue('1000')
  await incomePanel.getByLabel('Izoh').fill('E2E order payment')
  await incomePanel.getByRole('button', { name: 'Yozish' }).click()
  await expect(page.getByText('E2E order payment')).toBeVisible()

  await page.getByRole('tab', { name: 'Xarajatlar' }).click()
  await page.getByRole('button', { name: '+ Xarajat' }).click()
  const expensePanel = page.getByRole('dialog', { name: 'Xarajat yozish' })
  // QAD-149 gave the expense form a Turi toggle. A standalone expense is one
  // branch of it, so pick it explicitly rather than relying on whichever side
  // happens to be the default (which is «Boshqa xarajat» today).
  await expensePanel.getByRole('radio', { name: 'Boshqa xarajat' }).click()
  await expensePanel.getByLabel('Tavsif').fill('E2E standalone expense')
  await expensePanel.getByLabel("Summa (so'm)").fill('1000')
  await expensePanel.getByRole('button', { name: 'Yozish' }).click()
  await expect(page.getByText('E2E standalone expense')).toBeVisible()

  // `.table-wrap` is `overflow-x: auto`, so it clips on both axes. A row's ⋯
  // panel rendered inside it grew the wrapper's scrollHeight — the focus-on-open
  // then scrolled rows under the opaque sticky header — and was clipped besides.
  // It is teleported out now, so opening it must leave the table exactly where
  // it was and put the panel somewhere fully on screen (QAD-184).
  await page.locator('tbody tr').last().getByRole('button', { name: /amallari/ }).click()
  await expect(page.getByRole('menu')).toBeVisible()
  const geometry = await page.evaluate(() => {
    const wrap = document.querySelector('.table-wrap')!
    const panel = document.querySelector('.mp-action-menu')!.getBoundingClientRect()
    const header = document.querySelector('thead th')!.getBoundingClientRect()
    const firstRow = document.querySelector('tbody tr')!.getBoundingClientRect()
    return {
      wrapScrollTop: wrap.scrollTop,
      rowHiddenUnderHeader: Math.round(header.bottom - firstRow.top),
      panelEscapedTheClip: !wrap.contains(document.querySelector('.mp-action-menu')),
      panelOnScreen:
        panel.top >= 0 &&
        panel.left >= 0 &&
        panel.bottom <= window.innerHeight &&
        panel.right <= window.innerWidth,
    }
  })
  expect(geometry).toEqual({
    wrapScrollTop: 0,
    rowHiddenUnderHeader: 0,
    panelEscapedTheClip: true,
    panelOnScreen: true,
  })
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
  await expectOk(approved)
  const cutting = await assignForCutting(
    request,
    seeded.ownerAccess,
    placed.order.id,
    (await approved.json()).version,
    ownerId,
  )
  expect(cutting.status).toBe('cutting')

  await loginWorkshop(page, seeded.setup.ownerLogin, ownerReadyPassword)
  await page.goto(`/workshop/orders/${placed.order.id}`)
  await expect(page.getByText('Kesilmoqda', { exact: true }).first()).toBeVisible()
  // Revert sits in the header overflow menu.
  await page.getByRole('button', { name: 'Boshqa amallar' }).click()
  await page.getByRole('button', { name: 'tasdiqlangan holatiga qaytarish' }).click()
  const revertDialog = page.getByRole('dialog', { name: 'Buyurtmani qaytarish' })
  await revertDialog.getByLabel('Sabab').fill('E2E revert reason')
  await revertDialog.getByRole('button', { name: 'Ha, qaytarilsin' }).click()
  await expect(page.getByText('Tasdiqlangan', { exact: true }).first()).toBeVisible()

  const freshBeforeConflict = await orderDetail(request, seeded.ownerAccess, placed.order.id)
  const note = await request.patch(`/api/v1/workshop/orders/${placed.order.id}/note`, {
    headers: { Authorization: `Bearer ${seeded.ownerAccess}` },
    data: { note_workshop: `external update ${freshBeforeConflict.version}` },
  })
  await expectOk(note)

  await page.getByRole('button', { name: 'Boshqa amallar' }).click()
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

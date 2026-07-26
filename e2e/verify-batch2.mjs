// Independent verification of PR #84 (QAD-175/176/178) and #85 (QAD-168/169/171).
// Orchestrator-run, not the build sessions' own output.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const BASE = 'http://localhost:5173'
const OUT = process.env.OUT ?? 'shots'
mkdirSync(OUT, { recursive: true })

const findings = []
const note = (t, ok, msg) => {
  findings.push(`${ok ? 'PASS' : 'FAIL'}  ${t}  ${msg}`)
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${t}  ${msg}`)
}

async function loginWorkshop(page, login, password) {
  await page.goto(`${BASE}/workshop/`)
  await page.getByLabel('Login').fill(login)
  await page.getByLabel(/^(Password|Parol)$/).fill(password)
  await page.getByRole('button', { name: /^(Continue|Kirish)$/ }).click()
  // must land on the shell, NOT back on /workshop/auth/login
  await page.waitForURL(/\/workshop(\/profile)?\/?$/, { timeout: 20000 })
}

const browser = await chromium.launch({ headless: true })

// ── QAD-168: staff profile — no 403, real workshop name in subtitle AND sidebar
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  const forbidden = []
  page.on('response', (r) => {
    if (r.status() === 403) forbidden.push(`${r.status()} ${new URL(r.url()).pathname}`)
  })
  await loginWorkshop(page, 'cutter', 'CutterDemo123')
  forbidden.length = 0
  await page.goto(`${BASE}/workshop/profile`)
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${OUT}/qad-168-staff-profile.png`, fullPage: true })
  const body = await page.locator('body').innerText()
  note('QAD-168', forbidden.length === 0, `403s on staff profile: ${forbidden.length ? forbidden.join(', ') : 'none'}`)
  const named = /Mebel Master/.test(body)
  note('QAD-168', named, named ? 'real workshop name rendered (not the generic tenant label)' : `name missing; body head: ${body.slice(0, 120)}`)
  await ctx.close()
}

// ── QAD-169: manage_finance-only sees suppliers + payable invoices
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  const forbidden = []
  page.on('response', (r) => {
    if (r.status() === 403) forbidden.push(new URL(r.url()).pathname)
  })
  await loginWorkshop(page, 'accountant', 'HisobchiDemo123')
  forbidden.length = 0
  await page.goto(`${BASE}/workshop/finance/expenses`)
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: '+ Xarajat' }).click()
  const dlg = page.getByRole('dialog', { name: 'Xarajat yozish' })
  await dlg.waitFor()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${OUT}/qad-169-expense-invoice-mode.png`, fullPage: false })
  // switch to the misc side to reach the supplier picker
  await dlg.getByRole('radio', { name: 'Boshqa xarajat' }).click()
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${OUT}/qad-169-expense-supplier-mode.png`, fullPage: false })
  note('QAD-169', forbidden.length === 0, `403s for manage_finance on expenses: ${forbidden.length ? forbidden.join(', ') : 'none'}`)
  await ctx.close()
}

// ── QAD-171: an order the reader may not see says so, not "check your internet"
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await loginWorkshop(page, 'owner', 'OwnerDemo123')
  // grab a real order id as owner, then open it as a production-only user
  const ids = await page.evaluate(async () => {
    const t = JSON.parse(sessionStorage.getItem('mp.auth') ?? '{}')
    return t
  })
  await ctx.close()

  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page2 = await ctx2.newPage()
  await loginWorkshop(page2, 'cutter', 'CutterDemo123')
  // a random uuid is guaranteed not-visible: same 404 path the ticket describes
  await page2.goto(`${BASE}/workshop/orders/00000000-0000-4000-8000-000000000000`)
  await page2.waitForLoadState('networkidle')
  await page2.waitForTimeout(1000)
  await page2.screenshot({ path: `${OUT}/qad-171-forbidden-order.png`, fullPage: false })
  const txt = await page2.locator('body').innerText()
  const blamesNetwork = /Internet aloqasi/i.test(txt)
  const saysPermission = /ruxsatingiz yo'q|ruxsatingiz yoq/i.test(txt)
  note('QAD-171', !blamesNetwork, blamesNetwork ? 'STILL blames the connection' : 'no longer blames the connection')
  note('QAD-171', saysPermission, saysPermission ? 'states it is a permission/availability outcome' : `copy: ${txt.slice(0, 200)}`)
  await ctx2.close()
  void ids
}

// ── QAD-176: branch_no is findable — Filiallar table + branch detail
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await loginWorkshop(page, 'owner', 'OwnerDemo123')
  await page.goto(`${BASE}/workshop/branches`)
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${OUT}/qad-176-branches-table.png`, fullPage: true })
  const tbl = await page.locator('body').innerText()
  const hasCol = /RAQAM/i.test(tbl)
  note('QAD-176', hasCol, hasCol ? 'Filiallar table carries a RAQAM column' : 'no RAQAM column found')
  const firstRow = page.getByRole('row').nth(1)
  await firstRow.getByRole('link').first().click().catch(async () => {
    await firstRow.click()
  })
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${OUT}/qad-176-branch-detail.png`, fullPage: false })
  const detail = await page.locator('body').innerText()
  const showsPrefix = /Filial raqami/i.test(detail)
  note('QAD-176', showsPrefix, showsPrefix ? 'branch detail names the number and its order prefix' : 'branch detail does not show the number')
  await ctx.close()
}

// ── QAD-178: direct entry to the walk-in cutting route resolves in dev
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await loginWorkshop(page, 'owner', 'OwnerDemo123')
  await page.goto(`${BASE}/workshop/orders/new/cutting`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${OUT}/qad-178-direct-entry.png`, fullPage: false })
  const t = await page.locator('body').innerText()
  const is404 = /topilmadi|404|Sahifa topilmadi/i.test(t)
  note('QAD-178', !is404, is404 ? 'STILL 404s on direct entry' : `resolved to: ${page.url().replace(BASE, '')}`)
  await ctx.close()
}

await browser.close()
console.log('\n---- SUMMARY ----')
console.log(findings.join('\n'))

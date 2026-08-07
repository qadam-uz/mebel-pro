import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  type APIRequestContext,
  type APIResponse,
  type Locator,
  type Page,
} from "@playwright/test";

import { databaseUrl } from "../env";

const execFileAsync = promisify(execFile);

// Re-exported so specs reach the stack's DSN through the helper module they
// already import; `../env` is the single place it is declared.
export { databaseUrl };

export const adminPassword = "AdminPass123";
export const ownerReadyPassword = "OwnerReady123";
export const passwordLabel = /^(Password|Parol)$/;
export const continueButton = /^(Continue|Kirish)$/;

/**
 * A platform dekor — identity only (manufacturer, tur, kod, nomi). It has no
 * thickness, no size and no price: those are a branch fact now. `label` is the
 * server-composed display string; there is no stored name to read.
 */
export interface DekorResponse {
  id: string;
  manufacturer_id: string;
  manufacturer_name: string;
  tur: string;
  kod: string | null;
  nomi: string;
  label: string;
}

/**
 * One dekor in one concrete format, carried by one branch. **This** is the id a
 * stock row, a cutting part and an order item point at — and it is per branch,
 * so one branch's id for a format is not another's.
 */
export interface BranchMaterialResponse {
  id: string;
  branch_id: string;
  dekor_id: string;
  dekor: DekorResponse;
  qalinlik_mm: string;
  uzunlik_mm: number | null;
  eni_mm: number | null;
  kromka_eni_mm: number | null;
  price_tiyin: number;
  price_unset: boolean;
  min_stock: number;
  label: string;
}

/** One (thickness + size) combination to attach. Price/threshold default to 0. */
export interface BranchMaterialFormatInput {
  // A Decimal on the wire — sent as a string so 0.4 can never take a float trip.
  qalinlik_mm: string;
  uzunlik_mm?: number;
  eni_mm?: number;
  kromka_eni_mm?: number;
  price_tiyin?: number;
  min_stock?: number;
}

export interface OrderResponse {
  id: string;
  order_number: string;
  status: string;
  version: number;
}

/**
 * Assert a 2xx response, surfacing the URL, status, and body on failure —
 * a bare ok-is-true assertion reports only `false`, which made CI failures
 * undiagnosable.
 */
export async function expectOk(response: APIResponse) {
  if (!response.ok()) {
    const body = await response.text().catch(() => "<unreadable body>");
    throw new Error(
      `API call failed: ${response.url()} → ${response.status()} ${body.slice(0, 500)}`,
    );
  }
}

/**
 * Escape a value before it goes into a `RegExp` locator. Server-composed labels
 * carry `·`, `×` and run ids, so a raw string is not a safe pattern.
 */
export function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function runId(testInfo: { workerIndex: number }) {
  return `${testInfo.workerIndex}-${Date.now().toString(36).slice(-6)}-${Math.random()
    .toString(36)
    .slice(2, 7)}`;
}

export function phoneFor(id: string, offset: number) {
  let hash = offset;
  for (const char of id) hash = (hash * 33 + char.charCodeAt(0)) % 10_000_000;
  return `+99890${String(hash).padStart(7, "0")}`;
}

export async function seedPlatform(login: string) {
  await execFileAsync(
    "uv",
    [
      "--directory",
      "../backend",
      "run",
      "python",
      "-m",
      "app.cli",
      "seed-platform-user",
      "--login",
      login,
      "--password",
      adminPassword,
      "--full-name",
      "E2E Admin",
      "--phone",
      phoneFor(login, 1),
      "--no-password-reset-required",
    ],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        ENV: "test",
        DATABASE_URL: databaseUrl,
        OTP_DEV_CODES: '["000000"]',
      },
    },
  );
}

export async function platformToken(request: APIRequestContext, login: string) {
  const response = await request.post("/api/v1/auth/platform/login", {
    data: { login, password: adminPassword },
  });
  await expectOk(response);
  return (await response.json()).access_token as string;
}

export async function provisionWorkshop(
  request: APIRequestContext,
  token: string,
  id: string,
) {
  const ownerLogin = `owner-${id}`;
  const ownerPassword = "OwnerTemp123";
  const response = await request.post("/api/v1/platform/workshops", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Order Workshop ${id}`,
      },
      branch: {
        name: `Order Branch ${id}`,
        address: "Tashkent, Test",
        phone: phoneFor(id, 3),
      },
      owner: {
        login: ownerLogin,
      },
      temp_password: ownerPassword,
    },
  });
  await expectOk(response);
  return { ...(await response.json()), ownerLogin, ownerPassword };
}

export async function readyOwnerToken(
  request: APIRequestContext,
  setup: Awaited<ReturnType<typeof provisionWorkshop>>,
) {
  const login = await request.post("/api/v1/auth/workshop/login", {
    data: {
      login: setup.ownerLogin,
      password: setup.ownerPassword,
    },
  });
  await expectOk(login);
  const access = (await login.json()).access_token as string;
  const changed = await request.post("/api/v1/auth/password/change", {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      current_password: setup.ownerPassword,
      new_password: ownerReadyPassword,
    },
  });
  await expectOk(changed);
  return access;
}

export async function createManufacturer(
  request: APIRequestContext,
  token: string,
  name: string,
) {
  const response = await request.post(
    "/api/v1/platform/catalog/manufacturers",
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { name, country: "UZ" },
    },
  );
  await expectOk(response);
  return (await response.json()).id as string;
}

export async function createDekor(
  request: APIRequestContext,
  token: string,
  data: {
    manufacturer_id: string;
    tur: string;
    nomi: string;
    kod?: string | null;
    tolali?: boolean;
    image_file_id?: string | null;
  },
) {
  const response = await request.post("/api/v1/platform/catalog/dekorlar", {
    headers: { Authorization: `Bearer ${token}` },
    data: { tolali: false, ...data },
  });
  await expectOk(response);
  return (await response.json()) as DekorResponse;
}

/**
 * The two platform dekorlar every order flow needs: one panel-shaped (`ldsp`)
 * and one tape (`kromka`). Identity only — the branch decides the formats.
 */
export async function createCatalogDekorlar(
  request: APIRequestContext,
  token: string,
  id: string,
) {
  const manufacturerId = await createManufacturer(
    request,
    token,
    `Order Maker ${id}`,
  );
  const panel = await createDekor(request, token, {
    manufacturer_id: manufacturerId,
    tur: "ldsp",
    kod: `P5-P-${id}`,
    nomi: "White",
  });
  const edge = await createDekor(request, token, {
    manufacturer_id: manufacturerId,
    tur: "kromka",
    kod: `P5-E-${id}`,
    nomi: "White",
  });
  return { manufacturerId, panel, edge };
}

/**
 * Attach one dekor to a branch in one or more o'lchamlar — one transaction, and
 * an o'lcham the branch already carries is *skipped* rather than rejected.
 * Returns the created branch materials in request order, so a caller that asks
 * for two o'lchamlar can name both.
 *
 * The endpoint takes a *batch* (`items`), because the real job is many dekorlar
 * × one o'lcham; this helper is the one-dekor slice of it, which is what most
 * of the suite needs for setup.
 */
export async function carryDekor(
  request: APIRequestContext,
  token: string,
  branchId: string,
  dekorId: string,
  formats: BranchMaterialFormatInput[],
) {
  const response = await request.post(
    `/api/v1/workshop/branches/${branchId}/materials`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { items: [{ dekor_id: dekorId, formats }] },
    },
  );
  await expectOk(response);
  const body = (await response.json()) as {
    created: BranchMaterialResponse[];
    skipped: unknown[];
  };
  // Match each created row back to the format asked for by its own numbers, not
  // by list position: a mis-mapping here is invisible (every id is a plausible
  // uuid) and would silently point the test's stock and orders at another row.
  return formats.map((format) => {
    const row = body.created.find(
      (created) =>
        Number(created.qalinlik_mm) === Number(format.qalinlik_mm) &&
        created.uzunlik_mm === (format.uzunlik_mm ?? null) &&
        created.eni_mm === (format.eni_mm ?? null) &&
        created.kromka_eni_mm === (format.kromka_eni_mm ?? null),
    );
    if (!row) {
      throw new Error(
        `attach returned no row for ${JSON.stringify(format)} — got ${JSON.stringify(body)}`,
      );
    }
    return row;
  });
}

/** The single-format case, which is most of the suite. */
export async function carryOneFormat(
  request: APIRequestContext,
  token: string,
  branchId: string,
  dekorId: string,
  format: BranchMaterialFormatInput,
) {
  const [row] = await carryDekor(request, token, branchId, dekorId, [format]);
  return row;
}

/** The 900×600×18 panel format the order/cutting flows carry. */
export function panelFormat(
  overrides: Partial<BranchMaterialFormatInput> = {},
): BranchMaterialFormatInput {
  return {
    qalinlik_mm: "18",
    uzunlik_mm: 900,
    eni_mm: 600,
    price_tiyin: 250_000,
    min_stock: 1,
    ...overrides,
  };
}

/** The 2×19 tape format the order/cutting flows carry. */
export function edgeFormat(
  overrides: Partial<BranchMaterialFormatInput> = {},
): BranchMaterialFormatInput {
  return {
    qalinlik_mm: "2",
    kromka_eni_mm: 19,
    price_tiyin: 10_000,
    min_stock: 1_000,
    ...overrides,
  };
}

export async function updateBranchPricing(
  request: APIRequestContext,
  token: string,
  branchId: string,
) {
  const response = await request.put(
    `/api/v1/workshop/branches/${branchId}/pricing`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { cutting_rate_tiyin: 50_000, edge_banding_rate_tiyin: 20_000 },
    },
  );
  await expectOk(response);
}

export async function stockIn(
  request: APIRequestContext,
  token: string,
  branchId: string,
  branchMaterialId: string,
  quantity: number,
) {
  const response = await request.post(
    `/api/v1/workshop/branches/${branchId}/stock-in`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        branch_material_id: branchMaterialId,
        quantity,
        unit_price_tiyin: 25_000_000,
        supplier: { name: `E2E Supplier ${branchId.slice(0, 6)}` },
        note: "Order E2E stock",
      },
    },
  );
  await expectOk(response);
}

/**
 * A workshop+branch with pricing, two carried branch materials, and stock —
 * everything a client needs to optimize a draft and place an order. Returns the
 * IDs + an owner token (for driving workshop-side transitions) and the client
 * phone to log in.
 *
 * `panel` / `edge` are **branch materials**, not dekorlar: that is the id a part,
 * a stock row and an order item resolve to. The dekorlar behind them come back
 * as `panelDekor` / `edgeDekor` for the screens that show identity alone.
 */
export async function seedOrderableBranch(
  request: APIRequestContext,
  id: string,
) {
  const adminLogin = `cb-admin-${id}`;
  await seedPlatform(adminLogin);
  const adminAccess = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, adminAccess, id);
  const ownerAccess = await readyOwnerToken(request, setup);
  const {
    panel: panelDekor,
    edge: edgeDekor,
  } = await createCatalogDekorlar(request, adminAccess, id);
  const branchId = setup.branch.id as string;
  await updateBranchPricing(request, ownerAccess, branchId);
  const panel = await carryOneFormat(
    request,
    ownerAccess,
    branchId,
    panelDekor.id,
    panelFormat(),
  );
  const edge = await carryOneFormat(
    request,
    ownerAccess,
    branchId,
    edgeDekor.id,
    edgeFormat(),
  );
  await stockIn(request, ownerAccess, branchId, panel.id, 5);
  await stockIn(request, ownerAccess, branchId, edge.id, 10_000);
  return { setup, ownerAccess, branchId, panelDekor, edgeDekor, panel, edge };
}

export async function clientTokenViaApi(
  request: APIRequestContext,
  phone: string,
  name: string,
) {
  const requested = await request.post("/api/v1/auth/client/otp/request", {
    data: { phone },
  });
  await expectOk(requested);
  const verified = await request.post("/api/v1/auth/client/otp/verify", {
    data: { phone, code: "000000", name },
  });
  await expectOk(verified);
  return (await verified.json()).access_token as string;
}

/**
 * Drive the full draft → optimize → place flow through the API so a UI test can
 * start from a real placed order. Returns the order (with version) and a fresh
 * client token bound to `phone`.
 */
export async function placeClientOrderViaApi(
  request: APIRequestContext,
  opts: {
    phone: string;
    name: string;
    branchId: string;
    panelId: string;
    edgeId: string;
  },
) {
  const clientToken = await clientTokenViaApi(request, opts.phone, opts.name);
  const auth = { Authorization: `Bearer ${clientToken}` };

  const draft = await request.post("/api/v1/client/cutting-drafts", {
    headers: auth,
  });
  await expectOk(draft);
  const draftId = (await draft.json()).id as string;

  const patched = await request.patch(
    `/api/v1/client/cutting-drafts/${draftId}`,
    {
      headers: auth,
      data: {
        preferred_branch_id: opts.branchId,
        parts_snapshot: [
          {
            part_ref: "cb-part",
            material_id: opts.panelId,
            material_source: "shop",
            length_mm: 260,
            width_mm: 180,
            quantity: 2,
            edge_top: { material_id: opts.edgeId, source: "shop" },
            edge_bottom: null,
            edge_left: { material_id: opts.edgeId, source: "shop" },
            edge_right: null,
          },
        ],
      },
    },
  );
  await expectOk(patched);

  const optimized = await request.post(
    `/api/v1/client/cutting-drafts/${draftId}/optimize`,
    { headers: auth },
  );
  await expectOk(optimized);

  const placed = await request.post("/api/v1/client/orders", {
    headers: auth,
    data: {
      draft_id: draftId,
      branch_id: opts.branchId,
      contact_name: opts.name,
      contact_phone: "+998901555222",
      note_client: "E2E order",
    },
  });
  expect(placed.status()).toBe(201);
  return { order: (await placed.json()) as OrderResponse, clientToken };
}

export async function applyWorkshopDiscount(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
  version: number,
) {
  const response = await request.post(
    `/api/v1/workshop/orders/${orderId}/discount`,
    {
      headers: { Authorization: `Bearer ${ownerAccess}` },
      data: { version, kind: "fixed", value: 30_000, reason: "E2E promo" },
    },
  );
  await expectOk(response);
  return (await response.json()).version as number;
}

export async function approveWorkshopOrder(
  request: APIRequestContext,
  ownerAccess: string,
  orderId: string,
  version: number,
) {
  const response = await request.post(
    `/api/v1/workshop/orders/${orderId}/approve`,
    {
      headers: { Authorization: `Bearer ${ownerAccess}` },
      data: { version },
    },
  );
  await expectOk(response);
  return (await response.json()).version as number;
}

/** Log a client in through the UI (OTP). Skips the name step for existing clients. */
export async function loginClient(page: Page, phone: string, name?: string) {
  await page.goto("/client/auth/login");
  await page.getByLabel("Telefon raqami").fill(phone);
  await page.getByRole("button", { name: "Kod yuborish" }).click();
  await page.getByLabel("Tasdiqlash kodi").fill("000000");
  await page.getByRole("button", { name: "Tasdiqlash" }).click();
  const nameField = page.getByLabel("Ismingiz");
  if (
    await nameField
      .waitFor({ state: "visible", timeout: 2_000 })
      .then(() => true)
      .catch(() => false)
  ) {
    await nameField.fill(name ?? "Order Client");
    await page.getByRole("button", { name: "Davom etish" }).click();
  }
  await expect(page).toHaveURL(/\/client\/c$/);
}

/**
 * Click a control that opens a PDF and assert it opened a **tab**, not a download
 * (QAD-160).
 *
 * The obvious assertion — that the popup's URL is the `blob:` object URL — cannot
 * be made here: headless Chromium ships no PDF viewer, so navigating the tab to a
 * PDF blob is abandoned and `popup.url()` stays `about:blank`. It resolves to
 * `blob:…` in a headed browser. So this asserts what headless *can* see and what
 * the ticket actually claims: a new tab opened, the authed PDF request succeeded,
 * and nothing was written to the download directory.
 */
export async function expectPdfOpensInTab(
  page: Page,
  trigger: Locator,
  pdfPathPattern: RegExp,
) {
  const popupPromise = page.waitForEvent("popup");
  const responsePromise = page.waitForResponse(
    (response) =>
      pdfPathPattern.test(new URL(response.url()).pathname) &&
      response.request().method() === "GET",
  );
  let downloaded = false;
  page.once("download", () => {
    downloaded = true;
  });

  await trigger.click();

  const popup = await popupPromise;
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("application/pdf");
  expect(popup.isClosed()).toBe(false);
  expect(downloaded).toBe(false);
  return popup;
}

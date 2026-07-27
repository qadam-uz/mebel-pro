import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  type APIRequestContext,
  type APIResponse,
  type Locator,
  type Page,
} from "@playwright/test";

const execFileAsync = promisify(execFile);

export const databaseUrl =
  "postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e";
export const adminPassword = "AdminPass123";
export const ownerReadyPassword = "OwnerReady123";
export const passwordLabel = /^(Password|Parol)$/;
export const continueButton = /^(Continue|Kirish)$/;

export interface MaterialResponse {
  id: string;
  name: string;
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

export async function createCatalogMaterials(
  request: APIRequestContext,
  token: string,
  id: string,
) {
  const manufacturer = await request.post(
    "/api/v1/platform/catalog/manufacturers",
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { name: `Order Maker ${id}`, country: "UZ" },
    },
  );
  await expectOk(manufacturer);
  const manufacturerId = (await manufacturer.json()).id as string;

  const panel = await request.post("/api/v1/platform/catalog/materials", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "panel",
      manufacturer_id: manufacturerId,
      type: "dsp",
      thickness_mm: "18",
      color: "White",
      decor_code: `P5-P-${id}`,
      panel_length_mm: 900,
      panel_width_mm: 600,
      grain_direction: false,
    },
  });
  await expectOk(panel);

  const edge = await request.post("/api/v1/platform/catalog/materials", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "edge",
      manufacturer_id: manufacturerId,
      thickness_mm: "2",
      edge_width_mm: 19,
      color: "White",
      decor_code: `P5-E-${id}`,
    },
  });
  await expectOk(edge);

  return {
    panel: (await panel.json()) as MaterialResponse,
    edge: (await edge.json()) as MaterialResponse,
  };
}

export async function addBranchMaterial(
  request: APIRequestContext,
  token: string,
  branchId: string,
  materialId: string,
  priceTiyin: number,
  minStock: number,
) {
  const response = await request.post(
    `/api/v1/workshop/branches/${branchId}/materials`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { material_id: materialId, price_tiyin: priceTiyin, min_stock: minStock },
    },
  );
  await expectOk(response);
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
  materialId: string,
  quantity: number,
) {
  const response = await request.post(
    `/api/v1/workshop/branches/${branchId}/stock-in`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        material_id: materialId,
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
 * A workshop+branch with pricing, two carried materials, and stock — everything a
 * client needs to optimize a draft and place an order. Returns the IDs + an owner
 * token (for driving workshop-side transitions) and the client phone to log in.
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
  const { panel, edge } = await createCatalogMaterials(request, adminAccess, id);
  const branchId = setup.branch.id as string;
  await updateBranchPricing(request, ownerAccess, branchId);
  await addBranchMaterial(request, ownerAccess, branchId, panel.id, 250_000, 1);
  await addBranchMaterial(request, ownerAccess, branchId, edge.id, 10_000, 1_000);
  await stockIn(request, ownerAccess, branchId, panel.id, 5);
  await stockIn(request, ownerAccess, branchId, edge.id, 10_000);
  return { setup, ownerAccess, branchId, panel, edge };
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

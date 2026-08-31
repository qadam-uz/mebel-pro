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
 * A platform decor — a PATTERN: manufacturer, code, name, image, grain. It has
 * no substrate, no thickness, no size and no price. What it physically is
 * belongs to its `decor_formats`; `label` is the server-composed display
 * string.
 */
export interface DecorResponse {
  id: string;
  manufacturer_id: string;
  manufacturer_name: string;
  code: string | null;
  name: string;
  label: string;
  format_count: number;
}

/**
 * One concrete product of a decor — platform-owned and immutable. A branch
 * picks from these; it cannot invent one.
 */
export interface DecorFormatResponse {
  id: string;
  decor_id: string;
  type: string;
  thickness_mm: string;
  length_mm: number | null;
  width_mm: number | null;
  tape_width_mm: number | null;
  finished_sides: number | null;
  label: string;
}

/**
 * One platform format this branch has decided to carry. **This** is the id a
 * stock row, a cutting part and an order item point at — and it is per branch,
 * so one branch's id for a format is not another's.
 */
export interface BranchMaterialResponse {
  id: string;
  branch_id: string;
  decor_format_id: string;
  decor_format: DecorFormatResponse;
  decor: DecorResponse;
  price_tiyin: number;
  price_unset: boolean;
  min_stock: number;
  label: string;
}

/** The body of `POST /platform/catalog/decors/{id}/formats`. */
export interface DecorFormatInput {
  type: string;
  // A Decimal on the wire — sent as a string so 0.4 can never take a float trip.
  thickness_mm: string;
  length_mm?: number;
  width_mm?: number;
  tape_width_mm?: number;
  finished_sides?: number;
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

export async function createDecor(
  request: APIRequestContext,
  token: string,
  data: {
    manufacturer_id: string;
    name: string;
    code?: string | null;
    has_grain?: boolean;
    image_file_id?: string | null;
  },
) {
  const response = await request.post("/api/v1/platform/catalog/decors", {
    headers: { Authorization: `Bearer ${token}` },
    data: { has_grain: false, ...data },
  });
  await expectOk(response);
  return (await response.json()) as DecorResponse;
}

/**
 * Add one format to a decor. Platform-only: a branch picks from what exists and
 * cannot create one, which is the whole point of the format reshape.
 */
export async function createDecorFormat(
  request: APIRequestContext,
  token: string,
  decorId: string,
  format: DecorFormatInput,
) {
  const response = await request.post(
    `/api/v1/platform/catalog/decors/${decorId}/formats`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: format,
    },
  );
  await expectOk(response);
  return (await response.json()) as DecorFormatResponse;
}

/**
 * The two platform products every order flow needs: one panel-shaped (`ldsp`)
 * and one tape (`kromka`), each as a decor PLUS the format the branch will
 * carry. Two decors rather than one so the suite keeps exercising the
 * cross-decor case; a board and its matching kromka may now share one decor.
 */
export async function createCatalogDecors(
  request: APIRequestContext,
  token: string,
  id: string,
) {
  const manufacturerId = await createManufacturer(
    request,
    token,
    `Order Maker ${id}`,
  );
  const panelDecor = await createDecor(request, token, {
    manufacturer_id: manufacturerId,
    code: `P5-P-${id}`,
    name: "White",
  });
  const edgeDecor = await createDecor(request, token, {
    manufacturer_id: manufacturerId,
    code: `P5-E-${id}`,
    name: "White",
  });
  const panelFmt = await createDecorFormat(
    request,
    token,
    panelDecor.id,
    panelFormat(),
  );
  const edgeFmt = await createDecorFormat(
    request,
    token,
    edgeDecor.id,
    edgeFormat(),
  );
  return {
    manufacturerId,
    panel: { ...panelDecor, format: panelFmt },
    edge: { ...edgeDecor, format: edgeFmt },
  };
}

/**
 * Have a branch carry platform formats — one transaction, and a format the
 * branch already carries is *skipped* rather than rejected.
 *
 * The endpoint takes a flat batch of format ids: the branch no longer invents
 * formats, so there is nothing per-decor left to nest.
 */
export async function carryFormats(
  request: APIRequestContext,
  token: string,
  branchId: string,
  items: { decor_format_id: string; price_tiyin?: number; min_stock?: number }[],
) {
  const response = await request.post(
    `/api/v1/workshop/branches/${branchId}/materials`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { items },
    },
  );
  await expectOk(response);
  const body = (await response.json()) as {
    created: BranchMaterialResponse[];
    skipped: string[];
  };
  // Match each created row back to the format asked for by ID, not by list
  // position: a mis-mapping here is invisible (every id is a plausible uuid)
  // and would silently point the test's stock and orders at another row.
  return items.map((item) => {
    const row = body.created.find(
      (created) => created.decor_format_id === item.decor_format_id,
    );
    if (!row) {
      throw new Error(
        `attach returned no row for ${JSON.stringify(item)} — got ${JSON.stringify(body)}`,
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
  decorFormatId: string,
  numbers: { price_tiyin?: number; min_stock?: number } = {},
) {
  const [row] = await carryFormats(request, token, branchId, [
    { decor_format_id: decorFormatId, ...numbers },
  ]);
  return row;
}

/** The 900×600×18 panel format the order/cutting flows carry. */
export function panelFormat(
  overrides: Partial<DecorFormatInput> = {},
): DecorFormatInput {
  return {
    type: "ldsp",
    thickness_mm: "18",
    length_mm: 900,
    width_mm: 600,
    // Required for the board types, and the two-sided sheet is the norm.
    finished_sides: 2,
    ...overrides,
  };
}

/** The 2×19 tape format the order/cutting flows carry. */
export function edgeFormat(
  overrides: Partial<DecorFormatInput> = {},
): DecorFormatInput {
  return {
    type: "kromka",
    thickness_mm: "2",
    tape_width_mm: 19,
    ...overrides,
  };
}

/** The price + threshold a carried panel gets in most of the suite. */
export const panelNumbers = { price_tiyin: 250_000, min_stock: 1 };
/** The price + threshold a carried tape gets in most of the suite. */
export const edgeNumbers = { price_tiyin: 10_000, min_stock: 1_000 };

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
 * Put a branch on the full per-stage production flow.
 *
 * A branch is born `simple` (orders.md — that is the adoption default), where
 * the whole spine closes with one **Tayyor** tap and the per-step endpoints
 * answer `409 simple_mode_active`. Suites that drive assignment, the two starts,
 * the per-stage completions or the Kesish/Krom sidebar entries have to ask for
 * that surface explicitly.
 */
export async function setBranchProductionMode(
  request: APIRequestContext,
  ownerToken: string,
  branchId: string,
  mode: "simple" | "full",
) {
  const response = await request.patch(`/api/v1/workshop/branches/${branchId}`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: { production_mode: mode },
  });
  await expectOk(response);
}

/**
 * A workshop+branch with pricing, two carried branch materials, and stock —
 * everything a client needs to optimize a draft and place an order. Returns the
 * IDs + an owner token (for driving workshop-side transitions) and the client
 * phone to log in.
 *
 * The branch is switched to **full** production mode: every suite built on this
 * fixture asserts the per-stage surfaces (assignment, starts, the station
 * sidebar), which a simple-mode branch deliberately does not offer.
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
  const { panel: panelDecor, edge: edgeDecor } = await createCatalogDecors(
    request,
    adminAccess,
    id,
  );
  const branchId = setup.branch.id as string;
  await updateBranchPricing(request, ownerAccess, branchId);
  await setBranchProductionMode(request, ownerAccess, branchId, "full");
  const panel = await carryOneFormat(
    request,
    ownerAccess,
    branchId,
    panelDecor.format.id,
    panelNumbers,
  );
  const edge = await carryOneFormat(
    request,
    ownerAccess,
    branchId,
    edgeDecor.format.id,
    edgeNumbers,
  );
  await stockIn(request, ownerAccess, branchId, panel.id, 5);
  await stockIn(request, ownerAccess, branchId, edge.id, 10_000);
  return { setup, ownerAccess, branchId, panelDecor, edgeDecor, panel, edge };
}

/**
 * A client access token through the bot handshake, without a bot.
 *
 * The three calls are exactly the ones the login card makes — mint, confirm,
 * poll — with `TELEGRAM_LOGIN_DEV_MODE`'s dev-confirm standing in for the
 * Telegram conversation. The token is passed explicitly: the route falls back to
 * the newest pending handshake, which under `fullyParallel` would be another
 * test's.
 */
export async function clientTokenViaApi(
  request: APIRequestContext,
  phone: string,
  name: string,
) {
  const issued = await request.post("/api/v1/auth/client/telegram/token");
  await expectOk(issued);
  const handshake = (await issued.json()) as {
    token: string;
    poll_secret: string;
  };
  await devConfirmLogin(request, handshake.token, phone, name);
  const polled = await request.post("/api/v1/auth/client/telegram/poll", {
    data: { poll_secret: handshake.poll_secret },
  });
  await expectOk(polled);
  return (await polled.json()).access_token as string;
}

/** Stand in for the bot: confirm one pending handshake as `phone`. */
export async function devConfirmLogin(
  request: APIRequestContext,
  token: string,
  phone: string,
  name: string,
) {
  const confirmed = await request.post(
    "/api/v1/auth/client/telegram/dev-confirm",
    { data: { token, phone, name } },
  );
  await expectOk(confirmed);
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

/** The deep link the desktop card renders beside the QR — where the token rides. */
export const telegramDeepLink =
  /^(Havolani Telegram'da ochish|Открыть ссылку в Telegram)$/;

/**
 * Log a client in through the UI (Telegram bot handshake).
 *
 * The card mints a handshake and polls it; the token is read off the rendered
 * deep link — the same string the QR encodes — and confirmed through the
 * dev-confirm route in the bot's place. Registration happens inside the bot, so
 * there is no name step on screen: the name goes with the confirm.
 */
export async function loginClient(page: Page, phone: string, name?: string) {
  await page.goto("/client/auth/login");
  const link = page.getByRole("link", { name: telegramDeepLink });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  const token = new URL(href ?? "").searchParams.get("start");
  expect(token, `no ?start= token in the deep link ${href}`).toBeTruthy();
  await devConfirmLogin(
    page.request,
    token as string,
    phone,
    name ?? "Order Client",
  );
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

/**
 * Tick one dekor in the attach sheet's step 1.
 *
 * Narrow to this run's dekor first: the picker lists every active dekor on the
 * platform, 100 to a page (`BranchMaterialAttachSheet.vue`), so rows seeded by
 * the other workers push ours off page one and the checkbox never renders.
 * Searching is also what a real operator does in a catalog this size.
 *
 * The suite recreates its database per run, so a clean machine only has to
 * survive one run's worth of seeding. It grows without bound instead when a
 * host Postgres shadows the container on :5432: the recreate runs through
 * `compose exec` and lands in the container, while alembic, the backend and the
 * seeding CLI all connect to `localhost` and land on the host — see the trap in
 * `e2e/AGENTS.md`. Either way the fix is the same, which is why it is here and
 * not in the environment.
 */
export async function tickDecor(
  pickStep: Locator,
  decor: { code?: string | null; name?: string; label: string },
) {
  await pickStep.getByLabel("Qidirish").fill(decor.code ?? decor.name ?? decor.label);
  await pickStep.getByRole("checkbox", { name: new RegExp(escapeRegExp(decor.label)) }).check();
}

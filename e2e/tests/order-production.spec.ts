import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import {
  carryOneFormat,
  createCatalogDecors,
  databaseUrl,
  edgeNumbers,
  devConfirmLogin,
  escapeRegExp,
  expectOk,
  loginClient,
  panelNumbers,
  setBranchProductionMode,
  type BranchMaterialResponse,
} from "./helpers";

const execFileAsync = promisify(execFile);
const adminPassword = "AdminPass123";
const ownerReadyPassword = "OwnerReady123";
const passwordLabel = /^(Password|Parol)$/;
const continueButton = /^(Continue|Kirish)$/;

interface TokenResponse {
  access_token: string;
}

interface CuttingDraftResponse {
  id: string;
  chosen_result_id: string | null;
}

// The full client-places → workshop-completes lifecycle (cutting editor +
// optimise, then the Kesish/Krom station terminal) is the heaviest flow in the
// suite and sits right on the old 90s budget; give it headroom for slower CI.
test.setTimeout(150_000);

function runId(testInfo: { workerIndex: number }) {
  return `${testInfo.workerIndex}-${Date.now().toString(36).slice(-6)}-${Math.random()
    .toString(36)
    .slice(2, 7)}`;
}

function phoneFor(id: string, offset: number) {
  let hash = offset;
  for (const char of id) hash = (hash * 33 + char.charCodeAt(0)) % 10_000_000;
  return `+99890${String(hash).padStart(7, "0")}`;
}

async function seedPlatform(login: string) {
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

async function platformToken(request: APIRequestContext, login: string) {
  const response = await request.post("/api/v1/auth/platform/login", {
    data: { login, password: adminPassword },
  });
  await expectOk(response);
  return (await response.json()).access_token as string;
}

async function provisionWorkshop(
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

async function readyOwnerToken(
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

/**
 * The branch's carried formats. A dekor is platform identity; the panel and the
 * tape a part points at are **branch materials** — one dekor in one format,
 * carried by this branch.
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
  );
  const panel = await carryOneFormat(
    request,
    ownerToken,
    branchId,
    panelDecor.format.id,
    panelNumbers,
  );
  const edge = await carryOneFormat(
    request,
    ownerToken,
    branchId,
    edgeDecor.format.id,
    edgeNumbers,
  );
  return { panelDecor, edgeDecor, panel, edge };
}

async function updateBranchPricing(
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

async function stockIn(
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

// The three calls the login card makes, with dev-confirm standing in for the bot.
async function clientToken(request: APIRequestContext, phone: string, name: string) {
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
  return (await polled.json()) as TokenResponse;
}

async function optimizedDraftWithoutPricing(
  request: APIRequestContext,
  token: string,
  branchId: string,
  panel: BranchMaterialResponse,
) {
  const created = await request.post("/api/v1/client/cutting-drafts", {
    headers: { Authorization: `Bearer ${token}` },
  });
  await expectOk(created);
  const draft = (await created.json()) as CuttingDraftResponse;

  const patched = await request.patch(
    `/api/v1/client/cutting-drafts/${draft.id}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        preferred_branch_id: branchId,
        parts_snapshot: [
          {
            part_ref: `price-${draft.id.slice(0, 8)}`,
            material_id: panel.id,
            material_source: "shop",
            length_mm: 260,
            width_mm: 180,
            quantity: 1,
            edge_top: null,
            edge_bottom: null,
            edge_left: null,
            edge_right: null,
          },
        ],
      },
    },
  );
  await expectOk(patched);

  const optimized = await request.post(
    `/api/v1/client/cutting-drafts/${draft.id}/optimize`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  await expectOk(optimized);
  const result = (await optimized.json()) as CuttingDraftResponse;
  expect(result.chosen_result_id).not.toBeNull();
  return result;
}

async function loginWorkshop(
  page: Page,
  login: string,
  password: string,
  baseUrl = "",
) {
  await page.goto(`${baseUrl}/workshop/`);
  await page.getByLabel("Login").fill(login);
  await page.getByLabel(passwordLabel).fill(password);
  await page.getByRole("button", { name: continueButton }).click();
  await expect(page).toHaveURL(/\/workshop\/?$/);
}

async function chooseOption(
  page: Page,
  buttonName: RegExp,
  optionName: RegExp,
) {
  await page.getByRole("combobox", { name: buttonName }).click();
  await page.getByRole("option", { name: optionName }).click();
}

/**
 * Pick a material in the client's decor-first picker (SPEC_CLIENT_UX_MVP §7.3).
 * One row per DECOR; this branch carries the decor in a single format, so the
 * decor row itself is the choice and no format list appears.
 */
async function chooseMaterial(page: Page, dekorLabel: string) {
  const sheet = page.getByRole("dialog", { name: "Material tanlang" });
  await sheet
    .getByRole("button", { name: new RegExp(escapeRegExp(dekorLabel)) })
    .click();
  await expect(sheet).toBeHidden();
}

/**
 * Band the top and bottom of the first part (§7.1).
 *
 * On the client the tape DECOR belongs to the material group and only the
 * thickness is the side's: the row's kromka cell selects the row and opens the
 * docked card, whose group line either already names the branch's tape in the
 * board's colour or asks for one. No per-part tape list, no pattern pair.
 */
async function chooseEdgeBanding(page: Page) {
  await page.getByRole("button", { name: "Kromka tomonlari", exact: true }).click();
  const panel = page.getByRole("region", { name: "Kromka" });
  await expect(panel).toBeVisible();

  // The gate: a board decor the branch has no matching tape for asks for a
  // colour before any side can be banded.
  const pickTape = panel.getByRole("button", {
    name: /rangi mos lentani tanlang/,
  });
  if (await pickTape.isVisible()) {
    await pickTape.click();
    const sheet = page.getByRole("dialog", {
      name: "Rangi mos kromkani tanlang",
    });
    await sheet.getByRole("radio").first().click();
    await sheet.getByRole("button", { name: "Tanlash" }).click();
    await expect(sheet).toBeHidden();
  }
  await expect(panel.getByText(/^Kromka:/)).toBeVisible();

  await panel.getByRole("button", { name: /^Yuqori/ }).click();
  await panel.getByRole("button", { name: /^Pastki/ }).click();
}

test("client places an order and workshop completes it through production queues", async ({
  browser,
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `p5-admin-${id}`;
  const clientPhone = phoneFor(id, 40);
  await seedPlatform(adminLogin);
  const adminAccess = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, adminAccess, id);
  const ownerAccess = await readyOwnerToken(request, setup);
  const branchId = setup.branch.id as string;
  await updateBranchPricing(request, ownerAccess, branchId);
  // This spec walks the full per-stage choreography — assignment, the two
  // starts, both station terminals. A branch is born `simple` (orders.md), where
  // those endpoints answer `409 simple_mode_active` and the Kesish/Krom sidebar
  // entries are hidden, so the surface under test has to be asked for.
  await setBranchProductionMode(request, ownerAccess, branchId, "full");
  const { panelDecor, panel, edge } = await carriedMaterials(
    request,
    adminAccess,
    ownerAccess,
    branchId,
    id,
  );
  await stockIn(request, ownerAccess, branchId, panel.id, 5);
  await stockIn(request, ownerAccess, branchId, edge.id, 10_000);

  await loginClient(page, clientPhone, `Order Client ${id}`);
  const branchesLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes("/api/v1/client/branch-options") &&
      response.ok(),
  );
  // Fresh DB → empty home (first-run), so the create CTA is the centred
  // "Yangi chizma" in the empty state; the header button only shows with content.
  await page.getByRole("button", { name: "Yangi chizma" }).click();
  // CB-defer-draft: the editor opens unsaved at `/cutting/new`; the persisted
  // draft (with an id in the URL) is created only on the first optimise below.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/new$/);
  await expect(
    page.getByRole("heading", { name: "Chizma", exact: true }),
  ).toBeVisible();
  await branchesLoaded;

  // Decision 17: the editor never raises a branch picker of its own — the
  // branch is settled before it opens. An un-pinned client who reaches
  // `/c/cutting/new` anyway gets the recovery prompt.
  await page.getByRole("button", { name: "Filial tanlash" }).click();
  await page
    .getByRole("button", { name: new RegExp(`Order Branch ${id}`) })
    .click();
  // Decision 16, the naming rule: a workshop with one branch is named by the
  // workshop alone — a branch name is never shown on its own.
  await expect(page.getByText(`Order Workshop ${id}`).first()).toBeVisible();

  // A new compact entry starts by selecting its material; that selection creates
  // the first editable row in the material group.
  await page.getByRole("button", { name: "+ Material", exact: true }).click();
  await chooseMaterial(page, panelDecor.label);
  await page.getByLabel("Uzunlik millimetr").fill("260");
  await page.getByLabel("Kenglik millimetr").fill("180");
  await page.getByLabel("Soni").fill("2");
  await chooseEdgeBanding(page);
  await page.getByRole("button", { name: "Hisoblash" }).click();

  // First optimise persists the draft and hands off to the standalone result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/);
  await expect(page.getByRole("heading", { name: "Kesish natijasi" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Buyurtma berish" })).toBeVisible();
  await page.getByRole("link", { name: "Buyurtma berish" }).click();

  await expect(
    page.getByRole("heading", { name: "Buyurtmani tasdiqlash", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText(`Order Workshop ${id}`).first()).toBeVisible();
  await expect(page.getByText("Jami").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Buyurtmani tasdiqlash" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Buyurtmani tasdiqlash" }).click();

  await expect(page.getByText("Buyurtma berildi")).toBeVisible();
  // Six random platform-wide digits, printed as `№ 482 917` (sales.md).
  // The workshop app shows the same formatted string, so the one scraped
  // here is what every later locator matches on both sides.
  const numberPattern = /\u2116\u2009\d{3}\u2009\d{3}/;
  const orderText = await page.getByText(numberPattern).first().textContent();
  const orderNumber = orderText?.match(numberPattern)?.[0];
  expect(orderNumber).toBeTruthy();

  const baseUrl = new URL(page.url()).origin;
  const workshopContext = await browser.newContext();
  const workshopPage = await workshopContext.newPage();
  await loginWorkshop(
    workshopPage,
    setup.ownerLogin,
    ownerReadyPassword,
    baseUrl,
  );
  await workshopPage.getByRole("link", { name: "Buyurtmalar" }).first().click();
  await expect(
    workshopPage.getByRole("heading", { name: "Buyurtmalar" }),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Jadval" }).click();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  const workshopOrderRow = workshopPage.getByRole("row", {
    name: new RegExp(orderNumber as string),
  });
  // The table row itself opens the order detail (status actions now live only
  // on the detail page); click the order-number cell to navigate.
  await workshopOrderRow.getByText(orderNumber as string).click();

  await expect(
    workshopPage.getByRole("heading", { name: orderNumber as string }),
  ).toBeVisible();
  const workshopOrderUrl = workshopPage.url();
  await workshopPage.getByRole("button", { name: "Tasdiqlash" }).click();
  await expect(
    workshopPage.getByText("Tasdiqlangan", { exact: true }).first(),
  ).toBeVisible();

  // Picking a worker applies the assignment immediately — no separate save tap.
  const cutterAssigned = workshopPage.waitForResponse(
    (response) => response.url().includes("/assign") && response.ok(),
  );
  await chooseOption(workshopPage, /Kesuvchi/, new RegExp(setup.ownerLogin));
  await cutterAssigned;
  // Assignment is metadata — the order stays confirmed (queued in the
  // master's station) until the job is actually started. The edger slot may
  // stay open: cutting starts on a cutter-only assignment; the edger gate
  // lives at the banding start.
  await expect(
    workshopPage.getByRole("button", { name: "Kesishni boshlash" }),
  ).toBeEnabled();
  await expect(
    workshopPage.getByText("Tasdiqlangan", { exact: true }).first(),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Kesishni boshlash" }).click();
  await expect(
    workshopPage.getByText("Kesilmoqda", { exact: true }).first(),
  ).toBeVisible();

  // The open edger slot carries a nudge while the saw runs; filling it mid-cut
  // is the supported path (the edger locks only once banding starts).
  await expect(
    workshopPage.getByText(/kromka boshlanishidan oldin tanlang/i),
  ).toBeVisible();
  const edgerAssigned = workshopPage.waitForResponse(
    (response) => response.url().includes("/assign") && response.ok(),
  );
  await chooseOption(
    workshopPage,
    /Kromka yopishtiruvchi/,
    new RegExp(setup.ownerLogin),
  );
  await edgerAssigned;

  // The station terminal: the started job sits pinned as "Hozirgi ish" with
  // the worker's Tugatdim action behind a plain success confirm.
  await workshopPage.getByRole("link", { name: "Kesish" }).first().click();
  await expect(
    workshopPage.getByRole("heading", { name: "Kesish", exact: true }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  const cuttingDone = workshopPage.waitForResponse(
    (response) => response.url().includes("/cutting-done") && response.ok(),
  );
  await workshopPage.getByRole("button", { name: /Tugatdim$/ }).click();
  await workshopPage.getByRole("button", { name: /Ha, tugatdim/ }).click();
  await cuttingDone;

  // The job hands off to the Krom station queued-but-not-started: the edger
  // (here: the owner on-behalf) taps Boshlash — one tap starts the job and
  // lands on its Chizma sheet — then finishes it from the sheet.
  await workshopPage.getByRole("link", { name: "Krom" }).first().click();
  await expect(
    workshopPage.getByRole("heading", { name: "Krom", exact: true }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  const bandingStarted = workshopPage.waitForResponse(
    (response) => response.url().includes("/start-banding") && response.ok(),
  );
  await workshopPage
    .getByRole("button", { name: "Boshlash", exact: true })
    .click();
  await bandingStarted;
  await expect(workshopPage).toHaveURL(/\/workshop\/production\/[^/]+$/);
  const bandingDone = workshopPage.waitForResponse(
    (response) => response.url().includes("/banding-done") && response.ok(),
  );
  await workshopPage.getByRole("button", { name: /Tugatdim$/ }).click();
  await workshopPage.getByRole("button", { name: /Ha, tugatdim/ }).click();
  await bandingDone;
  // Completing from the sheet returns to the station queue.
  await expect(workshopPage).toHaveURL(/\/workshop\/banding$/);

  await workshopPage.goto(workshopOrderUrl);
  await expect(
    workshopPage.getByText("Tayyor", { exact: true }).first(),
  ).toBeVisible();
  const collected = workshopPage.waitForResponse(
    (response) => response.url().includes("/mark-collected") && response.ok(),
  );
  await workshopPage.getByRole("button", { name: "Mijoz olib ketdi" }).click();
  // Marking collected is final/irreversible, so it now goes through a
  // confirmation dialog — confirm it to fire the request.
  await workshopPage
    .getByRole("button", { name: "Ha, topshirildi" })
    .click();
  await collected;
  await expect(
    workshopPage.getByText("Olib ketildi", { exact: true }).first(),
  ).toBeVisible();
  await workshopContext.close();

  await page.goto("/client/c/orders");
  await expect(page.getByText(orderNumber as string).first()).toBeVisible();
  // The client track is four phases, mode-independent (orders.md): the final
  // one reads «Olib ketildi» whichever way the workshop ran the floor — the
  // completed status always means the client took the order.
  await expect(page.getByText("Olib ketildi", { exact: true }).first()).toBeVisible();
  // The card itself is the link now — no per-card button (spec §4).
  await page.getByRole("link", { name: new RegExp(orderNumber as string) }).click();
  await expect(page.getByRole("heading", { name: orderNumber as string })).toBeVisible();
  await expect(page.getByText("Olib ketildi", { exact: true }).first()).toBeVisible();
});

test("client sees branch pricing setup errors while placing an order", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `p5-price-admin-${id}`;
  const clientPhone = phoneFor(id, 41);
  await seedPlatform(adminLogin);
  const adminAccess = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, adminAccess, id);
  const ownerAccess = await readyOwnerToken(request, setup);
  const branchId = setup.branch.id as string;
  // No branch pricing on purpose — the quote must fail with a setup error.
  const { panel } = await carriedMaterials(
    request,
    adminAccess,
    ownerAccess,
    branchId,
    id,
  );
  const clientAccess = await clientToken(request, clientPhone, `Price Client ${id}`);
  const draft = await optimizedDraftWithoutPricing(
    request,
    clientAccess.access_token,
    branchId,
    panel,
  );

  await loginClient(page, clientPhone, `Price Client ${id}`);
  const quoteFailed = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().includes("/api/v1/client/orders/quote?") &&
      response.status() === 400,
  );
  await page.goto(`/client/c/orders/new/${draft.id}`);
  await quoteFailed;

  await expect(
    page.getByRole("heading", { name: "Buyurtmani tasdiqlash" }),
  ).toBeVisible();
  await expect(page.getByText("Filial narxi yuklanmadi.")).toBeVisible();
  await expect(page.getByText("Ustaxona kesish narxini hali kiritmagan.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Buyurtmani tasdiqlash" })).toBeDisabled();
});

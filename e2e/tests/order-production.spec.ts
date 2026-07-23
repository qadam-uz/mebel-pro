import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { expectOk } from "./helpers";

const execFileAsync = promisify(execFile);
const databaseUrl = "postgresql+asyncpg://mebel:mebel@localhost:5432/mebel_e2e";
const adminPassword = "AdminPass123";
const ownerReadyPassword = "OwnerReady123";
const passwordLabel = /^(Password|Parol)$/;
const continueButton = /^(Continue|Kirish)$/;

interface MaterialResponse {
  id: string;
  name: string;
}

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

function defaultWorkingHours() {
  return {
    monday: { open: "09:00", close: "18:00" },
    tuesday: { open: "09:00", close: "18:00" },
    wednesday: { open: "09:00", close: "18:00" },
    thursday: { open: "09:00", close: "18:00" },
    friday: { open: "09:00", close: "18:00" },
    saturday: { open: "10:00", close: "16:00" },
    sunday: { open: null, close: null },
  };
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
        OTP_DEV_CODES: '["000000"]',
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
        working_hours: defaultWorkingHours(),
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

async function createCatalogMaterials(
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

async function addBranchMaterial(
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
      data: {
        material_id: materialId,
        price_tiyin: priceTiyin,
        min_stock: minStock,
      },
    },
  );
  await expectOk(response);
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

async function clientToken(request: APIRequestContext, phone: string, name: string) {
  const requested = await request.post("/api/v1/auth/client/otp/request", {
    data: { phone },
  });
  await expectOk(requested);
  const verified = await request.post("/api/v1/auth/client/otp/verify", {
    data: { phone, code: "000000", name },
  });
  await expectOk(verified);
  return (await verified.json()) as TokenResponse;
}

async function optimizedDraftWithoutPricing(
  request: APIRequestContext,
  token: string,
  branchId: string,
  panel: MaterialResponse,
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

async function loginClient(page: Page, phone: string, name?: string) {
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

async function chooseEdgeBanding(page: Page, edgeName: string) {
  // The compact row exposes one rectangular edge diagram that opens the picker.
  await page.getByRole("button", { name: "Kromka tomonlari", exact: true }).click();
  // A drawing with no tapes yet opens straight into the branch tape catalog;
  // picking the tape returns to the banding panel with it armed as current.
  const catalog = page.getByRole("dialog", { name: /Yana kromka qo'shish/ });
  await catalog.getByRole("button", { name: new RegExp(edgeName) }).click();
  const dialog = page.getByRole("dialog", { name: /Kromka yopishtirish/ });
  await expect(dialog.getByText(new RegExp(edgeName))).toBeVisible();
  // Band top and bottom with the armed tape; edits apply live, so closing the
  // dialog keeps them.
  await dialog.getByRole("button", { name: /^Yuqori tomon/ }).click();
  await dialog.getByRole("button", { name: /^Pastki tomon/ }).click();
  await dialog.getByRole("button", { name: "Kromka oynasini yopish" }).click();
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
  const { panel, edge } = await createCatalogMaterials(
    request,
    adminAccess,
    id,
  );
  const branchId = setup.branch.id as string;
  await updateBranchPricing(request, ownerAccess, branchId);
  await addBranchMaterial(request, ownerAccess, branchId, panel.id, 250_000, 1);
  await addBranchMaterial(
    request,
    ownerAccess,
    branchId,
    edge.id,
    10_000,
    1_000,
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

  // The first editor visit opens the required branch picker automatically.
  // CB-51: the preferred-branch picker is a single flat branch list — one tap selects.
  await page
    .getByRole("button", { name: new RegExp(`Order Branch ${id}`) })
    .click();
  await expect(
    page.getByText(`Order Branch ${id} · Order Workshop ${id}`),
  ).toBeVisible();

  // A new compact entry starts by selecting its material; that selection creates
  // the first editable row in the material group.
  await page.getByRole("button", { name: "+ Material tanlash" }).click();
  await page
    .getByRole("dialog", { name: "Materialni almashtirish" })
    .getByRole("button", { name: new RegExp(panel.name) })
    .click();
  await page.getByLabel("Bo'y millimetr").fill("260");
  await page.getByLabel("Eni millimetr").fill("180");
  await page.getByLabel("Soni").fill("2");
  await chooseEdgeBanding(page, edge.name);
  await page.getByRole("button", { name: "Davom etish" }).click();

  // First optimise persists the draft and hands off to the standalone result stage.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+\/result$/);
  await expect(page.getByRole("heading", { name: "Kesish natijasi" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Buyurtmaga davom etish" })).toBeVisible();
  await page.getByRole("link", { name: "Buyurtmaga davom etish" }).click();

  await expect(
    page.getByRole("heading", { name: "Buyurtmani tasdiqlash", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText(`Order Branch ${id}`).first()).toBeVisible();
  await expect(page.getByText("Jami").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Buyurtmani tasdiqlash" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Buyurtmani tasdiqlash" }).click();

  await expect(page.getByText("Buyurtma berildi")).toBeVisible();
  const orderText = await page
    .getByText(/ORD-\d{4}-\d{6}/)
    .first()
    .textContent();
  const orderNumber = orderText?.match(/ORD-\d{4}-\d{6}/)?.[0];
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
  const edgerAssigned = workshopPage.waitForResponse(
    (response) => response.url().includes("/assign") && response.ok(),
  );
  await chooseOption(
    workshopPage,
    /Kromka yopishtiruvchi/,
    new RegExp(setup.ownerLogin),
  );
  await edgerAssigned;
  // Assignment is metadata — the order stays confirmed (queued in the
  // master's station) until the job is actually started.
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
    workshopPage.getByText("Tugatilgan", { exact: true }).first(),
  ).toBeVisible();
  await workshopContext.close();

  await page.goto("/client/c/orders");
  await expect(page.getByText(orderNumber as string).first()).toBeVisible();
  await expect(page.getByText("Topshirildi", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "Tafsilot" }).click();
  await expect(page.getByRole("heading", { name: orderNumber as string })).toBeVisible();
  await expect(page.getByText("Topshirildi", { exact: true }).first()).toBeVisible();
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
  const { panel } = await createCatalogMaterials(request, adminAccess, id);
  const branchId = setup.branch.id as string;
  await addBranchMaterial(request, ownerAccess, branchId, panel.id, 250_000, 1);
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

import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

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

test.setTimeout(90_000);

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
  expect(response.ok()).toBe(true);
  return (await response.json()).access_token as string;
}

async function provisionWorkshop(
  request: APIRequestContext,
  token: string,
  id: string,
) {
  const code = `p5-${id}`;
  const ownerLogin = `owner-${id}`;
  const ownerPassword = "OwnerTemp123";
  const response = await request.post("/api/v1/platform/workshops", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      workshop: {
        name: `Order Workshop ${id}`,
        code,
        phone: phoneFor(id, 2),
        address: "Tashkent",
      },
      branch: {
        name: `Order Branch ${id}`,
        address: "Tashkent, Test",
        phone: phoneFor(id, 3),
        latitude: "41.2995",
        longitude: "69.2401",
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: `Order Owner ${id}`,
        login: ownerLogin,
        phone: phoneFor(id, 4),
      },
      temp_password: ownerPassword,
    },
  });
  expect(response.ok()).toBe(true);
  return { ...(await response.json()), code, ownerLogin, ownerPassword };
}

async function readyOwnerToken(
  request: APIRequestContext,
  setup: Awaited<ReturnType<typeof provisionWorkshop>>,
) {
  const login = await request.post("/api/v1/auth/workshop/login", {
    data: {
      workshop_code: setup.code,
      login: setup.ownerLogin,
      password: setup.ownerPassword,
    },
  });
  expect(login.ok()).toBe(true);
  const access = (await login.json()).access_token as string;
  const changed = await request.post("/api/v1/auth/password/change", {
    headers: { Authorization: `Bearer ${access}` },
    data: {
      current_password: setup.ownerPassword,
      new_password: ownerReadyPassword,
    },
  });
  expect(changed.ok()).toBe(true);
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
  expect(manufacturer.ok()).toBe(true);
  const manufacturerId = (await manufacturer.json()).id as string;

  const panel = await request.post("/api/v1/platform/catalog/materials", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "panel",
      manufacturer_id: manufacturerId,
      type: "dsp",
      name: `Order Panel ${id}`,
      thickness_mm: "18",
      color: "White",
      decor_code: `P5-P-${id}`,
      panel_length_mm: 900,
      panel_width_mm: 600,
      grain_direction: false,
    },
  });
  expect(panel.ok()).toBe(true);

  const edge = await request.post("/api/v1/platform/catalog/materials", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      kind: "edge",
      manufacturer_id: manufacturerId,
      name: `Order Edge ${id}`,
      thickness_mm: "2",
      color: "White",
      decor_code: `P5-E-${id}`,
    },
  });
  expect(edge.ok()).toBe(true);

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
  expect(response.ok()).toBe(true);
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
  expect(response.ok()).toBe(true);
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
        supplier: { name: `E2E Supplier ${branchId.slice(0, 6)}` },
        note: "Order E2E stock",
      },
    },
  );
  expect(response.ok()).toBe(true);
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
  code: string,
  login: string,
  password: string,
  baseUrl = "",
) {
  await page.goto(`${baseUrl}/workshop/`);
  await page.getByLabel("Workshop code").fill(code);
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
  await page.getByRole("button", { name: buttonName }).click();
  await page.getByRole("option", { name: optionName }).click();
}

async function chooseEdgeBanding(page: Page, edgeName: string) {
  await page.getByRole("button", { name: /Qism #1 kromini tahrirlash/ }).click();
  const dialog = page.getByRole("dialog", { name: /Krom yopishtirish/ });
  await dialog.getByRole("button", { name: "Yuqori + pastki" }).click();
  await dialog.getByLabel("Krom qidirish").fill(edgeName);
  await dialog.getByRole("button", { name: new RegExp(edgeName) }).click();
  await dialog.getByRole("button", { name: "Qo'llash" }).click();
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

  await page.getByRole("button", { name: "Ustaxona tanlash" }).click();
  // CB-51: the preferred-branch picker is a single flat branch list — one tap selects.
  await page
    .getByRole("button", { name: new RegExp(`Order Branch ${id}`) })
    .click();
  await page.getByRole("button", { name: "Qo'llash" }).click();
  await expect(
    page.getByText(`Order Branch ${id} · Order Workshop ${id}`),
  ).toBeVisible();

  await page.getByRole("button", { name: "Qism qo'shish" }).first().click();
  await page.getByRole("combobox", { name: "Panel materiali" }).fill(panel.name);
  await page.getByRole("option", { name: new RegExp(panel.name) }).click();
  await page.getByRole("combobox", { name: "Panel materiali" }).press("Escape");
  await page.getByLabel("Uzunlik millimetr").fill("260");
  await page.getByLabel("Eni millimetr").fill("180");
  await page.getByLabel("Soni").fill("2");
  await chooseEdgeBanding(page, edge.name);
  await page.getByRole("button", { name: "Optimallashtirish" }).click();

  // First optimise persists the draft and hands off from `/new` to the real id.
  await expect(page).toHaveURL(/\/client\/c\/cutting\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "Natija", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Buyurtma berish" })).toBeVisible();
  await page.getByRole("link", { name: "Buyurtma berish" }).click();

  await expect(page.getByRole("heading", { name: "Ustaxonani tanlang" })).toBeVisible();
  await page
    .getByRole("button", { name: new RegExp(`Order Branch ${id}`) })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tasdiqlash", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Jami").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Buyurtma berish" })).toBeEnabled();
  await page.getByRole("button", { name: "Buyurtma berish" }).click();

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
    setup.code,
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
  await workshopOrderRow
    .getByRole("button", { name: `${orderNumber as string} amallari` })
    .click();
  await workshopPage.getByRole("menuitem", { name: "Tafsilotlar" }).click();

  await expect(
    workshopPage.getByRole("heading", { name: orderNumber as string }),
  ).toBeVisible();
  const workshopOrderUrl = workshopPage.url();
  await workshopPage.getByRole("button", { name: "Tasdiqlash" }).click();
  await expect(
    workshopPage.getByText("Tasdiqlangan", { exact: true }).first(),
  ).toBeVisible();

  await chooseOption(workshopPage, /Kesuvchi/, new RegExp(`Order Owner ${id}`));
  await chooseOption(
    workshopPage,
    /Krom yopishtiruvchi/,
    new RegExp(`Order Owner ${id}`),
  );
  await workshopPage.getByRole("button", { name: "Tayinlash va boshlash" }).click();
  await expect(
    workshopPage.getByText("Kesilmoqda", { exact: true }).first(),
  ).toBeVisible();

  await workshopPage
    .getByRole("link", { name: "Kesish navbati" })
    .first()
    .click();
  await expect(
    workshopPage.getByRole("heading", { name: "Kesish navbati" }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  const cuttingDone = workshopPage.waitForResponse(
    (response) => response.url().includes("/cutting-done") && response.ok(),
  );
  await workshopPage.getByRole("button", { name: "Kesish tugadi" }).click();
  await cuttingDone;

  await workshopPage
    .getByRole("link", { name: "Krom navbati" })
    .first()
    .click();
  await expect(
    workshopPage.getByRole("heading", { name: "Krom yopishtirish navbati" }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  const bandingDone = workshopPage.waitForResponse(
    (response) => response.url().includes("/banding-done") && response.ok(),
  );
  await workshopPage.getByRole("button", { name: "Krom tugadi" }).click();
  await bandingDone;

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

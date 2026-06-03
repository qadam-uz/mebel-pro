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
        name: `Phase 5 Workshop ${id}`,
        code,
        phone: phoneFor(id, 2),
        address: "Tashkent",
      },
      branch: {
        name: `Phase 5 Branch ${id}`,
        address: "Tashkent, Test",
        phone: phoneFor(id, 3),
        latitude: "41.2995",
        longitude: "69.2401",
        working_hours: defaultWorkingHours(),
      },
      owner: {
        full_name: `Phase 5 Owner ${id}`,
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
      data: { name: `Phase 5 Maker ${id}`, country: "UZ" },
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
      name: `Phase 5 Panel ${id}`,
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
      name: `Phase 5 Edge ${id}`,
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
        note: "Phase 5 E2E stock",
      },
    },
  );
  expect(response.ok()).toBe(true);
}

async function loginClient(page: Page, phone: string, name?: string) {
  await page.goto("/client/auth/login");
  await page.getByLabel("Phone").fill(phone);
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("Code").fill("000000");
  await page.getByRole("button", { name: "Continue" }).click();
  const nameField = page.getByLabel("Name");
  if (
    await nameField
      .waitFor({ state: "visible", timeout: 2_000 })
      .then(() => true)
      .catch(() => false)
  ) {
    await nameField.fill(name ?? "Phase 5 Client");
    await page.getByRole("button", { name: "Continue" }).click();
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
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/workshop$/);
}

async function chooseOption(
  page: Page,
  buttonName: RegExp,
  optionName: RegExp,
) {
  await page.getByRole("button", { name: buttonName }).click();
  await page.getByRole("option", { name: optionName }).click();
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

  await loginClient(page, clientPhone, `Phase 5 Client ${id}`);
  await page.getByRole("button", { name: "New cutting" }).click();
  await expect(
    page.getByRole("heading", { name: "Cutting editor" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Pick a branch" }).click();
  await chooseOption(
    page,
    /Preferred branch/,
    new RegExp(`Phase 5 Workshop ${id}`),
  );
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(
    page.getByText(`Phase 5 Branch ${id} · Phase 5 Workshop ${id}`),
  ).toBeVisible();

  await page.getByRole("button", { name: "Add part" }).click();
  await page.getByRole("combobox", { name: "Panel material" }).fill(panel.name);
  await page.getByRole("option", { name: new RegExp(panel.name) }).click();
  await page.getByRole("combobox", { name: "Panel material" }).press("Escape");
  await page.getByLabel("Length millimetres").fill("260");
  await page.getByLabel("Width millimetres").fill("180");
  await page.getByLabel("Quantity").fill("2");
  await page.getByRole("combobox", { name: "Edge tape" }).fill(edge.name);
  await page.getByRole("option", { name: new RegExp(edge.name) }).click();
  await page.getByRole("combobox", { name: "Edge tape" }).press("Escape");
  await page.getByRole("button", { name: "Top" }).click();
  await page.getByRole("button", { name: "Left" }).click();
  await page.getByRole("button", { name: "Optimise" }).click();

  await expect(
    page.getByRole("heading", { name: "Result", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Place order" })).toBeVisible();
  await page.getByRole("link", { name: "Place order" }).click();

  await expect(
    page.getByRole("heading", { name: "Place order" }),
  ).toBeVisible();
  await expect(page.getByText("Total")).toBeVisible();
  await expect(page.getByRole("button", { name: "Place order" })).toBeEnabled();
  await page.getByRole("button", { name: "Place order" }).click();

  await expect(
    page.getByRole("heading", { name: "Order tracking" }),
  ).toBeVisible();
  await expect(page.getByText("Order placed")).toBeVisible();
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
  await workshopPage.getByRole("link", { name: "Orders" }).first().click();
  await expect(
    workshopPage.getByRole("heading", { name: "Orders" }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  await workshopPage.getByRole("link", { name: "Open" }).click();

  await expect(
    workshopPage.getByRole("heading", { name: "Order detail" }),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Approve" }).click();
  await expect(
    workshopPage.getByText("Confirmed", { exact: true }).first(),
  ).toBeVisible();

  await chooseOption(workshopPage, /Cutter/, new RegExp(`Phase 5 Owner ${id}`));
  await chooseOption(
    workshopPage,
    /Edge bander/,
    new RegExp(`Phase 5 Owner ${id}`),
  );
  await workshopPage.getByRole("button", { name: "Assign and start" }).click();
  await expect(
    workshopPage.getByText("Cutting", { exact: true }).first(),
  ).toBeVisible();

  await workshopPage
    .getByRole("link", { name: "Cutting queue" })
    .first()
    .click();
  await expect(
    workshopPage.getByRole("heading", { name: "Cutting queue" }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Mark cutting done" }).click();
  await expect(
    workshopPage.getByText("No assigned cutting jobs"),
  ).toBeVisible();

  await workshopPage
    .getByRole("link", { name: "Banding queue" })
    .first()
    .click();
  await expect(
    workshopPage.getByRole("heading", { name: "Banding queue" }),
  ).toBeVisible();
  await expect(
    workshopPage.getByText(orderNumber as string).first(),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Mark banding done" }).click();
  await expect(
    workshopPage.getByText("No assigned banding jobs"),
  ).toBeVisible();

  await workshopPage.getByRole("link", { name: "Orders" }).first().click();
  await workshopPage.getByRole("link", { name: "Open" }).click();
  await expect(
    workshopPage.getByText("Ready", { exact: true }).first(),
  ).toBeVisible();
  await workshopPage.getByRole("button", { name: "Mark collected" }).click();
  await expect(
    workshopPage.getByText("Completed", { exact: true }).first(),
  ).toBeVisible();
  await workshopContext.close();

  await page.goto("/client/c/orders");
  await expect(page.getByText(orderNumber as string).first()).toBeVisible();
  await expect(page.getByText("Done", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "Track" }).click();
  await expect(
    page.getByRole("heading", { name: "Order tracking" }),
  ).toBeVisible();
  await expect(
    page.getByText("Collected", { exact: true }).first(),
  ).toBeVisible();
});

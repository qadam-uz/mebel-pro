import { execFile } from "node:child_process";
import { promisify } from "node:util";

import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import {
  databaseUrl,
  devConfirmLogin,
  expectOk,
  telegramDeepLink,
} from "./helpers";

const execFileAsync = promisify(execFile);
const adminPassword = "AdminPass123";
const ownerReadyPassword = "OwnerReady123";
const staffReadyPassword = "StaffReady123";
const passwordLabel = /^(Password|Parol)$/;
const currentPasswordLabel = /^(Current password|Joriy parol)$/;
const newPasswordLabel = /^(New password|Yangi parol)/;
const continueButton = /^(Continue|Kirish)$/;
const saveButton = /^(Save|Saqlash|O'zgartirish)$/;

function runId(testInfo: { workerIndex: number; title: string }) {
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
        name: `Workshop ${id}`,
      },
      branch: {
        name: `Branch ${id}`,
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

async function changeRequiredPassword(
  page: Page,
  current: string,
  next: string,
) {
  await expect(
    page
      .locator("main")
      .getByText(/Parolni o'zgartirish kerak|Password change required/),
  ).toBeVisible();
  await page.getByLabel(currentPasswordLabel).fill(current);
  await page.getByLabel(newPasswordLabel).fill(next);
  await page.getByRole("button", { name: saveButton }).click();
  await expect(
    page.getByText(/Parol o'zgartirildi\.|Password updated\./),
  ).toBeVisible();
}

test("admin provisions and blocks a workshop", async ({ page }, testInfo) => {
  const id = runId(testInfo);
  const login = `admin-${id}`;
  await seedPlatform(login);

  await page.goto("/admin/");
  await page.getByLabel("Login").fill(login);
  await page.getByLabel(passwordLabel).fill(adminPassword);
  await page.getByRole("button", { name: continueButton }).click();
  await page.getByRole("link", { name: "Ustaxonalar" }).first().click();

  await page.getByRole("button", { name: "Yangi ustaxona" }).click();
  const provisionForm = page.getByRole("dialog", { name: /Yangi ustaxona/ });
  await provisionForm.getByLabel("Ustaxona nomi").fill(`Workshop ${id}`);
  await provisionForm.getByLabel("Birinchi filial").fill(`Branch ${id}`);
  await provisionForm.getByLabel("Filial manzili").fill("Tashkent, Test");
  await provisionForm.getByLabel("Filial telefoni").fill(phoneFor(id, 11));
  await provisionForm.getByLabel("Rahbar login").fill(`ui-owner-${id}`);
  await provisionForm.getByLabel("Vaqtinchalik parol").fill("OwnerTemp123");
  await provisionForm.getByRole("button", { name: "Qo'shish", exact: true }).click();

  // The one-time secret is now shown in a focus-trapped modal (AB-03); assert it,
  // then dismiss it before navigating away.
  const secret = page.getByRole("dialog", { name: /maxfiy ma'lumot/ });
  await expect(secret).toBeVisible();
  await expect(
    secret.getByText(`ui-owner-${id}`, { exact: true }),
  ).toBeVisible();
  await secret.getByRole("button", { name: /Yopdim/ }).click();
  await page
    .getByRole("row", { name: new RegExp(`Workshop ${id}`) })
    .getByRole("link", { name: /tafsilotlarini ochish/ })
    .click();
  await expect(
    page.getByRole("heading", { name: `Workshop ${id}` }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: new RegExp(`Workshop ${id}.*bloklash`) })
    .click();
  await page.getByLabel(/sabab/i).fill("E2E block");
  await page.getByRole("button", { name: "Bloklash", exact: true }).click();
  await expect(page.getByText("Bloklangan").first()).toBeVisible();

  // AB-52: complete the lifecycle round-trip through the UI — unblock restores active.
  await page
    .getByRole("button", { name: /ustaxonasini blokdan chiqarish/ })
    .click();
  await expect(page.getByText("Faol").first()).toBeVisible();
});

test("owner changes temp password, creates staff, and saves a grant", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `admin-${id}`;
  await seedPlatform(adminLogin);
  const token = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, token, id);

  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(setup.ownerLogin);
  await page.getByLabel(passwordLabel).fill(setup.ownerPassword);
  await page.getByRole("button", { name: continueButton }).click();
  await changeRequiredPassword(page, setup.ownerPassword, ownerReadyPassword);
  await page.goto("/workshop/settings/users");

  await page.getByRole("button", { name: "Yangi xodim" }).click();
  const staffForm = page.getByRole("dialog", { name: "Yangi xodim" });
  await staffForm.getByRole("button", { name: "Qo'shish", exact: true }).click();
  await expect(
    staffForm.getByText("Bu maydonni to'ldiring.").first(),
  ).toBeVisible();
  await expect(
    staffForm.getByRole("button", { name: "Filiallar" }),
  ).toBeVisible();
  await staffForm.getByLabel("F.I.O").fill("E2E Staff");
  await staffForm.getByLabel("Telefon").fill(phoneFor(id, 20));
  await staffForm.getByLabel("Login").fill(`staff-${id}`);
  await staffForm.getByLabel("Vaqtinchalik parol").fill("StaffTemp123");
  await staffForm.getByRole("button", { name: "Qo'shish", exact: true }).click();
  await expect(page.getByText("StaffTemp123")).toBeVisible();
  // QAD-184: the row is the affordance — the staff name is the link that opens
  // the detail page, so there is no separate "Ochish" button to click.
  await page
    .getByRole("row", { name: /E2E Staff/ })
    .getByRole("link", { name: "E2E Staff" })
    .click();
  await page.getByRole("tab", { name: "Ruxsatlar" }).click();
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByRole("checkbox").first()).toBeChecked();
});

test("staff sees granted branch context after password change", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `admin-${id}`;
  await seedPlatform(adminLogin);
  const token = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, token, id);
  const ownerToken = await readyOwnerToken(request, setup);
  const staffLogin = `staff-${id}`;
  const created = await request.post("/api/v1/workshop/users", {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      full_name: "Granted Staff",
      phone: phoneFor(id, 30),
      login: staffLogin,
      home_branch_id: setup.branch.id,
      temp_password: "StaffTemp123",
      grants: [{ permission: "manage_orders", branch_id: setup.branch.id }],
    },
  });
  await expectOk(created);

  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(staffLogin);
  await page.getByLabel(passwordLabel).fill("StaffTemp123");
  await page.getByRole("button", { name: continueButton }).click();
  await changeRequiredPassword(page, "StaffTemp123", staffReadyPassword);

  // A single granted branch auto-pins the workshop context: the topbar
  // switcher is hidden on purpose (it only appears with >1 branch to choose
  // from), and the granted context shows as the working surface itself —
  // the manage_orders staff can open the orders board of their branch.
  await page.goto("/workshop/orders");
  await expect(
    page.getByRole("heading", { name: "Buyurtmalar" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: new RegExp(`Branch ${id}`) }),
  ).toHaveCount(0);
});

test("owner manages branches from a simple system table and detail view", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `admin-${id}`;
  await seedPlatform(adminLogin);
  const token = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, token, id);
  const ownerToken = await readyOwnerToken(request, setup);
  // Prices are set up front so the branch-detail onboarding spotlight stays out
  // of this test's way — the guided first-run flow owns onboarding.spec.ts.
  const priced = await request.put(
    `/api/v1/workshop/branches/${setup.branch.id}/pricing`,
    {
      headers: { Authorization: `Bearer ${ownerToken}` },
      data: { cutting_rate_tiyin: 50_000, edge_banding_rate_tiyin: 20_000 },
    },
  );
  await expectOk(priced);

  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(setup.ownerLogin);
  await page.getByLabel(passwordLabel).fill(ownerReadyPassword);
  await page.getByRole("button", { name: continueButton }).click();
  await expect(page.getByRole("heading", { name: "Asosiy" })).toBeVisible();

  // QAD-176: `branch_no` is the middle segment of every order number and
  // cutting map this branch prints (`#26-1-0003`); the owner must be able to
  // look it up somewhere, and these two screens are that somewhere.
  const branchNo = String(setup.branch.branch_no);

  await page.goto("/workshop/branches");
  await expect(page.getByRole("heading", { name: "Filiallar" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Raqam" })).toBeVisible();
  await expect(
    page
      .getByRole("row", { name: new RegExp(`Branch ${id}`) })
      .getByRole("cell", { name: branchNo, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Filial" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Manzil" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Telefon" }),
  ).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Holat" })).toBeVisible();
  await expect(page.getByText("Faol buyurtma")).toHaveCount(0);
  // QAD-184: the branch name is the link that opens the filial — the row's own
  // click target, with no separate "Ochish" button beside it.
  await page
    .getByRole("row", { name: new RegExp(`Branch ${id}`) })
    .getByRole("link", { name: new RegExp(`Branch ${id}`) })
    .click();

  await expect(page).toHaveURL(
    new RegExp(`/workshop/branches/${setup.branch.id}`),
  );
  await expect(
    page.getByRole("heading", { name: `Branch ${id}` }),
  ).toBeVisible();
  // The detail header spells out what the number means, so a deep link to one
  // branch is enough to decode a printed order number.
  const yy = String(new Date().getFullYear() % 100).padStart(2, "0");
  await expect(
    page.getByText(
      new RegExp(`Filial raqami\\s*${branchNo}.*#${yy}-${branchNo}-`),
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Filial ma'lumotlari" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tahrirlash" })).toHaveCount(
    0,
  );
  await expect(page.getByRole("heading", { name: "Holat" })).toBeVisible();
  await expect(page.getByRole("tab")).toHaveCount(0);

  const editForm = page
    .getByRole("heading", { name: "Filial ma'lumotlari" })
    .locator("xpath=ancestor::form[1]");
  await editForm.getByLabel("Manzil").fill("Tashkent, Updated");
  await editForm.getByRole("button", { name: "Saqlash" }).click();
  await expect(editForm.getByText("Saqlandi")).toBeVisible();
});

test("workshop staff direct URLs respect branch-scoped grants", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `admin-${id}`;
  await seedPlatform(adminLogin);
  const token = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, token, id);
  const ownerToken = await readyOwnerToken(request, setup);
  const staffLogin = `inventory-${id}`;
  const created = await request.post("/api/v1/workshop/users", {
    headers: { Authorization: `Bearer ${ownerToken}` },
    data: {
      full_name: "Inventory Staff",
      phone: phoneFor(id, 50),
      login: staffLogin,
      home_branch_id: setup.branch.id,
      temp_password: "StaffTemp123",
      grants: [{ permission: "manage_inventory", branch_id: setup.branch.id }],
    },
  });
  await expectOk(created);

  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(staffLogin);
  await page.getByLabel(passwordLabel).fill("StaffTemp123");
  await page.getByRole("button", { name: continueButton }).click();
  await changeRequiredPassword(page, "StaffTemp123", staffReadyPassword);

  await page.goto("/workshop/finance/expenses");
  await expect(page).toHaveURL(/\/workshop\/?$/);
  await expect(page.getByRole("heading", { name: "Asosiy" })).toBeVisible();

  await page.goto("/workshop/settings/users");
  await expect(page).toHaveURL(/\/workshop\/?$/);

  await page.goto("/workshop/inventory");
  await expect(page).toHaveURL(/\/workshop\/inventory\/?$/);
  await expect(page.getByRole("heading", { name: "Ombor" })).toBeVisible();

  await page.goto(`/workshop/branches/${setup.branch.id}`);
  await expect(page).toHaveURL(/\/workshop\/?$/);
  await expect(page.getByRole("heading", { name: "Asosiy" })).toBeVisible();
});

test("client signs in through the Telegram bot handshake", async ({
  page,
}, testInfo) => {
  const id = runId(testInfo);
  await page.goto("/client/auth/login");

  // Desktop card: a QR of the deep link, the link itself beside it, and a poll
  // running in the background — no phone field, no code, no name step.
  await expect(
    page.getByRole("img", { name: "Telegram botiga kirish QR kodi" }),
  ).toBeVisible();
  await expect(page.getByText("Telegramdan javob kutilmoqda")).toBeVisible();
  const href = await page
    .getByRole("link", { name: telegramDeepLink })
    .getAttribute("href");
  const token = new URL(href ?? "").searchParams.get("start");
  expect(token).toBeTruthy();

  // The bot's side of the handshake, driven by the dev-confirm route: a new
  // phone registers the client with the name the chat would have carried.
  await devConfirmLogin(
    page.request,
    token as string,
    phoneFor(id, 40),
    "E2E Client",
  );

  await expect(page).toHaveURL(/\/client\/c$/);
  // The home greets the client by the name registered in the bot (first given name).
  await expect(
    page.getByRole("heading", { name: "Salom, E2E", exact: true }),
  ).toBeVisible();
});

test("client sign-in refuses an unknown fallback code without saying why", async ({
  page,
}) => {
  await page.goto("/client/auth/login");
  await page.getByRole("button", { name: "Kod bilan kirish" }).click();
  await page.getByLabel("Kirish kodi").fill("000000");
  await page.getByRole("button", { name: "Kirish", exact: true }).click();

  // One generic refusal for unknown / expired / used — no oracle on which.
  await expect(
    page.getByText("Kod noto'g'ri yoki muddati tugagan."),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/client\/auth\/login/);
});

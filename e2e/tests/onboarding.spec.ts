import { expect, test, type Page } from "@playwright/test";

import {
  addBranchMaterial,
  continueButton,
  createCatalogMaterials,
  ownerReadyPassword,
  passwordLabel,
  platformToken,
  provisionWorkshop,
  readyOwnerToken,
  runId,
  seedPlatform,
  updateBranchPricing,
} from "./helpers";

// The guided first-run setup (docs/ref/features/onboarding.md): a fresh owner
// is led password → branch prices → materials by the checklist card, the
// spotlight hints, and the continuation toasts — ending with a workshop that
// can take orders and a checklist that has disappeared.

const currentPasswordLabel = /^(Current password|Joriy parol)$/;
const newPasswordLabel = /^(New password|Yangi parol)/;
const saveButton = /^(Save|Saqlash|O'zgartirish)$/;

async function changeRequiredPassword(page: Page, current: string, next: string) {
  await expect(
    page.locator("main").getByText(/Parolni o'zgartirish kerak|Password change required/),
  ).toBeVisible();
  await page.getByLabel(currentPasswordLabel).fill(current);
  await page.getByLabel(newPasswordLabel).fill(next);
  await page.getByRole("button", { name: saveButton }).click();
}

test("system leads a fresh owner from temp password to an orderable workshop", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `onb-admin-${id}`;
  await seedPlatform(adminLogin);
  const adminAccess = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, adminAccess, id);
  const { panel } = await createCatalogMaterials(request, adminAccess, id);

  // Step 1 — the account gate pins the fresh owner to the password form; after
  // the forced change the owner lands on the home checklist automatically.
  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(setup.ownerLogin);
  await page.getByLabel(passwordLabel).fill(setup.ownerPassword);
  await page.getByRole("button", { name: continueButton }).click();
  await changeRequiredPassword(page, setup.ownerPassword, ownerReadyPassword);

  await expect(page).toHaveURL(/\/workshop\/?$/);
  const checklist = page.getByRole("region", { name: "Ishni boshlash" });
  await expect(checklist).toBeVisible();
  await expect(checklist.getByText("1/3 bajarildi")).toBeVisible();

  // Step 2 — the checklist CTA deep-links to the branch and lights the
  // spotlight on the prices form; clicking the real field dismisses it.
  await checklist.getByRole("button", { name: "Narxlarni kiritish" }).click();
  await expect(page).toHaveURL(new RegExp(`/workshop/branches/${setup.branch.id}`));
  const pricingHint = page.getByRole("dialog", { name: "Kesish narxlarini kiriting" });
  await expect(pricingHint).toBeVisible();
  await expect(pricingHint.getByText("2/3-qadam")).toBeVisible();

  await page.getByLabel("Kesish narxi (so'm / list)").click();
  await expect(pricingHint).toHaveCount(0);
  await page.getByLabel("Kesish narxi (so'm / list)").fill("25000");
  await page.getByLabel("Kromka yopishtirish narxi (so'm / m)").fill("5000");
  const editForm = page
    .getByRole("heading", { name: "Filial ma'lumotlari" })
    .locator("xpath=ancestor::form[1]");
  await editForm.getByRole("button", { name: "Saqlash" }).click();

  // Continuation — the save toast hands the owner on to the catalog.
  await page.getByRole("button", { name: "Katalogga o'tish" }).click();
  await expect(page).toHaveURL(/\/workshop\/catalog/);

  // Step 3 — the spotlight lands on the add-material control; the real click
  // opens the real dialog, and the first material completes the setup.
  const catalogHint = page.getByRole("dialog", { name: "Katalogga material qo'shing" });
  await expect(catalogHint).toBeVisible();
  await expect(catalogHint.getByText("3/3-qadam")).toBeVisible();
  await page.getByRole("button", { name: "+ Material qo'shish" }).first().click();
  await expect(catalogHint).toHaveCount(0);

  // QAD-159: attaching is a two-step multi-select sheet — pick, then price.
  const attachSheet = page.getByRole("dialog");
  await attachSheet.getByRole("checkbox", { name: panel.name }).check();
  await attachSheet.getByRole("button", { name: /Davom etish/ }).click();
  await attachSheet.getByLabel(`${panel.name} narxi`).fill("250000");
  await attachSheet.getByRole("button", { name: /materialni qo'shish/ }).click();

  await expect(
    page.getByText("Dastlabki sozlash yakunlandi", { exact: false }),
  ).toBeVisible();

  // Setup complete — the checklist is gone from home.
  await page.goto("/workshop/");
  await expect(page.getByRole("heading", { name: "Asosiy" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Ishni boshlash" })).toHaveCount(0);
});

test("an established owner sees no checklist and no spotlight", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const adminLogin = `onb2-admin-${id}`;
  await seedPlatform(adminLogin);
  const adminAccess = await platformToken(request, adminLogin);
  const setup = await provisionWorkshop(request, adminAccess, id);
  // Complete the whole setup via the API — the derived status must read done.
  const ownerAccess = await readyOwnerToken(request, setup);
  const { panel } = await createCatalogMaterials(request, adminAccess, id);
  await updateBranchPricing(request, ownerAccess, setup.branch.id as string);
  await addBranchMaterial(request, ownerAccess, setup.branch.id as string, panel.id, 250_000, 1);

  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(setup.ownerLogin);
  await page.getByLabel(passwordLabel).fill(ownerReadyPassword);
  await page.getByRole("button", { name: continueButton }).click();
  await expect(page.getByRole("heading", { name: "Asosiy" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Ishni boshlash" })).toHaveCount(0);

  await page.goto(`/workshop/branches/${setup.branch.id}`);
  await expect(page.getByRole("heading", { name: "Filial ma'lumotlari" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Kesish narxlarini kiriting" })).toHaveCount(0);
});

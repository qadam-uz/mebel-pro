import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import {
  clientTokenViaApi,
  continueButton,
  devConfirmLogin,
  expectOk,
  ownerReadyPassword,
  passwordLabel,
  phoneFor,
  runId,
  seedOrderableBranch,
  telegramDeepLink,
} from "./helpers";

test.setTimeout(120_000);

interface WorkshopSettings {
  name: string;
  public_code: string;
}

interface BranchRead {
  id: string;
  branch_no: number;
  name: string;
  workshop_public_code: string;
}

interface CuttingDraftRead {
  id: string;
  preferred_branch_id: string | null;
}

async function workshopLinkFor(
  request: APIRequestContext,
  ownerAccess: string,
  branchId: string,
) {
  const headers = { Authorization: `Bearer ${ownerAccess}` };
  const settingsResponse = await request.get("/api/v1/workshop/settings", {
    headers,
  });
  await expectOk(settingsResponse);
  const settings = (await settingsResponse.json()) as WorkshopSettings;

  const branchResponse = await request.get(
    `/api/v1/workshop/branches/${branchId}`,
    { headers },
  );
  await expectOk(branchResponse);
  const branch = (await branchResponse.json()) as BranchRead;

  // The code is machine-generated and permanent; the branch carries it so the
  // counter QR needs no second request.
  expect(branch.workshop_public_code).toBe(settings.public_code);
  return { settings, branch };
}

async function loginWorkshop(page: Page, login: string, password: string) {
  await page.goto("/workshop/");
  await page.getByLabel("Login").fill(login);
  await page.getByLabel(passwordLabel).fill(password);
  await page.getByRole("button", { name: continueButton }).click();
  await expect(page).toHaveURL(/\/workshop\/?$/);
}

/**
 * The scripted pass of the workshop-scoped entry spec (§9): a client scans a
 * branch QR while signed out, signs in through the bot handshake, finds the
 * editor scoped to that workshop, and places an order at the pinned branch.
 */
test("a scanned branch link pins the client, scopes the editor and carries the order", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const clientPhone = phoneFor(id, 61);
  const clientName = `Entry Client ${id}`;
  const { setup, ownerAccess, branchId, panel, edge } =
    await seedOrderableBranch(request, id);
  const { settings, branch } = await workshopLinkFor(
    request,
    ownerAccess,
    branchId,
  );

  // 1. Scan the counter QR, signed out. The landing is public: no login bounce.
  await page.goto(`/client/w/${settings.public_code}/${branch.branch_no}`);
  await expect(
    page.getByText(`${settings.name} sizni taklif qilmoqda`),
  ).toBeVisible();
  // A branch link names its counter and never asks which branch.
  await expect(page.getByText(branch.name)).toBeVisible();
  await expect(
    page.getByText("Qaysi filialdan olib ketasiz?"),
  ).toHaveCount(0);

  // 2. Kirish → the existing Telegram handshake. The entry survives the trip
  //    through `localStorage`, so no branch has to be chosen again after login.
  await page.getByRole("button", { name: /^Kirish$/ }).click();
  const link = page.getByRole("link", { name: telegramDeepLink });
  await expect(link).toBeVisible();
  const href = await link.getAttribute("href");
  const token = new URL(href ?? "").searchParams.get("start");
  expect(token, `no ?start= token in the deep link ${href}`).toBeTruthy();
  await devConfirmLogin(page.request, token as string, clientPhone, clientName);

  // 3. Home, with the connected toast and the pinned context in the header.
  await expect(page).toHaveURL(/\/client\/c$/);
  await expect(
    page.getByText(`Siz ${settings.name} ustaxonasiga ulandingiz`),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: `${settings.name} · ${branch.name}` }),
  ).toBeVisible();

  // 4. The editor's branch picker is scoped to the pinned workshop, with no
  //    affordance that reaches another one.
  await page.goto("/client/c/cutting/new");
  await expect(page.getByText(`${settings.name} filiallari`)).toBeVisible();
  // The cross-workshop search is the one control that could reach another
  // workshop, so a scoped picker does not render it at all (spec §4).
  await expect(
    page.getByPlaceholder("Ustaxona, filial yoki manzil — masalan: Chilonzor"),
  ).toHaveCount(0);

  // 5. The pin reaches the drawing: a fresh draft is seeded with it, and the
  //    order that follows is placed at that branch.
  const clientToken = await clientTokenViaApi(request, clientPhone, clientName);
  const auth = { Authorization: `Bearer ${clientToken}` };

  const me = await request.get("/api/v1/auth/me", { headers: auth });
  await expectOk(me);
  const principal = (await me.json()) as {
    pinned_workshop_name: string | null;
    pinned_branch_name: string | null;
  };
  expect(principal.pinned_workshop_name).toBe(settings.name);
  expect(principal.pinned_branch_name).toBe(branch.name);

  const created = await request.post("/api/v1/client/cutting-drafts", {
    headers: auth,
  });
  await expectOk(created);
  const draft = (await created.json()) as CuttingDraftRead;
  // Draft seeding reads the pin — that is what makes the QR reach the editor.
  expect(draft.preferred_branch_id).toBe(branchId);

  const patched = await request.patch(
    `/api/v1/client/cutting-drafts/${draft.id}`,
    {
      headers: auth,
      data: {
        parts_snapshot: [
          {
            part_ref: "entry-part",
            material_id: panel.id,
            material_source: "shop",
            length_mm: 260,
            width_mm: 180,
            quantity: 2,
            edge_top: { material_id: edge.id, source: "shop" },
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
    { headers: auth },
  );
  await expectOk(optimized);

  const placed = await request.post("/api/v1/client/orders", {
    headers: auth,
    // The branch the draft was seeded with — the pinned one, never re-chosen.
    data: {
      draft_id: draft.id,
      branch_id: draft.preferred_branch_id,
      contact_name: clientName,
      contact_phone: clientPhone,
      note_client: "E2E entry order",
    },
  });
  expect(placed.status()).toBe(201);
  const order = (await placed.json()) as { order_number: string };

  // 6. And Ustaxonalarim shows the workshop the client entered, badged Asosiy.
  await page.goto("/client/c/branches");
  await expect(
    page.getByRole("heading", { name: "Ustaxonalarim" }),
  ).toBeVisible();
  await expect(page.getByText(settings.name).first()).toBeVisible();
  await expect(page.getByText("Asosiy", { exact: true })).toBeVisible();

  await page.goto("/client/c/orders");
  await expect(page.getByText(order.order_number)).toBeVisible();
});

/** §1.4 — the artifact the counter needs: the card, its QR, and the print sheet. */
test("the workshop's Mijoz havolasi card renders the QR and its print sheet", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const { setup, ownerAccess, branchId } = await seedOrderableBranch(
    request,
    id,
  );
  const { settings, branch } = await workshopLinkFor(
    request,
    ownerAccess,
    branchId,
  );

  await loginWorkshop(page, setup.ownerLogin, ownerReadyPassword);

  // Branch detail — the counter's own link.
  await page.goto(`/workshop/branches/${branchId}`);
  const card = page.getByRole("heading", { name: "Mijoz havolasi" });
  await expect(card).toBeVisible();

  const urlField = page.locator("#client-link-url");
  const branchUrl = await urlField.inputValue();
  expect(branchUrl).toContain(`/w/${settings.public_code}/${branch.branch_no}`);

  // The QR is drawn in the page as real SVG marks — never fetched from a service.
  const qr = page.getByRole("img", { name: "Mijoz havolasining QR kodi" });
  await expect(qr).toBeVisible();
  expect(await qr.locator("path").count()).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: "Nusxalash" })).toBeVisible();

  // The print sheet: workshop, branch, QR and the tagline, and no shell.
  await page.goto(`/workshop/branches/${branchId}/client-link`);
  await expect(page.getByRole("heading", { name: settings.name })).toBeVisible();
  await expect(page.getByText(branch.name)).toBeVisible();
  await expect(
    page.getByText("Chizmangizni o'zingiz chizing — narxini darhol bilasiz"),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Mijoz havolasining QR kodi" }),
  ).toBeVisible();
  // Chromeless: the workshop sidebar is not on the sheet.
  await expect(page.locator(".workshop-sidebar")).toHaveCount(0);

  // Workshop settings carries the same card with the workshop-level link.
  await page.goto("/workshop/settings");
  await expect(page.getByRole("heading", { name: "Mijoz havolasi" })).toBeVisible();
  const workshopUrl = await page.locator("#client-link-url").inputValue();
  expect(workshopUrl).toContain(`/w/${settings.public_code}`);
  expect(workshopUrl).not.toContain(`/w/${settings.public_code}/`);
});

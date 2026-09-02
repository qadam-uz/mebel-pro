import { expect, test } from "@playwright/test";

import {
  applyWorkshopDiscount,
  loginClient,
  phoneFor,
  placeClientOrderViaApi,
  runId,
  seedOrderableBranch,
} from "./helpers";

test.setTimeout(90_000);

// CB-122 — a client cancels a still-new order, and recovers from a 409 version
// conflict (the workshop changed the order out from under the open page).
test("client cancels a new order and recovers from a stale-version 409", async ({
  page,
  request,
}, testInfo) => {
  const id = runId(testInfo);
  const clientPhone = phoneFor(id, 50);
  const { branchId, panel, edge, ownerAccess } = await seedOrderableBranch(
    request,
    id,
  );
  const { order } = await placeClientOrderViaApi(request, {
    phone: clientPhone,
    name: `Cancel Client ${id}`,
    branchId,
    panelId: panel.id,
    edgeId: edge.id,
  });

  await loginClient(page, clientPhone, `Cancel Client ${id}`);
  await page.goto(`/client/c/orders/${order.id}`);
  await expect(
    page.getByRole("heading", { name: order.order_number }),
  ).toBeVisible();
  // Client phase 1 of the four-phase track (orders.md).
  await expect(page.getByText("Yangi").first()).toBeVisible();

  // The workshop applies a discount → the order version the page holds is now stale.
  await applyWorkshopDiscount(request, ownerAccess, order.id, order.version);

  // First cancel attempt carries the stale version → 409. The dialog stays open and
  // the page surfaces a recovery message after auto-refetching the fresh version.
  await page.getByRole("button", { name: "Bekor qilish" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Buyurtmani bekor qilish",
  });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Bekor qilish" }).click();
  await expect(page.getByText(/holati o'zgardi/)).toBeVisible();

  // Second attempt uses the refetched version → success.
  await dialog.getByRole("button", { name: "Bekor qilish" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("Bekor qilingan").first()).toBeVisible();
  // The order is genuinely terminal now — the cancel affordance is gone (not just a
  // status string), so the second attempt really transitioned the order server-side.
  await expect(
    page.getByRole("button", { name: "Bekor qilish" }),
  ).toBeHidden();
});
